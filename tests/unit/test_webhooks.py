"""
Unit tests for Twilio webhook endpoints
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import Request
import xml.etree.ElementTree as ET

from app.main import app
from app.core.conversation_state import ConversationState
from app.core.config import get_settings

settings = get_settings()


class TestWebhookEndpoints:
    """Test Twilio webhook functionality"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def twilio_form_data(self):
        """Sample Twilio webhook form data"""
        return {
            "CallSid": "CA123456789",
            "From": "+1234567890",
            "To": "+0987654321",
            "CallStatus": "in-progress",
            "Direction": "inbound",
            "AccountSid": "AC123456789"
        }
    
    @patch('app.api.webhooks.validate_twilio_request')
    @patch('app.api.webhooks.websocket_manager')
    async def test_incoming_call_success(self, mock_ws_manager, mock_validate, client, twilio_form_data):
        """Test successful incoming call webhook"""
        # Mock validation
        mock_validate.return_value = True
        
        # Mock WebSocket manager with proper async mock
        mock_ws_manager.store_conversation_state = AsyncMock(return_value=None)
        
        # Make request
        response = client.post(
            "/api/webhooks/incoming-call",
            data=twilio_form_data
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        
        # Parse TwiML response
        root = ET.fromstring(response.text)
        assert root.tag == "Response"
        
        # Check for Say element
        say_elements = root.findall("Say")
        assert len(say_elements) == 1
        assert "Thank you for calling" in say_elements[0].text
        
        # Check for Stream element
        stream_elements = root.findall("Stream")
        assert len(stream_elements) == 1
        stream = stream_elements[0]
        assert stream.get("url").startswith("wss://") or stream.get("url").startswith("ws://")
        
        # Verify conversation state was stored
        mock_ws_manager.store_conversation_state.assert_called_once()
    
    @patch('app.api.webhooks.validate_twilio_request')
    def test_incoming_call_invalid_signature(self, mock_validate, client, twilio_form_data):
        """Test incoming call with invalid Twilio signature"""
        mock_validate.return_value = False
        
        response = client.post(
            "/api/webhooks/incoming-call",
            data=twilio_form_data
        )
        
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid request signature"
    
    @patch('app.api.webhooks.validate_twilio_request')
    def test_incoming_call_missing_params(self, mock_validate, client):
        """Test incoming call with missing required parameters"""
        mock_validate.return_value = True
        
        response = client.post(
            "/api/webhooks/incoming-call",
            data={"CallSid": "CA123"}  # Missing From and To
        )
        
        assert response.status_code == 400
        assert response.json()["detail"] == "Missing required parameters"
    
    @pytest.mark.asyncio
    @patch('app.api.webhooks.validate_twilio_request')
    @patch('app.api.webhooks.websocket_manager')
    async def test_incoming_call_error_handling(self, mock_ws_manager, mock_validate, client, twilio_form_data):
        """Test error handling in incoming call webhook"""
        mock_validate.return_value = True
        
        # Mock WebSocket manager to raise error
        mock_ws_manager.store_conversation_state = AsyncMock(side_effect=Exception("Storage error"))
        
        response = client.post(
            "/api/webhooks/incoming-call",
            data=twilio_form_data
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        
        # Should return error TwiML
        root = ET.fromstring(response.text)
        say_elements = root.findall("Say")
        assert len(say_elements) == 1
        assert "technical difficulties" in say_elements[0].text
        
        # Should include Hangup
        hangup_elements = root.findall("Hangup")
        assert len(hangup_elements) == 1
    
    @pytest.mark.asyncio
    @patch('app.api.webhooks.validate_twilio_request')
    @patch('app.api.webhooks.websocket_manager')
    async def test_call_status_completed(self, mock_ws_manager, mock_validate, client):
        """Test call status webhook for completed call"""
        mock_validate.return_value = True
        mock_ws_manager.cleanup_call = AsyncMock()
        
        response = client.post(
            "/api/webhooks/call-status",
            data={
                "CallSid": "CA123456789",
                "CallStatus": "completed",
                "CallDuration": "120"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "OK"
        
        # Verify cleanup was called
        mock_ws_manager.cleanup_call.assert_called_once_with("CA123456789")
    
    @pytest.mark.asyncio
    @patch('app.api.webhooks.validate_twilio_request')
    @patch('app.api.webhooks.websocket_manager')
    async def test_call_status_failed(self, mock_ws_manager, mock_validate, client):
        """Test call status webhook for failed call"""
        mock_validate.return_value = True
        mock_ws_manager.cleanup_call = AsyncMock()
        
        response = client.post(
            "/api/webhooks/call-status",
            data={
                "CallSid": "CA123456789",
                "CallStatus": "failed"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "OK"
        
        # Verify cleanup was called
        mock_ws_manager.cleanup_call.assert_called_once_with("CA123456789")
    
    @patch('app.api.webhooks.validate_twilio_request')
    def test_recording_status(self, mock_validate, client):
        """Test recording status webhook"""
        mock_validate.return_value = True
        
        response = client.post(
            "/api/webhooks/recording-status",
            data={
                "CallSid": "CA123456789",
                "RecordingSid": "RE123456789",
                "RecordingStatus": "completed",
                "RecordingUrl": "https://api.twilio.com/recordings/RE123456789"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "OK"
    
    @patch('app.api.webhooks.validate_twilio_request')
    def test_sms_status(self, mock_validate, client):
        """Test SMS status webhook"""
        mock_validate.return_value = True
        
        response = client.post(
            "/api/webhooks/sms-status",
            data={
                "MessageSid": "SM123456789",
                "MessageStatus": "delivered",
                "To": "+1234567890"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "OK"
    
    @patch('app.api.webhooks.validate_twilio_request')
    def test_sms_status_error(self, mock_validate, client):
        """Test SMS status webhook with error"""
        mock_validate.return_value = True
        
        response = client.post(
            "/api/webhooks/sms-status",
            data={
                "MessageSid": "SM123456789",
                "MessageStatus": "failed",
                "To": "+1234567890",
                "ErrorCode": "30003"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "OK"
    
    def test_webhook_health_check(self, client):
        """Test webhook health check endpoint"""
        response = client.get("/api/webhooks/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "webhooks"
        assert "twilio_configured" in data
        assert "websocket_manager_active" in data


class TestRequestValidation:
    """Test Twilio request validation"""
    
    @patch('app.api.webhooks.settings')
    def test_validate_request_development_mode(self, mock_settings):
        """Test request validation in development mode"""
        from app.api.webhooks import validate_twilio_request
        
        # Mock settings
        mock_settings.IS_DEVELOPMENT = True
        mock_settings.TWILIO_VALIDATE_REQUESTS = False
        mock_settings.TWILIO_AUTH_TOKEN = "test_token"
        
        # Create mock request
        mock_request = MagicMock()
        
        # Should skip validation in development
        assert validate_twilio_request(mock_request) is True
    
    @patch('app.api.webhooks.RequestValidator')
    @patch('app.api.webhooks.settings')
    def test_validate_request_production_mode(self, mock_settings, mock_validator_class):
        """Test request validation in production mode"""
        from app.api.webhooks import validate_twilio_request
        
        # Mock settings
        mock_settings.IS_DEVELOPMENT = False
        mock_settings.TWILIO_VALIDATE_REQUESTS = True
        mock_settings.TWILIO_AUTH_TOKEN = "test_token"
        
        # Mock validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_validator_class.return_value = mock_validator
        
        # Create mock request
        mock_request = MagicMock()
        mock_request.url = "https://example.com/webhook"
        mock_request.headers = {"X-Twilio-Signature": "test_signature"}
        mock_request.query_params = {"test": "param"}
        
        # Should validate in production
        assert validate_twilio_request(mock_request) is True
        
        # Verify validator was called correctly
        mock_validator_class.assert_called_once_with("test_token")
        mock_validator.validate.assert_called_once()