"""
Главное приложение FastAPI
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from pythonjsonlogger import jsonlogger

from app.core.config import settings
from app.api import projects, files, issues, auth, norms
from app.core.database import get_db_session


# Настройка логирования
logger = logging.getLogger(__name__)
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt="%(timestamp)s %(level)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
logger.setLevel(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("Starting AutoNormCheck API", extra={"version": settings.APP_VERSION})
    
    # Инициализация подключений
    from app.core.qdrant_client import init_qdrant_collection
    from app.core.minio_client import ensure_bucket_exists
    
    try:
        await init_qdrant_collection()
        logger.info("Qdrant collection initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant: {e}")
    
    try:
        ensure_bucket_exists()
        logger.info("MinIO bucket ensured")
    except Exception as e:
        logger.error(f"Failed to initialize MinIO: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AutoNormCheck API")


app = FastAPI(
    title=settings.APP_NAME,
    description="""
## AutoNormCheck API

Система автоматического анализа проектной документации на соответствие нормам РФ.

### Возможности:
- **Загрузка файлов** PDF и DWG
- **Автоматический анализ** с использованием ИИ
- **Проверка по нормам** ГОСТ, СП, СНиП, ПДД
- **Интерактивный просмотр** замечаний с привязкой к координатам
- **Экспорт отчетов** в JSON, CSV, PDF

### Основные сценарии:
1. Загрузка проектной документации
2. Автоматический пайплайн обработки
3. Просмотр и фильтрация замечаний
4. Подтверждение/отклонение экспертом
5. Экспорт итогового отчета
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production настроить конкретно
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "client_ip": request.client.host if request.client else None,
        }
    )
    
    return response


# Обработчик исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Проверка работоспособности сервиса"""
    from sqlalchemy import text
    
    try:
        # Проверка БД
        db = next(get_db_session())
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    try:
        # Проверка Redis
        from app.core.redis_client import redis_client
        await redis_client.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "ok" and redis_status == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "services": {
            "database": db_status,
            "redis": redis_status,
        }
    }


# Регистрация роутеров
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(issues.router, prefix="/api/v1/issues", tags=["Issues"])
app.include_router(norms.router, prefix="/api/v1/norms", tags=["Norms"])


@app.get("/", tags=["Root"])
async def root():
    """Информация о API"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs_url": "/docs",
        "health_url": "/health",
    }
