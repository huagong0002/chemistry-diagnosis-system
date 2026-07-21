@echo off
chcp 936 >nul
title Chemistry Diagnosis System

echo ============================================
echo   Chemistry Diagnosis System
echo   AI-Powered Chemistry Education
echo ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] Python not found!
    echo.
    echo Please install Python 3.10+
    echo Download: https://www.python.org/downloads/
    echo Remember to check "Add Python to PATH"
    echo.
    pause
    exit
)

echo [OK] Python installed
python --version
echo.

echo [1/3] Checking dependencies...
pip show streamlit >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Dependencies missing!
    echo Please run install script first.
    echo.
    pause
    exit
)
echo [OK] Dependencies ready
echo.

echo [2/3] Checking data directory...
if not exist "data" (
    mkdir data
    echo [OK] Created data directory
) else (
    echo [OK] Data directory exists
)
echo.

echo [3/3] Starting system...
echo ============================================
echo   URL: http://localhost:8501
echo   Close this window to stop.
echo ============================================
echo.

python -m streamlit run app.py --server.headless true

pause
