# 文件说明：工程脚本：stop-local-rc。
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidFile = Join-Path $repoRoot "output\rc\pids.json"
if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Output "No local RC process file found."
    exit 0
}

$state = Get-Content -Raw $pidFile | ConvertFrom-Json

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

foreach ($name in @("web", "admin", "api")) {
    $processId = [int]$state.$name
    Stop-ProcessTree -ProcessId $processId
    Write-Output "Stopped $name process tree PID $processId"
}
Remove-Item -LiteralPath $pidFile
