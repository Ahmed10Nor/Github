@echo off
chcp 65001 >nul
title LuminAgents — Setup

echo.
echo ============================================
echo   LuminAgents — First-Time Setup
echo ============================================
echo.

:: Check embedded Python exists
if not exist "%~dp0python\python.exe" (
    echo [ERROR] Python runtime not found!
    echo.
    echo Steps:
    echo  1. Download: https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
    echo  2. Create folder: python\  inside this folder
    echo  3. Extract the zip contents into python\
    echo  4. Run setup.bat again
    echo.
    pause
    exit /b 1
)

echo [OK] Python runtime found.
echo.

:: Enable site-packages in embedded Python (uncomment "import site")
echo [1/3] Enabling site-packages...
powershell -Command "(Get-Content '%~dp0python\python311._pth') -replace '#import site','import site' | Set-Content '%~dp0python\python311._pth'"
echo [OK]

:: Install pip if not present
if not exist "%~dp0python\Scripts\pip.exe" (
    echo [2/3] Installing pip...
    if not exist "%~dp0python\get-pip.py" (
        echo [ERROR] get-pip.py not found.
        echo Download it from: https://bootstrap.pypa.io/get-pip.py
        echo Place it inside the python\ folder.
        pause
        exit /b 1
    )
    "%~dp0python\python.exe" "%~dp0python\get-pip.py" --quiet
    echo [OK]
) else (
    echo [2/3] pip already installed. Skipping.
)

:: Install requirements
echo [3/3] Installing packages (this may take 5-10 minutes)...
"%~dp0python\python.exe" -m pip install -r "%~dp0requirements_portable.txt" --quiet
echo [OK]

echo.
echo ============================================
echo   Setup complete!
echo.
echo   Next step: fill in your .env file
echo   Then run: run_api.bat, run_bot.bat, run_dashboard.bat
echo ============================================
echo.
pause
