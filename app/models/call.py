"""
Call record model with PHI encryption
"""
from datetime import datetime
from typing import Optional

from app.core.security_utils import encryption_manager, mask_phone


class CallRecord:
    """
    Call record model with encrypted PHI fields
    Stores call metadata and encrypted conversation data
    """
    
    def __init__(
        self,
        call_sid: str,
        from_number: str,
        to_number: str,
        stream_id: str
    ):
        self.call_sid = call_sid
        # Store encrypted phone numbers for PHI compliance
        self._from_number_encrypted = encryption_manager.encrypt(from_number)
        self._to_number_encrypted = encryption_manager.encrypt(to_number)
        self.stream_id = stream_id
        self.start_time = datetime.utcnow()
        self.end_time: Optional[datetime] = None
        # Store encrypted transcript and summary
        self._transcript_encrypted: Optional[str] = None
        self._summary_encrypted: Optional[str] = None
        self.appointment_booked = False
        
    @property
    def from_number(self) -> str:
        """Get decrypted from number"""
        return encryption_manager.decrypt(self._from_number_encrypted)
    
    @property
    def from_number_masked(self) -> str:
        """Get masked from number for logging/display"""
        return mask_phone(self.from_number)
    
    @property
    def to_number(self) -> str:
        """Get decrypted to number"""
        return encryption_manager.decrypt(self._to_number_encrypted)
    
    @property
    def to_number_masked(self) -> str:
        """Get masked to number for logging/display"""
        return mask_phone(self.to_number)
    
    @property
    def transcript(self) -> Optional[str]:
        """Get decrypted transcript"""
        if not self._transcript_encrypted:
            return None
        return encryption_manager.decrypt(self._transcript_encrypted)
    
    @transcript.setter
    def transcript(self, value: Optional[str]):
        """Set encrypted transcript"""
        if value:
            self._transcript_encrypted = encryption_manager.encrypt(value)
        else:
            self._transcript_encrypted = None
    
    @property
    def summary(self) -> Optional[str]:
        """Get decrypted summary"""
        if not self._summary_encrypted:
            return None
        return encryption_manager.decrypt(self._summary_encrypted)
    
    @summary.setter
    def summary(self, value: Optional[str]):
        """Set encrypted summary"""
        if value:
            self._summary_encrypted = encryption_manager.encrypt(value)
        else:
            self._summary_encrypted = None
    
    def end_call(self):
        """Mark call as ended"""
        self.end_time = datetime.utcnow()
        
    def add_transcript(self, text: str):
        """Add to transcript with proper concatenation"""
        if not text:
            return
            
        current = self.transcript
        if current:
            self.transcript = f"{current} {text}"
        else:
            self.transcript = text
    
    def get_duration_seconds(self) -> Optional[float]:
        """Get call duration in seconds"""
        if not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self, include_phi: bool = False) -> dict:
        """
        Convert to dictionary for serialization
        
        Args:
            include_phi: Whether to include PHI fields (decrypted)
            
        Returns:
            Dictionary representation
        """
        data = {
            "call_sid": self.call_sid,
            "stream_id": self.stream_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.get_duration_seconds(),
            "appointment_booked": self.appointment_booked
        }
        
        if include_phi:
            # Include decrypted PHI
            data.update({
                "from_number": self.from_number,
                "to_number": self.to_number,
                "transcript": self.transcript,
                "summary": self.summary
            })
        else:
            # Include only masked phone numbers
            data.update({
                "from_number_masked": self.from_number_masked,
                "to_number_masked": self.to_number_masked,
                "has_transcript": bool(self._transcript_encrypted),
                "has_summary": bool(self._summary_encrypted)
            })
        
        return data