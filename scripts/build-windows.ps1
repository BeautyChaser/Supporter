param([switch]$DirectoryOnly)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRoot
try {
    node node_modules/electron/install.js
    if ($LASTEXITCODE -ne 0) { throw 'Electron runtime installation failed.' }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $taskRoot 'build-native.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Native helper compilation failed.' }
    python -m pip download --no-deps --only-binary=:all: --dest .build-cache -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency download failed.' }
    python scripts/prepare-runtime.py
    if ($LASTEXITCODE -ne 0) { throw 'Runtime preparation failed.' }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'make-icon.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Application icon build failed.' }
    if ($DirectoryOnly) { npx --no-install electron-builder --config electron-builder.cjs --win --x64 --dir --publish never }
    else { npx --no-install electron-builder --config electron-builder.cjs --win --x64 --publish never }
    if ($LASTEXITCODE -ne 0) { throw 'Windows package build failed.' }
    if (-not $DirectoryOnly) {
        python scripts/checksums.py
        if ($LASTEXITCODE -ne 0) { throw 'Release checksum generation failed.' }
    }
} finally { Pop-Location }
