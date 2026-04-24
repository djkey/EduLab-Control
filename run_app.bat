@echo off
setlocal

REM Check python availability
where python >nul 2>&1
if errorlevel 1 (
  echo Python not found.
  echo Opening Microsoft Store search for Python 3.13...
  start "" "ms-windows-store://search/?query=Python%203.13"
  echo Please install Python from the Store, then re-run this file.
  pause
  exit /b 1
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

if errorlevel 1 (
  echo.
  echo The app exited with an error. Check messages above.
  pause
)

endlocal

REM --- Refresh PATH in current session (best-effort) ---
:RefreshPath
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','User')"`) do set "USERPATH=%%i"
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')"`) do set "MACHINEPATH=%%i"
set "PATH=%USERPATH%;%MACHINEPATH%"
goto :eof
