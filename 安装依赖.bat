@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 安装依赖...
pip install sqlcipher3
if %errorlevel% equ 0 (echo 完成!) else (echo 失败，请检查网络)
pause
