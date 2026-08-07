"""Main application module for the debug server.

This module creates and configures the FastAPI application with:
- All API routers registered
- Middleware stack (logging, gzip, auth, security headers)
- Exception handlers
- Lifespan event handlers for startup/shutdown
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import create_exception_handlers
from app.middleware.auth import AuthMiddleware
from app.middleware.encryption import EncryptionHandshakeMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.gzip import GzipMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None - Control returns to the application after startup
    """
    # Startup logic
    pass  # Add any startup logic here
    
    yield
    
    # Shutdown logic
    pass  # Add any shutdown logic here


def create_application() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    # Initialize logging
    setup_logging()
    
    # Create FastAPI instance with configuration
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        lifespan=lifespan,
    )
    
    # Register middleware in the correct order:
    # 1. Logging (first to capture all requests)
    # 2. Gzip (decompress requests, compress responses)
    # 3. Auth (validate JWT tokens for protected endpoints)
    # 4. Security headers (add security headers to responses)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add Gzip middleware
    app.add_middleware(GzipMiddleware, compress_level=6, minimum_size=1000)
    
    # Add Auth middleware
    app.add_middleware(AuthMiddleware)
    
    # Add Security Headers middleware
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Add Encryption Handshake middleware (for WebSocket monitoring)
    app.add_middleware(EncryptionHandshakeMiddleware)
    
    # Include API router (will be implemented in task-006)
    from app.api import api_router
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    # Register exception handlers
    for exception_class, handler in create_exception_handlers().items():
        app.add_exception_handler(exception_class, handler)
    
    return app


# Create application instance at module level
app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True,
    )