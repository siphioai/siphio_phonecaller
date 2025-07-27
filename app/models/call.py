"""
Call record model for database storage
Placeholder implementation - will be completed in Week 1: Database Setup
"""
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CallRecord:
    """
    Placeholder for call record model
    Will store call information in database
    """
    call_sid: str
    from_number: str
    to_number: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    status: str = "initiated"
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    appointment_booked: bool = False
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "call_sid": self.call_sid,
            "from_number": self.from_number,
            "to_number": self.to_number,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "recording_url": self.recording_url,
            "transcript": self.transcript,
            "summary": self.summary,
            "appointment_booked": self.appointment_booked,
            "metadata": self.metadata
        }