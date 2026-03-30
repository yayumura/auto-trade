@echo off
cd /d "c:\Users\yayum\git_work\auto-trade"
title KABU-BOT Running...
echo [%date% %time%] Trading Bot is Starting...

REM Environment variable setup (using system Python for now)
python auto_trade.py

echo.
echo [%date% %time%] Bot has finished its task.

REM Prevent window from closing on unexpected error (for debugging)
if %errorlevel% neq 0 (
    echo [ERROR] Bot exited with error code %errorlevel%. 
    pause
)
