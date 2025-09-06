@echo off
REM Run Auto Video Agent daily from venv
cd /d C:\auto_video_agent

REM Activate venv (Windows)
call venv\Scripts\activate.bat

REM Optional: set environment variables from .env automatically if you want - we assume .env is loaded in Python via python-dotenv
python run_daily.py --count 5 --upload
