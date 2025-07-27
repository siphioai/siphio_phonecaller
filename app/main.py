"""
Siphio AI Phone Receptionist - Main Application Entry Point
"""
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.security_utils import sanitize_log_data

# Configure logging first
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Try to import prometheus_client, but make it optional for now
try:
    from prometheus_client import Counter, Histogram, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not installed. Metrics will be disabled.")
    PROMETHEUS_AVAILABLE = False
    # Create dummy classes to avoid errors
    class Counter:
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def inc(self):
            pass
    class Histogram:
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def observe(self, value):
            pass
    def generate_latest():
        return b"# Prometheus metrics disabled"

# Prometheus metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
request_latency = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.utcnow()
        
        # Process request
        response = await call_next(request)
        
        # Record metrics
        latency = (datetime.utcnow() - start_time).total_seconds()
        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        request_latency.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(latency)
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle - startup and shutdown events
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Validate critical settings on startup
    if settings.ENVIRONMENT == "production":
        if settings.DEBUG:
            logger.warning("DEBUG mode is enabled in production!")
        if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key-here-change-in-production":
            logger.error("Invalid SECRET_KEY in production!")
            sys.exit(1)
    
    # Initialize services
    redis_client = None
    db_engine = None
    
    try:
        # Initialize Redis connection
        if settings.REDIS_URL:
            try:
                import redis.asyncio as redis
                redis_client = await redis.from_url(
                    settings.REDIS_URL,
                    password=settings.REDIS_PASSWORD,
                    decode_responses=settings.REDIS_DECODE_RESPONSES,
                    max_connections=settings.REDIS_POOL_SIZE
                )
                # Test connection
                await redis_client.ping()
                logger.info("Redis connection established")
                # Store in app state for access in routes
                app.state.redis = redis_client
            except ImportError:
                logger.warning("Redis module not installed. Redis features disabled.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                if settings.ENVIRONMENT == "production":
                    raise
        
        # Initialize database connection
        if settings.DATABASE_URL and not settings.DATABASE_URL.startswith("postgresql+asyncpg://user:password"):
            try:
                from sqlalchemy.ext.asyncio import create_async_engine
                db_engine = create_async_engine(
                    settings.DATABASE_URL,
                    pool_size=settings.DATABASE_POOL_SIZE,
                    max_overflow=settings.DATABASE_MAX_OVERFLOW,
                    echo=settings.DATABASE_ECHO
                )
                # Test connection
                from sqlalchemy import text
                async with db_engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                logger.info("Database connection established")
                # Store in app state
                app.state.db_engine = db_engine
            except ImportError:
                logger.warning("SQLAlchemy not installed. Database features disabled.")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                if settings.ENVIRONMENT == "production":
                    raise
    
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        if settings.ENVIRONMENT == "production":
            raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Cleanup connections
    try:
        if redis_client:
            await redis_client.close()
            logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")
    
    try:
        if db_engine:
            await db_engine.dispose()
            logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database connection: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered phone receptionist system for dental practices",
    docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.DEBUG else settings.ALLOWED_HOSTS
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add metrics middleware
app.add_middleware(MetricsMiddleware)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled exceptions
    """
    # Log the error with sanitized request data
    sanitized_data = sanitize_log_data({
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "client": request.client.host if request.client else None
    })
    
    logger.error(
        f"Unhandled exception: {exc}",
        extra={"request_data": sanitized_data},
        exc_info=True
    )
    
    # Return generic error in production
    if settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error occurred"}
        )
    else:
        # Return detailed error in development
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": str(exc),
                "type": type(exc).__name__,
                "request_data": sanitized_data
            }
        )


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for monitoring
    
    Returns:
        Dict containing health status and metadata
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "service": settings.APP_NAME
    }


# Detailed health check (only in non-production or with auth)
@app.get("/health/detailed", tags=["System"])
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with component status
    
    Returns:
        Dict containing detailed health information
    """
    if settings.ENVIRONMENT == "production":
        # In production, this should require authentication
        return {"error": "Detailed health check requires authentication"}
    
    # Check component health
    components = {
        "api": "healthy",
        "database": "not_configured",
        "redis": "not_configured",
        "twilio": "not_configured",
    }
    
    # Check Redis health
    if hasattr(app.state, 'redis') and app.state.redis:
        try:
            await app.state.redis.ping()
            components["redis"] = "healthy"
        except Exception as e:
            components["redis"] = f"unhealthy: {str(e)}"
    
    # Check Database health
    if hasattr(app.state, 'db_engine') and app.state.db_engine:
        try:
            from sqlalchemy import text
            async with app.state.db_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            components["database"] = "healthy"
        except Exception as e:
            components["database"] = f"unhealthy: {str(e)}"
    
    # Check Twilio configuration
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        components["twilio"] = "configured"
    
    health_status = {
        "status": "healthy" if all(v in ["healthy", "configured", "not_configured"] for v in components.values()) else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "components": components,
        "config": {
            "debug": settings.DEBUG,
            "hipaa_mode": settings.HIPAA_COMPLIANT_MODE,
            "encryption_enabled": settings.ENCRYPT_TRANSCRIPTS,
            "rate_limiting": settings.RATE_LIMIT_ENABLED
        }
    }
    
    return health_status


# Prometheus metrics endpoint
@app.get("/metrics", tags=["System"])
async def metrics():
    """
    Prometheus metrics endpoint
    
    Returns:
        Prometheus formatted metrics
    """
    if settings.ENVIRONMENT == "production":
        # In production, this should require authentication
        return {"error": "Metrics endpoint requires authentication"}
    
    return Response(generate_latest(), media_type="text/plain")


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint
    
    Returns:
        Welcome message
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else "Disabled in production"
    }


# Import and include routers
from app.api import webhooks

# WebSocket manager is initialized in webhooks module
from app.api.webhooks import websocket_manager

# Include API routers
app.include_router(webhooks.router)

# WebSocket endpoint for media streaming
@app.websocket("/media-stream/{stream_id}")
async def websocket_endpoint(websocket, stream_id: str):
    """
    WebSocket endpoint for Twilio media streaming
    Handles real-time audio bidirectional communication
    """
    await websocket_manager.handle_media_stream(websocket, stream_id)

# Admin and client routers will be added later
# from app.api import admin, client
# app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
# app.include_router(client.router, prefix="/api/client", tags=["Client"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )