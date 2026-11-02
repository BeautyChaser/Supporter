$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$electron = Join-Path $taskRoot 'node_modules/electron/dist/electron.exe'
$application = Join-Path $PSScriptRoot 'onboarding-agent-app'
$reportPath = Join-Path $taskRoot '.runtime/onboarding-agent-report.json'
if (-not (Test-Path -LiteralPath $electron)) { throw 'The local Electron runtime is required for development tests.' }
$started = (Get-Date).ToUniversalTime()
$testProcess = Start-Process -FilePath $electron -ArgumentList ('"' + $application + '"') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru
if (-not $testProcess.WaitForExit(30000)) {
    taskkill.exe /PID $testProcess.Id /T /F | Out-Null
    throw 'Onboarding tests exceeded the 30 second deadline.'
}
if (-not (Test-Path -LiteralPath $reportPath)) { throw 'The test did not write its report.' }
if ((Get-Item -LiteralPath $reportPath).LastWriteTimeUtc -lt $started) { throw 'The test report is stale.' }
$result = Get-Content -LiteralPath $reportPath -Raw -Encoding utf8 | ConvertFrom-Json
$result | ConvertTo-Json -Depth 10
if ($result.running -or -not $result.passed) { exit 1 }
