"""Main application module for the debug server.

This module creates and configures the FastAPI application with:
- All API routers registered
- Middleware stack (logging, gzip, auth, security headers)
- Exception handlers
- Lifespan event handlers for startup/shutdown
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import create_exception_handlers
from app.middleware.api_message_logger import APIMessageLoggingMiddleware
from app.middleware.auth import AuthMiddleware
from app.middleware.encryption import EncryptionHandshakeMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.gzip import GzipMiddleware
from app.middleware.server_message_logger import (
    get_server_message_logger,
    reset_server_message_logger,
)
from app.middleware.message_sent_logger import (
    get_message_sent_logger,
    reset_message_sent_logger,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None - Control returns to the application after startup
    """
    # Initialize the server message logger with config settings
    import logging as logging_module
    
    log_level = getattr(logging_module, settings.MESSAGE_LOGGING_LEVEL.upper(), logging_module.INFO)
    
    server_logger = get_server_message_logger(
        log_file_path=settings.LOG_FILE_PATH,
        async_mode=settings.MESSAGE_LOGGING_ASYNC,
        log_level=log_level,
        max_buffer_size=settings.MESSAGE_LOGGING_MAX_BUFFER_SIZE,
        sanitize=settings.MESSAGE_LOGGING_SANITIZE
    )
    
    # Initialize the message sent logger
    get_message_sent_logger(server_logger)
    
    # Log startup
    server_logger.log_system_event(
        event="server_startup",
        details={
            "port": settings.SERVER_PORT,
            "log_level": settings.MESSAGE_LOGGING_LEVEL,
            "async_mode": settings.MESSAGE_LOGGING_ASYNC,
            "sanitize": settings.MESSAGE_LOGGING_SANITIZE,
        }
    )
    
    yield
    
    # Shutdown logic - flush and stop async logging
    server_logger.flush()
    server_logger.stop_async_logging()
    
    # Reset global loggers
    reset_message_sent_logger()
    reset_server_message_logger()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    # Initialize logging and get the log file path
    log_file_path = setup_logging()
    
    # Create FastAPI instance with configuration
    # When API_V1_STR is empty, use root paths for openapi and docs
    openapi_url = "/openapi.json" if settings.API_V1_STR == "" else f"{settings.API_V1_STR}/openapi.json"
    docs_url = "/docs" if settings.API_V1_STR == "" else f"{settings.API_V1_STR}/docs"
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=openapi_url,
        docs_url=docs_url,
        lifespan=lifespan,
    )
    
    # Register middleware in the correct order:
    # 1. API Message Logging (first to capture all requests immediately)
    # 2. Gzip (decompress requests, compress responses)
    # 3. Auth (validate JWT tokens for protected endpoints)
    # 4. Security headers (add security headers to responses)
    
    # Add API Message Logging middleware (FIRST to log before any processing)
    # Use the timestamped log file path from setup_logging()
    app.add_middleware(APIMessageLoggingMiddleware, log_file_path=log_file_path)
    
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