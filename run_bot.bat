@echo off
cd /d "c:\Users\yayum\git_work\auto-trade"
title KABU-BOT Running...
echo [%date% %time%] 🚀 Trading Bot is Starting...

:: 環境変数等の設定があればここに追加（現在はシステムPythonを使用）
python auto_trade.py

echo.
echo [%date% %time%] 🏁 Bot has finished its task.
:: 予期せぬエラーで終了した場合に、画面が消えないようにする（デバッグ用）
if %errorlevel% neq 0 (
    echo [ERROR] Bot exited with error code %errorlevel%. 
    pause
)
