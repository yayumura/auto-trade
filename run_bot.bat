@echo off
setlocal
cd /d "%~dp0"

REM --- SET PATHS ---
set PYTHON_EXE=C:\Users\yayum\AppData\Local\Programs\Python\Python311\python.exe
set LOG_ROOT=data\kabucom_test\logs
set SCHEDULER_LOG=%LOG_ROOT%\task_scheduler.log

REM --- ENVIRONMENT ---
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM --- CREATE LOG DIR IF MISSING ---
if not exist "%LOG_ROOT%" (
    mkdir "%LOG_ROOT%"
)

REM --- RESET LOG IF OVER 5MB ---
if exist "%SCHEDULER_LOG%" (
    for %%I in ("%SCHEDULER_LOG%") do (
        if %%~zI GTR 5242880 (
            echo [%date% %time%] [INFO] Log file exceeded 5MB. Resetting log. > "%SCHEDULER_LOG%"
        )
    )
)

echo [%date% %time%] --- Bot Startup --- >> "%SCHEDULER_LOG%"

REM --- RUN BOT ---
"%PYTHON_EXE%" -u auto_trade.py >> "%SCHEDULER_LOG%" 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] [ERROR] Bot exited with code %errorlevel%. >> "%SCHEDULER_LOG%"
    exit /b %errorlevel%
)

echo [%date% %time%] Bot finished successfully. >> "%SCHEDULER_LOG%"
endlocal
