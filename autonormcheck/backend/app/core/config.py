"""
Application configuration using Pydantic Settings.
Loads environment variables from .env file.
"""
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    APP_NAME: str = "AutoNormCheck API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Security
    JWT_SECRET_KEY: str = "your-super-secret-jwt-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    POSTGRES_USER: str = "autonorm"
    POSTGRES_PASSWORD: str = "secure_password_here"
    POSTGRES_DB: str = "autonormcheck"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    @property
    def CELERY_BROKER(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL
    
    @property
    def CELERY_BACKEND(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL
    
    # Qdrant (Vector DB)
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_COLLECTION: str = "norms_collection"
    QDRANT_API_KEY: Optional[str] = None
    
    @property
    def QDRANT_URL(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"
    
    # MinIO (S3-compatible storage)
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadminpassword"
    MINIO_BUCKET: str = "projects"
    MINIO_SECURE: bool = False
    
    @property
    def MINIO_URL(self) -> str:
        scheme = "https" if self.MINIO_SECURE else "http"
        return f"{scheme}://{self.MINIO_ENDPOINT}"
    
    # AI Models
    EMBEDDING_MODEL: str = "sentence-transformers/rubert-tiny2"
    LLM_MODEL_PATH: Optional[str] = None
    LLM_MAX_TOKENS: int = 2048
    RAG_TOP_K: int = 5
    
    # File processing
    FILE_UPLOAD_MAX_SIZE: int = 104857600  # 100MB
    DATA_RETENTION_DAYS: int = 7
    TEMP_DIR: str = "/tmp/autonormcheck"
    ALLOWED_FILE_EXTENSIONS: List[str] = ["pdf", "dwg", "dxf"]
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
    ]
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    SENTRY_DSN: Optional[str] = None
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
