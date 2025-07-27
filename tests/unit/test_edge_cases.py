"""
Edge case tests for the AI Phone Receptionist System
Tests race conditions, missing state, and error scenarios
"""
import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from fastapi import WebSocket
from fastapi.testclient import TestClient

from app.main import app
from app.core.websocket_manager import WebSocketManager, WebSocketConnection
from app.core.conversation_state import ConversationState
from app.core.audio_buffer import AudioBuffer
from app.core.config import get_settings

settings = get_settings()


class TestWebSocketEdgeCases:
    """Test WebSocket edge cases and error conditions"""
    
    @pytest.fixture
    def websocket_manager(self):
        """Create WebSocket manager instance"""
        return WebSocketManager(max_connections=5)
    
    @pytest.mark.asyncio
    async def test_missing_conversation_state(self, websocket_manager):
        """
        Test handling when conversation state is missing (race condition)
        """
        # Create mock WebSocket
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()
        
        # Try to handle stream without storing state first
        stream_id = "test_stream_missing_state"
        
        # Should close connection with proper error code
        await websocket_manager.handle_media_stream(mock_websocket, stream_id)
        
        # Verify WebSocket was accepted then closed
        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called_once_with(code=1011, reason="Invalid state")
    
    @pytest.mark.asyncio
    async def test_max_connections_enforcement(self, websocket_manager):
        """
        Test that max connections limit is enforced
        """
        # Fill up to max connections
        for i in range(5):
            state = ConversationState(
                call_sid=f"CA{i}",
                stream_id=f"stream_{i}",
                from_number="+1234567890",
                to_number="+0987654321"
            )
            await websocket_manager.store_conversation_state(f"stream_{i}", state)
            
            # Mock connection
            mock_conn = MagicMock()
            websocket_manager.connections[f"stream_{i}"] = mock_conn
        
        # Try to add one more
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.close = AsyncMock()
        
        # Should reject before accepting
        await websocket_manager.handle_media_stream(mock_websocket, "stream_overflow")
        
        # Should close with capacity error
        mock_websocket.close.assert_called_once_with(code=1008, reason="Server at capacity")
        # Should NOT call accept
        mock_websocket.accept.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_race_condition_double_check(self, websocket_manager):
        """
        Test race condition protection with double-check pattern
        """
        # Set up state
        state = ConversationState(
            call_sid="CA_race",
            stream_id="stream_race",
            from_number="+1234567890",
            to_number="+0987654321"
        )
        await websocket_manager.store_conversation_state("stream_race", state)
        
        # Fill connections to just below limit
        for i in range(4):
            websocket_manager.connections[f"dummy_{i}"] = MagicMock()
        
        # Create multiple websockets that will try to connect simultaneously
        websockets_list = []
        for i in range(3):  # Try 3 connections when only 1 slot available
            mock_ws = AsyncMock(spec=WebSocket)
            mock_ws.accept = AsyncMock()
            mock_ws.close = AsyncMock()
            websockets_list.append(mock_ws)
        
        # Simulate concurrent connection attempts
        tasks = [
            websocket_manager.handle_media_stream(ws, "stream_race")
            for ws in websockets_list
        ]
        
        # Run concurrently with slight delays to increase race likelihood
        async def delayed_task(task, delay):
            await asyncio.sleep(delay)
            return await task
        
        results = await asyncio.gather(
            *[delayed_task(task, i * 0.001) for i, task in enumerate(tasks)],
            return_exceptions=True
        )
        
        # At least one should be rejected
        close_calls = sum(1 for ws in websockets_list if ws.close.called)
        assert close_calls >= 2, "At least 2 connections should be rejected"


class TestAudioBufferEdgeCases:
    """Test audio buffer edge cases"""
    
    @pytest.fixture
    def audio_buffer(self):
        """Create audio buffer instance"""
        return AudioBuffer(
            sample_rate=8000,
            chunk_duration_ms=20,
            buffer_duration_ms=200,
            max_buffer_size=100,
            vad_enabled=True
        )
    
    @pytest.mark.asyncio
    async def test_buffer_overflow_handling(self, audio_buffer):
        """
        Test buffer behavior when approaching max capacity
        """
        # Fill buffer to near capacity
        for i in range(95):
            await audio_buffer.add(b'\x00' * 160, i)
        
        # Check warning threshold
        assert len(audio_buffer.buffer) == 95
        
        # Add more to exceed warning threshold
        for i in range(10):
            await audio_buffer.add(b'\x00' * 160, 95 + i)
        
        # Should be capped at max_buffer_size
        assert len(audio_buffer.buffer) <= audio_buffer.max_buffer_size
    
    @pytest.mark.asyncio
    async def test_flush_with_remnants(self, audio_buffer):
        """
        Test flushing buffer with uneven chunks
        """
        # Add uneven chunks that don't align with buffer size
        await audio_buffer.add(b'\x00' * 160, 0)  # 160 bytes
        await audio_buffer.add(b'\x00' * 80, 1)   # 80 bytes (half chunk)
        await audio_buffer.add(b'\x00' * 240, 2)  # 240 bytes (1.5 chunks)
        
        # Flush remaining
        remaining = await audio_buffer.flush()
        
        assert remaining is not None
        assert len(remaining) == 480  # Total bytes added
        assert len(audio_buffer.buffer) == 0  # Buffer should be empty
    
    def test_vad_with_corrupted_audio(self, audio_buffer):
        """
        Test VAD behavior with corrupted/invalid audio data
        """
        # Test with empty data
        result = audio_buffer._is_silence(b'')
        assert result is False  # Should handle gracefully
        
        # Test with odd-length data (zeros should be detected as silence)
        result = audio_buffer._is_silence(b'\x00' * 159)  # Not divisible by sample size
        assert result is True  # Zeros = silence
        
        # Test with non-audio data (random bytes with energy)
        result = audio_buffer._is_silence(b'not audio data')
        # This should have energy and not be silence
        assert result is False  # Random data should have energy
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, audio_buffer):
        """
        Test thread-safe access to buffer
        """
        async def add_chunks(start_idx):
            for i in range(20):
                await audio_buffer.add(b'\x00' * 160, start_idx + i)
                await asyncio.sleep(0.001)  # Small delay
        
        async def get_chunks():
            chunks = []
            for _ in range(10):
                if await audio_buffer.has_sufficient_data():
                    chunk = await audio_buffer.get_chunk()
                    if chunk:
                        chunks.append(chunk)
                await asyncio.sleep(0.002)
            return chunks
        
        # Run concurrent operations
        results = await asyncio.gather(
            add_chunks(0),
            add_chunks(1000),
            get_chunks(),
            get_chunks(),
            return_exceptions=True
        )
        
        # Should complete without exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Concurrent access failed: {exceptions}"


