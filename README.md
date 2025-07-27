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
git clone https://github.com/siphioai/ai-phone-system.git
cd ai-phone-system
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

## Troubleshooting

### Common Issues

#### Invalid Encryption Key Error
If you see "Invalid encryption key" errors:

1. **Generate a valid Fernet key**:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

2. **Add to your .env file**:
```
ENCRYPTION_KEY=<generated-key-here>
```

**Note**: Fernet keys must be exactly 44 characters of base64-encoded data. The example key in `.env.example` is for reference only - **never use it in production**. Always generate your own unique key.

#### Development Mode Encryption Keys
In development mode:
- A temporary key is auto-generated if not provided
- The key is cached in `.env.dev-key` for persistence across restarts
- You'll see a warning about the temporary key
- The cached key ensures encrypt/decrypt works across application restarts

#### Module Import Errors
If you see "ModuleNotFoundError":

1. **Ensure virtual environment is activated**:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

#### Email Validation Issues
- The system uses `email-validator` for robust email validation
- International domains (IDN) are supported (e.g., user@café.com)
- Invalid emails are fully masked for privacy
- Check logs for validation warnings with partial hints

#### Development vs Production Settings
- Development mode auto-generates temporary encryption keys with warnings
- Production mode requires all security keys to be properly set
- Check logs for configuration validation warnings

### Running Tests with Coverage

To check test coverage:
```bash
# Install coverage tools (already in requirements.txt)
pip install pytest-cov

# Run tests with coverage report
pytest --cov=app --cov-report=html --cov-report=term

# View detailed HTML report
# Open htmlcov/index.html in your browser
```

Target coverage: >80% for production code

### Performance Benchmarks
- Health endpoint: <10ms response time
- Encryption/decryption: <1ms for typical PHI data
- Concurrent encryption: ~1000 ops/sec on standard hardware
- Startup time: <2 seconds

## License

Proprietary - All rights reserved by Siphio AI

## Support

For support, email support@siphio.com