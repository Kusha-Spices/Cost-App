@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is required. Please install Python 3 from python.org and tick "Add Python to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -c "import streamlit, pandas, openpyxl" >nul 2>nul
if errorlevel 1 (
  python -m pip install -r requirements.txt
)
python run_app.py
pause
