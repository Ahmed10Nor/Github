@echo off
chcp 65001 >nul
title LuminAgents — Dashboard
cd /d %~dp0

if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Copy your .env file to this folder first.
    pause
    exit /b 1
)

echo [LuminAgents] Starting Streamlit Dashboard...
echo Opening on http://localhost:8501
echo Press Ctrl+C to stop.
echo.
python\python.exe -m streamlit run dashboard/streamlit_app.py --server.port 8501
pause
