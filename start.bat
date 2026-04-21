@echo off
title AI PC Suitability Checker
color 0B
cls

echo.
echo  ==============================================
echo   AI PC SUITABILITY CHECKER  - STARTING
echo  ==============================================
echo.

setlocal enabledelayedexpansion

:: ── Detect script folder ──────────────────────────────────────────────────────
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"

:: ── Parse --cli flag ──────────────────────────────────────────────────────────
set "MODE=web"
if /i "%~1"=="--cli" set "MODE=cli"
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-h"     goto :show_help

:: ── Try to find bash (Git Bash / WSL / Cygwin) ───────────────────────────────
set "BASH_EXE="

:: Check PATH first
where bash >nul 2>&1
if not errorlevel 1 (
    for /f "usebackq tokens=*" %%I in (`where bash 2^>nul`) do (
        if not defined BASH_EXE set "BASH_EXE=%%I"
    )
)

:: Git for Windows default locations
if not defined BASH_EXE (
    for %%P in (
        "C:\Program Files\Git\bin\bash.exe"
        "C:\Program Files\Git\usr\bin\bash.exe"
        "C:\Program Files (x86)\Git\bin\bash.exe"
        "%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
        "%ProgramFiles%\Git\bin\bash.exe"
    ) do (
        if not defined BASH_EXE (
            if exist %%P set "BASH_EXE=%%~P"
        )
    )
)

:: WSL bash
if not defined BASH_EXE (
    where wsl >nul 2>&1
    if not errorlevel 1 (
        wsl bash --version >nul 2>&1
        if not errorlevel 1 set "BASH_EXE=WSL"
    )
)

:: ── Run via bash if found ─────────────────────────────────────────────────────
if defined BASH_EXE (
    if "%BASH_EXE%"=="WSL" (
        echo   [INFO]  Using WSL bash to run start.sh
        echo.
        if "%MODE%"=="cli" (
            wsl bash "%HERE%/start.sh" --cli
        ) else (
            wsl bash "%HERE%/start.sh"
        )
        goto :done
    ) else (
        echo   [INFO]  Found bash at: %BASH_EXE%
        echo   [INFO]  Running start.sh via bash
        echo.
        if "%MODE%"=="cli" (
            "%BASH_EXE%" "%HERE%\start.sh" --cli
        ) else (
            "%BASH_EXE%" "%HERE%\start.sh"
        )
        goto :done
    )
)

:: ── No bash found - run Python directly ──────────────────────────────────────
echo   [INFO]  Bash not found. Running Python directly.
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [ERROR] Python not found!
    echo.
    echo   Please install Python 3.10+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo   Or install Git for Windows to get bash:
    echo   https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo   [INFO]  %%V

echo.
if "%MODE%"=="cli" (
    echo   [INFO]  Running CLI checker...
    echo.
    python "%HERE%\ai_pc_checker.py"
) else (
    echo   [INFO]  Starting web dashboard...
    echo   [INFO]  A browser window will open automatically.
    echo   [INFO]  Press Ctrl+C to stop the server.
    echo.
    python "%HERE%\ai_pc_web.py"
)

:done
echo.
echo  ==============================================
echo   Server stopped. Press any key to exit.
echo  ==============================================
echo.
pause >nul
exit /b 0

:show_help
echo.
echo   Usage:
echo     start.bat             Launch web dashboard (browser opens automatically)
echo     start.bat --cli       Run CLI terminal version
echo     start.bat --help      Show this message
echo.
echo   On Windows, this script tries bash in this order:
echo     1. bash in PATH
echo     2. Git for Windows (C:\Program Files\Git\bin\bash.exe)
echo     3. WSL (wsl bash)
echo     4. Python directly (fallback - no bash needed)
echo.
pause >nul
exit /b 0
