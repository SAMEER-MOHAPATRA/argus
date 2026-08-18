@echo off
rem refresh.bat — fetch fresh RSS jobs, then serve the dashboard (Ctrl+C to stop)
cd /d "%~dp0"
rem use the project venv, not whatever python is on PATH
".venv\Scripts\python.exe" discover.py --days 3
".venv\Scripts\python.exe" dashboard.py
