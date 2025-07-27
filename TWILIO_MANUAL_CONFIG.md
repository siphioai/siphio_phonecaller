# TWILIO MANUAL CONFIGURATION - URGENT FIX

## Why your calls aren't working:
Your Twilio number (+441615243042) has NO webhook URL configured. When someone calls, Twilio doesn't know where to send the call data.

## QUICK FIX - Do this NOW:

### Step 1: Open Twilio Console
Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming

### Step 2: Find Your Number
Look for: +441615243042

### Step 3: Configure Webhooks
Click on the number and scroll to "Voice Configuration"

Set these EXACT values:

**A CALL COMES IN:**
- Configure with: `Webhook`
- URL: `https://79c9e80e881e.ngrok-free.app/api/webhooks/incoming-call`
- HTTP Method: `POST`

**CALL STATUS UPDATES:**
- URL: `https://79c9e80e881e.ngrok-free.app/api/webhooks/call-status`
- HTTP Method: `POST`

### Step 4: Save Configuration
Click the "Save configuration" button at the bottom.

## TEST IMMEDIATELY:
1. Make sure your server is running:
   ```
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. Make sure ngrok is running and showing:
   ```
   Forwarding  https://79c9e80e881e.ngrok-free.app -> http://localhost:8000
   ```

3. Call +441615243042

You should now hear: "Thank you for calling. How may I assist you today?"

## Still need to update .env:
Don't forget to update your TWILIO_AUTH_TOKEN in the .env file for the automated script to work next time!

## Verification:
In your server console, you should see:
- "Incoming call: CA..." when you call
- "WebSocket connection accepted" when audio starts