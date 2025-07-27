"""
Audio buffer management for streaming audio processing
Handles buffering of audio chunks for real-time STT processing
"""
import asyncio
import logging
from collections import deque
from typing import Optional, Deque, Tuple
import struct
import numpy as np

logger = logging.getLogger(__name__)


class AudioBuffer:
    """
    Manages audio buffering for real-time streaming
    Handles chunk aggregation and silence detection
    """
    
    def __init__(
        self,
        sample_rate: int = 8000,  # Twilio uses 8kHz
        chunk_duration_ms: int = 20,  # 20ms chunks from Twilio
        buffer_duration_ms: int = 200,  # Buffer 200ms before sending to STT
        silence_threshold: float = 0.01,  # Silence detection threshold
        max_buffer_size: int = 100  # Maximum number of chunks to buffer
    ):
        """
        Initialize audio buffer
        
        Args:
            sample_rate: Audio sample rate in Hz
            chunk_duration_ms: Duration of each audio chunk in milliseconds
            buffer_duration_ms: Target buffer duration before processing
            silence_threshold: RMS threshold for silence detection
            max_buffer_size: Maximum buffer size to prevent memory issues
        """
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.buffer_duration_ms = buffer_duration_ms
        self.silence_threshold = silence_threshold
        self.max_buffer_size = max_buffer_size
        
        # Calculate samples per chunk
        self.samples_per_chunk = int(sample_rate * chunk_duration_ms / 1000)
        self.chunks_per_buffer = int(buffer_duration_ms / chunk_duration_ms)
        
        # Audio buffer
        self.buffer: Deque[Tuple[bytes, int]] = deque(maxlen=max_buffer_size)
        self.current_chunks: Deque[bytes] = deque()
        
        # State tracking
        self.total_chunks_received = 0
        self.total_chunks_processed = 0
        self.is_speech_active = False
        self.silence_chunks = 0
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        logger.info(
            f"AudioBuffer initialized: {sample_rate}Hz, {chunk_duration_ms}ms chunks, "
            f"{buffer_duration_ms}ms buffer"
        )
    
    async def add(self, audio_data: bytes, timestamp: int):
        """
        Add audio chunk to buffer
        
        Args:
            audio_data: Raw audio bytes
            timestamp: Timestamp or sequence number
        """
        async with self._lock:
            self.buffer.append((audio_data, timestamp))
            self.total_chunks_received += 1
            
            # Check if we're approaching max buffer size
            if len(self.buffer) > self.max_buffer_size * 0.9:
                logger.warning(
                    f"Audio buffer near capacity: {len(self.buffer)}/{self.max_buffer_size}"
                )
    
    def add_sync(self, audio_data: bytes, timestamp: int):
        """
        Synchronous version of add for non-async contexts
        
        Args:
            audio_data: Raw audio bytes
            timestamp: Timestamp or sequence number
        """
        self.buffer.append((audio_data, timestamp))
        self.total_chunks_received += 1
    
    async def has_sufficient_data(self) -> bool:
        """
        Check if buffer has enough data for processing
        
        Returns:
            True if buffer has sufficient data
        """
        async with self._lock:
            return len(self.buffer) >= self.chunks_per_buffer
    
    def has_sufficient_data_sync(self) -> bool:
        """
        Synchronous version for non-async contexts
        
        Returns:
            True if buffer has sufficient data
        """
        return len(self.buffer) >= self.chunks_per_buffer
    
    async def get_chunk(self) -> Optional[bytes]:
        """
        Get aggregated audio chunk for processing
        
        Returns:
            Aggregated audio bytes or None if insufficient data
        """
        async with self._lock:
            if len(self.buffer) < self.chunks_per_buffer:
                return None
            
            # Collect chunks for processing
            audio_chunks = []
            for _ in range(self.chunks_per_buffer):
                if self.buffer:
                    audio_data, _ = self.buffer.popleft()
                    audio_chunks.append(audio_data)
                    self.total_chunks_processed += 1
            
            if not audio_chunks:
                return None
            
            # Concatenate chunks
            combined_audio = b''.join(audio_chunks)
            
            # Check for silence
            if self._is_silence(combined_audio):
                self.silence_chunks += 1
                if self.is_speech_active and self.silence_chunks > 10:  # 200ms of silence
                    self.is_speech_active = False
                    logger.debug("Speech ended (silence detected)")
            else:
                self.silence_chunks = 0
                if not self.is_speech_active:
                    self.is_speech_active = True
                    logger.debug("Speech started")
            
            return combined_audio
    
    def get_chunk_sync(self) -> Optional[bytes]:
        """
        Synchronous version for non-async contexts
        
        Returns:
            Aggregated audio bytes or None if insufficient data
        """
        if len(self.buffer) < self.chunks_per_buffer:
            return None
        
        # Collect chunks for processing
        audio_chunks = []
        for _ in range(self.chunks_per_buffer):
            if self.buffer:
                audio_data, _ = self.buffer.popleft()
                audio_chunks.append(audio_data)
                self.total_chunks_processed += 1
        
        if not audio_chunks:
            return None
        
        # Concatenate chunks
        return b''.join(audio_chunks)
    
    def _is_silence(self, audio_data: bytes) -> bool:
        """
        Detect if audio chunk contains silence
        
        Args:
            audio_data: Audio bytes to check
            
        Returns:
            True if audio is silence
        """
        try:
            # Convert bytes to numpy array (assuming 16-bit PCM)
            # If audio is 8-bit μ-law, it should be converted to PCM first
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Calculate RMS (Root Mean Square)
            rms = np.sqrt(np.mean(audio_array.astype(float) ** 2))
            
            # Normalize RMS (16-bit audio max value is 32767)
            normalized_rms = rms / 32767.0
            
            return normalized_rms < self.silence_threshold
            
        except Exception as e:
            logger.error(f"Error in silence detection: {e}")
            return False
    
    async def clear(self):
        """Clear the buffer"""
        async with self._lock:
            self.buffer.clear()
            self.current_chunks.clear()
            self.silence_chunks = 0
            self.is_speech_active = False
            logger.debug("Audio buffer cleared")
    
    def clear_sync(self):
        """Synchronous version of clear"""
        self.buffer.clear()
        self.current_chunks.clear()
        self.silence_chunks = 0
        self.is_speech_active = False
    
    async def get_stats(self) -> dict:
        """
        Get buffer statistics
        
        Returns:
            Dictionary with buffer stats
        """
        async with self._lock:
            return {
                "buffer_size": len(self.buffer),
                "chunks_received": self.total_chunks_received,
                "chunks_processed": self.total_chunks_processed,
                "is_speech_active": self.is_speech_active,
                "silence_chunks": self.silence_chunks,
                "buffer_duration_ms": len(self.buffer) * self.chunk_duration_ms
            }
    
    def __len__(self) -> int:
        """Get current buffer size"""
        return len(self.buffer)