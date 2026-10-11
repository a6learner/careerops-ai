[CmdletBinding()]
param(
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,40}$')]
    [string]$RunId = ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')),
    [ValidateRange(1, 65535)]
    [int]$PostgresPort = 15412
)

$ErrorActionPreference = 'Stop'
$projectName = "careerops-p111-rollback-$RunId"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$environmentFile = Join-Path $PSScriptRoot 'compose-acceptance.env'
$composeFile = Join-Path $repositoryRoot 'docker-compose.yml'
$composePrefix = @('--project-name', $projectName, '--env-file', $environmentFile, '-f', $composeFile)
$previousPostgresPort = $env:CAREEROPS_POSTGRES_PORT
$result = [ordered]@{
    run_id = $RunId
    project = $projectName
    boundary = '202610060001 <-> 202609190001'
    upgrade_to_head = 'not_run'
    model_migration_check = 'not_run'
    downgrade = 'not_run'
    data_preserved = 'not_checked'
    reupgrade = 'not_run'
    constraint_rejection = 'not_checked'
    cleanup = 'not_run'
}

function Invoke-Compose {
    param([Parameter(Mandatory)][string[]]$Arguments)
    $output = (& docker compose @composePrefix @Arguments) | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE"
    }
    return $output.Trim()
}

function Invoke-DatabaseSql {
    param([Parameter(Mandatory)][string]$Sql)
    $output = (& docker compose @composePrefix exec -T postgres psql -X -v ON_ERROR_STOP=1 -U careerops -d careerops -Atc $Sql) | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL command failed with exit code $LASTEXITCODE"
    }
    return $output.Trim()
}

function Get-ProjectResources {
    $containers = @(& docker ps -a --filter "label=com.docker.compose.project=$projectName" --format '{{.ID}}')
    $networks = @(& docker network ls --filter "label=com.docker.compose.project=$projectName" --format '{{.ID}}')
    $volumes = @(& docker volume ls --filter "label=com.docker.compose.project=$projectName" --format '{{.Name}}')
    return @($containers + $networks + $volumes | Where-Object { $_ })
}

$seedSql = @"
INSERT INTO users (id, email, password_hash)
VALUES ('11111111-1111-1111-1111-111111111111', 'p111-rollback@example.com', 'synthetic');
INSERT INTO jobs (
  id, user_id, company, title, raw_description, description_hash, status, version
) VALUES (
  '22222222-2222-2222-2222-222222222222',
  '11111111-1111-1111-1111-111111111111',
  'Synthetic Company', 'Backend Engineer', 'Python required',
  repeat('a', 64), 'saved', 1
);
INSERT INTO parse_runs (
  id, user_id, job_id, status, idempotency_key, input_fingerprint, input_text,
  model_name, prompt_version, attempt, started_at, finished_at
) VALUES (
  '33333333-3333-3333-3333-333333333333',
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222',
  'succeeded', 'p111-rollback-parse', repeat('b', 64), 'Python required',
  'fake-requirement-parser', 'synthetic-rollback', 1, now(), now()
);
INSERT INTO analysis_runs (
  id, user_id, job_id, parse_run_id, status, idempotency_key, input_fingerprint,
  model_name, prompt_version, attempt, validation_failure_count, started_at, finished_at
) VALUES (
  '44444444-4444-4444-4444-444444444444',
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222',
  '33333333-3333-3333-3333-333333333333',
  'succeeded', 'p111-rollback-analysis', repeat('c', 64),
  'fake-evidence-matcher', 'synthetic-rollback', 1, 0, now(), now()
);
"@

