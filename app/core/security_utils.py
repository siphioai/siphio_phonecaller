"""
Security utilities for encryption, decryption, and data sanitization
HIPAA-compliant data handling for PHI (Protected Health Information)
"""
import base64
import hashlib
import hmac
import re
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Optional, Union, Callable
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class EncryptionManager:
    """
    Manages encryption and decryption of sensitive data
    Uses Fernet symmetric encryption with key from environment
    """
    
    def __init__(self, key: Optional[str] = None):
        """
        Initialize encryption manager with key from environment or parameter
        
        Args:
            key: Base64 encoded encryption key (uses env var if not provided)
        """
        key_str = key or settings.ENCRYPTION_KEY
        
        # Validate key format
        if key_str == "your-encryption-key-here-change-in-production":
            if settings.IS_PRODUCTION:
                raise ValueError("Encryption key must be set in production")
            else:
                # Generate a temporary key for development
                logger.warning("Using temporary encryption key for development")
                key_str = Fernet.generate_key().decode()
        
        try:
            # Ensure key is valid
            self.fernet = Fernet(key_str.encode() if isinstance(key_str, str) else key_str)
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")
        
        # Track encryption operations for audit
        self.operation_count = 0
    
    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Encrypt data and return base64 encoded string
        
        Args:
            data: String or bytes to encrypt
            
        Returns:
            Base64 encoded encrypted string
        """
        if not data:
            return ""
        
        try:
            # Convert string to bytes if necessary
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Encrypt and decode to string
            encrypted = self.fernet.encrypt(data)
            self.operation_count += 1
            
            # Log operation (without sensitive data)
            if settings.AUDIT_LOG_ENABLED:
                logger.debug(f"Encrypted data (operation #{self.operation_count})")
            
            return encrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: Union[str, bytes]) -> str:
        """
        Decrypt data and return original string
        
        Args:
            encrypted_data: Base64 encoded encrypted string or bytes
            
        Returns:
            Decrypted string
        """
        if not encrypted_data:
            return ""
        
        try:
            # Convert string to bytes if necessary
            if isinstance(encrypted_data, str):
                encrypted_data = encrypted_data.encode('utf-8')
            
            # Decrypt
            decrypted = self.fernet.decrypt(encrypted_data)
            self.operation_count += 1
            
            # Log operation (without sensitive data)
            if settings.AUDIT_LOG_ENABLED:
                logger.debug(f"Decrypted data (operation #{self.operation_count})")
            
            return decrypted.decode('utf-8')
        except InvalidToken:
            logger.error("Invalid encryption token - data may be corrupted or key mismatch")
            raise
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def rotate_key(self, new_key: str, old_data: Dict[str, str]) -> Dict[str, str]:
        """
        Rotate encryption key by re-encrypting data with new key
        
        Args:
            new_key: New encryption key
            old_data: Dictionary of encrypted data to rotate
            
        Returns:
            Dictionary with data re-encrypted with new key
        """
        # Create new encryption manager with new key
        new_manager = EncryptionManager(new_key)
        rotated_data = {}
        
        for key, encrypted_value in old_data.items():
            try:
                # Decrypt with old key, encrypt with new key
                decrypted = self.decrypt(encrypted_value)
                rotated_data[key] = new_manager.encrypt(decrypted)
            except Exception as e:
                logger.error(f"Failed to rotate key for {key}: {e}")
                raise
        
        logger.info(f"Successfully rotated {len(rotated_data)} encrypted values")
        return rotated_data


# Global encryption manager instance
encryption_manager = EncryptionManager()


# Data Masking Functions for PHI/PII
def mask_phone(phone: str, show_last: int = 4) -> str:
    """
    Mask phone number showing only last N digits
    
    Args:
        phone: Phone number to mask
        show_last: Number of digits to show at the end
        
    Returns:
        Masked phone number (e.g., "XXX-XXX-1234")
    """
    if not phone:
        return ""
    
    # Remove non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    if len(digits_only) <= show_last:
        return phone  # Don't mask if too short
    
    # Mask all but last N digits
    masked_part = 'X' * (len(digits_only) - show_last)
    visible_part = digits_only[-show_last:]
    
    # Format as XXX-XXX-1234 for US numbers
    if len(digits_only) == 10:  # US number without country code
        return f"{masked_part[:3]}-{masked_part[3:6]}-{visible_part}"
    elif len(digits_only) == 11 and digits_only[0] == '1':  # US number with country code
        return f"+1-{masked_part[1:4]}-{masked_part[4:7]}-{visible_part}"
    else:
        # Generic masking
        return masked_part + visible_part


def mask_email(email: str) -> str:
    """
    Mask email address showing only first letter and domain
    
    Args:
        email: Email address to mask
        
    Returns:
        Masked email (e.g., "j****@example.com")
    """
    if not email or '@' not in email:
        return email
    
    local, domain = email.split('@', 1)
    
    if len(local) <= 1:
        return email  # Don't mask single character
    
    # Show first character and mask the rest
    masked_local = local[0] + '*' * (len(local) - 1)
    return f"{masked_local}@{domain}"


def mask_name(name: str) -> str:
    """
    Mask person's name showing only initials
    
    Args:
        name: Full name to mask
        
    Returns:
        Masked name (e.g., "J. D.")
    """
    if not name:
        return ""
    
    parts = name.strip().split()
    if not parts:
        return ""
    
    # Return initials only
    initials = [part[0].upper() + '.' for part in parts if part]
    return ' '.join(initials)


def mask_ssn(ssn: str) -> str:
    """
    Mask SSN showing only last 4 digits
    
    Args:
        ssn: Social Security Number
        
    Returns:
        Masked SSN (e.g., "XXX-XX-1234")
    """
    if not ssn:
        return ""
    
    # Remove non-digit characters
    digits_only = re.sub(r'\D', '', ssn)
    
    if len(digits_only) < 4:
        return 'X' * len(digits_only)
    
    # Show only last 4 digits
    if len(digits_only) == 9:
        return f"XXX-XX-{digits_only[-4:]}"
    else:
        return 'X' * (len(digits_only) - 4) + digits_only[-4:]


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize sensitive data for logging
    Masks PHI/PII according to HIPAA requirements
    
    Args:
        data: Dictionary containing potentially sensitive data
        
    Returns:
        Sanitized dictionary safe for logging
    """
    if not settings.PII_MASKING_ENABLED:
        return data
    
    # Define sensitive field patterns
    sensitive_patterns = {
        'phone': mask_phone,
        'email': mask_email,
        'name': mask_name,
        'ssn': mask_ssn,
        'patient': mask_name,
        'caller': mask_name,
    }
    
    sanitized = data.copy()
    
    for key, value in data.items():
        if value is None:
            continue
            
        # Check if key matches sensitive patterns
        key_lower = key.lower()
        for pattern, mask_func in sensitive_patterns.items():
            if pattern in key_lower and isinstance(value, str):
                sanitized[key] = mask_func(value)
                break
        
        # Mask specific fields
        if key_lower in ['password', 'token', 'api_key', 'secret']:
            sanitized[key] = '***REDACTED***'
        elif key_lower in ['authorization', 'cookie'] and isinstance(value, str):
            # Show only first few characters
            sanitized[key] = value[:10] + '***' if len(value) > 10 else '***'
    
    return sanitized


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token
    
    Args:
        length: Length of the token
        
    Returns:
        Secure random token string
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_api_key() -> str:
    """
    Generate a secure API key with checksum
    
    Returns:
        API key in format: sk_live_<random>_<checksum>
    """
    # Generate random part
    random_part = generate_secure_token(32)
    
    # Create checksum
    checksum = hashlib.sha256(random_part.encode()).hexdigest()[:8]
    
    # Determine prefix based on environment
    prefix = "sk_test" if settings.IS_DEVELOPMENT else "sk_live"
    
    return f"{prefix}_{random_part}_{checksum}"


