@echo off
REM Molly startup script for Windows
REM Run this to start the bot. Keep this window open (or use pythonw for background).

cd /d "%~dp0"

REM Start the bot using the venv Python directly (no activate needed)
.venv\Scripts\python.exe bot.py

pause
