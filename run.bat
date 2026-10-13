@echo off
title ARIA - AI Voice Assistant Setup
color 0A

echo ========================================
echo    ARIA - AI Voice Assistant Launcher
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo [1/3] Installing core dependencies...
pip install SpeechRecognition pyttsx3 requests pillow --quiet

echo.
echo [2/3] Installing audio backend (sounddevice - compatible with Python 3.14+)...
pip install sounddevice numpy --quiet
if errorlevel 1 (
    echo [WARN] No audio backend installed. Voice input unavailable.
    echo        Text commands will still work fine.
) else (
    echo [OK] sounddevice installed - Voice input is ENABLED!
)

echo.
echo [3/3] Launching ARIA...
echo.
python main.py

pause
