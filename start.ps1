$ErrorActionPreference = 'Stop'
$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw 'Python 3.11+ is required on PATH.' }
& (Join-Path $PSScriptRoot 'build-native.ps1')
$electron = Join-Path $PSScriptRoot 'node_modules/electron/dist/electron.exe'
if (-not (Test-Path $electron)) { throw 'Run npm install in the Supporter directory first.' }
$legacyEntry = Join-Path $PSScriptRoot 'run.py'
Get-CimInstance Win32_Process -Filter "name = 'pythonw.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine.Contains('"' + $legacyEntry + '"')
} | ForEach-Object { Stop-Process -Id $_.ProcessId }
$env:SUPPORTER_PYTHON = $pythonCommand.Source
Start-Process -FilePath $electron -ArgumentList ('"' + $PSScriptRoot + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
