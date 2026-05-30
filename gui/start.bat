@echo off
title Couch Petato — Product Manager
echo.
echo  Starting Couch Petato Product Manager...
echo.

cd /d "%~dp0"

:: Install dependencies if needed
pip install flask werkzeug requests -q

:: Launch the app and open browser
start http://localhost:5001
python app.py

pause