def verify_api_key(api_key: str) -> bool:
    """
    Verify API key format and checksum
    
    Args:
        api_key: API key to verify
        
    Returns:
        True if valid, False otherwise
    """
    try:
        parts = api_key.split('_')
        if len(parts) != 4:
            return False
        
        prefix, _, random_part, provided_checksum = parts
        
        # Verify prefix
        expected_prefix = "sk_test" if settings.IS_DEVELOPMENT else "sk_live"
        if prefix != expected_prefix:
            return False
        
        # Verify checksum
        calculated_checksum = hashlib.sha256(random_part.encode()).hexdigest()[:8]
        return hmac.compare_digest(calculated_checksum, provided_checksum)
    except Exception:
        return False


# JWT Token Management
def create_jwt_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT token with expiration
    
    Args:
        data: Payload data
        expires_delta: Token expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    # Set expiration
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    # Encode token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify JWT token
    
    Args:
        token: JWT token to decode
        
    Returns:
        Decoded payload
        
    Raises:
        jwt.InvalidTokenError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("JWT token has expired")
        raise
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {e}")
        raise


# Password Hashing
def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        True if password matches
    """
    return pwd_context.verify(plain_password, hashed_password)


# Audit Logging Decorator
def audit_log(action: str):
    """
    Decorator to log security-sensitive operations
    
    Args:
        action: Description of the action being performed
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            user_id = kwargs.get('user_id', 'anonymous')
            
            try:
                result = await func(*args, **kwargs)
                
                if settings.AUDIT_LOG_ENABLED:
                    logger.info(
                        f"AUDIT: {action} | User: {user_id} | "
                        f"Duration: {(datetime.utcnow() - start_time).total_seconds():.3f}s | "
                        f"Status: SUCCESS"
                    )
                
                return result
            except Exception as e:
                if settings.AUDIT_LOG_ENABLED:
                    logger.error(
                        f"AUDIT: {action} | User: {user_id} | "
                        f"Duration: {(datetime.utcnow() - start_time).total_seconds():.3f}s | "
                        f"Status: FAILED | Error: {str(e)}"
                    )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            user_id = kwargs.get('user_id', 'anonymous')
            
            try:
                result = func(*args, **kwargs)
                
                if settings.AUDIT_LOG_ENABLED:
                    logger.info(
                        f"AUDIT: {action} | User: {user_id} | "
                        f"Duration: {(datetime.utcnow() - start_time).total_seconds():.3f}s | "
                        f"Status: SUCCESS"
                    )
                
                return result
            except Exception as e:
                if settings.AUDIT_LOG_ENABLED:
                    logger.error(
                        f"AUDIT: {action} | User: {user_id} | "
                        f"Duration: {(datetime.utcnow() - start_time).total_seconds():.3f}s | "
                        f"Status: FAILED | Error: {str(e)}"
                    )
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Input Sanitization
def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injection attacks
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Truncate to max length
    text = text[:max_length]
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove control characters except newlines and tabs
    text = ''.join(char for char in text if char == '\n' or char == '\t' or not ord(char) < 32)
    
    # Basic HTML escape (if needed for web display)
    # text = html.escape(text)
    
    return text.strip()


def validate_phone_number(phone: str) -> bool:
    """
    Validate phone number format
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid phone number
    """
    # Remove common formatting characters
    cleaned = re.sub(r'[\s\-\(\)\+\.]', '', phone)
    
    # Check if it's a valid phone number (10-15 digits)
    return bool(re.match(r'^\d{10,15}$', cleaned))


def validate_email(email: str) -> bool:
    """
    Validate email address format
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid email
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))