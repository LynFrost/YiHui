@echo off
setlocal EnableExtensions
chcp 65001 >nul
title 意绘 V0.72

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8787"
set "URL=http://%HOST%:%PORT%/"
set "PYTHON_CMD="
set "PYTHON_LABEL="
set "LOG_DIR=%~dp0..\logs"
set "LOG_FILE=%LOG_DIR%\YiHui-V0.72.log"

echo.
echo 意绘 V0.72
echo Folder: %CD%
echo URL:    %URL%
echo Log:    %LOG_FILE%
echo.

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul

if not exist "app.py" (
  echo [ERROR] app.py was not found next to this launcher.
  echo Please run this file from the YiHui software folder.
  echo.
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import flask" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    set "PYTHON_LABEL=project .venv"
  )
)

if not defined PYTHON_CMD if exist "C:\ProgramData\anaconda3\python.exe" (
  "C:\ProgramData\anaconda3\python.exe" -c "import flask" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=C:\ProgramData\anaconda3\python.exe"
    set "PYTHON_LABEL=Anaconda"
  )
)

if not defined PYTHON_CMD where python >nul 2>nul
if not errorlevel 1 (
  python -c "import flask" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=python"
    set "PYTHON_LABEL=PATH python"
  )
)

if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.12 -c "import flask" >nul 2>nul
    if not errorlevel 1 (
      set "PYTHON_CMD=py -3.12"
      set "PYTHON_LABEL=Python Launcher 3.12"
    )
  )
)

if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -c "import flask" >nul 2>nul
    if not errorlevel 1 (
      set "PYTHON_CMD=py -3"
      set "PYTHON_LABEL=Python Launcher default 3.x"
    )
  )
)

if not defined PYTHON_CMD (
  echo [ERROR] Could not find Python with Flask installed.
  echo Tried: .venv, C:\ProgramData\anaconda3, python, py -3.12, py -3
  echo.
  echo From this folder, install requirements into a Python you use with:
  echo   C:\ProgramData\anaconda3\python.exe -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo Python: %PYTHON_LABEL%
%PYTHON_CMD% --version

powershell -NoProfile -ExecutionPolicy Bypass -Command "$conn = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if (-not $conn) { exit 1 }; $proc = Get-CimInstance Win32_Process -Filter \"ProcessId=$($conn.OwningProcess)\"; Write-Host '[WARN] Port %PORT% is already in use.'; Write-Host ('PID:     ' + $conn.OwningProcess); Write-Host ('Process: ' + $proc.Name); Write-Host ('Command: ' + $proc.CommandLine); exit 0"
if not errorlevel 1 (
  echo.
  echo Detected an existing local server on port %PORT%.
  echo To make this window control the service, close the old service and restart it here.
  echo.
  choice /C YN /N /M "Close the old service and restart V0.72 in this CMD? [Y/N] "
  if errorlevel 2 (
    echo.
    echo Keeping the existing service. Opening %URL%
    start "" "%URL%"
    echo.
    echo This window did not start the running service, so closing it will not free port %PORT%.
    echo.
    pause
    exit /b 0
  )

  echo.
  echo Stopping existing service on port %PORT%...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$conn = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if (-not $conn) { exit 0 }; Stop-Process -Id $conn.OwningProcess -Force; $deadline = (Get-Date).AddSeconds(10); do { Start-Sleep -Milliseconds 250; $after = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 } while ($after -and (Get-Date) -lt $deadline); if ($after) { Write-Host '[ERROR] Port %PORT% is still in use.'; exit 1 }; Write-Host 'Port %PORT% released.'"
  if errorlevel 1 (
    echo.
    echo [ERROR] Could not release port %PORT%.
    echo Please close the old service manually and run this launcher again.
    echo.
    pause
    exit /b 1
  )
)

echo.
echo Starting local server...
echo Leave this window open while using the app.
echo Close this window or press Ctrl+C to stop the server.
echo Log file: %LOG_FILE%
echo.

start "YiHui Browser Opener" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Milliseconds 900; Start-Process '%URL%'"
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $ErrorActionPreference = 'Continue'; '[START] ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' 意绘 V0.72' | Tee-Object -FilePath '%LOG_FILE%' -Append; & %PYTHON_CMD% app.py --host %HOST% --port %PORT% 2>&1 | Tee-Object -FilePath '%LOG_FILE%' -Append; exit $LASTEXITCODE }"
set "EXITCODE=%ERRORLEVEL%"

echo.
echo Server stopped. Exit code: %EXITCODE%
if not "%EXITCODE%"=="0" (
  echo.
  echo If the server stopped unexpectedly, check the log file:
  echo %LOG_FILE%
)
echo.
pause
exit /b %EXITCODE%




