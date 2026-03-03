@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [QQ Bot] 依赖安装失败，请检查网络或 Python 环境
    pause
    exit /b 1
)
echo [QQ Bot] 启动中，监听 127.0.0.1:8080 ...
python bot.py
pause
