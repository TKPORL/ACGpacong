@echo off
chcp 65001 >nul
title ACG游戏姬抓取工具
echo.
echo ====================================
echo   ACG游戏姬抓取工具 - 网页版
echo   端口被占用会自动顺延 5001-5019
echo   自定义起始端口: set PORT=8000
echo   启动后会自动打开浏览器
echo ====================================
echo.
cd /d "%~dp0"
python web_app.py
pause
