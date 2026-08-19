@echo off
title HIDInput
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python is not on PATH.
  echo Install Python 3.11+ from https://www.python.org/downloads/
  echo Tick "Add python.exe to PATH", then run this file again.
  echo.
  pause
  exit /b 1
)

python -c "import vgamepad" 2>nul
if errorlevel 1 (
  echo Installing vgamepad (needs ViGEmBus for games to see a pad)...
  python -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 (
    echo.
    echo pip install failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
)

echo.
echo Starting HIDInput — keep this window open.
echo Dashboard: http://127.0.0.1:8765/
echo Games need ViGEmBus: https://github.com/nefarius/ViGEmBus/releases/latest
echo.
python "%~dp0run.py"
if errorlevel 1 pause
