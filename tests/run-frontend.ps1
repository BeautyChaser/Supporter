$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$electron = Join-Path $taskRoot 'node_modules/electron/dist/electron.exe'
$application = Join-Path $PSScriptRoot 'frontend-agent-app'
$reportPath = Join-Path $taskRoot '.runtime/frontend-agent-report.json'
if (-not (Test-Path -LiteralPath $electron)) { throw 'Install the local Electron runtime before running frontend tests.' }
$started = (Get-Date).ToUniversalTime()
$testProcess = Start-Process -FilePath $electron -ArgumentList ('"' + $application + '"') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru
if (-not $testProcess.WaitForExit(45000)) {
    # This PID was returned by this exact test launch. It is never a user app.
    taskkill.exe /PID $testProcess.Id /T /F | Out-Null
    throw 'Frontend tests exceeded the 45 second deadline.'
}
if (-not (Test-Path -LiteralPath $reportPath)) { throw 'The test process did not write a report.' }
if ((Get-Item -LiteralPath $reportPath).LastWriteTimeUtc -lt $started) { throw 'The report is stale; this test run did not update it.' }
$result = Get-Content -LiteralPath $reportPath -Raw -Encoding utf8 | ConvertFrom-Json
$result | ConvertTo-Json -Depth 10
if ($result.running -or -not $result.passed) { exit 1 }
