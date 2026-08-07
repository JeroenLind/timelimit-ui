"""API router module for the debug server.

This module aggregates all API routers and provides the main api_router
instance that is included in the FastAPI application.
"""

from fastapi import APIRouter

# Create the main API router
api_router = APIRouter()

# Include health check router
from app.api.health import router as health_router
api_router.include_router(health_router)

# Include time endpoint router
from app.api.time import router as time_router
api_router.include_router(time_router)

# Include authentication router
from app.api.auth import router as auth_router
api_router.include_router(auth_router)

# Include users router
from app.api.users import router as users_router
api_router.include_router(users_router)

# Include child device router
from app.api.child import router as child_router
api_router.include_router(child_router)

# Include sync router
from app.api.sync import router as sync_router
api_router.include_router(sync_router)

# Include parent management router
from app.api.parent import router as parent_router
api_router.include_router(parent_router)

# Include purchase router
from app.api.purchase import router as purchase_router
api_router.include_router(purchase_router)