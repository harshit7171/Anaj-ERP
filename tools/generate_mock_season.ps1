# Generate 520+ posted documents for GST / load testing (wheat/paddy season mix).
param(
    [Parameter(Mandatory = $true)]
    [string]$DataDir,
    [int]$Count = 520,
    [string]$CompanyName = "Mock Season Co"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location (Join-Path $root "backend")
try {
    py -m anaj_erp.mock_crop_season --data-dir $DataDir --count $Count --company-name $CompanyName
}
finally {
    Pop-Location
}
