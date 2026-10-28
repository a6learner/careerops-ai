[CmdletBinding()]
param(
    [ValidateSet('Start', 'Stop')]
    [string]$Action = 'Start'
)

$ErrorActionPreference = 'Stop'
$docker = 'D:\software\basic\Docker\resources\bin\docker.exe'
$projectName = 'careerops-agent-demo-20261027'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composePrefix = @(
    '--project-name', $projectName,
    '--env-file', (Join-Path $PSScriptRoot 'compose-acceptance.env'),
    '-f', (Join-Path $repositoryRoot 'docker-compose.yml'),
    '-f', (Join-Path $repositoryRoot 'docker-compose.acceptance.yml'),
    '-f', (Join-Path $repositoryRoot 'docker-compose.agent-demo.yml')
)

function Invoke-DemoCompose {
    param([Parameter(Mandatory)][string[]]$Arguments)
    & $docker compose @composePrefix @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "The isolated demo operation failed with exit code $LASTEXITCODE."
    }
}

function Assert-DemoConfiguration {
    $raw = (& $docker compose @composePrefix config --format json) | Out-String
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the isolated demo configuration.' }
    $configuration = $raw | ConvertFrom-Json
    if ($configuration.name -ne $projectName) { throw 'Unexpected demo project identity.' }
    foreach ($service in @('api', 'worker')) {
        $environment = $configuration.services.$service.environment
        foreach ($setting in @(
            'CAREEROPS_LLM_PROVIDER', 'CAREEROPS_EMBEDDING_PROVIDER',
            'CAREEROPS_EVIDENCE_MATCHER_PROVIDER'
        )) {
            if ($environment.$setting -ne 'fake') { throw "$service must use fake providers." }
        }
        foreach ($setting in @('CAREEROPS_LLM_API_KEY', 'CAREEROPS_GEMINI_API_KEY')) {
            if ($environment.$setting) { throw "$service must not receive model provider keys." }
        }
        if ($environment.CAREEROPS_ENV -ne 'local') { throw 'Demo must use local configuration.' }
    }
    $expectedPorts = @{ postgres = 15421; redis = 16321; api = 18021; frontend = 13021 }
    foreach ($service in $expectedPorts.Keys) {
        $published = @($configuration.services.$service.ports)
        if ($published.Count -ne 1 -or $published[0].host_ip -ne '127.0.0.1' -or
            [int]$published[0].published -ne $expectedPorts[$service]) {
            throw "Unexpected $service demo port binding."
        }
    }
    if ($configuration.services.frontend.environment.CAREEROPS_FRONTEND_ORIGIN -ne
        'http://127.0.0.1:13021') { throw 'Unexpected demo frontend origin.' }
}

function Assert-DemoPortsAvailable {
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    $published = (& $docker ps --format '{{.Ports}}') | Out-String
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect published Docker ports.' }
    $dockerPorts = @([regex]::Matches($published, ':(\d+)->') | ForEach-Object { [int]$_.Groups[1].Value })
    $occupied = @($listeners | ForEach-Object Port) + $dockerPorts
    $conflicts = @(15421, 16321, 18021, 13021 | Where-Object { $occupied -contains $_ })
    if ($conflicts.Count -gt 0) {
        throw "Demo ports are occupied: $($conflicts -join ', '). Stop only this demo before restarting it."
    }
}

Assert-DemoConfiguration
if ($Action -eq 'Stop') {
    # Fixed project scope; deliberately omit --volumes to retain user demo records.
    Invoke-DemoCompose @('down')
    Write-Output "Stopped only $projectName. Its PostgreSQL volume and demo data are retained."
    exit 0
}

Assert-DemoPortsAvailable
Invoke-DemoCompose @('up', '-d', '--build', '--wait', '--wait-timeout', '300')
foreach ($service in @('api', 'worker')) {
    foreach ($setting in @(
        'CAREEROPS_LLM_PROVIDER', 'CAREEROPS_EMBEDDING_PROVIDER',
        'CAREEROPS_EVIDENCE_MATCHER_PROVIDER'
    )) {
        $value = (& $docker compose @composePrefix exec -T $service printenv $setting) | Out-String
        if ($LASTEXITCODE -ne 0 -or $value.Trim() -ne 'fake') {
            throw "$service is not running with the expected fake providers."
        }
    }
}
$readiness = Invoke-RestMethod 'http://127.0.0.1:13021/readyz'
if ($readiness.status -ne 'ready' -or !$readiness.api) { throw 'Demo frontend is not ready.' }
[ordered]@{
    project = $projectName
    frontend_url = 'http://127.0.0.1:13021'
    api_url = 'http://127.0.0.1:18021'
    provider_mode = 'fake'
    code = 'rebuilt from the current working tree'
    readiness = 'passed'
    data = 'retained until an explicit volume deletion'
    stop_command = '.\scripts\local_project_agent_demo.ps1 -Action Stop'
} | ConvertTo-Json
