# 文件说明：工程脚本：performance-smoke。
[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8010/api/v1",
    [int]$Vus = 5,
    [int]$DurationSeconds = 10,
    [switch]$UseK6
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputDirectory = Join-Path $repoRoot "output\performance"
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$summaryFile = Join-Path $outputDirectory "trip-crud-$timestamp.json"

$health = Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/v1/health" -TimeoutSec 5
if ($health.status -ne "ok") {
    throw "API health check is not ok"
}

if ($UseK6) {
    $duration = "${DurationSeconds}s"
    $containerBaseUrl = $BaseUrl.Replace("127.0.0.1", "host.docker.internal")
    & docker run --rm `
        -v "${repoRoot}:/work" `
        -w "/work" `
        -e "BASE_URL=$containerBaseUrl" `
        -e "VUS=$Vus" `
        -e "DURATION=$duration" `
        grafana/k6 run `
        --summary-export "/work/output/performance/k6-$timestamp.json" `
        "/work/tests/performance/trip_crud.js"
    if ($LASTEXITCODE -ne 0) {
        throw "k6 performance thresholds failed with exit code $LASTEXITCODE"
    }
    Get-Content -Raw (Join-Path $outputDirectory "k6-$timestamp.json")
    exit 0
}

& node (Join-Path $repoRoot "scripts\uv.mjs") run `
    --project (Join-Path $repoRoot "apps\api") `
    python (Join-Path $repoRoot "tests\performance\trip_crud.py") `
    --base-url $BaseUrl `
    --vus $Vus `
    --duration $DurationSeconds `
    --output $summaryFile
if ($LASTEXITCODE -ne 0) {
    throw "Python CRUD performance thresholds failed with exit code $LASTEXITCODE"
}
Get-Content -Raw $summaryFile
