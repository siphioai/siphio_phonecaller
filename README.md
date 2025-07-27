# Siphio AI Phone Receptionist

An AI-powered phone receptionist system designed for dental practices and small businesses. Handles incoming calls 24/7, conducts natural conversations, books appointments, and integrates with Google Calendar.

## Features

- 🤖 AI-powered natural conversations using Claude
- 📞 Real-time phone call handling via Twilio
- 🎤 Speech-to-text with Deepgram
- 🔊 Natural text-to-speech with ElevenLabs
- 📅 Google Calendar integration for appointments
- 🔒 HIPAA-compliant with encryption for PHI data
- 🏢 Multi-tenant architecture
- ⚡ Low latency (<1.5s response time)
- 📊 Prometheus metrics and monitoring

## Tech Stack

- **Backend**: Python 3.10+, FastAPI
- **Real-time**: WebSockets, Redis Pub/Sub
- **Database**: PostgreSQL with encryption
- **Cache**: Redis
- **AI/ML**: Claude 3 Haiku, Deepgram Nova-2, ElevenLabs Turbo
- **Telephony**: Twilio
- **Monitoring**: Prometheus, Grafana

## Quick Start

### Prerequisites

- Python 3.10 or higher
- PostgreSQL 14+
- Redis 6+
- Twilio account (with HIPAA BAA)
- API keys for: Deepgram, Anthropic Claude, ElevenLabs, Google Cloud

### Installation

1. Clone the repository:
```bash
git clone https://github.com/siphioai/siphio-phone.git
cd siphio-phone
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

5. Run the application:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### Local Testing with Twilio

For testing Twilio webhooks locally:

1. Install ngrok: https://ngrok.com/download
2. Run ngrok: `ngrok http 8000`
3. Update your Twilio phone number webhook to the ngrok URL

## Configuration

Key environment variables (see `.env.example` for full list):

- `ENVIRONMENT`: development/staging/production
- `SECRET_KEY`: Application secret key
- `ENCRYPTION_KEY`: Key for encrypting PHI data
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `TWILIO_ACCOUNT_SID`: Your Twilio account SID
- `DEEPGRAM_API_KEY`: Deepgram API key
- `ANTHROPIC_API_KEY`: Claude API key
- `ELEVENLABS_API_KEY`: ElevenLabs API key

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (development only)
- `POST /api/webhooks/incoming-call` - Twilio webhook for incoming calls
- `WebSocket /media-stream/{stream_id}` - Real-time audio streaming

## Security & Compliance

This system is designed with HIPAA compliance in mind:

- All PHI data is encrypted at rest using Fernet encryption
- TLS/HTTPS enforced for all connections
- Row-level security in PostgreSQL for multi-tenancy
- Audit logging for all sensitive operations
- Automatic PII/PHI masking in logs

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
black app/

# Lint
flake8 app/

# Type checking
mypy app/
```

## Deployment

See `docs/DEPLOYMENT.md` for detailed deployment instructions.

## License

Proprietary - All rights reserved by Siphio AI

## Support

For support, email support@siphio.com