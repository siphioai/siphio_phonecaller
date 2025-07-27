"""
Conversation state management for phone calls
Tracks state, history, and context for ongoing conversations
"""
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CallStatus(Enum):
    """Call status enumeration"""
    INITIATED = "initiated"
    CONNECTED = "connected"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    TRANSFERRING = "transferring"
    COMPLETED = "completed"
    FAILED = "failed"


class ConversationIntent(Enum):
    """Detected conversation intents"""
    UNKNOWN = "unknown"
    # Appointment-related
    BOOKING_APPOINTMENT = "booking_appointment"
    CANCELING_APPOINTMENT = "canceling_appointment"
    RESCHEDULING_APPOINTMENT = "rescheduling_appointment"
    # Dental-specific
    CLEANING_INQUIRY = "cleaning_inquiry"
    ROOT_CANAL_INQUIRY = "root_canal_inquiry"
    CROWN_INQUIRY = "crown_inquiry"
    FILLING_INQUIRY = "filling_inquiry"
    EXTRACTION_INQUIRY = "extraction_inquiry"
    ORTHODONTICS_INQUIRY = "orthodontics_inquiry"
    COSMETIC_INQUIRY = "cosmetic_inquiry"
    # General
    GENERAL_INQUIRY = "general_inquiry"
    INSURANCE_INQUIRY = "insurance_inquiry"
    PRICING_INQUIRY = "pricing_inquiry"
    HOURS_INQUIRY = "hours_inquiry"
    LOCATION_INQUIRY = "location_inquiry"
    # Urgent/Special
    EMERGENCY = "emergency"
    PAIN_COMPLAINT = "pain_complaint"
    COMPLAINT = "complaint"
    FEEDBACK = "feedback"
    
    def to_dict(self) -> dict:
        """Convert intent to dictionary for serialization"""
        return {
            "value": self.value,
            "name": self.name,
            "category": self._get_category()
        }
    
    def _get_category(self) -> str:
        """Get intent category"""
        if "appointment" in self.value:
            return "appointment"
        elif "inquiry" in self.value and self.value != "general_inquiry":
            return "dental_service"
        elif self in [self.EMERGENCY, self.PAIN_COMPLAINT]:
            return "urgent"
        elif self in [self.COMPLAINT, self.FEEDBACK]:
            return "feedback"
        else:
            return "general"


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation"""
    timestamp: datetime
    speaker: str  # "caller" or "assistant"
    text: str
    confidence: Optional[float] = None
    intent: Optional[ConversationIntent] = None
    entities: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AppointmentContext:
    """Context for appointment-related conversations"""
    appointment_type: Optional[str] = None
    preferred_date: Optional[datetime] = None
    preferred_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    confirmed: bool = False


class ConversationState:
    """
    Manages the state of a phone conversation
    Tracks history, context, and intent throughout the call
    """
    
    def __init__(
        self,
        call_sid: str,
        stream_id: str,
        from_number: str,
        to_number: str,
        client_id: Optional[str] = None
    ):
        """
        Initialize conversation state
        
        Args:
            call_sid: Twilio call SID
            stream_id: Unique stream identifier
            from_number: Caller's phone number
            to_number: Called phone number
            client_id: Optional client/tenant ID for multi-tenancy
        """
        self.call_sid = call_sid
        self.stream_id = stream_id
        self.from_number = from_number
        self.to_number = to_number
        self.client_id = client_id
        
        # Call metadata
        self.start_time = datetime.utcnow()
        self.end_time: Optional[datetime] = None
        self.status = CallStatus.INITIATED
        self.twilio_stream_sid: Optional[str] = None
        
        # Conversation history
        self.conversation_history: List[ConversationTurn] = []
        self.current_intent = ConversationIntent.UNKNOWN
        self.appointment_context = AppointmentContext()
        
        # State management
        self.is_on_hold = False
        self.hold_music_playing = False
        self.transfer_target: Optional[str] = None
        
        # Performance tracking
        self.transcript_queue: asyncio.Queue = asyncio.Queue()
        self.response_times: List[float] = []
        self.interruption_count = 0
        
        # Context and memory
        self.context_variables: Dict[str, Any] = {}
        self.conversation_summary: Optional[str] = None
        
        logger.info(f"Initialized conversation state for call {call_sid}")
    
    def add_turn(
        self,
        speaker: str,
        text: str,
        confidence: Optional[float] = None,
        intent: Optional[ConversationIntent] = None,
        entities: Optional[Dict[str, Any]] = None
    ):
        """
        Add a turn to the conversation history
        
        Args:
            speaker: Who is speaking ("caller" or "assistant")
            text: What was said
            confidence: Speech recognition confidence
            intent: Detected intent
            entities: Extracted entities (dates, names, etc.)
        """
        turn = ConversationTurn(
            timestamp=datetime.utcnow(),
            speaker=speaker,
            text=text,
            confidence=confidence,
            intent=intent,
            entities=entities or {}
        )
        
        self.conversation_history.append(turn)
        
        # Update current intent if provided
        if intent and intent != ConversationIntent.UNKNOWN:
            self.current_intent = intent
            logger.debug(f"Updated intent to: {intent.value}")
    
    def get_recent_context(self, turns: int = 5) -> List[ConversationTurn]:
        """
        Get the most recent conversation turns for context
        
        Args:
            turns: Number of recent turns to retrieve
            
        Returns:
            List of recent conversation turns
        """
        return self.conversation_history[-turns:] if self.conversation_history else []
    
    def get_conversation_text(self, speaker_filter: Optional[str] = None) -> str:
        """
        Get the conversation as text
        
        Args:
            speaker_filter: Optional filter for specific speaker
            
        Returns:
            Formatted conversation text
        """
        turns = self.conversation_history
        if speaker_filter:
            turns = [t for t in turns if t.speaker == speaker_filter]
        
        return "\n".join([
            f"{turn.speaker}: {turn.text}"
            for turn in turns
        ])
    
    def update_appointment_context(self, **kwargs):
        """
        Update appointment context with new information
        
        Args:
            **kwargs: Appointment context fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self.appointment_context, key):
                setattr(self.appointment_context, key, value)
                logger.debug(f"Updated appointment context: {key} = {value}")
    
    def set_status(self, status: CallStatus):
        """
        Update call status
        
        Args:
            status: New call status
        """
        old_status = self.status
        self.status = status
        logger.info(f"Call {self.call_sid} status changed: {old_status.value} -> {status.value}")
        
        if status == CallStatus.COMPLETED:
            self.end_time = datetime.utcnow()
    
    def put_on_hold(self):
        """Put the call on hold"""
        self.is_on_hold = True
        self.hold_music_playing = True
        logger.info(f"Call {self.call_sid} put on hold")
    
    def resume_from_hold(self):
        """Resume the call from hold"""
        self.is_on_hold = False
        self.hold_music_playing = False
        logger.info(f"Call {self.call_sid} resumed from hold")
    
    def record_response_time(self, response_time: float):
        """
        Record response time for performance tracking
        
        Args:
            response_time: Response time in milliseconds
        """
        self.response_times.append(response_time)
    
    def get_average_response_time(self) -> float:
        """
        Get average response time
        
        Returns:
            Average response time in milliseconds
        """
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def increment_interruptions(self):
        """Increment interruption counter"""
        self.interruption_count += 1
    
    def get_call_duration(self) -> float:
        """
        Get call duration in seconds
        
        Returns:
            Duration in seconds
        """
        end = self.end_time or datetime.utcnow()
        return (end - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to dictionary for serialization
        
        Returns:
            Dictionary representation of state
        """
        return {
            "call_sid": self.call_sid,
            "stream_id": self.stream_id,
            "from_number": self.from_number,
            "to_number": self.to_number,
            "client_id": self.client_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value,
            "duration_seconds": self.get_call_duration(),
            "current_intent": self.current_intent.value,
            "appointment_context": {
                "appointment_type": self.appointment_context.appointment_type,
                "preferred_date": self.appointment_context.preferred_date.isoformat() if self.appointment_context.preferred_date else None,
                "preferred_time": self.appointment_context.preferred_time,
                "patient_name": self.appointment_context.patient_name,
                "confirmed": self.appointment_context.confirmed
            },
            "conversation_turns": len(self.conversation_history),
            "average_response_time": self.get_average_response_time(),
            "interruption_count": self.interruption_count,
            "summary": self.conversation_summary
        }