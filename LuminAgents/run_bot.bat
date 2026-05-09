@echo off
chcp 65001 >nul
title LuminAgents — Telegram Bot
cd /d %~dp0

if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Copy your .env file to this folder first.
    pause
    exit /b 1
)

echo [LuminAgents] Starting Telegram Bot...
echo Press Ctrl+C to stop.
echo.
python\python.exe telegram_bot.py
pause
