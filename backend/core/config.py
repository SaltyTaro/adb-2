import os
from pydantic import BaseSettings
from typing import Optional, Dict, Any, List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    APP_NAME: str = "Advanced Dependency Intelligence Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # API settings
    API_PREFIX: str = "/api/v1"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database settings
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    
    # External API credentials
    GITHUB_API_TOKEN: Optional[str] = None
    NPM_REGISTRY_URL: str = "https://registry.npmjs.org"
    PYPI_URL: str = "https://pypi.org/pypi"
    
    # Analysis settings
    STATIC_ANALYSIS_TIMEOUT: int = 300  # seconds
    MAX_PROJECT_SIZE_MB: int = 500
    
    # AI settings
    ENABLE_AI_FEATURES: bool = True
    MODEL_PATHS: Dict[str, str] = {
        "code_transformer": "models/code_transformer.pkl",
        "compatibility_predictor": "models/compatibility_predictor.pkl"
    }
    
    # Monitoring
    DEPENDENCY_HEALTH_CHECK_INTERVAL: int = 86400  # 24 hours
    ENABLE_TELEMETRY: bool = False
    
    # Cache settings
    CACHE_TTL: int = 3600  # 1 hour
    MAX_CACHE_SIZE: int = 1024  # MB
    
    # Scanning thresholds
    LICENSE_RISK_THRESHOLDS: Dict[str, float] = {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.2
    }
    
    DEPENDENCY_HEALTH_THRESHOLDS: Dict[str, float] = {
        "active": 0.7,  # Activity level to consider a project active
        "abandoned": 0.2,  # Activity level to consider a project abandoned
        "critical": 0.9  # Importance level to consider a dependency critical
    }
    
    # Feature flags
    FEATURES: Dict[str, bool] = {
        "impact_scoring": True,
        "predictive_management": True,
        "dependency_consolidation": True,
        "code_adaptation": True,
        "health_monitoring": True,
        "license_compliance": True,
        "performance_profiling": True
    }
    
    # Worker configuration
    WORKER_CONCURRENCY: int = 4
    WORKER_QUEUE_URL: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()