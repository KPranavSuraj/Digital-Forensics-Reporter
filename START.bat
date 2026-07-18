@echo off
setlocal enabledelayedexpansion
title AUTOPSY SIM
color 0A
cls

echo.
echo  AUTOPSY SIM -- Digital Forensics Bureau
echo  ----------------------------------------
echo.

set "BACKEND=%~dp0backend"
set "SPLASH=%~dp0frontend\loading.html"
set "RUNNER=%TEMP%\autopsy_run.py"

if not exist "%BACKEND%\main.py" (
  echo  ERROR: Cannot find backend\main.py
  pause & exit /b 1
)

if not exist "%BACKEND%\.env" (
  echo GROQ_API_KEY=> "%BACKEND%\.env"
  echo OPENAI_API_KEY=>> "%BACKEND%\.env"
)

:: Force reinstall if version stamp is outdated (fixes Pydantic/FastAPI version conflicts)
set REQUIRED_VERSION=2025.1
if exist "%BACKEND%\.installed" (
  set /p INSTALLED_VERSION=<"%BACKEND%\.installed"
  if not "!INSTALLED_VERSION!"=="%REQUIRED_VERSION%" (
    echo  Version mismatch detected — reinstalling dependencies...
    del "%BACKEND%\.installed"
  )
)
if not exist "%BACKEND%\.installed" (
  echo  Installing dependencies, please wait...
  cd /d "%BACKEND%"
  pip install fastapi==0.115.5 "uvicorn[standard]==0.32.0" pydantic==2.9.2 python-multipart==0.0.12 openai==1.54.0 groq==0.11.0 reportlab==4.2.5 python-dotenv==1.0.1 httpx==0.27.2 cryptography==43.0.3 bcrypt==4.2.0 mysql-connector-python==8.3.0 sqlalchemy==2.0.30 -q --disable-pip-version-check
  if %errorlevel% neq 0 ( echo  ERROR: Install failed. & pause & exit /b 1 )
  echo 2025.1 > "%BACKEND%\.installed"
  echo  Done.
  echo.
)

for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /PID %%a /F >nul 2>&1
timeout /t 1 /nobreak >nul

(
echo import sys, threading, time, webbrowser, uvicorn
echo sys.path.insert^(0, r'%BACKEND%'^)
echo from main import app
echo SPLASH = r'%SPLASH%'
echo def launch^(^):
echo     time.sleep^(0.3^)
echo     webbrowser.open^('file:///' + SPLASH.replace^('\\', '/'^)^)
echo threading.Thread^(target=launch, daemon=True^).start^(^)
echo try:
echo     uvicorn.run^(app, host='0.0.0.0', port=8000^)
echo except ^(KeyboardInterrupt, SystemExit^): pass
echo print^(""^)
echo print^("Server stopped. You can close this window."^)
) > "%RUNNER%"

echo  Starting server...
echo  Keep this window open. Press CTRL+C to stop.
echo.

cd /d "%BACKEND%"
python "%RUNNER%"

echo.
echo  Stopped. Press any key to close.
pause > nul
