"""Health check and readiness endpoints for the debug server.

This module provides basic health check endpoints for monitoring and testing
the server's availability and readiness status.
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint.
    
    Returns the current health status of the server.
    This endpoint is used for basic liveness probes.
    
    Returns:
        dict: Health status response with status "healthy"
    """
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check() -> dict:
    """Readiness check endpoint.
    
    Returns the current readiness status of the server.
    This endpoint is used for readiness probes to determine if the server
    is ready to accept traffic.
    
    Returns:
        dict: Readiness status response with status "ready"
    """
    return {"status": "ready"}