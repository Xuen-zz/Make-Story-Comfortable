@echo off
chcp 65001 >nul
title NovelWriter 小说创作工作台
cd /d "%~dp0"

echo ================================================
echo   NovelWriter - 智能小说创作平台
echo ================================================
echo.
echo 正在启动服务...
echo 访问地址: http://127.0.0.1:7860
echo.

python api_server.py
pause
