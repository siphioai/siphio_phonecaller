"""
Audio utility functions for format conversion
Handles μ-law (G.711) to PCM conversion for Twilio/Deepgram compatibility
"""
import logging
import numpy as np
from typing import Union

logger = logging.getLogger(__name__)


# μ-law constants
ULAW_BIAS = 0x84
ULAW_CLIP = 32635
ULAW_MAX = 0xFF


def convert_mulaw_to_pcm(mulaw_data: bytes) -> bytes:
    """
    Convert μ-law encoded audio to PCM
    μ-law is used by Twilio for compressed audio transmission
    
    Args:
        mulaw_data: μ-law encoded audio bytes (8-bit)
        
    Returns:
        PCM encoded audio bytes (16-bit little endian)
    """
    if not mulaw_data:
        return b''
    
    try:
        # μ-law to PCM conversion table (pre-computed for efficiency)
        # This avoids recalculating the same values repeatedly
        ulaw_to_pcm_table = _get_ulaw_to_pcm_table()
        
        # Convert bytes to numpy array for efficient processing
        ulaw_array = np.frombuffer(mulaw_data, dtype=np.uint8)
        
        # Apply conversion using lookup table
        pcm_array = np.array([ulaw_to_pcm_table[u] for u in ulaw_array], dtype=np.int16)
        
        # Convert to bytes (little endian)
        pcm_bytes = pcm_array.tobytes()
        
        logger.debug(f"Converted {len(mulaw_data)} bytes μ-law to {len(pcm_bytes)} bytes PCM")
        return pcm_bytes
        
    except Exception as e:
        logger.error(f"Error converting μ-law to PCM: {e}")
        # Return empty bytes on error to prevent crash
        return b''


def convert_pcm_to_mulaw(pcm_data: bytes) -> bytes:
    """
    Convert PCM encoded audio to μ-law
    Used for sending audio back to Twilio
    
    Args:
        pcm_data: PCM encoded audio bytes (16-bit little endian)
        
    Returns:
        μ-law encoded audio bytes (8-bit)
    """
    if not pcm_data:
        return b''
    
    try:
        # Ensure we have an even number of bytes (16-bit samples)
        if len(pcm_data) % 2 != 0:
            logger.warning("PCM data has odd number of bytes, truncating last byte")
            pcm_data = pcm_data[:-1]
        
        # Convert bytes to numpy array
        pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
        
        # Convert each PCM sample to μ-law
        ulaw_array = np.array([_pcm_to_ulaw(sample) for sample in pcm_array], dtype=np.uint8)
        
        # Convert to bytes
        ulaw_bytes = ulaw_array.tobytes()
        
        logger.debug(f"Converted {len(pcm_data)} bytes PCM to {len(ulaw_bytes)} bytes μ-law")
        return ulaw_bytes
        
    except Exception as e:
        logger.error(f"Error converting PCM to μ-law: {e}")
        # Return empty bytes on error to prevent crash
        return b''


def _get_ulaw_to_pcm_table() -> list:
    """
    Generate μ-law to PCM conversion table
    Pre-computing this table improves performance significantly
    
    Returns:
        List of 256 PCM values corresponding to μ-law values 0-255
    """
    table = []
    for ulaw in range(256):
        # Invert all bits
        ulaw = ~ulaw & 0xFF
        
        # Extract sign bit
        sign = (ulaw & 0x80)
        
        # Extract exponent bits
        exponent = (ulaw >> 4) & 0x07
        
        # Extract mantissa bits
        mantissa = ulaw & 0x0F
        
        # Compute sample value
        sample = (mantissa << (exponent + 3)) + ULAW_BIAS
        sample = sample << (exponent + 3)
        
        # Apply sign bit
        if sign != 0:
            sample = -sample
            
        table.append(sample)
    
    return table


def _pcm_to_ulaw(pcm_val: int) -> int:
    """
    Convert a single PCM sample to μ-law
    
    Args:
        pcm_val: 16-bit signed PCM sample
        
    Returns:
        8-bit μ-law encoded value
    """
    # Handle sign
    sign = 0
    if pcm_val < 0:
        sign = 0x80
        pcm_val = -pcm_val
        
    # Clip to maximum value
    if pcm_val > ULAW_CLIP:
        pcm_val = ULAW_CLIP
        
    # Add bias
    pcm_val += ULAW_BIAS
    
    # Find exponent
    exponent = 7
    mask = 0x4000
    while exponent > 0:
        if pcm_val & mask:
            break
        exponent -= 1
        mask >>= 1
        
    # Extract mantissa
    mantissa = (pcm_val >> (exponent + 3)) & 0x0F
    
    # Combine components
    ulaw = sign | (exponent << 4) | mantissa
    
    # Invert all bits
    return ~ulaw & 0xFF


def resample_audio(audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
    """
    Resample audio from one sample rate to another
    
    Args:
        audio_data: Audio data to resample (16-bit PCM)
        from_rate: Source sample rate (e.g., 8000 for Twilio)
        to_rate: Target sample rate (e.g., 16000 for Deepgram)
        
    Returns:
        Resampled audio data
    """
    if not audio_data:
        return b''
    
    if from_rate == to_rate:
        # No resampling needed
        return audio_data
    
    try:
        # Ensure we have an even number of bytes (16-bit samples)
        if len(audio_data) % 2 != 0:
            logger.warning("Audio data has odd number of bytes, truncating last byte")
            audio_data = audio_data[:-1]
        
        # Convert to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Calculate resampling ratio
        ratio = to_rate / from_rate
        
        # Calculate new length
        new_length = int(len(audio_array) * ratio)
        
        # Simple linear interpolation resampling
        # For production, consider using scipy.signal.resample for better quality
        old_indices = np.arange(len(audio_array))
        new_indices = np.linspace(0, len(audio_array) - 1, new_length)
        
        # Interpolate
        resampled_array = np.interp(new_indices, old_indices, audio_array)
        
        # Convert back to int16
        resampled_array = np.round(resampled_array).astype(np.int16)
        
        # Convert to bytes
        resampled_bytes = resampled_array.tobytes()
        
        logger.debug(f"Resampled audio from {from_rate}Hz to {to_rate}Hz ({len(audio_data)} bytes to {len(resampled_bytes)} bytes)")
        return resampled_bytes
        
    except Exception as e:
        logger.error(f"Error resampling audio: {e}")
        # Return original data on error
        return audio_data