@echo off
echo Starting Siphio Phone System Server
echo ==================================
echo.

cd /d "C:\Users\marley\siphio_phone"

echo Activating virtual environment...
call venv\Scripts\activate

echo.
echo Starting FastAPI server on port 8000...
echo.
echo Server logs will appear below:
echo ==============================
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000