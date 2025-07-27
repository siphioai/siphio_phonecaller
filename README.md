# Siphio AI Phone Receptionist System - Segment 1+2: Twilio Integration

## 🚀 Project Overview

An AI-powered phone receptionist system designed for dental practices and small businesses. This system handles incoming calls 24/7, providing natural conversation capabilities with the goal of booking appointments and integrating with business calendars.

### Current Implementation Status (Segment 1+2)

✅ **Completed Features:**
- Full Twilio phone integration with real-time call handling
- WebSocket-based bidirectional audio streaming
- Voice Activity Detection (VAD) with silence detection
- Secure HIPAA-compliant infrastructure with encryption
- Multi-tenant architecture foundation
- Comprehensive error handling and logging
- Production-ready configuration management
- Audio buffering with overflow protection
- Real-time conversation state management
- Redis service stub for future scaling

🎯 **Live Capabilities:**
- Receive incoming calls on UK number: +441615243042
- Play AI greeting: "Thank you for calling. How may I assist you today?"
- Establish WebSocket connection for real-time audio
- Handle up to 50 concurrent calls
- Track conversation intents (dental-specific)
- Maintain call state and history

## 🏗️ Architecture

### System Components

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Twilio Phone   │────▶│  Ngrok Tunnel   │────▶│  FastAPI Server │
│  +441615243042  │     │  (Public URL)   │     │  (Port 8000)    │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │                                               │
        ▼                                               ▼
┌─────────────────┐                         ┌─────────────────┐
│                 │                         │                 │
│  WebSocket      │◀────────────────────────│  Audio Buffer   │
│  Connection     │                         │  with VAD       │
│                 │                         │                 │
└─────────────────┘                         └─────────────────┘
```

### Key Features Implemented

1. **Twilio Integration**
   - Webhook endpoints for incoming calls
   - TwiML response generation
   - WebSocket media streaming
   - Call status tracking

2. **Audio Processing**
   - Real-time audio buffering
   - Voice Activity Detection (VAD)
   - Silence detection with configurable thresholds
   - μ-law audio encoding support

3. **Security & Compliance**
   - Fernet encryption for PHI data
   - Input sanitization and masking
   - JWT authentication preparation
   - HIPAA-compliant logging

4. **Conversation Management**
   - State tracking per call
   - Intent classification (dental-specific)
   - Conversation history
   - Multi-tenant support foundation

## 🚦 Quick Start Guide

### Prerequisites

- Python 3.10+
- Twilio account with phone number
- Ngrok for local tunneling
- Virtual environment set up

### Step 1: Install Dependencies

```bash
cd C:\Users\marley\siphio_phone
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure Environment

1. Copy `.env.example` to `.env`
2. Update the following in `.env`:
   - `TWILIO_AUTH_TOKEN` - Your Twilio auth token
   - `TWILIO_ACCOUNT_SID` - Your Twilio account SID
   - `TWILIO_PHONE_NUMBER` - Your Twilio phone number

### Step 3: Start Ngrok

```bash
# In Terminal 1 - Keep this running!
ngrok http 8000
```

Copy the HTTPS forwarding URL (e.g., `https://abc123.ngrok-free.app`)

### Step 4: Start FastAPI Server

```bash
# In Terminal 2 - Different window!
cd C:\Users\marley\siphio_phone
venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 5: Configure Twilio Webhooks

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to Phone Numbers → Manage → Active Numbers
3. Click on your phone number
4. Set these webhook URLs:
   - **When a call comes in**: `https://YOUR-NGROK-URL.ngrok-free.app/api/webhooks/incoming-call` (POST)
   - **Call status changes**: `https://YOUR-NGROK-URL.ngrok-free.app/api/webhooks/call-status` (POST)
5. Save configuration

### Step 6: Test Your Setup

Call your Twilio number and you should hear: "Thank you for calling. How may I assist you today?"

## 📁 Project Structure

```
siphio_phone/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   ├── core/
│   │   ├── config.py               # Environment configuration
│   │   ├── websocket_manager.py    # WebSocket connection handling
│   │   ├── audio_buffer.py         # Audio buffering with VAD
│   │   ├── conversation_state.py   # Call state management
│   │   ├── latency_tracker.py      # Performance monitoring
│   │   └── security_utils.py       # Encryption and security
│   ├── services/
│   │   ├── twilio_service.py       # Twilio integration (placeholder)
│   │   └── redis_service.py        # Redis caching stub
│   ├── api/
│   │   └── webhooks.py             # Twilio webhook endpoints
│   └── utils/
│       └── __init__.py
├── tests/
│   ├── unit/                       # Comprehensive unit tests
│   ├── integration/                # Integration tests
│   └── load/                       # Load testing
├── docs/
│   ├── SEGMENT1.md                 # Initial architecture
│   └── TWILIO_SETUP_GUIDE.md       # Detailed setup guide
├── requirements.txt                # Python dependencies
├── .env                           # Environment variables (create from .env.example)
├── .env.example                   # Environment template
└── README.md                      # This file
```

## 🧪 Testing

### Run All Tests
```bash
pytest tests/ -v --cov=app --cov-report=html
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Load tests
pytest tests/load/ -v
```

### Test Coverage
Current test coverage: >80% across all modules

## 🛠️ Monitoring

### Server Logs
Watch the FastAPI console for:
- `INFO: Incoming call: CA...` - New call received
- `INFO: WebSocket connection accepted` - Audio stream started
- `INFO: Media stream started: SM...` - Audio flowing

### Health Checks
```bash
# Local health check
curl http://localhost:8000/health

# Webhook health check
curl http://localhost:8000/api/webhooks/health
```

## 🔒 Security Features

- **Encryption**: Fernet encryption for all PHI data
- **Input Sanitization**: All inputs sanitized before processing
- **Secure Logging**: PHI automatically masked in logs
- **HIPAA Compliance**: Built with healthcare compliance in mind
- **Multi-tenant Isolation**: Data isolation between clients

## 🚧 Upcoming Features (Week 2-4)

- [ ] Deepgram STT integration for speech recognition
- [ ] Claude AI for intelligent conversation
- [ ] ElevenLabs TTS for natural voice responses
- [ ] Google Calendar integration for bookings
- [ ] SMS confirmations via Twilio
- [ ] Admin dashboard
- [ ] PostgreSQL database layer
- [ ] Prometheus monitoring
- [ ] Docker containerization

## 🐛 Troubleshooting

### Common Issues

1. **"Number not recognized" error**
   - Ensure Twilio webhooks are configured
   - Verify ngrok is running
   - Check webhook URLs match current ngrok URL

2. **502 Bad Gateway**
   - FastAPI server not running
   - Wrong port in ngrok command
   - Server crashed - check logs

3. **No audio/silent call**
   - WebSocket connection failed
   - Check ngrok URL in .env matches Twilio
   - Restart FastAPI server after .env changes

4. **Ngrok URL changes**
   - Free ngrok generates new URLs on restart
   - Update Twilio webhooks each time
   - Consider ngrok paid plan for persistent URL

## 📊 Performance Metrics

- **Response Time**: Currently <1.5s (greeting only)
- **Concurrent Calls**: Supports up to 50
- **Audio Quality**: μ-law encoding for telephony
- **Uptime Target**: 99.9%

## 🤝 Contributing

This is a private project for Siphio AI. For questions or issues, contact marley@siphio.com

## 📝 License

Proprietary - Siphio AI © 2024. All rights reserved.

---

**Current Version**: v0.1.0 - Segment 1+2 (Twilio Integration)
**Last Updated**: July 2024
**Next Milestone**: Deepgram STT Integration