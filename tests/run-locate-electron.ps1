$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$electron = Join-Path $taskRoot 'node_modules/electron/dist/electron.exe'
$application = Join-Path $PSScriptRoot 'locate-fixture-app'
$reportPath = Join-Path $taskRoot '.runtime/locate-electron-test.json'
$started = (Get-Date).ToUniversalTime()
$testProcess = Start-Process -FilePath $electron -ArgumentList ('"' + $application + '"') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru
if (-not $testProcess.WaitForExit(15000)) {
    Stop-Process -Id $testProcess.Id
    throw 'Isolated locate fixture exceeded its deadline.'
}
if (-not (Test-Path -LiteralPath $reportPath)) { throw ('Fixture produced no report; exit code ' + $testProcess.ExitCode) }
if ((Get-Item -LiteralPath $reportPath).LastWriteTimeUtc -lt $started) { throw 'Fixture report is stale.' }
$result = Get-Content -LiteralPath $reportPath -Raw -Encoding utf8 | ConvertFrom-Json
$result | ConvertTo-Json -Depth 10
if (-not $result.passed) { exit 1 }
