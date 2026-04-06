@echo off
setlocal
cd /d "%~dp0"

REM --- SET PYTHON PATH (USER CONTEXT) ---
set PYTHON_EXE=C:\Users\yayum\AppData\Local\Programs\Python\Python311\python.exe
set LOG_FILE=data\kabucom_test\logs\imperial_cycle.log

REM --- ENSURE LOG DIR ---
if not exist "data\kabucom_test\logs" (
    mkdir "data\kabucom_test\logs"
)

REM --- STARTUP LOG ---
echo [%date% %time%] [INFO] [IMPERIAL_ORACLE_STARTUP] >> "%LOG_FILE%"

REM --- CALL THE ORCHESTRATOR ---
REM -u flag ensures unbuffered output for real-time logging
"%PYTHON_EXE%" -u run_daily_cycle.py >> "%LOG_FILE%" 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] [ERROR] Imperial Cycle failed with code %errorlevel%. >> "%LOG_FILE%"
    exit /b %errorlevel%
)

echo [%date% %time%] [INFO] [IMPERIAL_ORACLE_COMPLETED] >> "%LOG_FILE%"
endlocal
