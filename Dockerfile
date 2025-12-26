# TermiVoxed - Production Dockerfile
# Author: Santhosh T / LXUSBrain Technologies
#
# Multi-stage build for optimized image size and security
# This bundles EVERYTHING: Python, FFmpeg, frontend, backend

# =============================================================================
# Stage 1: Build Frontend (React/Vite)
# =============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Copy package files first (better layer caching)
COPY web_ui/frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy frontend source
COPY web_ui/frontend/ ./

# Build production bundle
RUN npm run build

# =============================================================================
# Stage 2: Build Python Dependencies
# =============================================================================
FROM python:3.11-slim AS python-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment (for complete isolation)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 3: Production Runtime
# =============================================================================
FROM python:3.11-slim AS production

# Metadata
LABEL maintainer="Santhosh T <support@luxusbrain.com>"
LABEL org.opencontainers.image.title="TermiVoxed"
LABEL org.opencontainers.image.description="AI Voice-Over Dubbing Studio - By LXUSBrain"
LABEL org.opencontainers.image.vendor="LXUSBrain Technologies"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.url="https://termivoxed.com"

WORKDIR /app

# Install runtime dependencies ONLY (no build tools)
# This is the KEY: FFmpeg is BUNDLED in the container
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgomp1 \
    libsdl2-2.0-0 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /var/cache/apt/archives/*

# Copy Python virtual environment from builder (ALL packages included)
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy built frontend (static files - no Node.js needed at runtime!)
COPY --from=frontend-builder /build/dist /app/web_ui/frontend/dist

# Copy application code
COPY backend/ /app/backend/
COPY core/ /app/core/
COPY models/ /app/models/
COPY subscription/ /app/subscription/
COPY web_ui/api/ /app/web_ui/api/
COPY config.py main.py /app/
COPY *.py /app/

# Copy cloud functions (for Firebase deployment)
COPY cloud_functions/ /app/cloud_functions/

# Create runtime directories
RUN mkdir -p /app/storage/{projects,temp,cache,output,fonts,voice_samples} \
             /app/logs \
             /app/models/tts \
    && chmod -R 755 /app

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TERMIVOXED_HOST=0.0.0.0 \
    TERMIVOXED_PORT=8000 \
    TERMIVOXED_STORAGE_DIR=/app/storage \
    TERMIVOXED_MODELS_DIR=/app/models

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 termivoxed \
    && chown -R termivoxed:termivoxed /app

USER termivoxed

# Expose ports
EXPOSE 8000

# Persistent volumes
VOLUME ["/app/storage", "/app/logs", "/app/models"]

# Health check - verify API is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${TERMIVOXED_PORT}/api/v1/health || exit 1

# Start command - runs the FastAPI server
CMD ["python", "-m", "uvicorn", "web_ui.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
