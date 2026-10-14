# Start Locflix backend + frontend for local development.
$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList @(
  '-NoExit',
  '-Command',
  "cd `"$root\backend`"; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8787"
)

Start-Process powershell -ArgumentList @(
  '-NoExit',
  '-Command',
  "cd `"$root\frontend`"; npm run dev"
)

Write-Host "Started Locflix backend (8787) and frontend (5173)."
