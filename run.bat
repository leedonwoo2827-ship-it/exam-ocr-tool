@echo off
REM Start review web UI at http://127.0.0.1:8010
cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "" http://127.0.0.1:8010
python -m app.cli serve
