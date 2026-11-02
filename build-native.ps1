$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$source = Join-Path $PSScriptRoot 'supporter/CaretProbe.cs'
$hasher=[Security.Cryptography.SHA256]::Create()
$hash = ([BitConverter]::ToString($hasher.ComputeHash([IO.File]::ReadAllBytes($source))).Replace('-','')).Substring(0,12).ToLowerInvariant()
$target = Join-Path $runtime ('caret-probe-' + $hash + '.exe')
if (-not (Test-Path $target)) {
    Add-Type -Path (Join-Path $PSScriptRoot 'supporter/CaretProbe.cs') -ReferencedAssemblies @('UIAutomationClient','UIAutomationTypes','WindowsBase','System.Web.Extensions') -OutputAssembly $target -OutputType ConsoleApplication
}
Set-Content -LiteralPath (Join-Path $runtime 'caret-path.txt') -Value $target -Encoding utf8
$pasteSource = Join-Path $PSScriptRoot 'supporter/PasteBridge.cs'
$pasteHash = ([BitConverter]::ToString($hasher.ComputeHash([IO.File]::ReadAllBytes($pasteSource))).Replace('-','')).Substring(0,12).ToLowerInvariant()
$pasteTarget = Join-Path $runtime ('paste-bridge-' + $pasteHash + '.exe')
if (-not (Test-Path $pasteTarget)) {
    Add-Type -Path $pasteSource -ReferencedAssemblies @('System.Windows.Forms','System.Drawing','System.Web.Extensions') -OutputAssembly $pasteTarget -OutputType ConsoleApplication
}
Set-Content -LiteralPath (Join-Path $runtime 'paste-path.txt') -Value $pasteTarget -Encoding utf8
$hasher.Dispose()
