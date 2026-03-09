@echo off
cd /d "%~dp0"
echo ============================================
echo  AI News Agent - One-time Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Create virtual environment
echo [1/3] Creating virtual environment...
python -m venv venv
if errorlevel 1 ( echo FAILED & pause & exit /b 1 )

:: Install dependencies
echo [2/3] Installing dependencies...
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
if errorlevel 1 ( echo FAILED & pause & exit /b 1 )

:: Register scheduled task
echo [3/3] Registering Windows Task Scheduler job...
echo       (You may see a UAC prompt - click Yes)
powershell -ExecutionPolicy Bypass -File "%~dp0setup_scheduler.ps1"

echo.
echo ============================================
echo  Setup complete!
echo  - Run manually any time: run_agent.bat
echo  - Reports saved to:      reports\
echo ============================================
pause
