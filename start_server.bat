@echo off
chcp 65001 >nul
title AI Novel Studio
cd /d "%~dp0"

echo ========================================================
echo    AI 小说工作室 (AI Novel Studio)
echo ========================================================
echo.
echo 正在启动本地服务...
echo 网页地址: http://127.0.0.1:7860/
echo.
echo 提示:
echo 1. 稍后会自动在浏览器中打开主页。
echo 2. 使用期间请保持此窗口开启；关闭此窗口即可停止服务。
echo ========================================================
echo.

:: 延迟 3 秒待服务器初始化完成后自动弹出浏览器
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:7860/"

python api_server.py

pause
