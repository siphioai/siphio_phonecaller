# 🚨 URGENT: Twilio Setup Guide for Siphio Phone System

## ⚠️ IMMEDIATE SECURITY ACTION REQUIRED

**YOUR TWILIO AUTH TOKEN HAS BEEN EXPOSED!** Follow these steps immediately:

1. **Go to Twilio Console NOW**: https://console.twilio.com
2. Navigate to your Account Settings
3. Find your Auth Token and click "View" then "Generate New Token"
4. Copy the new token and keep it secure
5. Update your `.env` file with the new token

## 📋 Your Current Configuration

- **Account SID**: [YOUR_ACCOUNT_SID]
- **Phone Number**: +441615243042 (UK)
- **Auth Token**: [NEEDS TO BE REGENERATED]

## 🚀 Quick Start Guide

### Step 1: Install and Start Ngrok

1. **Download ngrok**: https://ngrok.com/download
2. Extract `ngrok.exe` to your project directory
3. Open a terminal and run:
   ```bash
   ngrok http 8000
   ```
4. You'll see output like:
   ```
   Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
   ```
5. **Copy the HTTPS URL** (e.g., `https://abc123.ngrok-free.app`)

### Step 2: Update Your Configuration

1. **Update your Auth Token** in `.env`:
   ```bash
   TWILIO_AUTH_TOKEN="your-new-auth-token-here"
   ```

2. **Run the configuration script**:
   ```bash
   python update_twilio_config.py https://your-ngrok-url.ngrok-free.app
   ```

   This will automatically:
   - Update your Twilio phone number webhooks
   - Update your `.env` file with the correct URLs

### Step 3: Start the Server

1. **Activate your virtual environment**:
   ```bash
   venv\Scripts\activate
   ```

2. **Start the server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Step 4: Test Your Setup

1. **Run the test script**:
   ```bash
   python test_twilio_integration.py
   ```

2. **Make a test call**:
   - Call your Twilio number: **+441615243042**
   - You should hear: "Thank you for calling. How may I assist you today?"

## 📱 What Happens When Someone Calls

1. **Call arrives** at +441615243042
2. **Twilio sends webhook** to your ngrok URL
3. **Server responds** with TwiML instructions
4. **WebSocket opens** for real-time audio
5. **Audio streams** between caller and your server

## 🔍 Monitoring Your Calls

### Server Logs to Watch For:
```
INFO: Incoming call: CA123... from +44... to +441615243042
INFO: WebSocket connection accepted for stream CA123_abc123
INFO: Media stream started: SM123...
```

### Check System Health:
```bash
# Local health check
curl http://localhost:8000/health

# Webhook health check
curl http://localhost:8000/api/webhooks/health
```

## 🐛 Troubleshooting

### Issue: "Invalid request signature"
- We've temporarily disabled validation in `.env`
- Once working, re-enable with `TWILIO_VALIDATE_REQUESTS=True`

### Issue: No audio/silent call
- Check that ngrok is still running
- Verify WebSocket connection in logs
- Ensure server is running on port 8000

### Issue: Ngrok session expired
- Free ngrok sessions expire after ~2 hours
- Just restart ngrok and update webhooks again

## 🔒 Security Reminders

1. **Never share your Auth Token**
2. **Regenerate tokens if exposed**
3. **Use environment variables** for all secrets
4. **Enable webhook validation** in production

## 📞 UK-Specific Configuration

Your number (+441615243042) is a UK Manchester number. The system is configured for:
- UK time zones
- UK phone number formatting
- British English voice (can be customized)

## 🚀 Next Steps After Testing

1. **Implement Deepgram** for speech-to-text
2. **Connect Claude AI** for conversations
3. **Add ElevenLabs** for natural voice responses
4. **Deploy to production** server (AWS/GCP/Azure)

## 💡 Quick Commands Reference

```bash
# Start ngrok
ngrok http 8000

# Update Twilio webhooks
python update_twilio_config.py https://YOUR-NGROK-URL.ngrok-free.app

# Start server
uvicorn app.main:app --reload

# Test setup
python test_twilio_integration.py

# Make a test call
Call: +441615243042
```

---

**Remember**: After testing with ngrok, we'll help you deploy to a permanent server for production use.
