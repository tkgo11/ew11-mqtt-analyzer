@echo off
rem EW11 MQTT packet analyzer launcher (Windows)
rem Usage:
rem   run.bat --demo                                       demo mode (no wallpad needed)
rem   run.bat --host 192.168.x.x                           connect to a real MQTT broker
rem   run.bat --host 192.168.x.x --port 1883 --topic "ew11/#"
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto :have_venv
echo venv not found. Creating it...
where py >nul 2>nul
if errorlevel 1 (
  python -m venv .venv
) else (
  py -3 -m venv .venv
)
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
if errorlevel 1 exit /b 1

:have_venv
if exist "frontend\dist\index.html" goto :have_frontend
echo frontend build not found. Building it...
pushd frontend
call npm ci && call npm run build
set "rc=%errorlevel%"
popd
if not "%rc%"=="0" exit /b %rc%

:have_frontend
".venv\Scripts\python.exe" -m ew11_analyzer %*
