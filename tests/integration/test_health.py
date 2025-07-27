"""
Integration tests for health check endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.core.config import settings


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_check(self, client):
        """Test basic health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == settings.APP_VERSION
        assert data["environment"] == settings.ENVIRONMENT
        assert data["service"] == settings.APP_NAME
    
    @patch('app.core.config.settings')
    def test_detailed_health_check_development(self, mock_settings, client):
        """Test detailed health check in development"""
        mock_settings.ENVIRONMENT = "development"
        mock_settings.APP_VERSION = "0.1.0"
        mock_settings.DEBUG = True
        mock_settings.HIPAA_COMPLIANT_MODE = True
        mock_settings.ENCRYPT_TRANSCRIPTS = True
        mock_settings.RATE_LIMIT_ENABLED = True
        
        response = client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "0.1.0"
        assert data["environment"] == "development"
        
        # Check components
        assert data["components"]["api"] == "healthy"
        assert data["components"]["database"] == "not_configured"
        assert data["components"]["redis"] == "not_configured"
        assert data["components"]["twilio"] == "not_configured"
        
        # Check config
        assert data["config"]["debug"] is True
        assert data["config"]["hipaa_mode"] is True
        assert data["config"]["encryption_enabled"] is True
        assert data["config"]["rate_limiting"] is True
    
    @patch('app.core.config.settings')
    def test_detailed_health_check_production(self, mock_settings, client):
        """Test detailed health check in production (requires auth)"""
        mock_settings.ENVIRONMENT = "production"
        
        response = client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert data["error"] == "Detailed health check requires authentication"
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert settings.APP_NAME in data["message"]
        assert data["version"] == settings.APP_VERSION
        assert "docs" in data
    
    @patch('app.core.config.settings')
    def test_metrics_endpoint_development(self, mock_settings, client):
        """Test metrics endpoint in development"""
        mock_settings.ENVIRONMENT = "development"
        
        # Make a request to generate some metrics
        client.get("/health")
        
        response = client.get("/metrics")
        
        # In development, should return metrics
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        
        # Check for Prometheus format
        content = response.text
        assert "http_requests_total" in content
        assert "http_request_duration_seconds" in content
    
    @patch('app.core.config.settings')
    def test_metrics_endpoint_production(self, mock_settings, client):
        """Test metrics endpoint in production (requires auth)"""
        mock_settings.ENVIRONMENT = "production"
        
        response = client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["error"] == "Metrics endpoint requires authentication"
    
    def test_cors_headers(self, client):
        """Test CORS headers are properly set"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
    
    def test_404_handling(self, client):
        """Test 404 error handling"""
        response = client.get("/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    @patch('app.core.config.settings')
    def test_exception_handling_development(self, mock_settings, client):
        """Test exception handling in development"""
        mock_settings.ENVIRONMENT = "development"
        
        # Create an endpoint that raises an exception
        @app.get("/test-error")
        def test_error():
            raise ValueError("Test exception")
        
        response = client.get("/test-error")
        
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Test exception"
        assert data["type"] == "ValueError"
        assert "request_data" in data
    
    @patch('app.core.config.settings')
    def test_exception_handling_production(self, mock_settings, client):
        """Test exception handling in production"""
        mock_settings.ENVIRONMENT = "production"
        
        # Create an endpoint that raises an exception
        @app.get("/test-error-prod")
        def test_error():
            raise ValueError("Test exception")
        
        response = client.get("/test-error-prod")
        
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "An internal error occurred"
        # Should not expose error details in production
        assert "type" not in data
        assert "request_data" not in data
    
    def test_metrics_middleware(self, client):
        """Test that metrics middleware is recording requests"""
        # Make several requests
        client.get("/health")
        client.get("/health")
        client.get("/")
        client.get("/nonexistent")  # 404
        
        # In a real test, we would check Prometheus metrics
        # For now, just verify the endpoints still work
        response = client.get("/health")
        assert response.status_code == 200
    
    @pytest.mark.parametrize("endpoint,expected_status", [
        ("/health", 200),
        ("/health/detailed", 200),
        ("/", 200),
        ("/metrics", 200),
        ("/api/invalid", 404),
    ])
    def test_endpoint_availability(self, client, endpoint, expected_status):
        """Test that all expected endpoints are available"""
        response = client.get(endpoint)
        assert response.status_code == expected_status
    
    def test_openapi_availability(self, client):
        """Test OpenAPI documentation availability based on debug mode"""
        if settings.DEBUG:
            # Should be available in debug mode
            response = client.get("/docs")
            assert response.status_code == 200
            
            response = client.get("/redoc")
            assert response.status_code == 200
            
            response = client.get("/openapi.json")
            assert response.status_code == 200
            data = response.json()
            assert "openapi" in data
            assert data["info"]["title"] == settings.APP_NAME
        else:
            # Should not be available in production
            response = client.get("/docs")
            assert response.status_code == 404
    
    def test_startup_shutdown_lifecycle(self):
        """Test application lifecycle events"""
        # This test verifies the app can start and shutdown properly
        # In a real scenario, we would test actual startup/shutdown logic
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
        # App should shutdown cleanly after context manager exit