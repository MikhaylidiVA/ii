"""
AutoNormCheck - Main FastAPI Application
Automatic analysis of project documentation for compliance with Russian regulations.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api import projects, files, issues, auth, norms

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Initialize database connections, caches, etc.
    # await init_db()
    # await init_redis()
    # await init_qdrant()
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    # await close_db()
    # await close_redis()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## AutoNormCheck API

AI-powered system for automatic analysis of project documentation (PDF, DWG) 
for compliance with Russian regulatory requirements (GOST, SP, SNiP, Traffic Rules).

### Features:
- **File Upload**: Support for PDF and DWG formats
- **Automatic Analysis**: AI-powered compliance checking
- **RAG System**: Vector search through regulatory documents
- **Interactive Reports**: GeoJSON-based issue visualization
- **Expert Review**: Human-in-the-loop validation

### Authentication:
Use `/api/v1/auth/login` to obtain JWT token.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__}
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "AI-powered system for automatic analysis of project documentation",
        "docs": "/docs",
        "health": "/health"
    }


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
app.include_router(issues.router, prefix="/api/v1/issues", tags=["Issues"])
app.include_router(norms.router, prefix="/api/v1/norms", tags=["Norms"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
