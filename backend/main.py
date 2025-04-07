import logging
import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

from backend.api.router import api_router
from backend.core.config import get_settings
from backend.core.db import get_db, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API for Advanced Dependency Intelligence Platform",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)


# Root endpoint
@app.get("/", tags=["root"])
def root() -> Dict[str, Any]:
    """
    Root endpoint, returns basic API information.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs_url": "/docs",
        "api_prefix": settings.API_PREFIX
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Initialize database and perform other startup tasks.
    """
    logger.info("Starting up Advanced Dependency Intelligence Platform")
    
    # Initialize database
    init_db()
    
    # Check for initial setup
    db = next(get_db())
    try:
        from backend.core.models import User
        
        # Check if admin user exists
        admin_user = db.query(User).filter(User.is_superuser == True).first()
        
        if not admin_user and os.environ.get("ADMIN_USERNAME") and os.environ.get("ADMIN_PASSWORD"):
            # Create admin user
            from backend.api.auth import get_password_hash
            import uuid
            
            logger.info("Creating initial admin user")
            
            admin = User(
                id=uuid.uuid4(),
                username=os.environ["ADMIN_USERNAME"],
                email=os.environ.get("ADMIN_EMAIL", "admin@example.com"),
                hashed_password=get_password_hash(os.environ["ADMIN_PASSWORD"]),
                is_active=True,
                is_superuser=True
            )
            
            db.add(admin)
            db.commit()
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
    finally:
        db.close()


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Perform cleanup on shutdown.
    """
    logger.info("Shutting down Advanced Dependency Intelligence Platform")


# For running with uvicorn
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )