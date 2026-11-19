@echo off
rem Opens the two-way ISL conversation window (webcam signing + typed English signed by the avatar).
cd /d "%~dp0"
".venv\Scripts\python.exe" isl_app.py %*
if errorlevel 1 pause
