# Anaj ERP release pipeline (Point 5) — PyInstaller + optional sign + Inno Setup.
# Electron/Bytenode path documented in docs/release-build-pipeline.md for teams migrating shell.

param(
    [string]$Version = "0.1.0",
    [switch]$SkipSign,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== Frontend production build =="
if ($env:ANAJ_BUILD_OBFUSCATE -eq "1") {
    Write-Host "Obfuscation flag set (vite release profile)."
}
npm run build

Write-Host "== PyInstaller one-dir =="
& .\.venv\Scripts\python.exe -m PyInstaller AnajERP.spec --noconfirm

if (-not $SkipSign) {
    $SignScript = Join-Path $PSScriptRoot "sign_release.ps1"
    if (Test-Path $SignScript) {
        & $SignScript -Target (Join-Path $Root "dist\AnajERP\AnajERP.exe")
    } else {
        Write-Warning "sign_release.ps1 missing — skip code signing (SmartScreen may warn)."
    }
}

if (-not $SkipInstaller) {
    $Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $Iscc)) {
        Write-Warning "Inno Setup not found — open installer\AnajERP.iss manually."
    } else {
        & $Iscc (Join-Path $Root "installer\AnajERP.iss")
    }
}

Write-Host "Release artifacts: dist\AnajERP, installer\output\"
