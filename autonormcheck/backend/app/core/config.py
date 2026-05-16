"""
Конфигурация приложения
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "AutoNormCheck"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Database
    DATABASE_URL: str = "postgresql://autonorm:password@localhost:5432/autonormcheck"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "norms_collection"
    
    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "projects"
    MINIO_USE_SSL: bool = False
    
    # Security
    JWT_SECRET: str = "change_this_secret_key_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    ENCRYPTION_KEY: str = "32_character_encryption_key_here!"
    DATA_RETENTION_DAYS: int = 7
    
    # AI Models
    EMBEDDING_MODEL: str = "cointegrated/rubert-tiny2"
    LLM_MODEL_PATH: Optional[str] = None
    LLM_MAX_TOKENS: int = 2048
    DEVICE: str = "cpu"  # cpu, cuda, mps
    
    # Processing
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: list = ["pdf", "dwg", "dxf"]
    OCR_ENABLED: bool = True
    CONFIDENCE_THRESHOLD_HIGH: float = 0.85
    CONFIDENCE_THRESHOLD_MEDIUM: float = 0.60
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL
    
    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL


settings = Settings()
