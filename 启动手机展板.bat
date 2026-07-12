@echo off
chcp 65001 >nul
title 手机端数据展板 - Vue3 Dev Server
echo ==========================================
echo   管道探测小车 手机数据展板
echo   启动后手机浏览器访问:
echo.
echo   http://你的电脑IP:5173
echo.
echo   查看本机IP方法: 新开命令行输入 ipconfig
echo ==========================================
echo.
cd /d "%~dp0dashboard"
call npm run dev
pause
