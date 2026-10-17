# Start Locflix backend + frontend (assumes deps already installed).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$venvActivate = Join-Path $root "backend\.venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
  Write-Error "Missing backend\.venv - create and install deps first."
}

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "cd `"$root\backend`"; . `"$venvActivate`"; uvicorn app.main:app --host 0.0.0.0 --port 8787"
)

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "cd `"$root\frontend`"; npm run dev"
)

Write-Host "Started Locflix backend (http://0.0.0.0:8787) and frontend (http://localhost:5173)."
Write-Host "LAN sharing: open /lan in the UI. Backend listens on all interfaces for leechers."
