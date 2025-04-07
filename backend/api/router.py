from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api import auth
from backend.api.endpoints import projects, dependencies, analysis, recommendations
from backend.core.db import get_db
from backend.core.config import get_settings

settings = get_settings()

# Main API router
api_router = APIRouter(prefix=settings.API_PREFIX)

# Include authentication routes
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)

# Include module routes
api_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(auth.get_current_active_user)]
)

api_router.include_router(
    dependencies.router,
    prefix="/dependencies",
    tags=["dependencies"],
    dependencies=[Depends(auth.get_current_active_user)]
)

api_router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(auth.get_current_active_user)]
)

api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["recommendations"],
    dependencies=[Depends(auth.get_current_active_user)]
)

# Health check endpoint (no auth required)
@api_router.get("/health", tags=["system"])
def health_check():
    """
    Health check endpoint for monitoring systems.
    """
    return {
        "status": "ok",
        "api_version": settings.APP_VERSION,
        "api_name": settings.APP_NAME
    }