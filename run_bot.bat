@echo off
setlocal
cd /d "c:\Users\yayum\git_work\auto-trade"

REM Set paths
set PYTHON_EXE=C:\Users\yayum\AppData\Local\Programs\Python\Python311\python.exe
set SCHEDULER_LOG=data\kabucom_test\logs\task_scheduler.log
set LOG_ROOT=data\kabucom_test\logs

REM Force UTF-8 for everything (to avoid UnicodeDecodeError on Windows)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
REM --- フォルダがなければ作成 (重要: これがないと起動前にエラー落ちする) ---
if not exist "%LOG_ROOT%" mkdir "%LOG_ROOT%"

REM --- ログ肥大化対策: 5MBを超えていたらリセット ---
if exist "%SCHEDULER_LOG%" (
    for %%I in ("%SCHEDULER_LOG%") do (
        if %%~zI GTR 5242880 (
            echo [%date% %time%] [INFO] Log file exceeded 5MB. Resetting log. > "%SCHEDULER_LOG%"
        )
    )
)

echo [%date% %time%] --- Bot Startup --- >> "%SCHEDULER_LOG%"

REM Run the bot and redirect output to the scheduler log
"%PYTHON_EXE%" -u auto_trade.py >> "%SCHEDULER_LOG%" 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] [ERROR] Bot exited with error code %errorlevel%. >> "%SCHEDULER_LOG%"
    exit /b %errorlevel%
)

echo [%date% %time%] Bot finished successfully. >> "%SCHEDULER_LOG%"
endlocal
