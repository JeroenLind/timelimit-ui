"""Time endpoint for the debug server.

This module provides the server time endpoint used by clients
to synchronize their clocks.
"""

import time

from fastapi import APIRouter

from app.models.auth import TimeResponse

router = APIRouter()


@router.get("/time", response_model=TimeResponse)
async def get_server_time() -> TimeResponse:
    """Return server time in milliseconds.

    This endpoint is used by clients to synchronize their clocks.
    Uses GET method as per the official TimeLimit API specification.

    Returns:
        TimeResponse: Server time in milliseconds.
    """
    return TimeResponse(ms=int(time.time() * 1000))