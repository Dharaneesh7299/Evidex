"""Evidex Backend Entrypoint.

FastAPI application configuring routes, CORS, database lifespan, and error handling.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.database import get_db
from app.services.sample_service import seed_sample_data

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("evidex")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle management."""
    logger.info("Initializing Evidex backend database...")
    db = get_db()
    
    # Auto-seed sample investigation on initial startup for zero-friction demo experience
    try:
        logger.info("Verifying sample papers and benchmark investigation...")
        seed_sample_data(db)
    except Exception as e:
        logger.warning(f"Could not auto-seed sample papers on startup: {e}")

    yield

    logger.info("Shutting down Evidex backend...")


app = FastAPI(
    title="Evidex API",
    description="Agentic AI Research Investigation Platform with Verifiable Citations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
is_wildcard = "*" in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Format schema validation errors consistently."""
    errors = exc.errors()
    msg = errors[0].get("msg") if errors else "Validation failed"
    loc = " -> ".join(str(l) for l in errors[0].get("loc", [])) if errors else ""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": f"{loc}: {msg}" if loc else msg, "code": "VALIDATION_ERROR"},
    )


# Attach API router with /api prefix and root fallback for deployment resilience
app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="", include_in_schema=False)


@app.get("/", tags=["System"])
def root() -> dict:
    return {
        "service": "Evidex",
        "description": "Investigate the evidence behind research.",
        "docs": "/docs",
        "health": "/api/health",
    }
