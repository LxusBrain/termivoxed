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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    # Startup
    settings.create_directories()
    print("TermiVoxed Web API starting...")
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

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from web_ui.api.routes import projects, videos, segments, tts, export, llm, settings_routes, fonts, timeline_ws

app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(videos.router, prefix="/api/v1/videos", tags=["Videos"])
app.include_router(segments.router, prefix="/api/v1/segments", tags=["Segments"])
app.include_router(tts.router, prefix="/api/v1/tts", tags=["Text-to-Speech"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["LLM/AI"])
app.include_router(settings_routes.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(fonts.router, prefix="/api/v1/fonts", tags=["Fonts"])
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
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
