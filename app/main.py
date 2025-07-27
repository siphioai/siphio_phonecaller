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
from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.security_utils import sanitize_log_data

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

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
    
    # Initialize services (Redis, DB, etc.) here in the future
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    # Cleanup connections here


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
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "components": {
            "api": "healthy",
            "database": "not_configured",  # Will be updated when DB is added
            "redis": "not_configured",     # Will be updated when Redis is added
            "twilio": "not_configured",    # Will be updated when Twilio is added
        },
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


# Import and include routers (will be added as we build features)
# from app.api import webhooks, admin, client
# app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
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