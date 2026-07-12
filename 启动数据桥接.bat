@echo off
title Bridge Program
echo ==========================================
echo   PipeCar Data Bridge
echo   TCP -> MQTT + SQLite + RTSP
echo ==========================================
echo.
echo   [1] Simulate Mode (dev/test)
echo   [2] Real Mode (connect to car)
echo.
set /p mode="Select (1/2): "

cd /d "%~dp0bridge"

if "%mode%"=="1" (
    echo *** Simulate Mode ***
    set SIMULATE=1
    python main.py
) else if "%mode%"=="2" (
    echo *** Real Mode ***
    python main.py
) else (
    echo Invalid, using simulate mode
    set SIMULATE=1
    python main.py
)
pause
