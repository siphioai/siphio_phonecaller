"""
Redis service stub for future state management scaling
Provides interface for Redis-based state storage
"""
import logging
from typing import Optional, Dict, Any
import json
import asyncio
from datetime import timedelta

try:
    # Try newer redis versions first (>= 4.2.0)
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    try:
        # Fallback to older redis import style
        import aioredis as redis
        REDIS_AVAILABLE = True
    except ImportError:
        REDIS_AVAILABLE = False
        redis = None

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RedisService:
    """
    Redis service for distributed state management
    Currently a stub - replace in-memory dicts with Redis when scaling
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.connected = False
        self._lock = asyncio.Lock()
        
        # In-memory fallback for development
        self._memory_store: Dict[str, Any] = {}
    
    async def connect(self):
        """
        Connect to Redis server
        Falls back to in-memory storage if Redis not available
        """
        if not REDIS_AVAILABLE:
            logger.warning("Redis client not installed, using in-memory storage")
            return
        
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL_WITH_PASSWORD,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.REDIS_POOL_SIZE
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connected = True
            logger.info("Connected to Redis server")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Falling back to in-memory storage")
            self.redis_client = None
            self.connected = False
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False
            logger.info("Disconnected from Redis")
    
    async def set_conversation_state(self, stream_id: str, state: Dict[str, Any], ttl: int = 3600):
        """
        Store conversation state with TTL
        
        Args:
            stream_id: Unique stream identifier
            state: State dictionary to store
            ttl: Time to live in seconds (default: 1 hour)
        """
        key = f"conversation:{stream_id}"
        value = json.dumps(state)
        
        if self.connected and self.redis_client:
            try:
                await self.redis_client.setex(key, ttl, value)
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                # Fall back to memory
                async with self._lock:
                    self._memory_store[key] = value
        else:
            # Use in-memory storage
            async with self._lock:
                self._memory_store[key] = value
    
    async def get_conversation_state(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve conversation state
        
        Args:
            stream_id: Unique stream identifier
            
        Returns:
            State dictionary or None if not found
        """
        key = f"conversation:{stream_id}"
        
        if self.connected and self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                # Fall back to memory
                async with self._lock:
                    value = self._memory_store.get(key)
                    if value:
                        return json.loads(value)
        else:
            # Use in-memory storage
            async with self._lock:
                value = self._memory_store.get(key)
                if value:
                    return json.loads(value)
        
        return None
    
    async def delete_conversation_state(self, stream_id: str):
        """
        Delete conversation state
        
        Args:
            stream_id: Unique stream identifier
        """
        key = f"conversation:{stream_id}"
        
        if self.connected and self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
                # Fall back to memory
                async with self._lock:
                    self._memory_store.pop(key, None)
        else:
            # Use in-memory storage
            async with self._lock:
                self._memory_store.pop(key, None)
    
    async def publish_event(self, channel: str, event: Dict[str, Any]):
        """
        Publish event to Redis pub/sub channel
        
        Args:
            channel: Channel name
            event: Event data
        """
        if self.connected and self.redis_client:
            try:
                message = json.dumps(event)
                await self.redis_client.publish(channel, message)
            except Exception as e:
                logger.error(f"Redis publish error: {e}")
                # In-memory fallback doesn't support pub/sub
                logger.warning("Pub/sub not available without Redis")
        else:
            logger.debug(f"Would publish to {channel}: {event}")
    
    async def cache_tts_audio(self, text_hash: str, audio_data: bytes, ttl: int = 86400):
        """
        Cache TTS audio for common phrases
        
        Args:
            text_hash: Hash of the text
            audio_data: Audio bytes
            ttl: Time to live in seconds (default: 24 hours)
        """
        key = f"tts_cache:{text_hash}"
        
        if self.connected and self.redis_client:
            try:
                # Store as base64 for JSON compatibility
                import base64
                value = base64.b64encode(audio_data).decode('utf-8')
                await self.redis_client.setex(key, ttl, value)
            except Exception as e:
                logger.error(f"Redis cache error: {e}")
        else:
            # Skip caching in memory for audio (too large)
            logger.debug("TTS caching skipped - Redis not available")
    
    async def get_cached_tts_audio(self, text_hash: str) -> Optional[bytes]:
        """
        Retrieve cached TTS audio
        
        Args:
            text_hash: Hash of the text
            
        Returns:
            Audio bytes or None if not found
        """
        key = f"tts_cache:{text_hash}"
        
        if self.connected and self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    import base64
                    return base64.b64decode(value)
            except Exception as e:
                logger.error(f"Redis cache get error: {e}")
        
        return None
    
    def is_healthy(self) -> bool:
        """Check if Redis service is healthy"""
        return True  # Always return True for stub


# Global instance
_redis_service: Optional[RedisService] = None


async def get_redis_service() -> RedisService:
    """
    Get or create Redis service instance
    
    Returns:
        RedisService instance
    """
    global _redis_service
    
    if _redis_service is None:
        _redis_service = RedisService()
        await _redis_service.connect()
    
    return _redis_service
