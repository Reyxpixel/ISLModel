@echo off
rem Opens the ISL chat window (webcam + 3D hands + conversation). Double-click to start.
rem Errors are written to isl_chat_app.log in this folder.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo The .venv folder is missing. See README.md, "Setup on Windows".
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" isl_chat_app.py %*
