@echo off
title AYURCASE Backend Server (Port 5000)
cd /d "%~dp0"

echo ===================================================================
echo                     AYURCASE BACKEND SERVER
echo ===================================================================
echo.
echo Starting Flask backend connected to SQLite database...
echo.

if exist ".\venv\Scripts\python.exe" (
    echo [INFO] Using virtual environment: .\venv\Scripts\python.exe
    echo [INFO] Backend URL: http://127.0.0.1:5000
    echo [INFO] Database: backend\ayurcase.db
    echo.
    echo ===================================================================
    echo Keep this window OPEN while browsing the website!
    echo To stop the server, press Ctrl + C or close this window.
    echo ===================================================================
    echo.
    .\venv\Scripts\python.exe backend\app.py
) else (
    echo [INFO] Using system Python...
    echo [INFO] Backend URL: http://127.0.0.1:5000
    echo.
    echo ===================================================================
    echo Keep this window OPEN while browsing the website!
    echo To stop the server, press Ctrl + C or close this window.
    echo ===================================================================
    echo.
    python backend\app.py
)

pause
