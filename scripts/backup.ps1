# 文件说明：工程脚本：backup。
[CmdletBinding()]
param(
    [string]$OutputDirectory = "",
    [string]$UploadDirectory = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot "output\backups"
}
if (-not $UploadDirectory) {
    $UploadDirectory = if ($env:UPLOAD_DIR) {
        $env:UPLOAD_DIR
    } else {
        Join-Path $repoRoot "output\uploads"
    }
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$postgresUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "tripmate" }
$postgresDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "tripmate" }
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$containerFile = "/tmp/tripmate-$timestamp.dump"
$localFile = Join-Path $OutputDirectory "tripmate-$timestamp.dump"

Push-Location $repoRoot
try {
    & docker compose exec -T postgres pg_dump `
        -U $postgresUser `
        -d $postgresDb `
        --format=custom `
        --no-owner `
        --no-privileges `
        --file=$containerFile
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }

    & docker compose cp "postgres:$containerFile" $localFile
    if ($LASTEXITCODE -ne 0) { throw "docker compose cp failed with exit code $LASTEXITCODE" }

    & docker compose exec -T postgres rm -f $containerFile | Out-Null

    $revisionOutput = & docker compose exec -T postgres psql `
        -U $postgresUser `
        -d $postgresDb `
        -tA `
        -c "SELECT version_num FROM alembic_version LIMIT 1"
    $revision = ($revisionOutput | Out-String).Trim()

    $countSql = @"
SELECT json_build_object(
  'users', (SELECT count(*) FROM users),
  'trips', (SELECT count(*) FROM trips),
  'trip_versions', (SELECT count(*) FROM trip_versions),
  'conversations', (SELECT count(*) FROM conversations),
  'uploaded_assets', (SELECT count(*) FROM uploaded_assets)
)::text;
"@
    $countsOutput = & docker compose exec -T postgres psql `
        -U $postgresUser `
        -d $postgresDb `
        -tA `
        -c $countSql
    $counts = ($countsOutput | Out-String).Trim() | ConvertFrom-Json

    $file = Get-Item -LiteralPath $localFile
    $uploadManifest = $null
    if (Test-Path -LiteralPath $UploadDirectory -PathType Container) {
        $uploadFiles = Get-ChildItem -LiteralPath $UploadDirectory -File -Recurse
        if ($uploadFiles.Count -gt 0) {
            $uploadArchive = Join-Path $OutputDirectory "tripmate-$timestamp.uploads.tar.gz"
            & tar.exe -czf $uploadArchive -C $UploadDirectory .
            if ($LASTEXITCODE -ne 0) {
                throw "upload archive failed with exit code $LASTEXITCODE"
            }
            $uploadFile = Get-Item -LiteralPath $uploadArchive
            $uploadManifest = [ordered]@{
                file = $uploadFile.Name
                size_bytes = $uploadFile.Length
                sha256 = (Get-FileHash -LiteralPath $uploadFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
                file_count = $uploadFiles.Count
            }
        } else {
            $uploadManifest = [ordered]@{
                file = $null
                size_bytes = 0
                sha256 = $null
                file_count = 0
            }
        }
    }
    $manifest = [ordered]@{
        format_version = 1
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        database = $postgresDb
        alembic_revision = $revision
        file = $file.FullName
        size_bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        counts = $counts
        uploads = $uploadManifest
    }
    $manifestPath = "$localFile.manifest.json"
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8

    [pscustomobject]@{
        backup = $file.FullName
        manifest = $manifestPath
        revision = $revision
        sha256 = $manifest.sha256
        uploads = $uploadManifest
    } | ConvertTo-Json -Compress
}
finally {
    Pop-Location
}
