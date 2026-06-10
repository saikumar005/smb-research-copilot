import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

# Configure basic logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager handling startup events:
    1. Triggers SQLAlchemy metadata table creation.
    2. Builds/verifies Memori database tables.
    """
    logger.info("Starting up Business Research Copilot API service...")
    
    # Auto-create all SQLAlchemy models in PostgreSQL on startup
    try:
        from app.models import Base
        from app.core.database import engine
        logger.info("Verifying and creating app database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked and created.")
    except Exception as e:
        logger.critical(f"Failed to auto-create database tables on startup: {e}")
        
    # Trigger Memori SQL schema build
    try:
        from app.services.memory_service import init_memori_db
        init_memori_db()
    except Exception as e:
        logger.error(f"Failed to build Memori tables: {e}")
        
    yield
    
    logger.info("Shutting down Business Research Copilot API service...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Add CORS Middleware to allow requests from our frontend container
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev simplicity, allow all. Restrict in prod.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["health"])
def health_check():
    """
    Health check endpoint to monitor status of backend API container.
    """
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME
    }
