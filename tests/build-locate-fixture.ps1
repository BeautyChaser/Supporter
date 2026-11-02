$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $root '.runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$source = Join-Path $PSScriptRoot 'LocateEditorFixture.cs'
$hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.Substring(0,12).ToLowerInvariant()
$target = Join-Path $runtime ('locate-editor-fixture-' + $hash + '.exe')
if (-not (Test-Path -LiteralPath $target)) {
    Add-Type -Path $source -ReferencedAssemblies @('System.Windows.Forms','System.Drawing','System.Web.Extensions') -OutputAssembly $target -OutputType ConsoleApplication
}
Set-Content -LiteralPath (Join-Path $runtime 'locate-fixture-path.txt') -Value $target -Encoding utf8
Write-Output $target
