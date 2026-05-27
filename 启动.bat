@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo QQ 聊天记录视角互换工具 v3.1
echo.
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请安装 Python 3.10+
    pause & exit /b 1
)
python -c "import sqlcipher3" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] sqlcipher3 未安装，正在尝试安装...
    pip install sqlcipher3
)
python gui.py
pause
