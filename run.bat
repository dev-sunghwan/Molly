@echo off
REM Dobby startup script for Windows
REM Run this to start the bot. Keep this window open (or use pythonw for background).

cd /d "%~dp0"

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Start the bot
python bot.py

pause
