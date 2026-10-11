[CmdletBinding()]
param(
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,40}$')]
    [string]$RunId = ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')),
    [ValidateRange(1, 65535)]
    [int]$PostgresPort = 15411,
    [ValidateRange(1, 65535)]
    [int]$RedisPort = 16311,
    [ValidateRange(1, 65535)]
    [int]$ApiPort = 18011,
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,80}$')]
    [string]$EvidenceName = '2026-10-10-read-endpoint-performance'
)

$ErrorActionPreference = 'Stop'
$projectName = "careerops-p111-perf-$RunId"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$environmentFile = Join-Path $PSScriptRoot 'compose-acceptance.env'
$composeFile = Join-Path $repositoryRoot 'docker-compose.yml'
$jsonOutput = Join-Path $repositoryRoot "docs\metrics\$EvidenceName.json"
$markdownOutput = Join-Path $repositoryRoot "docs\metrics\$EvidenceName.md"
$composePrefix = @('--project-name', $projectName, '--env-file', $environmentFile, '-f', $composeFile)
$ports = @($PostgresPort, $RedisPort, $ApiPort)
$previousPostgresPort = $env:CAREEROPS_POSTGRES_PORT
$previousRedisPort = $env:CAREEROPS_REDIS_PORT
$previousApiPort = $env:CAREEROPS_API_PORT
$previousParserProvider = $env:CAREEROPS_LLM_PROVIDER
$previousEmbeddingProvider = $env:CAREEROPS_EMBEDDING_PROVIDER
$previousMatcherProvider = $env:CAREEROPS_EVIDENCE_MATCHER_PROVIDER

function Invoke-Compose {
    param([Parameter(Mandatory)][string[]]$Arguments)
    & docker compose @composePrefix @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE"
    }
}

function Get-ProjectResources {
    $containers = @(& docker ps -a --filter "label=com.docker.compose.project=$projectName" --format '{{.ID}}')
    $networks = @(& docker network ls --filter "label=com.docker.compose.project=$projectName" --format '{{.ID}}')
    $volumes = @(& docker volume ls --filter "label=com.docker.compose.project=$projectName" --format '{{.Name}}')
    return @($containers + $networks + $volumes | Where-Object { $_ })
}

function Assert-PortsAvailable {
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    $publishedPorts = (& docker ps --format '{{.Ports}}') | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to inspect Docker published ports.'
    }
    $dockerPorts = @(
        [regex]::Matches($publishedPorts, ':(\d+)->') |
            ForEach-Object { [int]$_.Groups[1].Value }
    )
    $activePorts = @($listeners | ForEach-Object Port) + $dockerPorts
    $conflicts = @($ports | Where-Object { $activePorts -contains $_ })
    if ($conflicts.Count -gt 0) {
        throw "Benchmark ports are already in use: $($conflicts -join ', ')"
    }
}

Push-Location $repositoryRoot
try {
    if ((Get-ProjectResources).Count -gt 0) {
        throw "Refusing to reuse existing resources for $projectName."
    }
    if ((Test-Path $jsonOutput) -or (Test-Path $markdownOutput)) {
        throw 'Refusing to overwrite existing P1-11 performance evidence.'
    }
    Assert-PortsAvailable

    $env:CAREEROPS_POSTGRES_PORT = [string]$PostgresPort
    $env:CAREEROPS_REDIS_PORT = [string]$RedisPort
    $env:CAREEROPS_API_PORT = [string]$ApiPort
    $env:CAREEROPS_LLM_PROVIDER = 'fake'
    $env:CAREEROPS_EMBEDDING_PROVIDER = 'fake'
    $env:CAREEROPS_EVIDENCE_MATCHER_PROVIDER = 'fake'

    Invoke-Compose @('up', '-d', '--build', '--wait', '--wait-timeout', '300', 'postgres', 'redis', 'migrate', 'api')

    $gitRevision = "$(git rev-parse --short=12 HEAD)+working-tree-p1-11"
    & .\.venv\Scripts\python -m careerops.operations.read_endpoint_benchmark `
        --base-url "http://127.0.0.1:$ApiPort" `
        --database-url "postgresql+asyncpg://careerops:careerops@127.0.0.1:$PostgresPort/careerops" `
        --redis-url "redis://127.0.0.1:$RedisPort/0" `
        --run-id $RunId `
        --git-revision $gitRevision `
        --json-output $jsonOutput `
        --markdown-output $markdownOutput
    if ($LASTEXITCODE -ne 0) {
        throw "Read endpoint benchmark failed with exit code $LASTEXITCODE"
    }
} finally {
    try {
        if ((Get-ProjectResources).Count -gt 0) {
            & docker compose @composePrefix down --volumes --remove-orphans
            if ($LASTEXITCODE -ne 0) {
                throw "Benchmark cleanup failed with exit code $LASTEXITCODE"
            }
        }
        if ((Get-ProjectResources).Count -gt 0) {
            throw "Benchmark cleanup left resources for $projectName."
        }
    } finally {
        $env:CAREEROPS_POSTGRES_PORT = $previousPostgresPort
        $env:CAREEROPS_REDIS_PORT = $previousRedisPort
        $env:CAREEROPS_API_PORT = $previousApiPort
        $env:CAREEROPS_LLM_PROVIDER = $previousParserProvider
        $env:CAREEROPS_EMBEDDING_PROVIDER = $previousEmbeddingProvider
        $env:CAREEROPS_EVIDENCE_MATCHER_PROVIDER = $previousMatcherProvider
        Pop-Location
    }
}
