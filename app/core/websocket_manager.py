"""
WebSocket connection management for real-time audio streaming
"""
import asyncio
import base64
import json
import logging
from typing import Dict, Optional, Set
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.config import get_settings
from app.core.conversation_state import ConversationState
from app.core.audio_buffer import AudioBuffer
from app.core.latency_tracker import LatencyTracker
from app.services.deepgram_service import DeepgramService
from app.core.orchestrator import Orchestrator
from app.utils.audio_utils import convert_mulaw_to_pcm, convert_pcm_to_mulaw

logger = logging.getLogger(__name__)
settings = get_settings()


class WebSocketConnection:
    """
    Represents a single WebSocket connection for a call
    """
    def __init__(self, websocket: WebSocket, stream_id: str, conversation_state: ConversationState):
        self.websocket = websocket
        self.stream_id = stream_id
        self.conversation_state = conversation_state
        self.audio_buffer = AudioBuffer()
        self.deepgram_service: Optional[DeepgramService] = None
        self.orchestrator: Optional[Orchestrator] = None
        self.latency_tracker = LatencyTracker(stream_id)
        self.is_connected = False
        self.start_time = datetime.utcnow()
        self.tasks: Set[asyncio.Task] = set()
    
    async def initialize(self):
        """
        Initialize services for this connection
        """
        try:
            # Initialize Deepgram for STT
            self.deepgram_service = DeepgramService()
            await self.deepgram_service.connect()
            
            # Initialize orchestrator
            self.orchestrator = Orchestrator(
                conversation_state=self.conversation_state,
                websocket=self.websocket
            )
            
            self.is_connected = True
            logger.info(f"WebSocket connection initialized for stream {self.stream_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket connection: {e}", exc_info=True)
            raise
    
    async def cleanup(self):
        """
        Clean up resources for this connection
        """
        try:
            # Cancel all running tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete cancellation
            if self.tasks:
                await asyncio.gather(*self.tasks, return_exceptions=True)
            
            # Disconnect services
            if self.deepgram_service:
                await self.deepgram_service.disconnect()
            
            if self.orchestrator:
                await self.orchestrator.cleanup()
            
            # Mark as disconnected
            self.is_connected = False
            
            # Log connection duration
            duration = (datetime.utcnow() - self.start_time).total_seconds()
            logger.info(f"WebSocket connection closed for stream {self.stream_id} after {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Error during WebSocket cleanup: {e}", exc_info=True)


