# Sign Windows binaries with a code signing certificate (Point 5).
param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [string]$Description = "Anaj Accounting ERP",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Target)) {
    throw "Target not found: $Target"
}

$Thumbprint = $env:ANAJ_CODE_SIGN_THUMBPRINT
if (-not $Thumbprint) {
    Write-Warning "Set ANAJ_CODE_SIGN_THUMBPRINT to your Authenticode cert SHA1 thumbprint."
    exit 0
}

Write-Host "Signing $Target"
& signtool.exe sign /fd SHA256 /tr $TimestampUrl /td SHA256 /sha1 $Thumbprint /d $Description $Target
& signtool.exe verify /pa $Target
