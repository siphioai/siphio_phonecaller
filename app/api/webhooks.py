"""
Webhook endpoints for Twilio integration
"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import PlainTextResponse
import xml.etree.ElementTree as ET
from twilio.twiml.voice_response import VoiceResponse, Stream
from twilio.request_validator import RequestValidator

from app.core.config import get_settings
from app.core.websocket_manager import WebSocketManager
from app.core.conversation_state import ConversationState
from app.models.call import CallRecord
from app.core.security_utils import generate_secure_token, audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

settings = get_settings()
websocket_manager = WebSocketManager(max_connections=settings.MAX_CONCURRENT_CALLS)


def validate_twilio_request(request: Request) -> bool:
    """
    Validate that the request came from Twilio
    
    Args:
        request: FastAPI request object
        
    Returns:
        True if request is valid from Twilio
    """
    # Check if validation should be skipped (development mode with explicit flag)
    if settings.IS_DEVELOPMENT and not settings.TWILIO_VALIDATE_REQUESTS:
        # Only skip if explicitly disabled in dev mode
        if settings.ENVIRONMENT == "development":
            logger.warning("Skipping Twilio request validation in development mode (TWILIO_VALIDATE_REQUESTS=False)")
            return True
    
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    
    # Get the full URL
    url = str(request.url)
    
    # Get the signature from headers
    signature = request.headers.get('X-Twilio-Signature', '')
    
    # Get POST parameters
    # Note: This assumes form data. Adjust if using JSON
    params = dict(request.query_params)
    
    # Validate the request
    is_valid = validator.validate(url, params, signature)
    
    if not is_valid:
        logger.warning(f"Invalid Twilio request signature from {request.client.host}")
    
    return is_valid


def create_twiml_response(
    greeting: Optional[str] = None,
    websocket_url: Optional[str] = None,
    voice: str = 'alice',
    language: str = 'en-US'
) -> str:
    """
    Create a TwiML response with proper defaults
    
    Args:
        greeting: Optional greeting message
        websocket_url: Optional WebSocket URL for streaming
        voice: Voice to use for speech (default: alice)
        language: Language for speech (default: en-US)
        
    Returns:
        TwiML XML string
    """
    response = VoiceResponse()
    
    # Use default greeting if none provided
    if greeting is None:
        greeting = "Thank you for calling. How may I assist you today?"
    
    # Say greeting
    response.say(greeting, voice=voice, language=language)
    
    # Add stream if URL provided
    if websocket_url:
        stream = Stream(url=websocket_url)
        response.append(stream)
    
    return str(response)


@router.post("/incoming-call")
@audit_log("incoming_call_webhook")
async def handle_incoming_call(request: Request) -> Response:
    """
    Handle incoming call webhook from Twilio
    Returns TwiML response to establish WebSocket connection
    
    Expected Twilio parameters:
    - CallSid: Unique identifier for the call
    - From: Caller's phone number
    - To: Called phone number
    - CallStatus: Current status of the call
    """
    try:
        # Validate request is from Twilio
        if not validate_twilio_request(request):
            raise HTTPException(status_code=403, detail="Invalid request signature")
        
        # Parse form data from Twilio
        form_data = await request.form()
        
        # Extract call information
        call_sid = form_data.get('CallSid')
        from_number = form_data.get('From')
        to_number = form_data.get('To')
        call_status = form_data.get('CallStatus')
        
        if not all([call_sid, from_number, to_number]):
            logger.error("Missing required Twilio parameters")
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        logger.info(f"Incoming call: {call_sid} from {from_number} to {to_number} (status: {call_status})")
        
        # Generate unique stream ID for this call
        stream_id = f"{call_sid}_{generate_secure_token(8)}"
        
        # Initialize conversation state for this call
        conversation_state = ConversationState(
            call_sid=call_sid,
            stream_id=stream_id,
            from_number=from_number,
            to_number=to_number
        )
        
        # Store conversation state (will be retrieved by WebSocket handler)
        await websocket_manager.store_conversation_state(stream_id, conversation_state)
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Get client configuration for custom greeting
        # TODO: Implement client lookup based on to_number
        greeting = "Thank you for calling. How may I assist you today?"
        
        # Say initial greeting
        response.say(greeting, voice='alice')
        
        # Start bi-directional streaming
        # Construct WebSocket URL
        ws_protocol = "wss" if settings.USE_HTTPS else "ws"
        ws_host = settings.WEBSOCKET_HOST or request.headers.get('host', 'localhost')
        ws_url = f"{ws_protocol}://{ws_host}/media-stream/{stream_id}"
        
        logger.info(f"Starting media stream to: {ws_url}")
        
        stream = Stream(url=ws_url)
        stream.parameter(name='streamId', value=stream_id)
        stream.parameter(name='callSid', value=call_sid)
        response.append(stream)
        
        # Return TwiML response
        return Response(
            content=str(response),
            media_type="application/xml",
            headers={"Cache-Control": "no-cache"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}", exc_info=True)
        
        # Return error TwiML
        error_response = VoiceResponse()
        error_response.say(
            "We're experiencing technical difficulties. Please try again later.",
            voice='alice'
        )
        error_response.hangup()
        
        return Response(
            content=str(error_response),
            media_type="application/xml"
        )


@router.post("/call-status")
async def handle_call_status(request: Request) -> PlainTextResponse:
    """
    Handle call status updates from Twilio
    Called when call state changes (ringing, answered, completed, etc.)
    """
    try:
        # Validate request
        if not validate_twilio_request(request):
            raise HTTPException(status_code=403, detail="Invalid request signature")
        
        # Parse form data
        form_data = await request.form()
        
        call_sid = form_data.get('CallSid')
        call_status = form_data.get('CallStatus')
        call_duration = form_data.get('CallDuration')
        
        logger.info(f"Call status update: {call_sid} - {call_status} (duration: {call_duration}s)")
        
        # Handle different statuses
        if call_status == 'completed':
            # Call ended - trigger cleanup
            await websocket_manager.cleanup_call(call_sid)
            
            # TODO: Save call record to database
            # TODO: Send SMS confirmation if appointment was booked
            
        elif call_status == 'failed' or call_status == 'busy' or call_status == 'no-answer':
            logger.warning(f"Call failed: {call_sid} - {call_status}")
            await websocket_manager.cleanup_call(call_sid)
        
        return PlainTextResponse("OK")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling call status: {e}", exc_info=True)
        return PlainTextResponse("Error", status_code=500)


@router.post("/recording-status")
async def handle_recording_status(request: Request) -> PlainTextResponse:
    """
    Handle recording status updates from Twilio
    Used if call recording is enabled for compliance
    """
    try:
        # Validate request
        if not validate_twilio_request(request):
            raise HTTPException(status_code=403, detail="Invalid request signature")
        
        # Parse form data
        form_data = await request.form()
        
        call_sid = form_data.get('CallSid')
        recording_sid = form_data.get('RecordingSid')
        recording_status = form_data.get('RecordingStatus')
        recording_url = form_data.get('RecordingUrl')
        
        logger.info(f"Recording status: {recording_sid} for call {call_sid} - {recording_status}")
        
        if recording_status == 'completed' and recording_url:
            # TODO: Download and securely store recording
            # TODO: Update call record with recording URL
            pass
        
        return PlainTextResponse("OK")
        
    except Exception as e:
        logger.error(f"Error handling recording status: {e}", exc_info=True)
        return PlainTextResponse("Error", status_code=500)


@router.post("/sms-status")
async def handle_sms_status(request: Request) -> PlainTextResponse:
    """
    Handle SMS delivery status updates from Twilio
    Used to track appointment confirmation delivery
    """
    try:
        # Validate request
        if not validate_twilio_request(request):
            raise HTTPException(status_code=403, detail="Invalid request signature")
        
        # Parse form data
        form_data = await request.form()
        
        message_sid = form_data.get('MessageSid')
        message_status = form_data.get('MessageStatus')
        to_number = form_data.get('To')
        error_code = form_data.get('ErrorCode')
        
        logger.info(f"SMS status: {message_sid} to {to_number} - {message_status}")
        
        if error_code:
            logger.error(f"SMS delivery failed: {message_sid} - Error {error_code}")
            # TODO: Implement retry logic or alternative notification
        
        return PlainTextResponse("OK")
        
    except Exception as e:
        logger.error(f"Error handling SMS status: {e}", exc_info=True)
        return PlainTextResponse("Error", status_code=500)


@router.get("/health")
async def webhook_health_check() -> dict:
    """
    Health check endpoint for webhook service
    """
    return {
        "status": "healthy",
        "service": "webhooks",
        "twilio_configured": bool(settings.TWILIO_ACCOUNT_SID),
        "websocket_manager_active": websocket_manager.is_healthy()
    }