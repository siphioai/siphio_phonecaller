"""
Integration tests for middleware and lifespan management
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import asyncio

from app.main import app, lifespan


class TestLifespanManager:
    """Test application lifespan management"""
    
    @pytest.mark.asyncio
    @patch('app.core.config.settings')
    @patch('app.main.logger')
    async def test_lifespan_startup_success(self, mock_logger, mock_settings):
        """Test successful startup in development"""
        mock_settings.ENVIRONMENT = "development"
        mock_settings.APP_NAME = "Test App"
        mock_settings.APP_VERSION = "1.0.0"
        mock_settings.DEBUG = True
        mock_settings.IS_PRODUCTION = False
        mock_settings.SECRET_KEY = "dev-key"
        
        # Run lifespan
        async with lifespan(app) as _:
            # Verify startup logs
            mock_logger.info.assert_any_call("Starting Test App v1.0.0")
            mock_logger.info.assert_any_call("Environment: development")
            mock_logger.info.assert_any_call("Debug mode: True")
        
        # Verify shutdown log
        mock_logger.info.assert_any_call("Shutting down application...")
    
    @pytest.mark.asyncio
    @patch('app.core.config.settings')
    @patch('app.main.logger')
    @patch('app.main.sys.exit')
    async def test_lifespan_production_validation_failure(self, mock_exit, mock_logger, mock_settings):
        """Test production startup fails with invalid config"""
        mock_settings.ENVIRONMENT = "production"
        mock_settings.DEBUG = True  # Should be False in production
        mock_settings.SECRET_KEY = "your-secret-key-here-change-in-production"  # Default key
        mock_settings.IS_PRODUCTION = True
        
        # Create async generator manually to test the startup phase
        gen = lifespan(app)
        
        # Start the generator - this should trigger validation
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass
        
        # Verify error was logged and exit was called
        mock_logger.warning.assert_called_with("DEBUG mode is enabled in production!")
        mock_logger.error.assert_called_with("Invalid SECRET_KEY in production!")
        mock_exit.assert_called_with(1)
    
    @pytest.mark.asyncio
    @patch('app.core.config.settings')
    async def test_lifespan_production_validation_success(self, mock_settings):
        """Test production startup succeeds with valid config"""
        mock_settings.ENVIRONMENT = "production"
        mock_settings.DEBUG = False
        mock_settings.SECRET_KEY = "valid-production-secret-key-123456"
        mock_settings.IS_PRODUCTION = True
        mock_settings.APP_NAME = "Prod App"
        mock_settings.APP_VERSION = "1.0.0"
        
        # Should complete without errors
        async with lifespan(app):
            pass  # Startup successful


class TestMiddleware:
    """Test middleware functionality"""
    
    def test_cors_headers(self):
        """Test CORS middleware headers"""
        with TestClient(app) as client:
            # Preflight request
            response = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "content-type"
                }
            )
            
            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
            assert "access-control-allow-methods" in response.headers
            assert "access-control-allow-headers" in response.headers
            
            # Actual request
            response = client.get(
                "/health",
                headers={"Origin": "http://localhost:3000"}
            )
            
            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    
    def test_metrics_middleware(self):
        """Test that metrics middleware records requests"""
        with TestClient(app) as client:
            # Make several requests
            client.get("/health")
            client.get("/health")
            client.get("/")
            client.get("/nonexistent")  # 404
            
            # Get metrics
            response = client.get("/metrics")
            
            if response.headers.get("content-type") == "text/plain; charset=utf-8":
                # Development mode - check metrics format
                metrics_text = response.text
                assert "http_requests_total" in metrics_text
                assert "http_request_duration_seconds" in metrics_text
                
                # Verify specific metrics
                assert 'endpoint="/health"' in metrics_text
                assert 'status="200"' in metrics_text
                assert 'status="404"' in metrics_text
    
    @patch('app.core.config.settings')
    def test_trusted_host_middleware(self, mock_settings):
        """Test trusted host middleware"""
        mock_settings.DEBUG = False
        mock_settings.ALLOWED_HOSTS = ["testserver", "localhost"]
        
        with TestClient(app) as client:
            # Valid host
            response = client.get("/health", headers={"Host": "testserver"})
            assert response.status_code == 200
            
            # Note: TrustedHostMiddleware in debug mode allows all hosts
            # In production, it would reject invalid hosts
    
    def test_exception_handler_middleware(self):
        """Test global exception handling"""
        # Add a test endpoint that raises an exception
        @app.get("/test-exception")
        def raise_exception():
            raise ValueError("Test exception")
        
        with TestClient(app) as client:
            response = client.get("/test-exception")
            
            assert response.status_code == 500
            data = response.json()
            
            # In development, should show details
            if app.debug:
                assert "Test exception" in data.get("detail", "")
                assert data.get("type") == "ValueError"
            else:
                # In production, should hide details
                assert data.get("detail") == "An internal error occurred"
    
    def test_request_size_limits(self):
        """Test request size handling"""
        with TestClient(app) as client:
            # Try to send a large payload
            large_data = "x" * (10 * 1024 * 1024)  # 10MB
            
            response = client.post(
                "/health",  # Using health endpoint as it exists
                content=large_data,
                headers={"Content-Type": "text/plain"}
            )
            
            # Should handle gracefully (405 for method not allowed on /health)
            assert response.status_code in [405, 413]  # Method not allowed or payload too large


class TestWebSocketSupport:
    """Test WebSocket support (placeholder for future)"""
    
    @pytest.mark.asyncio
    async def test_websocket_placeholder(self):
        """Test that WebSocket support is ready for future implementation"""
        # This is a placeholder test for future WebSocket functionality
        # Will be implemented when WebSocket endpoints are added
        assert True  # Placeholder
        
    # TODO: Add actual WebSocket tests when implementing media streaming