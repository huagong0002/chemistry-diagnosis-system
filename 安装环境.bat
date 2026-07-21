@echo off
chcp 936 >nul
title Chemistry Diagnosis System - Install

echo ============================================
echo   Chemistry Diagnosis System - Install
echo ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] Python not found!
    echo.
    echo Please install Python 3.10+ first.
    echo Download: https://www.python.org/downloads/
    echo Remember to check "Add Python to PATH"
    echo.
    pause
    exit
)

echo [OK] Python installed
python --version
echo.

echo [1/3] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo.

echo [2/3] Installing dependencies...
pip install -r requirements.txt --quiet
echo.

echo [3/3] Verifying...
pip show streamlit >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Installation complete!
) else (
    echo [Error] Installation failed!
    echo Try manually: pip install -r requirements.txt
    echo.
    pause
    exit
)

echo.
echo ============================================
echo   Done! Run start.bat to launch system.
echo ============================================
echo.
pause
