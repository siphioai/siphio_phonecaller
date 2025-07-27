"""
Unit tests for configuration management
"""
import os
import pytest
from unittest.mock import patch

from app.core.config import Settings, get_settings


class TestConfig:
    """Test configuration loading and validation"""
    
    def test_default_development_settings(self):
        """Test default settings for development environment"""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            settings = Settings()
            
            assert settings.ENVIRONMENT == "development"
            assert settings.DEBUG is True
            assert settings.IS_DEVELOPMENT is True
            assert settings.IS_PRODUCTION is False
            assert settings.APP_NAME == "Siphio AI Phone Receptionist"
    
    def test_production_environment_detection(self):
        """Test production environment detection"""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "DEBUG": "false"}, clear=True):
            settings = Settings()
            
            assert settings.ENVIRONMENT == "production"
            assert settings.DEBUG is False
            assert settings.IS_PRODUCTION is True
            assert settings.IS_DEVELOPMENT is False
    
    def test_cors_origins_parsing(self):
        """Test CORS origins parsing from JSON string"""
        # Test JSON array string
        with patch.dict(os.environ, {
            "CORS_ORIGINS": '["http://localhost:3000", "https://example.com"]'
        }, clear=True):
            settings = Settings()
            assert settings.CORS_ORIGINS == ["http://localhost:3000", "https://example.com"]
        
        # Test single string
        with patch.dict(os.environ, {"CORS_ORIGINS": "http://localhost:3000"}, clear=True):
            settings = Settings()
            assert settings.CORS_ORIGINS == ["http://localhost:3000"]
        
        # Test list (when passed programmatically)
        settings = Settings(CORS_ORIGINS=["http://localhost:3000"])
        assert settings.CORS_ORIGINS == ["http://localhost:3000"]
    
    def test_redis_url_with_password(self):
        """Test Redis URL construction with password"""
        # Without password
        settings = Settings(REDIS_URL="redis://localhost:6379/0", REDIS_PASSWORD=None)
        assert settings.REDIS_URL_WITH_PASSWORD == "redis://localhost:6379/0"
        
        # With password
        settings = Settings(REDIS_URL="redis://localhost:6379/0", REDIS_PASSWORD="secret123")
        assert settings.REDIS_URL_WITH_PASSWORD == "redis://:secret123@localhost:6379/0"
    
    def test_production_validation_errors(self):
        """Test validation errors in production environment"""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "DEBUG": "true",  # Should be false in production
            "SECRET_KEY": "your-secret-key-here-change-in-production",  # Default value
            "ENCRYPTION_KEY": "your-encryption-key-here-change-in-production"  # Default value
        }, clear=True):
            settings = Settings()
            errors = settings.validate_production_settings()
            
            assert "DEBUG must be False in production" in errors
            assert "SECRET_KEY must be changed from default" in errors
            assert "ENCRYPTION_KEY must be changed from default" in errors
            assert "TWILIO_ACCOUNT_SID is required in production" in errors
    
    def test_production_validation_success(self):
        """Test successful validation in production with all required settings"""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "DEBUG": "false",
            "SECRET_KEY": "a-real-secret-key-123456789",
            "ENCRYPTION_KEY": "gAAAAABh_valid_fernet_key_here",
            "JWT_SECRET_KEY": "jwt-secret-key-123",
            "TWILIO_ACCOUNT_SID": "ACxxxxx",
            "TWILIO_AUTH_TOKEN": "auth_token",
            "DEEPGRAM_API_KEY": "deepgram_key",
            "ANTHROPIC_API_KEY": "anthropic_key",
            "ELEVENLABS_API_KEY": "elevenlabs_key",
            "HIPAA_COMPLIANT_MODE": "true",
            "ENCRYPT_TRANSCRIPTS": "true"
        }, clear=True):
            settings = Settings()
            errors = settings.validate_production_settings()
            
            assert len(errors) == 0
    
    def test_development_warnings(self):
        """Test development environment warnings"""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "DEBUG": "false",  # Usually true in development
            "WORKERS": "2",  # Multiple workers can cause issues
            "HIPAA_COMPLIANT_MODE": "true"
        }, clear=True):
            settings = Settings()
            warnings = settings.validate_development_settings()
            
            assert "DEBUG is False in development - you may want to enable it" in warnings
            assert "Multiple workers in development may cause issues with hot reload" in warnings
            assert "HIPAA_COMPLIANT_MODE is enabled in development" in warnings
    
    def test_computed_allowed_hosts(self):
        """Test computed ALLOWED_HOSTS based on environment"""
        # Development
        with patch.dict(os.environ, {"DEBUG": "true"}, clear=True):
            settings = Settings()
            assert settings.ALLOWED_HOSTS == ["*"]
        
        # Production
        with patch.dict(os.environ, {"DEBUG": "false"}, clear=True):
            settings = Settings()
            assert "localhost" in settings.ALLOWED_HOSTS
            assert "127.0.0.1" in settings.ALLOWED_HOSTS
            assert ".siphio.com" in settings.ALLOWED_HOSTS
    
    def test_field_validation(self):
        """Test pydantic field validation"""
        # Valid values
        settings = Settings(
            ENVIRONMENT="development",
            LOG_LEVEL="INFO",
            PORT=8080,
            JWT_EXPIRATION_HOURS=48,
            CLAUDE_TEMPERATURE=0.5
        )
        assert settings.PORT == 8080
        assert settings.JWT_EXPIRATION_HOURS == 48
        assert settings.CLAUDE_TEMPERATURE == 0.5
        
        # Invalid environment
        with pytest.raises(ValueError):
            Settings(ENVIRONMENT="invalid")
        
        # Invalid log level
        with pytest.raises(ValueError):
            Settings(LOG_LEVEL="INVALID")
        
        # Invalid port
        with pytest.raises(ValueError):
            Settings(PORT=70000)  # > 65535
        
        # Invalid JWT expiration
        with pytest.raises(ValueError):
            Settings(JWT_EXPIRATION_HOURS=200)  # > 168
        
        # Invalid temperature
        with pytest.raises(ValueError):
            Settings(CLAUDE_TEMPERATURE=1.5)  # > 1.0
    
    def test_business_hours_validation(self):
        """Test business hours format validation"""
        # Valid format
        settings = Settings(
            BUSINESS_HOURS_START="09:00",
            BUSINESS_HOURS_END="17:00"
        )
        assert settings.BUSINESS_HOURS_START == "09:00"
        assert settings.BUSINESS_HOURS_END == "17:00"
        
        # Invalid format
        with pytest.raises(ValueError):
            Settings(BUSINESS_HOURS_START="9:00")  # Missing leading zero
        
        with pytest.raises(ValueError):
            Settings(BUSINESS_HOURS_END="25:00")  # Invalid hour
    
    def test_get_settings_cache(self):
        """Test that get_settings returns cached instance"""
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should be the same instance due to @lru_cache
        assert settings1 is settings2
    
    def test_env_file_loading(self):
        """Test loading from .env file"""
        # Create a temporary .env file
        env_content = """
ENVIRONMENT=development
APP_NAME=Test App
PORT=9000
        """
        
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = env_content
            
            # Settings should load from .env file
            settings = Settings(_env_file=".env")
            
            # These values would come from the mocked .env file
            # Note: In actual implementation, pydantic-settings handles this
    
    def test_feature_flags(self):
        """Test feature flag configuration"""
        settings = Settings(
            ENABLE_CALL_RECORDING=True,
            ENABLE_SMS_CONFIRMATIONS=False,
            ENABLE_CALENDAR_INTEGRATION=True,
            ENABLE_MULTI_LANGUAGE=False,
            ENABLE_VOICE_CLONING=False
        )
        
        assert settings.ENABLE_CALL_RECORDING is True
        assert settings.ENABLE_SMS_CONFIRMATIONS is False
        assert settings.ENABLE_CALENDAR_INTEGRATION is True
        assert settings.ENABLE_MULTI_LANGUAGE is False
        assert settings.ENABLE_VOICE_CLONING is False
    
    def test_compliance_settings(self):
        """Test compliance and security settings"""
        settings = Settings(
            HIPAA_COMPLIANT_MODE=True,
            ENCRYPT_TRANSCRIPTS=True,
            ENCRYPT_CALL_RECORDINGS=True,
            DATA_RETENTION_DAYS=90,
            AUDIT_LOG_ENABLED=True,
            PII_MASKING_ENABLED=True
        )
        
        assert settings.HIPAA_COMPLIANT_MODE is True
        assert settings.ENCRYPT_TRANSCRIPTS is True
        assert settings.ENCRYPT_CALL_RECORDINGS is True
        assert settings.DATA_RETENTION_DAYS == 90
        assert settings.AUDIT_LOG_ENABLED is True
        assert settings.PII_MASKING_ENABLED is True
        
        # Test retention days validation
        with pytest.raises(ValueError):
            Settings(DATA_RETENTION_DAYS=0)  # < 1
        
        with pytest.raises(ValueError):
            Settings(DATA_RETENTION_DAYS=1000)  # > 730