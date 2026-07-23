@echo off
REM First-time setup: create venv and install dependencies
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo [DONE] Setup complete. Now run: run.bat
pause
