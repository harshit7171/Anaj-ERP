# Rerun Anaj ERP dev mode (Vite + desktop). Usage:
#   .\tools\rerun_dev.ps1           — start Vite if needed, open desktop window
#   .\tools\rerun_dev.ps1 -Agent    — same, for Cursor/automation (minimal output, exits)

param(
    [switch]$Agent,
    [string]$Root = "C:\Accblue_Software",
    [string]$DevUrl = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"
Set-Location $Root

function Test-DevServer {
    try {
        $response = Invoke-WebRequest -Uri $DevUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Start-ViteIfNeeded {
    if (Test-DevServer) {
        Write-Output "Vite: already running at $DevUrl"
        return
    }
    if (-not (Test-Path "$Root\node_modules")) {
        throw "node_modules missing. Run: npm install"
    }
    Write-Output "Vite: starting npm run dev..."
    Start-Process -WorkingDirectory $Root -WindowStyle Minimized `
        -FilePath "npm" -ArgumentList "run", "dev"
    $deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Seconds 2
        if (Test-DevServer) {
            Write-Output "Vite: ready at $DevUrl"
            return
        }
    } while ((Get-Date) -lt $deadline)
    throw "Vite did not become ready on port 5173 within 60s"
}

function Start-DesktopApp {
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw ".venv missing. Run one-time setup in docs/dev-run-reference.md"
    }
    $desktopCmd = @"
Set-Location '$Root'
`$env:ANAJ_ERP_DEV_URL = '$DevUrl'
& '$python' -m anaj_erp.main
"@
    if ($Agent) {
        Start-Process -WorkingDirectory $Root -WindowStyle Normal `
            -FilePath "powershell.exe" `
            -ArgumentList "-NoProfile", "-Command", $desktopCmd
        Write-Output "Desktop: started (ANAJ_ERP_DEV_URL=$DevUrl)"
    } else {
        Write-Output "Desktop: launching..."
        Invoke-Expression $desktopCmd
    }
}

Start-ViteIfNeeded
Start-DesktopApp
Write-Output "Done."