Push-Location $repositoryRoot
try {
    if ((Get-ProjectResources).Count -gt 0) {
        throw "Refusing to reuse existing resources for $projectName."
    }
    $publishedPorts = (& docker ps --format '{{.Ports}}') | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to inspect Docker published ports.'
    }
    $dockerPorts = @(
        [regex]::Matches($publishedPorts, ':(\d+)->') |
            ForEach-Object { [int]$_.Groups[1].Value }
    )
    $activePorts = @(
        [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
            ForEach-Object Port
    ) + $dockerPorts
    if ($activePorts -contains $PostgresPort) {
        throw "Rollback drill port is already in use: $PostgresPort"
    }

    $env:CAREEROPS_POSTGRES_PORT = [string]$PostgresPort
    Invoke-Compose @('up', '-d', '--wait', '--wait-timeout', '120', 'postgres') | Out-Null
    Invoke-Compose @('run', '--rm', 'migrate', 'alembic', 'upgrade', 'head') | Out-Null
    $head = Invoke-Compose @('run', '--rm', 'migrate', 'alembic', 'current')
    if ($head -notmatch '202610060001') {
        throw "Expected head 202610060001, observed: $head"
    }
    $result.upgrade_to_head = 'passed'
    $schemaCheck = Invoke-Compose @('run', '--rm', 'migrate', 'alembic', 'check')
    if ($schemaCheck -notmatch 'No new upgrade operations detected') {
        throw "Alembic model/migration check failed: $schemaCheck"
    }
    $result.model_migration_check = 'passed'

    Invoke-DatabaseSql $seedSql | Out-Null
    $before = Invoke-DatabaseSql "SELECT count(*) || ':' || min(status) FROM analysis_runs;"
    $constraintAtHead = Invoke-DatabaseSql "SELECT count(*) FROM pg_constraint WHERE conname = 'ck_analysis_runs_lifecycle';"
    if ($constraintAtHead -ne '1') {
        throw 'Lifecycle constraint is missing at head.'
    }

    Invoke-Compose @('run', '--rm', 'migrate', 'alembic', 'downgrade', '202609190001') | Out-Null
    $downgraded = Invoke-Compose @('run', '--rm', 'migrate', 'alembic', 'current')
    if ($downgraded -notmatch '202609190001') {
        throw "Expected downgrade revision 202609190001, observed: $downgraded"
    }
    $result.downgrade = 'passed'
    $constraintAfterDowngrade = Invoke-DatabaseSql "SELECT count(*) FROM pg_constraint WHERE conname = 'ck_analysis_runs_lifecycle';"
    $afterDowngrade = Invoke-DatabaseSql "SELECT count(*) || ':' || min(status) FROM analysis_runs;"
    if ($constraintAfterDowngrade -ne '0' -or $afterDowngrade -ne $before) {
        throw 'The supported downgrade did not preserve the expected data boundary.'
    }
    $result.data_preserved = 'passed'

    Invoke-Compose @('run', '--rm', 'migrate', 'alembic', 'upgrade', 'head') | Out-Null
    $constraintAfterUpgrade = Invoke-DatabaseSql "SELECT count(*) FROM pg_constraint WHERE conname = 'ck_analysis_runs_lifecycle';"
    $afterUpgrade = Invoke-DatabaseSql "SELECT count(*) || ':' || min(status) FROM analysis_runs;"
    if ($constraintAfterUpgrade -ne '1' -or $afterUpgrade -ne $before) {
        throw 'Re-upgrade did not restore the constraint and preserve data.'
    }
    $result.reupgrade = 'passed'

    & docker compose @composePrefix exec -T postgres psql -X -v ON_ERROR_STOP=1 -U careerops -d careerops -c @"
INSERT INTO analysis_runs (
  id, user_id, job_id, parse_run_id, status, idempotency_key, input_fingerprint,
  model_name, prompt_version, attempt, validation_failure_count
) VALUES (
  '55555555-5555-5555-5555-555555555555',
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222',
  '33333333-3333-3333-3333-333333333333',
  'succeeded', 'p111-invalid-analysis', repeat('d', 64),
  'fake-evidence-matcher', 'synthetic-rollback', 1, 0
);
"@ | Out-Null
    if ($LASTEXITCODE -eq 0) {
        throw 'PostgreSQL accepted an invalid lifecycle row after re-upgrade.'
    }
    $result.constraint_rejection = 'passed'
} finally {
    try {
        if ((Get-ProjectResources).Count -gt 0) {
            & docker compose @composePrefix down --volumes --remove-orphans | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "Rollback cleanup failed with exit code $LASTEXITCODE"
            }
        }
        if ((Get-ProjectResources).Count -gt 0) {
            $result.cleanup = 'failed'
            throw "Rollback cleanup left resources for $projectName."
        }
        $result.cleanup = 'passed'
    } finally {
        $env:CAREEROPS_POSTGRES_PORT = $previousPostgresPort
        Pop-Location
        $result | ConvertTo-Json -Depth 3
    }
}
