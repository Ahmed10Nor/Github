@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Starting LuminAgents...

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH. Install Python 3.11 and add to PATH.
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo Setup: Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv.
        pause
        exit /b 1
    )
    call venv\Scripts\activate.bat
    echo Setup: Installing requirements...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: pip install failed.
        pause
        exit /b 1
    )
) else (
    call venv\Scripts\activate.bat
)

python fix_db.py >nul 2>&1

start "API" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate.bat && uvicorn api.main:app --reload"
timeout /t 3 /nobreak >nul
start "Bot" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate.bat && python -B telegram_bot.py"
start "Dashboard" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate.bat && streamlit run dashboard\streamlit_app.py"

echo Done. Check the opened windows.
timeout /t 4 /nobreak >nul
exit
