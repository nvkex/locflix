@echo off
setlocal
REM Start Locflix backend + frontend (assumes deps already installed).

set "ROOT=%~dp0.."
if not exist "%ROOT%\backend\.venv\Scripts\activate.bat" (
  echo Missing backend\.venv - create and install deps first.
  exit /b 1
)

start "Locflix Backend" /D "%ROOT%\backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port 8787"
start "Locflix Frontend" /D "%ROOT%\frontend" cmd /k "npm run dev"

echo Started Locflix backend (http://0.0.0.0:8787) and frontend (http://localhost:5173).
echo LAN sharing: open /lan in the UI.
endlocal
