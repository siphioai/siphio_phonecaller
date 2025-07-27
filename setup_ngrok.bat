@echo off
echo Setting up Ngrok for Siphio Phone System
echo ========================================
echo.
echo Step 1: Download ngrok from https://ngrok.com/download
echo Step 2: Extract ngrok.exe to this directory
echo Step 3: Run this script again
echo.

if not exist ngrok.exe (
    echo ERROR: ngrok.exe not found in current directory!
    echo Please download ngrok and place ngrok.exe here.
    pause
    exit /b 1
)

echo Starting ngrok tunnel on port 8000...
echo.
echo Once ngrok starts, copy the HTTPS URL (e.g., https://abc123.ngrok.io)
echo and update your .env file with it.
echo.
echo Press Ctrl+C to stop ngrok when done.
echo.

ngrok http 8000
