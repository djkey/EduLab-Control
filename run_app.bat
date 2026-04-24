@echo off
setlocal

REM Check python availability
where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Please install Python 3.10+ and try again.
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

endlocal
