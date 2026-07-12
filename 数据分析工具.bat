@echo off
title Data Analysis Tool
echo ==========================================
echo   PipeCar Data Analysis Tool
echo ==========================================
echo.
echo   [1] Analysis Report
echo   [2] Export CSV
echo   [3] Export CSV + Excel + HTML
echo   [4] Run All
echo   [0] Exit
echo.
set /p choice="Select (0-4): "

cd /d "%~dp0analysis"

if "%choice%"=="1" (
    python analyze.py
)
if "%choice%"=="2" (
    python export_csv.py
)
if "%choice%"=="3" (
    python report_generator.py
)
if "%choice%"=="4" (
    echo [1/3] Analysis...
    python analyze.py
    echo [2/3] CSV...
    python export_csv.py
    echo [3/3] HTML report...
    python report_generator.py
)

echo.
echo Done. Output in: database\exports\
pause
