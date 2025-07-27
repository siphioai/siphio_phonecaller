"""
Audio buffer management for streaming audio processing
Handles buffering of audio chunks for real-time STT processing
"""
import asyncio
import logging
from collections import deque
from typing import Optional, Deque, Tuple, List
import struct
import numpy as np

logger = logging.getLogger(__name__)


class AudioBuffer:
    """
    Manages audio buffering for real-time streaming
    Handles chunk aggregation and silence detection with VAD
    """
    
    def __init__(
        self,
        sample_rate: int = 8000,  # Twilio uses 8kHz
        chunk_duration_ms: int = 20,  # 20ms chunks from Twilio
        buffer_duration_ms: int = 200,  # Buffer 200ms before sending to STT
        silence_threshold: float = 0.01,  # Silence detection threshold
        max_buffer_size: int = 100,  # Maximum number of chunks to buffer
        vad_enabled: bool = True  # Enable Voice Activity Detection
    ):
        """
        Initialize audio buffer
        
        Args:
            sample_rate: Audio sample rate in Hz
            chunk_duration_ms: Duration of each audio chunk in milliseconds
            buffer_duration_ms: Target buffer duration before processing
            silence_threshold: RMS threshold for silence detection
            max_buffer_size: Maximum buffer size to prevent memory issues
            vad_enabled: Enable Voice Activity Detection
        """
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.buffer_duration_ms = buffer_duration_ms
        self.silence_threshold = silence_threshold
        self.max_buffer_size = max_buffer_size
        self.vad_enabled = vad_enabled
        
        # Calculate samples per chunk
        self.samples_per_chunk = int(sample_rate * chunk_duration_ms / 1000)
        self.chunks_per_buffer = int(buffer_duration_ms / chunk_duration_ms)
        
        # Audio buffer with overflow protection
        self.buffer: Deque[Tuple[bytes, int]] = deque(maxlen=max_buffer_size)
        self.overflow_buffer: List[bytes] = []  # Store remnants between calls
        
        # State tracking
        self.total_chunks_received = 0
        self.total_chunks_processed = 0
        self.is_speech_active = False
        self.silence_chunks = 0
        self.consecutive_speech_chunks = 0
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        logger.info(
            f"AudioBuffer initialized: {sample_rate}Hz, {chunk_duration_ms}ms chunks, "
            f"{buffer_duration_ms}ms buffer, VAD={'enabled' if vad_enabled else 'disabled'}"
        )
    
    async def add(self, audio_data: bytes, timestamp: int):
        """
        Add audio chunk to buffer with overflow handling
        
        Args:
            audio_data: Raw audio bytes
            timestamp: Timestamp or sequence number
        """
        async with self._lock:
            # Handle any overflow from previous operations
            if self.overflow_buffer:
                audio_data = b''.join(self.overflow_buffer) + audio_data
                self.overflow_buffer.clear()
            
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
        Detect if audio chunk contains silence using energy-based VAD
        
        Args:
            audio_data: Audio bytes to check
            
        Returns:
            True if audio is silence
        """
        if not self.vad_enabled:
            return False
            
        try:
            # Handle empty data
            if not audio_data or len(audio_data) == 0:
                return False
            
            # Convert bytes to numpy array
            # Note: Twilio sends μ-law encoded audio, needs conversion
            audio_array = np.frombuffer(audio_data, dtype=np.uint8)
            
            # Handle arrays with no data
            if len(audio_array) == 0:
                return False
            
            # Simple energy-based VAD
            # Calculate energy (sum of squares)
            energy = np.sum(audio_array.astype(float) ** 2) / len(audio_array)
            
            # Normalize energy (8-bit audio max value is 255)
            normalized_energy = energy / (255.0 ** 2)
            
            # Update speech state with hysteresis
            is_silence = normalized_energy < self.silence_threshold
            
            # Add hysteresis to prevent rapid state changes
            if is_silence:
                self.consecutive_speech_chunks = 0
            else:
                self.consecutive_speech_chunks += 1
            
            # Ensure we return a Python bool, not numpy bool
            return bool(is_silence)
            
        except Exception as e:
            logger.error(f"Error in silence detection: {e}")
            return False
    
    async def flush(self) -> Optional[bytes]:
        """
        Flush any remaining audio data in buffer
        
        Returns:
            Remaining audio bytes or None if buffer is empty
        """
        async with self._lock:
            if not self.buffer and not self.overflow_buffer:
                return None
            
            # Collect all remaining chunks
            remaining_chunks = []
            
            # Add overflow buffer first
            if self.overflow_buffer:
                remaining_chunks.extend(self.overflow_buffer)
                self.overflow_buffer.clear()
            
            # Add all buffered chunks
            while self.buffer:
                audio_data, _ = self.buffer.popleft()
                remaining_chunks.append(audio_data)
                self.total_chunks_processed += 1
            
            if not remaining_chunks:
                return None
            
            logger.info(f"Flushing {len(remaining_chunks)} remaining audio chunks")
            return b''.join(remaining_chunks)
    
    async def clear(self):
        """Clear the buffer"""
        async with self._lock:
            self.buffer.clear()
            self.overflow_buffer.clear()
            self.silence_chunks = 0
            self.is_speech_active = False
            self.consecutive_speech_chunks = 0
            logger.debug("Audio buffer cleared")
    
    def clear_sync(self):
        """Synchronous version of clear"""
        self.buffer.clear()
        self.overflow_buffer.clear()
        self.silence_chunks = 0
        self.is_speech_active = False
        self.consecutive_speech_chunks = 0
    
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