class TestConversationStateEdgeCases:
    """Test conversation state edge cases"""
    
    @pytest.fixture
    def conversation_state(self):
        """Create conversation state instance"""
        return ConversationState(
            call_sid="CA123",
            stream_id="stream123",
            from_number="+1234567890",
            to_number="+0987654321"
        )
    
    def test_intent_enum_serialization(self, conversation_state):
        """
        Test that all intents can be serialized properly
        """
        from app.core.conversation_state import ConversationIntent
        
        # Test each intent
        for intent in ConversationIntent:
            conversation_state.current_intent = intent
            
            # Should serialize without error
            state_dict = conversation_state.to_dict()
            assert state_dict["current_intent"] == intent.value
            
            # Test to_dict method on intent
            intent_dict = intent.to_dict()
            assert "value" in intent_dict
            assert "name" in intent_dict
            assert "category" in intent_dict
    
    def test_appointment_context_partial_update(self, conversation_state):
        """
        Test partial updates to appointment context
        """
        # Update with valid fields
        conversation_state.update_appointment_context(
            appointment_type="cleaning",
            duration_minutes=60,
            invalid_field="should be ignored"
        )
        
        assert conversation_state.appointment_context.appointment_type == "cleaning"
        assert conversation_state.appointment_context.duration_minutes == 60
        assert not hasattr(conversation_state.appointment_context, "invalid_field")
    
    def test_conversation_history_overflow(self, conversation_state):
        """
        Test behavior with very large conversation history
        """
        # Add many turns
        for i in range(1000):
            conversation_state.add_turn(
                speaker="caller" if i % 2 == 0 else "assistant",
                text=f"Message {i}",
                confidence=0.95
            )
        
        # Should handle large history
        assert len(conversation_state.conversation_history) == 1000
        
        # Get recent context should work
        recent = conversation_state.get_recent_context(5)
        assert len(recent) == 5
        assert recent[-1].text == "Message 999"
        
        # Serialization should work
        state_dict = conversation_state.to_dict()
        assert state_dict["conversation_turns"] == 1000


class TestWebhookEdgeCases:
    """Test webhook edge cases"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @patch('app.api.webhooks.validate_twilio_request')
    def test_webhook_with_invalid_phone_numbers(self, mock_validate, client):
        """
        Test webhook handling with malformed phone numbers
        """
        mock_validate.return_value = True
        
        # Various invalid phone formats
        invalid_numbers = [
            "",  # Empty
            "not a phone number",
            "123",  # Too short
            "+1" * 50,  # Too long
            "<script>alert('xss')</script>",  # XSS attempt
            None  # None value
        ]
        
        for invalid_number in invalid_numbers:
            data = {
                "CallSid": "CA123",
                "From": invalid_number or "",
                "To": "+0987654321",
                "CallStatus": "in-progress"
            }
            
            response = client.post("/api/webhooks/incoming-call", data=data)
            
            # Should handle gracefully
            assert response.status_code in [200, 400], f"Failed for number: {invalid_number}"
    
    @patch('app.api.webhooks.validate_twilio_request')
    @patch('app.api.webhooks.websocket_manager')
    async def test_webhook_storage_failure(self, mock_ws_manager, mock_validate, client):
        """
        Test webhook behavior when state storage fails
        """
        mock_validate.return_value = True
        
        # Mock storage failure
        mock_ws_manager.store_conversation_state = AsyncMock(
            side_effect=Exception("Storage unavailable")
        )
        
        data = {
            "CallSid": "CA123",
            "From": "+1234567890",
            "To": "+0987654321",
            "CallStatus": "in-progress"
        }
        
        response = client.post("/api/webhooks/incoming-call", data=data)
        
        # Should return error TwiML
        assert response.status_code == 200
        assert "technical difficulties" in response.text
    
    def test_webhook_concurrent_requests(self, client):
        """
        Test handling concurrent webhook requests
        """
        import concurrent.futures
        import threading
        
        # Use threading for true concurrency in tests
        def make_request(call_id):
            with TestClient(app) as client:
                data = {
                    "CallSid": f"CA{call_id}",
                    "From": "+1234567890",
                    "To": "+0987654321",
                    "CallStatus": "in-progress"
                }
                return client.post("/api/webhooks/incoming-call", data=data)
        
        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should complete
        assert len(results) == 20
        success_count = sum(1 for r in results if r.status_code == 200)
        assert success_count >= 18, f"Only {success_count}/20 requests succeeded"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
