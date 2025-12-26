"""
TermiVoxed Web API - Main FastAPI Application

This API wraps the existing console-based functionality and adds:
- LLM integration (Ollama + Cloud APIs) for AI script generation
- Real-time export progress via WebSocket
- Smart script generation with timing/duration fitting
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Add parent directory to path to import existing modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings

# Server configuration from environment
TERMIVOXED_HOST = os.getenv("TERMIVOXED_HOST", "localhost")
TERMIVOXED_PORT = int(os.getenv("TERMIVOXED_PORT", "8000"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    # Startup
    settings.create_directories()
    print("")
    print("=" * 50)
    print("  TermiVoxed - AI Voice-Over Studio")
    print("=" * 50)
    print("")
    print(f"  → http://{TERMIVOXED_HOST}:{TERMIVOXED_PORT}")
    print(f"  → API Docs: http://{TERMIVOXED_HOST}:{TERMIVOXED_PORT}/docs")
    print("")
    print("=" * 50)
    print("")
    yield
    # Shutdown
    print("TermiVoxed Web API shutting down...")


app = FastAPI(
    title="TermiVoxed Web API",
    description="AI Voice-Over Dubbing Tool - Web Interface",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,  # Don't redirect /path to /path/ - causes CORS issues
)

# Build CORS origins list including custom hostname
cors_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
]

# Add custom hostname origins if configured
if TERMIVOXED_HOST and TERMIVOXED_HOST not in ["localhost", "127.0.0.1"]:
    cors_origins.extend([
        f"http://{TERMIVOXED_HOST}:5173",
        f"http://{TERMIVOXED_HOST}:5174",
        f"http://{TERMIVOXED_HOST}:5175",
        f"http://{TERMIVOXED_HOST}:{TERMIVOXED_PORT}",
    ])

# CORS configuration for frontend
# Use explicit methods and headers for security (avoid wildcards in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Authorization",
        "Cache-Control",
        "Content-Type",
        "Origin",
        "X-Requested-With",
        "X-Device-Fingerprint",
        "X-Request-ID",
    ],
    expose_headers=[
        "Content-Disposition",
        "Content-Length",
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
    ],
)

# Security headers middleware (adds X-Frame-Options, CSP, HSTS, etc.)
from web_ui.api.middleware.security_headers import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting middleware (must be after CORS)
from web_ui.api.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Import and include routers
from web_ui.api.routes import projects, videos, segments, tts, export, llm, settings_routes, fonts, timeline_ws, subscription, favorites, consent, models, auth, payments

# Public routes (no auth required)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments & Pricing"])

# Protected routes (auth required for most endpoints)
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(videos.router, prefix="/api/v1/videos", tags=["Videos"])
app.include_router(segments.router, prefix="/api/v1/segments", tags=["Segments"])
app.include_router(tts.router, prefix="/api/v1/tts", tags=["Text-to-Speech"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["LLM/AI"])
app.include_router(settings_routes.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(fonts.router, prefix="/api/v1/fonts", tags=["Fonts"])
app.include_router(favorites.router, prefix="/api/v1/favorites", tags=["Favorites"])
app.include_router(subscription.router, prefix="/api/v1", tags=["Subscription"])
app.include_router(consent.router, prefix="/api/v1/consent", tags=["Privacy Consent"])
app.include_router(models.router, prefix="/api/v1/models", tags=["AI Models"])
# WebSocket routes (no prefix needed - path defined in router)
app.include_router(timeline_ws.router, tags=["Timeline WebSocket"])

# Serve uploaded videos and output files
app.mount("/storage", StaticFiles(directory="storage"), name="storage")


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "TermiVoxed Web API",
        "version": "1.0.0",
        "description": "AI Voice-Over Dubbing Tool",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=TERMIVOXED_PORT, reload=True)
