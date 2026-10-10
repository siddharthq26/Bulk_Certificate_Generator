"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.config import settings
from app.db.database import async_engine, Base
from app.api.routes import jobs

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (Alembic handles migrations in production)."""
    logger.info("Starting up — creating database tables if they don't exist...")
    async with async_engine.begin() as conn:
        # Import all models so Base sees them
        from app.models import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready.")
    yield
    logger.info("Shutting down...")
    await async_engine.dispose()


# ── App Factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "A production-ready bulk certificate generation API. "
        "Submit a list of recipients and track the background generation of PDF certificates."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception Handlers ────────────────────────────────────────────────────────
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# ── Static / Frontend Files ───────────────────────────────────────────────────
# Check both relative to backend/app and relative to project root
possible_frontend_dirs = [
    Path(__file__).resolve().parent.parent.parent / "frontend" / "public",
    Path(__file__).resolve().parent / "static",
]

frontend_dir = next((d for d in possible_frontend_dirs if d.exists()), None)
if frontend_dir:
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(jobs.router, prefix="/api/v1")


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/", tags=["Root"], response_class=FileResponse)
async def root():
    if frontend_dir:
        index_file = frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
    return JSONResponse({
        "message": "Bulk Certificate Generator API",
        "docs": "/docs",
        "health": "/health",
    })


