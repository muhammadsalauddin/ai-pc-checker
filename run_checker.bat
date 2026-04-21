@echo off
title AI PC Suitability Checker v2.0
color 0B
cls

echo.
echo  ============================================
echo    AI PC SUITABILITY CHECKER v2.0
echo    Checking your system for Local AI...
echo  ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo.
    echo  Please install Python 3.10+ from:
    echo  https://www.python.org/downloads/
    echo.
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo  Python found. Starting AI PC Web Dashboard...
echo.
echo  The dashboard will open in your browser automatically.
echo  Press Ctrl+C in this window to stop the server.
echo.

:: Run the web version (auto-opens browser)
python "%~dp0ai_pc_web.py"

echo.
echo  ============================================
echo    Server stopped. Press any key to exit.
echo  ============================================
pause >nul
