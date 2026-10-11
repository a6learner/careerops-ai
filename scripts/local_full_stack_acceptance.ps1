[CmdletBinding()]
param(
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,40}$')]
    [string]$RunId = ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')),
    [ValidateRange(1, 65535)]
    [int]$PostgresPort = 15410,
    [ValidateRange(1, 65535)]
    [int]$RedisPort = 16310,
    [ValidateRange(1, 65535)]
    [int]$ApiPort = 18010,
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 13010,
    [switch]$DemoRehearsal
)

$ErrorActionPreference = 'Stop'
$projectName = "careerops-p110-$RunId"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$environmentFile = Join-Path $PSScriptRoot 'compose-acceptance.env'
$composeFile = Join-Path $repositoryRoot 'docker-compose.yml'
$acceptanceFile = Join-Path $repositoryRoot 'docker-compose.acceptance.yml'
$composePrefix = @(
    '--project-name', $projectName,
    '--env-file', $environmentFile,
    '-f', $composeFile,
    '-f', $acceptanceFile
)
$ports = @($PostgresPort, $RedisPort, $ApiPort, $FrontendPort)
$previousPostgresPort = $env:CAREEROPS_POSTGRES_PORT
$previousRedisPort = $env:CAREEROPS_REDIS_PORT
$previousApiPort = $env:CAREEROPS_API_PORT
$previousFrontendPort = $env:CAREEROPS_FRONTEND_PORT
$result = [ordered]@{
    run_id = $RunId
    project = $projectName
    frontend_url = "http://127.0.0.1:$FrontendPort"
    providers = [ordered]@{
        parser = 'fake'
        embedding = 'fake'
        matcher = 'fake'
    }
    migration = 'not_run'
    frontend_user = 'not_checked'
    core_loop = 'not_run'
    demo_rehearsal = if ($DemoRehearsal) { 'not_run' } else { 'not_requested' }
    browser_elapsed_seconds = $null
    cleanup = 'not_run'
}

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
        throw "Acceptance ports are already in use: $($conflicts -join ', ')"
    }
}

function Assert-FakeProviders {
    $configurationJson = (& docker compose @composePrefix config --format json) | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to resolve the acceptance Compose configuration.'
    }
    $configuration = $configurationJson | ConvertFrom-Json
    foreach ($serviceName in @('api', 'worker')) {
        $environment = $configuration.services.$serviceName.environment
        foreach ($variableName in @(
            'CAREEROPS_LLM_PROVIDER',
            'CAREEROPS_EMBEDDING_PROVIDER',
            'CAREEROPS_EVIDENCE_MATCHER_PROVIDER'
        )) {
            if ($environment.$variableName -ne 'fake') {
                throw "$serviceName must set $variableName=fake for acceptance."
            }
        }
    }
    if ($configuration.services.frontend.environment.CAREEROPS_API_BASE_URL -ne 'http://api:8000') {
        throw 'The frontend must use CAREEROPS_API_BASE_URL=http://api:8000.'
    }
    if ($configuration.services.frontend.environment.CAREEROPS_FRONTEND_ORIGIN -ne "http://127.0.0.1:$FrontendPort") {
        throw 'The frontend public origin must match the browser acceptance URL.'
    }
}

function Assert-RunningProviderEnvironment {
    foreach ($serviceName in @('api', 'worker')) {
        foreach ($variableName in @(
            'CAREEROPS_LLM_PROVIDER',
            'CAREEROPS_EMBEDDING_PROVIDER',
            'CAREEROPS_EVIDENCE_MATCHER_PROVIDER'
        )) {
            $value = (& docker compose @composePrefix exec -T $serviceName printenv $variableName) | Out-String
            if ($LASTEXITCODE -ne 0 -or $value.Trim() -ne 'fake') {
                throw "$serviceName is not running with $variableName=fake."
            }
        }
    }
}

