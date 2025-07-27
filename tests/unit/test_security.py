"""
Unit tests for security utilities
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import jwt

from app.core.security_utils import (
    EncryptionManager,
    mask_phone,
    mask_email,
    mask_name,
    mask_ssn,
    sanitize_log_data,
    generate_secure_token,
    generate_api_key,
    verify_api_key,
    create_jwt_token,
    decode_jwt_token,
    hash_password,
    verify_password,
    sanitize_input,
    validate_phone_number,
    validate_email,
    audit_log
)


class TestEncryptionManager:
    """Test encryption and decryption functionality"""
    
    def test_encryption_roundtrip(self):
        """Test encrypting and decrypting data"""
        manager = EncryptionManager()
        
        # Test string encryption
        original = "Sensitive patient data: John Doe, DOB: 01/01/1980"
        encrypted = manager.encrypt(original)
        decrypted = manager.decrypt(encrypted)
        
        assert encrypted != original  # Should be encrypted
        assert decrypted == original  # Should decrypt back to original
        assert isinstance(encrypted, str)  # Should return string
    
    def test_empty_data_encryption(self):
        """Test handling of empty data"""
        manager = EncryptionManager()
        
        assert manager.encrypt("") == ""
        assert manager.decrypt("") == ""
    
    def test_bytes_encryption(self):
        """Test encrypting bytes data"""
        manager = EncryptionManager()
        
        original = b"Binary data here"
        encrypted = manager.encrypt(original)
        decrypted = manager.decrypt(encrypted)
        
        assert decrypted == original.decode('utf-8')
    
    def test_invalid_decryption_key(self):
        """Test decryption with wrong key"""
        manager1 = EncryptionManager()
        manager2 = EncryptionManager("gAAAAABhDifferentKeyHere123456789012345678=")
        
        encrypted = manager1.encrypt("Secret data")
        
        with pytest.raises(Exception):  # InvalidToken or similar
            manager2.decrypt(encrypted)
    
    @patch('app.core.config.settings')
    def test_production_key_validation(self, mock_settings):
        """Test that production requires valid encryption key"""
        mock_settings.IS_PRODUCTION = True
        mock_settings.ENCRYPTION_KEY = "your-encryption-key-here-change-in-production"
        
        with pytest.raises(ValueError, match="Invalid encryption key in production"):
            EncryptionManager()
    
    @patch('app.core.config.settings')
    @patch('app.core.security_utils.logger')
    def test_development_key_generation(self, mock_logger, mock_settings):
        """Test that development generates temporary key with warning"""
        import os
        import tempfile
        
        mock_settings.IS_PRODUCTION = False
        mock_settings.ENCRYPTION_KEY = "your-encryption-key-here-change-in-production"
        
        # Use a temp file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.dev-key') as f:
            temp_key_file = f.name
        
        # Patch the dev key file path
        with patch('app.core.security_utils.os.path.exists') as mock_exists:
            with patch('builtins.open', create=True) as mock_open:
                mock_exists.return_value = False  # First run, no cached key
                
                # Configure mock file operations
                mock_file = mock_open.return_value.__enter__.return_value
                mock_file.read.return_value = ""
                
                # Should not raise an error in development
                manager = EncryptionManager()
                
                # Should log warning about temporary key
                mock_logger.warning.assert_called()
                warning_message = mock_logger.warning.call_args[0][0]
                assert "temporary encryption key" in warning_message.lower()
                assert "cached for this project" in warning_message
                
                # Should be able to encrypt/decrypt with generated key
                encrypted = manager.encrypt("test data")
                decrypted = manager.decrypt(encrypted)
                assert decrypted == "test data"
        
        # Clean up
        if os.path.exists(temp_key_file):
            os.unlink(temp_key_file)
    
    @patch('app.core.config.settings')
    @patch('app.core.security_utils.logger')
    def test_development_key_persistence(self, mock_logger, mock_settings):
        """Test that development key persists across restarts"""
        mock_settings.IS_PRODUCTION = False
        mock_settings.ENCRYPTION_KEY = "your-encryption-key-here-change-in-production"
        
        # Generate a test key
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()
        
        # Mock file operations to simulate cached key
        with patch('app.core.security_utils.os.path.exists') as mock_exists:
            with patch('builtins.open', create=True) as mock_open:
                mock_exists.return_value = True  # Cached key exists
                
                # Configure mock to return our test key
                mock_file = mock_open.return_value.__enter__.return_value
                mock_file.read.return_value = test_key
                
                # Create manager
                manager = EncryptionManager()
                
                # Should log that it loaded cached key
                mock_logger.info.assert_any_call("Loaded cached development key from .env.dev-key")
                
                # Should use the cached key
                encrypted = manager.encrypt("test data")
                
                # Create another manager instance (simulating restart)
                mock_file.read.return_value = test_key
                manager2 = EncryptionManager()
                
                # Should be able to decrypt with same key
                decrypted = manager2.decrypt(encrypted)
                assert decrypted == "test data"
    
    def test_valid_fernet_key_validation(self):
        """Test validation of Fernet key format"""
        manager = EncryptionManager()
        
        # Valid key (44 chars, base64)
        valid_key = "gAAAAABhvalid_key_here_that_is_44_chars_ok="
        assert manager._is_valid_fernet_key(valid_key) is False  # Not actually valid base64
        
        # Generate real valid key
        from cryptography.fernet import Fernet
        real_key = Fernet.generate_key().decode()
        assert manager._is_valid_fernet_key(real_key) is True
        
        # Invalid keys
        assert manager._is_valid_fernet_key("") is False
        assert manager._is_valid_fernet_key("short") is False
        assert manager._is_valid_fernet_key("a" * 43) is False  # Too short
        assert manager._is_valid_fernet_key("a" * 45) is False  # Too long
    
    def test_key_rotation(self):
        """Test encryption key rotation"""
        old_manager = EncryptionManager()
        
        # Encrypt data with old key
        data = {
            "field1": old_manager.encrypt("value1"),
            "field2": old_manager.encrypt("value2"),
            "field3": old_manager.encrypt("value3")
        }
        
        # Rotate to new key
        new_key = "gAAAAABhNewKeyForRotation123456789012345678="
        rotated_data = old_manager.rotate_key(new_key, data)
        
        # Verify with new key
        new_manager = EncryptionManager(new_key)
        assert new_manager.decrypt(rotated_data["field1"]) == "value1"
        assert new_manager.decrypt(rotated_data["field2"]) == "value2"
        assert new_manager.decrypt(rotated_data["field3"]) == "value3"


class TestDataMasking:
    """Test PHI/PII masking functions"""
    
    def test_mask_phone(self):
        """Test phone number masking"""
        # US phone number formats
        assert mask_phone("1234567890") == "XXX-XXX-7890"
        assert mask_phone("123-456-7890") == "XXX-XXX-7890"
        assert mask_phone("(123) 456-7890") == "XXX-XXX-7890"
        assert mask_phone("+1-123-456-7890") == "+1-XXX-XXX-7890"
        assert mask_phone("11234567890") == "+1-XXX-XXX-7890"
        
        # Short numbers
        assert mask_phone("1234") == "1234"  # Too short to mask
        assert mask_phone("") == "XXX-XXX-XXXX"  # Fixed: returns placeholder
        
        # International format
        assert mask_phone("441234567890") == "XXXXXXXX7890"
        
        # Custom show_last parameter
        assert mask_phone("1234567890", show_last=2) == "XXXXXXXX90"
        
        # Edge cases
        assert mask_phone("abc") == "XXX-XXX-XXXX"  # Non-digits return placeholder
        assert mask_phone("   ") == "XXX-XXX-XXXX"  # Whitespace returns placeholder
    
    def test_mask_email(self):
        """Test email masking with email-validator"""
        # Valid emails
        assert mask_email("john.doe@example.com") == "j*******@example.com"
        assert mask_email("j@example.com") == "j@example.com"  # Single char
        assert mask_email("admin@siphio.com") == "a****@siphio.com"
        assert mask_email("") == "****@****.***"  # Fixed: returns placeholder
        assert mask_email("invalid-email") == "****@****.***"  # Fixed: invalid email masked
        
        # Edge cases
        assert mask_email("no@at") == "****@****.***"  # Invalid format
        assert mask_email("@example.com") == "****@****.***"  # No local part
        assert mask_email("test@") == "****@****.***"  # No domain
        assert mask_email("ab@example.com") == "a*@example.com"  # Two chars
        
        # International emails (if email-validator is installed)
        try:
            import email_validator
            # These should work with email-validator
            # Test IDN domain - allow for both normalized forms
            masked_idn = mask_email("user@café.com")
            assert masked_idn.startswith("u***@"), f"Expected u***@ prefix, got {masked_idn}"
            assert ("café.com" in masked_idn or "xn--caf-dma.com" in masked_idn), f"Expected café.com or punycode, got {masked_idn}"
            
            # Test Unicode local part
            masked_unicode = mask_email("测试@example.com")
            assert masked_unicode.startswith("测*@"), f"Expected 测*@ prefix, got {masked_unicode}"
            assert masked_unicode.endswith("@example.com"), f"Expected @example.com suffix, got {masked_unicode}"
        except ImportError:
            # If email-validator not installed, these get masked
            assert mask_email("user@café.com") == "****@****.***"
            assert mask_email("测试@example.com") == "****@****.***"
    
    def test_mask_name(self):
        """Test name masking"""
        assert mask_name("John Doe") == "J. D."
        assert mask_name("Jane Mary Smith") == "J. M. S."
        assert mask_name("SingleName") == "S."
        assert mask_name("") == ""
        assert mask_name("   ") == ""
        assert mask_name("a b c") == "A. B. C."
    
    def test_mask_ssn(self):
        """Test SSN masking"""
        assert mask_ssn("123456789") == "XXX-XX-6789"
        assert mask_ssn("123-45-6789") == "XXX-XX-6789"
        assert mask_ssn("12345") == "X2345"
        assert mask_ssn("123") == "XXX"
        assert mask_ssn("") == ""
    
    @patch('app.core.config.settings')
    def test_sanitize_log_data(self, mock_settings):
        """Test log data sanitization"""
        mock_settings.PII_MASKING_ENABLED = True
        
        data = {
            "phone": "1234567890",
            "email": "test@example.com",
            "patient_name": "John Doe",
            "ssn": "123456789",
            "password": "secret123",
            "api_key": "sk_test_123456",
            "authorization": "Bearer token123456789",
            "normal_field": "This stays the same",
            "caller_phone": "9876543210"
        }
        
        sanitized = sanitize_log_data(data)
        
        assert sanitized["phone"] == "XXX-XXX-7890"
        assert sanitized["email"] == "t***@example.com"
        assert sanitized["patient_name"] == "J. D."
        assert sanitized["ssn"] == "XXX-XX-6789"
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["api_key"] == "***REDACTED***"
        assert sanitized["authorization"] == "Bearer tok***"
        assert sanitized["normal_field"] == "This stays the same"
        assert sanitized["caller_phone"] == "XXX-XXX-3210"
    
    @patch('app.core.config.settings')
    def test_sanitize_log_data_disabled(self, mock_settings):
        """Test log data when masking is disabled"""
        mock_settings.PII_MASKING_ENABLED = False
        
        data = {
            "phone": "1234567890",
            "email": "test@example.com"
        }
        
        sanitized = sanitize_log_data(data)
        
        # Should return data unchanged
        assert sanitized == data


class TestTokenGeneration:
    """Test token and API key generation"""
    
    def test_generate_secure_token(self):
        """Test secure token generation"""
        token1 = generate_secure_token(32)
        token2 = generate_secure_token(32)
        
        assert len(token1) == 32
        assert len(token2) == 32
        assert token1 != token2  # Should be random
        assert token1.isalnum()  # Should be alphanumeric
    
    @patch('app.core.config.settings')
    def test_generate_api_key(self, mock_settings):
        """Test API key generation"""
        # Development environment
        mock_settings.IS_DEVELOPMENT = True
        api_key = generate_api_key()
        
        assert api_key.startswith("sk_test_")
        parts = api_key.split("_")
        assert len(parts) == 4
        assert len(parts[2]) == 32  # Random part
        assert len(parts[3]) == 8   # Checksum
        
        # Production environment
        mock_settings.IS_DEVELOPMENT = False
        api_key = generate_api_key()
        assert api_key.startswith("sk_live_")
    
    @patch('app.core.config.settings')
    def test_verify_api_key(self, mock_settings):
        """Test API key verification"""
        mock_settings.IS_DEVELOPMENT = True
        
        # Generate and verify valid key
        api_key = generate_api_key()
        assert verify_api_key(api_key) is True
        
        # Test invalid formats
        assert verify_api_key("invalid") is False
        assert verify_api_key("sk_test_123") is False  # Wrong format
        assert verify_api_key("sk_test_123_456_789") is False  # Too many parts
        
        # Test wrong environment
        mock_settings.IS_DEVELOPMENT = False
        assert verify_api_key(api_key) is False  # Was generated for dev
        
        # Test tampered checksum
        parts = api_key.split("_")
        tampered = f"{parts[0]}_{parts[1]}_{parts[2]}_wrongsum"
        assert verify_api_key(tampered) is False


class TestJWT:
    """Test JWT token management"""
    
    @patch('app.core.config.settings')
    def test_create_jwt_token(self, mock_settings):
        """Test JWT token creation"""
        mock_settings.JWT_SECRET_KEY = "test-secret-key"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_EXPIRATION_HOURS = 24
        
        data = {"user_id": "123", "role": "admin"}
        token = create_jwt_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode to verify
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert decoded["user_id"] == "123"
        assert decoded["role"] == "admin"
        assert "exp" in decoded
        assert "iat" in decoded
    
    @patch('app.core.config.settings')
    def test_decode_jwt_token(self, mock_settings):
        """Test JWT token decoding"""
        mock_settings.JWT_SECRET_KEY = "test-secret-key"
        mock_settings.JWT_ALGORITHM = "HS256"
        
        # Create and decode token
        data = {"user_id": "123"}
        token = create_jwt_token(data)
        decoded = decode_jwt_token(token)
        
        assert decoded["user_id"] == "123"
        assert "exp" in decoded
        assert "iat" in decoded
    
    @patch('app.core.config.settings')
    def test_expired_jwt_token(self, mock_settings):
        """Test expired JWT token"""
        mock_settings.JWT_SECRET_KEY = "test-secret-key"
        mock_settings.JWT_ALGORITHM = "HS256"
        
        # Create token that expires immediately
        data = {"user_id": "123"}
        token = create_jwt_token(data, expires_delta=timedelta(seconds=-1))
        
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_jwt_token(token)
    
    @patch('app.core.config.settings')
    def test_jwt_with_custom_expiration(self, mock_settings):
        """Test JWT token with custom expiration"""
        mock_settings.JWT_SECRET_KEY = "test-secret-key"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_EXPIRATION_HOURS = 48
        
        # Create token with custom expiration
        data = {"user_id": "456", "role": "user"}
        token = create_jwt_token(data, expires_delta=timedelta(hours=72))
        
        # Decode and verify
        decoded = decode_jwt_token(token)
        assert decoded["user_id"] == "456"
        assert decoded["role"] == "user"
        
        # Verify expiration is set correctly
        iat = decoded["iat"]
        exp = decoded["exp"]
        assert (exp - iat) == 72 * 3600  # 72 hours in seconds
    
    @patch('app.core.config.settings')
    def test_invalid_jwt_token(self, mock_settings):
        """Test invalid JWT token"""
        mock_settings.JWT_SECRET_KEY = "test-secret-key"
        mock_settings.JWT_ALGORITHM = "HS256"
        
        with pytest.raises(jwt.InvalidTokenError):
            decode_jwt_token("invalid.token.here")


class TestPasswordHashing:
    """Test password hashing and verification"""
    
    def test_hash_password(self):
        """Test password hashing"""
        password = "SecurePassword123!"
        hashed = hash_password(password)
        
        assert hashed != password  # Should be hashed
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")  # bcrypt format
    
    def test_verify_password(self):
        """Test password verification"""
        password = "SecurePassword123!"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False
        assert verify_password("", hashed) is False
    
    def test_different_hashes_same_password(self):
        """Test that same password produces different hashes"""
        password = "TestPassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2  # Different salts
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestInputValidation:
    """Test input sanitization and validation"""
    
    def test_sanitize_input(self):
        """Test input sanitization"""
        # Normal text
        assert sanitize_input("Hello World") == "Hello World"
        
        # Remove null bytes
        assert sanitize_input("Hello\x00World") == "HelloWorld"
        
        # Keep newlines and tabs
        assert sanitize_input("Hello\nWorld\t!") == "Hello\nWorld\t!"
        
        # Remove control characters
        assert sanitize_input("Hello\x01\x02World") == "HelloWorld"
        
        # Truncation
        long_text = "a" * 2000
        assert len(sanitize_input(long_text, max_length=100)) == 100
        
        # Empty input
        assert sanitize_input("") == ""
        assert sanitize_input("   ") == ""
    
    def test_validate_phone_number(self):
        """Test phone number validation"""
        # Valid US numbers
        assert validate_phone_number("1234567890") is True
        assert validate_phone_number("11234567890") is True
        assert validate_phone_number("123-456-7890") is True
        assert validate_phone_number("(123) 456-7890") is True
        assert validate_phone_number("+1-123-456-7890") is True
        
        # Valid international
        assert validate_phone_number("441234567890") is True
        
        # Invalid
        assert validate_phone_number("123") is False  # Too short
        assert validate_phone_number("12345678901234567") is False  # Too long
        assert validate_phone_number("abcd") is False  # Letters
        assert validate_phone_number("") is False
    
    def test_validate_email(self):
        """Test email validation"""
        # Valid emails
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@example.com") is True
        assert validate_email("user+tag@example.co.uk") is True
        assert validate_email("123@example.com") is True
        
        # Invalid emails
        assert validate_email("invalid") is False
        assert validate_email("@example.com") is False
        assert validate_email("test@") is False
        assert validate_email("test@.com") is False
        assert validate_email("test@example") is False
        assert validate_email("") is False


class TestAuditLogging:
    """Test audit logging decorator"""
    
    @patch('app.core.config.settings')
    @patch('app.core.security_utils.logger')
    async def test_audit_log_async_success(self, mock_logger, mock_settings):
        """Test audit logging for async function success"""
        mock_settings.AUDIT_LOG_ENABLED = True
        
        @audit_log("test_action")
        async def test_function(user_id: str):
            return "success"
        
        result = await test_function(user_id="user123")
        
        assert result == "success"
        mock_logger.info.assert_called()
        log_message = mock_logger.info.call_args[0][0]
        assert "AUDIT: test_action" in log_message
        assert "User: user123" in log_message
        assert "Status: SUCCESS" in log_message
    
    @patch('app.core.config.settings')
    @patch('app.core.security_utils.logger')
    def test_audit_log_sync_failure(self, mock_logger, mock_settings):
        """Test audit logging for sync function failure"""
        mock_settings.AUDIT_LOG_ENABLED = True
        
        @audit_log("test_action")
        def test_function(user_id: str):
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_function(user_id="user123")
        
        mock_logger.error.assert_called()
        log_message = mock_logger.error.call_args[0][0]
        assert "AUDIT: test_action" in log_message
        assert "User: user123" in log_message
        assert "Status: FAILED" in log_message
        assert "Error: Test error" in log_message
    
    @patch('app.core.config.settings')
    @patch('app.core.security_utils.logger')
    def test_audit_log_disabled(self, mock_logger, mock_settings):
        """Test audit logging when disabled"""
        mock_settings.AUDIT_LOG_ENABLED = False
        
        @audit_log("test_action")
        def test_function(user_id: str):
            return "success"
        
        result = test_function(user_id="user123")
        
        assert result == "success"
        # Should not log when disabled
        mock_logger.info.assert_not_called()
    
    @patch('app.core.config.settings')
    @patch('app.core.security_utils.logger')
    def test_audit_log_anonymous_user(self, mock_logger, mock_settings):
        """Test audit logging with anonymous user"""
        mock_settings.AUDIT_LOG_ENABLED = True
        
        @audit_log("test_action")
        def test_function():
            return "success"
        
        result = test_function()
        
        assert result == "success"
        mock_logger.info.assert_called()
        log_message = mock_logger.info.call_args[0][0]
        assert "User: anonymous" in log_message