class WebSocketManager:
    """
    Manages WebSocket connections for all active calls
    """
    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.conversation_states: Dict[str, ConversationState] = {}
        self._lock = asyncio.Lock()
    
    async def store_conversation_state(self, stream_id: str, state: ConversationState):
        """
        Store conversation state for later retrieval by WebSocket handler
        """
        async with self._lock:
            self.conversation_states[stream_id] = state
            logger.debug(f"Stored conversation state for stream {stream_id}")
    
    async def get_conversation_state(self, stream_id: str) -> Optional[ConversationState]:
        """
        Retrieve stored conversation state
        """
        async with self._lock:
            return self.conversation_states.get(stream_id)
    
    async def handle_media_stream(self, websocket: WebSocket, stream_id: str):
        """
        Handle incoming WebSocket connection for media streaming
        """
        connection = None
        
        try:
            # Accept WebSocket connection
            await websocket.accept()
            logger.info(f"WebSocket connection accepted for stream {stream_id}")
            
            # Retrieve conversation state
            conversation_state = await self.get_conversation_state(stream_id)
            if not conversation_state:
                logger.error(f"No conversation state found for stream {stream_id}")
                await websocket.close(code=1008, reason="No conversation state")
                return
            
            # Create connection object
            connection = WebSocketConnection(websocket, stream_id, conversation_state)
            
            # Store connection
            async with self._lock:
                self.connections[stream_id] = connection
            
            # Initialize connection services
            await connection.initialize()
            
            # Start concurrent tasks for handling the stream
            receive_task = asyncio.create_task(
                self._receive_audio(connection),
                name=f"receive_audio_{stream_id}"
            )
            process_task = asyncio.create_task(
                self._process_transcripts(connection),
                name=f"process_transcripts_{stream_id}"
            )
            monitor_task = asyncio.create_task(
                self._monitor_latency(connection),
                name=f"monitor_latency_{stream_id}"
            )
            
            # Track tasks
            connection.tasks.update({receive_task, process_task, monitor_task})
            
            # Wait for any task to complete (usually due to disconnect)
            done, pending = await asyncio.wait(
                connection.tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Log which task completed first
            for task in done:
                if task.exception():
                    logger.error(f"Task {task.get_name()} failed: {task.exception()}")
                else:
                    logger.info(f"Task {task.get_name()} completed normally")
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for stream {stream_id}")
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}", exc_info=True)
        finally:
            # Clean up connection
            if connection:
                await connection.cleanup()
            
            # Remove from active connections
            async with self._lock:
                self.connections.pop(stream_id, None)
                self.conversation_states.pop(stream_id, None)
    
    async def _receive_audio(self, connection: WebSocketConnection):
        """
        Receive audio data from Twilio and forward to Deepgram
        """
        try:
            while connection.is_connected and connection.websocket.client_state == WebSocketState.CONNECTED:
                # Receive message from Twilio
                message = await connection.websocket.receive_text()
                data = json.loads(message)
                
                if data.get('event') == 'media':
                    # Extract audio payload
                    payload = data['media']['payload']
                    timestamp = data.get('sequenceNumber', 0)
                    
                    # Decode from base64
                    audio_data = base64.b64decode(payload)
                    
                    # Convert from μ-law to PCM for Deepgram
                    pcm_data = convert_mulaw_to_pcm(audio_data)
                    
                    # Add to buffer
                    connection.audio_buffer.add(pcm_data, timestamp)
                    
                    # Forward to Deepgram if we have enough data
                    if connection.audio_buffer.has_sufficient_data():
                        audio_chunk = connection.audio_buffer.get_chunk()
                        if audio_chunk and connection.deepgram_service:
                            await connection.deepgram_service.send_audio(audio_chunk)
                    
                    # Track metrics
                    connection.latency_tracker.record_audio_received()
                    
                elif data.get('event') == 'start':
                    # Stream started
                    stream_sid = data['start']['streamSid']
                    logger.info(f"Media stream started: {stream_sid}")
                    connection.conversation_state.twilio_stream_sid = stream_sid
                    
                elif data.get('event') == 'stop':
                    # Stream stopped
                    logger.info(f"Media stream stopped for {connection.stream_id}")
                    connection.is_connected = False
                    break
                    
                elif data.get('event') == 'mark':
                    # Custom mark event (used for tracking)
                    mark_name = data['mark']['name']
                    logger.debug(f"Received mark event: {mark_name}")
                    
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected during audio receive for {connection.stream_id}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
        except Exception as e:
            logger.error(f"Error receiving audio: {e}", exc_info=True)
            raise
    
    async def _process_transcripts(self, connection: WebSocketConnection):
        """
        Process transcripts from Deepgram and generate responses
        """
        try:
            if not connection.deepgram_service or not connection.orchestrator:
                logger.error("Services not initialized for transcript processing")
                return
            
            async for transcript in connection.deepgram_service.receive_transcripts():
                if not connection.is_connected:
                    break
                
                # Process transcript through orchestrator
                await connection.orchestrator.process_transcript(transcript)
                
                # Track latency
                connection.latency_tracker.record_transcript_processed()
                
        except Exception as e:
            logger.error(f"Error processing transcripts: {e}", exc_info=True)
            raise
    
    async def _monitor_latency(self, connection: WebSocketConnection):
        """
        Monitor and report latency metrics
        """
        try:
            while connection.is_connected:
                # Report metrics every 5 seconds
                await asyncio.sleep(5)
                
                metrics = connection.latency_tracker.get_metrics()
                if metrics:
                    logger.info(f"Latency metrics for {connection.stream_id}: {metrics}")
                    
                    # Check if latency is too high
                    if metrics.get('avg_response_time', 0) > settings.MAX_RESPONSE_LATENCY:
                        logger.warning(
                            f"High latency detected for {connection.stream_id}: "
                            f"{metrics['avg_response_time']:.2f}ms"
                        )
                
        except asyncio.CancelledError:
            logger.debug(f"Latency monitoring cancelled for {connection.stream_id}")
        except Exception as e:
            logger.error(f"Error monitoring latency: {e}", exc_info=True)
    
    async def send_audio(self, stream_id: str, audio_data: bytes):
        """
        Send audio data back to Twilio
        """
        try:
            connection = self.connections.get(stream_id)
            if not connection or not connection.is_connected:
                logger.warning(f"No active connection for stream {stream_id}")
                return
            
            # Convert PCM to μ-law for Twilio
            mulaw_data = convert_pcm_to_mulaw(audio_data)
            
            # Encode to base64
            encoded_audio = base64.b64encode(mulaw_data).decode('utf-8')
            
            # Create media message
            message = {
                "event": "media",
                "streamSid": connection.conversation_state.twilio_stream_sid,
                "media": {
                    "payload": encoded_audio
                }
            }
            
            # Send to Twilio
            await connection.websocket.send_text(json.dumps(message))
            
            # Track metrics
            connection.latency_tracker.record_audio_sent()
            
        except Exception as e:
            logger.error(f"Error sending audio: {e}", exc_info=True)
    
    async def send_mark(self, stream_id: str, mark_name: str):
        """
        Send a mark event to track timing
        """
        try:
            connection = self.connections.get(stream_id)
            if not connection or not connection.is_connected:
                return
            
            message = {
                "event": "mark",
                "streamSid": connection.conversation_state.twilio_stream_sid,
                "mark": {
                    "name": mark_name
                }
            }
            
            await connection.websocket.send_text(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Error sending mark: {e}", exc_info=True)
    
    async def cleanup_call(self, call_sid: str):
        """
        Clean up all resources associated with a call
        """
        try:
            # Find connections for this call
            connections_to_close = []
            
            async with self._lock:
                for stream_id, conn in self.connections.items():
                    if conn.conversation_state.call_sid == call_sid:
                        connections_to_close.append(stream_id)
            
            # Close connections
            for stream_id in connections_to_close:
                connection = self.connections.get(stream_id)
                if connection and connection.websocket.client_state == WebSocketState.CONNECTED:
                    await connection.websocket.close()
                    logger.info(f"Closed WebSocket for call {call_sid}, stream {stream_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up call {call_sid}: {e}", exc_info=True)
    
    def is_healthy(self) -> bool:
        """
        Check if the WebSocket manager is healthy
        """
        return True  # Basic health check
    
    def get_active_connections(self) -> int:
        """
        Get number of active connections
        """
        return len(self.connections)
    
    def get_connection_info(self, stream_id: str) -> Optional[dict]:
        """
        Get information about a specific connection
        """
        connection = self.connections.get(stream_id)
        if not connection:
            return None
        
        return {
            "stream_id": stream_id,
            "call_sid": connection.conversation_state.call_sid,
            "is_connected": connection.is_connected,
            "duration": (datetime.utcnow() - connection.start_time).total_seconds(),
            "latency_metrics": connection.latency_tracker.get_metrics()
        }