@echo off
echo Starting Ngrok for Siphio Phone System
echo =====================================
echo.

if not exist ngrok.exe (
    echo ERROR: ngrok.exe not found!
    pause
    exit /b 1
)

echo Starting ngrok tunnel on port 8000...
echo.
echo IMPORTANT: Once ngrok starts:
echo 1. Look for the line that says "Forwarding"
echo 2. Copy the HTTPS URL (e.g., https://abc123.ngrok-free.app)
echo 3. Keep this window open!
echo 4. Open a NEW terminal to continue setup
echo.
echo Starting in 3 seconds...
timeout /t 3 /nobreak >nul

ngrok.exe http 8000