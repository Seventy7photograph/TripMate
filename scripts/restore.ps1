# 文件说明：工程脚本：restore。
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$RestoreDatabase = "tripmate_restore_check",
    [switch]$KeepDatabase
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backup = (Resolve-Path -LiteralPath $BackupFile).Path
$postgresUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "tripmate" }
$postgresDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "tripmate" }

if ($RestoreDatabase -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
    throw "RestoreDatabase must be a safe PostgreSQL identifier"
}
if ($RestoreDatabase -eq $postgresDb) {
    throw "RestoreDatabase must differ from the source database"
}

$containerFile = "/tmp/tripmate-restore-$([guid]::NewGuid().ToString('N')).dump"
$restoreCreated = $false

function Invoke-Psql {
    param(
        [string]$Database,
        [string]$Sql
    )
    $output = & docker compose exec -T postgres psql `
        -U $postgresUser `
        -d $Database `
        -v ON_ERROR_STOP=1 `
        -tA `
        -c $Sql
    if ($LASTEXITCODE -ne 0) { throw "psql failed with exit code $LASTEXITCODE" }
    return ($output | Out-String).Trim()
}

function Get-DatabaseCounts {
    param([string]$Database)
    $sql = @"
SELECT json_build_object(
  'users', (SELECT count(*) FROM users),
  'trips', (SELECT count(*) FROM trips),
  'trip_versions', (SELECT count(*) FROM trip_versions),
  'conversations', (SELECT count(*) FROM conversations),
  'uploaded_assets', (SELECT count(*) FROM uploaded_assets)
)::text;
"@
    return (Invoke-Psql -Database $Database -Sql $sql | ConvertFrom-Json)
}

Push-Location $repoRoot
try {
    & docker compose cp $backup "postgres:$containerFile"
    if ($LASTEXITCODE -ne 0) { throw "docker compose cp failed with exit code $LASTEXITCODE" }

    Invoke-Psql -Database "postgres" `
        -Sql "DROP DATABASE IF EXISTS `"$RestoreDatabase`" WITH (FORCE)" | Out-Null
    Invoke-Psql -Database "postgres" `
        -Sql "CREATE DATABASE `"$RestoreDatabase`"" | Out-Null
    $restoreCreated = $true

    & docker compose exec -T postgres pg_restore `
        -U $postgresUser `
        -d $RestoreDatabase `
        --no-owner `
        --no-privileges `
        --exit-on-error `
        $containerFile
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE" }

    $sourceCounts = Get-DatabaseCounts -Database $postgresDb
    $restoredCounts = Get-DatabaseCounts -Database $RestoreDatabase
    $sourceJson = $sourceCounts | ConvertTo-Json -Compress
    $restoredJson = $restoredCounts | ConvertTo-Json -Compress
    if ($sourceJson -ne $restoredJson) {
        throw "Restored table counts do not match source: $sourceJson != $restoredJson"
    }

    $sourceRevision = Invoke-Psql -Database $postgresDb `
        -Sql "SELECT version_num FROM alembic_version LIMIT 1"
    $restoredRevision = Invoke-Psql -Database $RestoreDatabase `
        -Sql "SELECT version_num FROM alembic_version LIMIT 1"
    if ($sourceRevision -ne $restoredRevision) {
        throw "Restored migration revision does not match source"
    }

    [pscustomobject]@{
        restored_database = $RestoreDatabase
        revision = $restoredRevision
        counts = $restoredCounts
        kept = [bool]$KeepDatabase
    } | ConvertTo-Json -Compress -Depth 4
}
finally {
    & docker compose exec -T postgres rm -f $containerFile | Out-Null
    if ($restoreCreated -and -not $KeepDatabase) {
        try {
            Invoke-Psql -Database "postgres" `
                -Sql "DROP DATABASE IF EXISTS `"$RestoreDatabase`" WITH (FORCE)" | Out-Null
        }
        catch {
            Write-Warning "Could not drop restore database: $($_.Exception.Message)"
        }
    }
    Pop-Location
}