function Assert-RuntimeBoundaries {
    $migrateContainerId = ((& docker compose @composePrefix ps -a -q migrate) | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or !$migrateContainerId) {
        throw 'The one-shot migration container was not found.'
    }
    $migrationExitCode = ((& docker inspect --format '{{.State.ExitCode}}' $migrateContainerId) | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $migrationExitCode -ne '0') {
        throw "The one-shot migration did not exit successfully: $migrationExitCode"
    }
    $result.migration = 'passed'

    $frontendUid = ((& docker compose @composePrefix exec -T frontend id -u) | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or !$frontendUid -or $frontendUid -eq '0') {
        throw "The frontend must run as a non-root user; observed UID: $frontendUid"
    }
    $result.frontend_user = "uid=$frontendUid"
}

Push-Location $repositoryRoot
try {
    if ((Get-ProjectResources).Count -gt 0) {
        throw "Refusing to reuse existing resources for $projectName."
    }
    Assert-PortsAvailable

    $env:CAREEROPS_POSTGRES_PORT = [string]$PostgresPort
    $env:CAREEROPS_REDIS_PORT = [string]$RedisPort
    $env:CAREEROPS_API_PORT = [string]$ApiPort
    $env:CAREEROPS_FRONTEND_PORT = [string]$FrontendPort
    Assert-FakeProviders

    Invoke-Compose @('up', '-d', '--build', '--wait', '--wait-timeout', '300')
    Assert-RuntimeBoundaries
    Assert-RunningProviderEnvironment

    $health = Invoke-RestMethod "http://127.0.0.1:$FrontendPort/healthz"
    $readiness = Invoke-RestMethod "http://127.0.0.1:$FrontendPort/readyz"
    if ($health.status -ne 'ok' -or $readiness.status -ne 'ready' -or !$readiness.api) {
        throw 'Frontend liveness or readiness did not satisfy the acceptance contract.'
    }

    $previousBaseUrl = $env:CAREEROPS_E2E_BASE_URL
    $previousDemoPacing = $env:CAREEROPS_E2E_DEMO_PACING
    try {
        $env:CAREEROPS_E2E_BASE_URL = "http://127.0.0.1:$FrontendPort"
        if ($DemoRehearsal) {
            $env:CAREEROPS_E2E_DEMO_PACING = '1'
        } else {
            Remove-Item Env:CAREEROPS_E2E_DEMO_PACING -ErrorAction SilentlyContinue
        }
        $browserStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        & npm --prefix frontend run test:e2e
        $browserStopwatch.Stop()
        $result.browser_elapsed_seconds = [Math]::Round($browserStopwatch.Elapsed.TotalSeconds, 1)
        if ($LASTEXITCODE -ne 0) {
            throw "Playwright failed with exit code $LASTEXITCODE"
        }
        if ($DemoRehearsal) {
            if ($browserStopwatch.Elapsed.TotalMinutes -lt 3 -or $browserStopwatch.Elapsed.TotalMinutes -gt 5) {
                throw "Demo rehearsal must take 3-5 minutes; observed $($result.browser_elapsed_seconds) seconds."
            }
            $result.demo_rehearsal = 'passed'
        }
    } finally {
        $env:CAREEROPS_E2E_BASE_URL = $previousBaseUrl
        $env:CAREEROPS_E2E_DEMO_PACING = $previousDemoPacing
    }

    $result.core_loop = 'passed'
} finally {
    try {
        if ((Get-ProjectResources).Count -gt 0) {
            & docker compose @composePrefix down --volumes --remove-orphans
            if ($LASTEXITCODE -ne 0) {
                throw "Acceptance cleanup failed with exit code $LASTEXITCODE"
            }
        }
        $remainingResources = @(Get-ProjectResources)
        if ($remainingResources.Count -gt 0) {
            $result.cleanup = 'failed'
            throw "Acceptance cleanup left project resources: $($remainingResources -join ', ')"
        }
        $result.cleanup = 'passed'
    } finally {
        $env:CAREEROPS_POSTGRES_PORT = $previousPostgresPort
        $env:CAREEROPS_REDIS_PORT = $previousRedisPort
        $env:CAREEROPS_API_PORT = $previousApiPort
        $env:CAREEROPS_FRONTEND_PORT = $previousFrontendPort
        Pop-Location
        $result | ConvertTo-Json -Depth 4
    }
}
