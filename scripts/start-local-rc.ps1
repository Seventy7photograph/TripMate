# 文件说明：工程脚本：start-local-rc。
[CmdletBinding()]
param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 4173,
    [int]$AdminPort = 4174,
    [string]$ProviderProfile = "mock"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeDirectory = Join-Path $repoRoot "output\rc"
New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null
$pidFile = Join-Path $runtimeDirectory "pids.json"
$startedProcesses = @()

function Stop-ProcessTree {
    param([int]$ProcessId)
    $children = Get-CimInstance Win32_Process `
        -Filter "ParentProcessId=$ProcessId" `
        -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId $child.ProcessId
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

Push-Location $repoRoot
try {
    & docker compose up -d postgres redis
    if ($LASTEXITCODE -ne 0) { throw "Could not start PostgreSQL/Redis" }

    & corepack pnpm db:migrate
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed" }

    & corepack pnpm build
    if ($LASTEXITCODE -ne 0) { throw "Production build failed" }

    $node = (Get-Command node.exe).Source
    $corepack = (Get-Command corepack.cmd).Source
    $apiEnvironment = @{
        PROVIDER_PROFILE = $ProviderProfile
        MAP_PROVIDER_PROFILE = $ProviderProfile
        PLANNING_WORKER_ENABLED = "true"
    }
    $frontendEnvironment = @{
        VITE_API_PROXY_TARGET = "http://127.0.0.1:$ApiPort"
    }

    $api = Start-Process -FilePath $node `
        -ArgumentList @(
            "scripts/uv.mjs", "run", "--project", "apps/api",
            "python", "apps/api/run.py",
            "--host", "127.0.0.1", "--port", "$ApiPort"
        ) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -Environment $apiEnvironment `
        -RedirectStandardOutput (Join-Path $runtimeDirectory "api.out.log") `
        -RedirectStandardError (Join-Path $runtimeDirectory "api.err.log") `
        -PassThru
    $startedProcesses += $api

    $web = Start-Process -FilePath $corepack `
        -ArgumentList @(
            "pnpm", "--filter", "@tripmate/web", "preview",
            "--host", "127.0.0.1", "--port", "$WebPort"
        ) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -Environment $frontendEnvironment `
        -RedirectStandardOutput (Join-Path $runtimeDirectory "web.out.log") `
        -RedirectStandardError (Join-Path $runtimeDirectory "web.err.log") `
        -PassThru
    $startedProcesses += $web

    $admin = Start-Process -FilePath $corepack `
        -ArgumentList @(
            "pnpm", "--filter", "@tripmate/admin", "preview",
            "--host", "127.0.0.1", "--port", "$AdminPort"
        ) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -Environment $frontendEnvironment `
        -RedirectStandardOutput (Join-Path $runtimeDirectory "admin.out.log") `
        -RedirectStandardError (Join-Path $runtimeDirectory "admin.err.log") `
        -PassThru
    $startedProcesses += $admin

    [ordered]@{
        api = $api.Id
        web = $web.Id
        admin = $admin.Id
        started_at = (Get-Date).ToUniversalTime().ToString("o")
        urls = [ordered]@{
            api = "http://127.0.0.1:$ApiPort"
            web = "http://127.0.0.1:$WebPort"
            admin = "http://127.0.0.1:$AdminPort"
        }
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $pidFile -Encoding utf8

    $deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Milliseconds 800
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/api/v1/health" -TimeoutSec 3
            $webResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$WebPort" -UseBasicParsing -TimeoutSec 3
            $adminResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$AdminPort" -UseBasicParsing -TimeoutSec 3
        }
        catch {
            $health = $null
        }
    } until (
        ($health.status -eq "ok" -and $webResponse.StatusCode -eq 200 -and $adminResponse.StatusCode -eq 200) -or
        (Get-Date) -gt $deadline
    )

    if (-not $health -or $webResponse.StatusCode -ne 200 -or $adminResponse.StatusCode -ne 200) {
        Get-Content (Join-Path $runtimeDirectory "api.err.log") -ErrorAction SilentlyContinue
        Get-Content (Join-Path $runtimeDirectory "web.err.log") -ErrorAction SilentlyContinue
        Get-Content (Join-Path $runtimeDirectory "admin.err.log") -ErrorAction SilentlyContinue
        throw "Local production-mode RC did not become healthy"
    }

    [pscustomobject]@{
        api = "http://127.0.0.1:$ApiPort"
        web = "http://127.0.0.1:$WebPort"
        admin = "http://127.0.0.1:$AdminPort"
        provider_profile = $ProviderProfile
        status = "healthy"
        pid_file = $pidFile
    } | ConvertTo-Json -Compress
}
catch {
    foreach ($process in $startedProcesses) {
        Stop-ProcessTree -ProcessId $process.Id
    }
    Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue
    throw
}
finally {
    Pop-Location
}
