@echo off
setlocal

REM Check python availability
where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Trying to install Python 3.13 (per-user, no admin)...
  set "PY_INSTALLER=%TEMP%\python-3.13.0-amd64.exe"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe -OutFile '%PY_INSTALLER%'"
  if errorlevel 1 (
    echo Failed to download Python installer.
    echo You can install Python from Microsoft Store or python.org manually.
    pause
    exit /b 1
  )
  "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
  if errorlevel 1 (
    echo Python install failed. Please install manually.
    pause
    exit /b 1
  )
  REM Refresh PATH for current session
  call :RefreshPath
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python still not found after install. Please restart and try again.
    pause
    exit /b 1
  )
)

REM Move to script directory
cd /d "%~dp0"

REM Create venv if missing
if not exist ".venv\Scripts\activate.bat" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

REM Activate venv
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo Failed to activate virtual environment.
  pause
  exit /b 1
)

REM Install dependencies if needed
if exist "requirements.txt" (
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
)

REM Run app
python main.py

endlocal

REM --- Refresh PATH in current session (best-effort) ---
:RefreshPath
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','User')"`) do set "USERPATH=%%i"
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')"`) do set "MACHINEPATH=%%i"
set "PATH=%USERPATH%;%MACHINEPATH%"
goto :eof
