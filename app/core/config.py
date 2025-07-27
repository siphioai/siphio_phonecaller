"""
Application configuration using Pydantic Settings
Handles all environment variables and provides type-safe access
"""
import json
import sys
import warnings
from typing import List, Optional, Dict, Any
from functools import lru_cache

from pydantic import Field, field_validator, computed_field

# Handle pydantic-settings import with fallback
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    warnings.warn(
        "pydantic-settings not installed. Please install with: pip install pydantic-settings",
        ImportWarning
    )
    # Fallback to basic pydantic BaseSettings if available
    try:
        from pydantic import BaseSettings
        SettingsConfigDict = dict  # Basic dict as fallback
    except ImportError:
        print("ERROR: pydantic is required. Please install dependencies: pip install -r requirements.txt")
        sys.exit(1)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    Uses pydantic-settings to automatically load from .env file
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra environment variables
    )
    
    # Application Settings
    APP_NAME: str = Field(default="Siphio AI Phone Receptionist")
    APP_VERSION: str = Field(default="0.1.0")
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    
    # Security
    SECRET_KEY: str = Field(default="your-secret-key-here-change-in-production")
    ENCRYPTION_KEY: str = Field(default="your-encryption-key-here-change-in-production")
    JWT_SECRET_KEY: str = Field(default="your-jwt-secret-here-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_HOURS: int = Field(default=24, ge=1, le=168)  # 1 hour to 7 days
    
    # Server Configuration
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000, ge=1, le=65535)
    WORKERS: int = Field(default=1, ge=1)
    CORS_ORIGINS: str = Field(default='["http://localhost:3000", "http://localhost:8000"]')
    
    # Database
    DATABASE_URL: str = Field(default="postgresql+asyncpg://user:password@localhost:5432/siphio_phone")
    DATABASE_POOL_SIZE: int = Field(default=20, ge=1)
    DATABASE_MAX_OVERFLOW: int = Field(default=0, ge=0)
    DATABASE_ECHO: bool = Field(default=False)
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = Field(default=None)
    REDIS_POOL_SIZE: int = Field(default=10, ge=1)
    REDIS_DECODE_RESPONSES: bool = Field(default=True)
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None)
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None)
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None)
    TWILIO_WEBHOOK_URL: Optional[str] = Field(default=None)
    TWILIO_STATUS_CALLBACK_URL: Optional[str] = Field(default=None)
    
    # Deepgram Configuration
    DEEPGRAM_API_KEY: Optional[str] = Field(default=None)
    DEEPGRAM_MODEL: str = Field(default="nova-2-phonecall")
    DEEPGRAM_LANGUAGE: str = Field(default="en")
    DEEPGRAM_PUNCTUATE: bool = Field(default=True)
    DEEPGRAM_DIARIZE: bool = Field(default=True)
    DEEPGRAM_NUMERALS: bool = Field(default=True)
    DEEPGRAM_PROFANITY_FILTER: bool = Field(default=False)
    DEEPGRAM_INTERIM_RESULTS: bool = Field(default=True)
    
    # Anthropic Claude Configuration
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    CLAUDE_MODEL: str = Field(default="claude-3-haiku-20240307")
    CLAUDE_MAX_TOKENS: int = Field(default=500, ge=1, le=4096)
    CLAUDE_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=1.0)
    CLAUDE_SYSTEM_PROMPT_PATH: str = Field(default="prompts/receptionist_system.txt")
    
    # ElevenLabs Configuration
    ELEVENLABS_API_KEY: Optional[str] = Field(default=None)
    ELEVENLABS_VOICE_ID: Optional[str] = Field(default=None)
    ELEVENLABS_MODEL: str = Field(default="eleven_turbo_v2_5")
    ELEVENLABS_STABILITY: float = Field(default=0.5, ge=0.0, le=1.0)
    ELEVENLABS_SIMILARITY_BOOST: float = Field(default=0.75, ge=0.0, le=1.0)
    ELEVENLABS_STYLE: float = Field(default=0.0, ge=0.0, le=1.0)
    ELEVENLABS_USE_SPEAKER_BOOST: bool = Field(default=True)
    
    # Google Calendar Configuration
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None)
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(default=None)
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:8000/api/auth/google/callback")
    GOOGLE_CALENDAR_ID: str = Field(default="primary")
    GOOGLE_OAUTH_SCOPES: str = Field(default='["https://www.googleapis.com/auth/calendar"]')
    
    # Business Logic Settings
    APPOINTMENT_DURATION_MINUTES: int = Field(default=30, ge=15, le=120)
    APPOINTMENT_BUFFER_MINUTES: int = Field(default=15, ge=0, le=60)
    BUSINESS_HOURS_START: str = Field(default="09:00", pattern="^\\d{2}:\\d{2}$")
    BUSINESS_HOURS_END: str = Field(default="17:00", pattern="^\\d{2}:\\d{2}$")
    BUSINESS_TIMEZONE: str = Field(default="America/New_York")
    MAX_FUTURE_BOOKING_DAYS: int = Field(default=60, ge=1, le=365)
    
    # Call Handling Settings
    MAX_CALL_DURATION_SECONDS: int = Field(default=600, ge=60, le=3600)  # 1 min to 1 hour
    SILENCE_THRESHOLD_MS: int = Field(default=2000, ge=500, le=5000)
    INTERRUPTION_THRESHOLD_MS: int = Field(default=500, ge=100, le=2000)
    MAX_RETRY_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    DEFAULT_GREETING: str = Field(default="Thank you for calling. How may I help you today?")
    
    # Monitoring & Alerting
    PROMETHEUS_METRICS_PATH: str = Field(default="/metrics")
    ALERT_EMAIL: Optional[str] = Field(default=None)
    ALERT_WEBHOOK_URL: Optional[str] = Field(default=None)
    SENTRY_DSN: Optional[str] = Field(default=None)
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_CALLS_PER_MINUTE: int = Field(default=60, ge=1)
    RATE_LIMIT_CALLS_PER_HOUR: int = Field(default=1000, ge=1)
    
    # Feature Flags
    ENABLE_CALL_RECORDING: bool = Field(default=False)
    ENABLE_SMS_CONFIRMATIONS: bool = Field(default=True)
    ENABLE_CALENDAR_INTEGRATION: bool = Field(default=True)
    ENABLE_MULTI_LANGUAGE: bool = Field(default=False)
    ENABLE_VOICE_CLONING: bool = Field(default=False)
    
    # Compliance & Security
    HIPAA_COMPLIANT_MODE: bool = Field(default=True)
    ENCRYPT_TRANSCRIPTS: bool = Field(default=True)
    ENCRYPT_CALL_RECORDINGS: bool = Field(default=True)
    DATA_RETENTION_DAYS: int = Field(default=90, ge=1, le=730)  # 1 day to 2 years
    AUDIT_LOG_ENABLED: bool = Field(default=True)
    PII_MASKING_ENABLED: bool = Field(default=True)
    
    # Testing & Development
    TEST_MODE: bool = Field(default=False)
    MOCK_EXTERNAL_SERVICES: bool = Field(default=False)
    NGROK_AUTHTOKEN: Optional[str] = Field(default=None)
    
    # Computed fields
    @computed_field
    @property
    def ALLOWED_HOSTS(self) -> List[str]:
        """Compute allowed hosts based on environment"""
        if self.DEBUG:
            return ["*"]
        return ["localhost", "127.0.0.1", ".siphio.com"]  # Add your domains
    
    @computed_field
    @property
    def IS_PRODUCTION(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == "production"
    
    @computed_field
    @property
    def IS_DEVELOPMENT(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT == "development"
    
    @computed_field
    @property
    def REDIS_URL_WITH_PASSWORD(self) -> str:
        """Build Redis URL with password if provided"""
        if self.REDIS_PASSWORD:
            # Parse and inject password into URL
            parts = self.REDIS_URL.split("://")
            if len(parts) == 2:
                return f"{parts[0]}://:{self.REDIS_PASSWORD}@{parts[1].split('@')[-1]}"
        return self.REDIS_URL
    
    # Field validators
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        """Parse CORS origins from JSON string or list"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]  # Single origin as string
        elif isinstance(v, list):
            return v
        return []
    
    @field_validator("GOOGLE_OAUTH_SCOPES", mode="before")
    @classmethod
    def parse_oauth_scopes(cls, v: Any) -> List[str]:
        """Parse OAuth scopes from JSON string or list"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]  # Single scope as string
        elif isinstance(v, list):
            return v
        return []
    
    def validate_production_settings(self) -> List[str]:
        """
        Validate settings for production environment
        Returns list of validation errors
        """
        errors = []
        
        if self.IS_PRODUCTION:
            # Security validations
            if self.DEBUG:
                errors.append("DEBUG must be False in production")
            if self.SECRET_KEY == "your-secret-key-here-change-in-production":
                errors.append("SECRET_KEY must be changed from default")
            if self.ENCRYPTION_KEY == "your-encryption-key-here-change-in-production":
                errors.append("ENCRYPTION_KEY must be changed from default")
            if self.JWT_SECRET_KEY == "your-jwt-secret-here-change-in-production":
                errors.append("JWT_SECRET_KEY must be changed from default")
            
            # Service validations
            if not self.TWILIO_ACCOUNT_SID:
                errors.append("TWILIO_ACCOUNT_SID is required in production")
            if not self.TWILIO_AUTH_TOKEN:
                errors.append("TWILIO_AUTH_TOKEN is required in production")
            if not self.DEEPGRAM_API_KEY:
                errors.append("DEEPGRAM_API_KEY is required in production")
            if not self.ANTHROPIC_API_KEY:
                errors.append("ANTHROPIC_API_KEY is required in production")
            if not self.ELEVENLABS_API_KEY:
                errors.append("ELEVENLABS_API_KEY is required in production")
            
            # Compliance validations
            if not self.HIPAA_COMPLIANT_MODE:
                errors.append("HIPAA_COMPLIANT_MODE should be True for healthcare applications")
            if not self.ENCRYPT_TRANSCRIPTS:
                errors.append("ENCRYPT_TRANSCRIPTS must be True in production")
            if self.ENABLE_CALL_RECORDING and not self.ENCRYPT_CALL_RECORDINGS:
                errors.append("ENCRYPT_CALL_RECORDINGS must be True when recording is enabled")
        
        return errors
    
    def validate_development_settings(self) -> List[str]:
        """
        Validate settings for development environment
        Returns list of warnings
        """
        warnings = []
        
        if self.IS_DEVELOPMENT:
            # Development warnings
            if self.WORKERS > 1:
                warnings.append("Multiple workers in development may cause issues with hot reload")
            if self.HIPAA_COMPLIANT_MODE:
                warnings.append("HIPAA_COMPLIANT_MODE is enabled in development - some features may be restricted")
            if not self.DEBUG:
                warnings.append("DEBUG is False in development - you may want to enable it")
        
        return warnings


# Cache settings instance
@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Use this function to import settings throughout the application
    """
    return Settings()


# Create settings instance
settings = get_settings()

# Validate settings on import
if settings.IS_PRODUCTION:
    errors = settings.validate_production_settings()
    if errors:
        import sys
        print("Production configuration errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
elif settings.IS_DEVELOPMENT:
    warnings = settings.validate_development_settings()
    if warnings:
        print("Development configuration warnings:")
        for warning in warnings:
            print(f"  - {warning}")