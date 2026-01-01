#!/bin/bash

# TermiVoxed Web UI - Startup Script
# This script starts both the backend API and frontend dev server
#
# SAFE PORT HANDLING: This script finds available ports instead of killing
# existing processes. It never terminates other applications.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${RED}"
echo "  _____                   _ __     __                    _ "
echo " |_   _|__ _ __ _ __ ___ (_)\ \   / /____  _____  __  __| |"
echo "   | |/ _ \ '__| '_ \` _ \| | \ \ / / _ \ \/ / _ \/ _|| / _\` |"
echo "   | |  __/ |  | | | | | | |  \ V / (_) >  <  __/ (_| | (_| |"
echo "   |_|\___|_|  |_| |_| |_|_|   \_/ \___/_/\_\___|\__,_|\__,_|"
echo -e "${NC}"
echo -e "${GREEN}AI Voice-Over Studio - Web UI${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "api/main.py" ]; then
    echo -e "${RED}Error: Please run this script from the web_ui directory${NC}"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required${NC}"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is required for the frontend${NC}"
    exit 1
fi

# Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}Warning: FFmpeg not found. Video processing will not work.${NC}"
fi

# Check Ollama
if command -v ollama &> /dev/null; then
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Ollama is running${NC}"
    else
        echo -e "${YELLOW}⚠ Ollama is installed but not running. Start with: ollama serve${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Ollama not found. Local AI features will be unavailable.${NC}"
fi

echo ""

# =============================================================================
# SAFE PORT FINDING FUNCTIONS
# =============================================================================

# Find an available port starting from the given port
# Usage: find_available_port <start_port> <max_attempts>
find_available_port() {
    local port=$1
    local max_attempts=${2:-10}
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if ! lsof -i:$port > /dev/null 2>&1; then
            echo $port
            return 0
        fi
        port=$((port + 1))
        attempt=$((attempt + 1))
    done

    # Failed to find available port
    echo ""
    return 1
}

# Check if a port is in use
is_port_in_use() {
    lsof -i:$1 > /dev/null 2>&1
}

# =============================================================================
# CONFIGURATION
# =============================================================================

# Read custom hostname from .env if available
TERMIVOXED_HOST=${TERMIVOXED_HOST:-localhost}
if [ -f "../.env" ]; then
    export $(grep -v '^#' ../.env | grep -E '^TERMIVOXED_HOST=' | xargs 2>/dev/null) || true
fi

# Auto-detect Firebase service account credentials
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    # Look for Firebase service account JSON in project root
    FIREBASE_CRED=$(find .. -maxdepth 1 -name "*firebase*adminsdk*.json" -type f 2>/dev/null | head -1)
    if [ -n "$FIREBASE_CRED" ]; then
        export GOOGLE_APPLICATION_CREDENTIALS="$(cd "$(dirname "$FIREBASE_CRED")" && pwd)/$(basename "$FIREBASE_CRED")"
        echo -e "${GREEN}✓ Firebase credentials: $(basename "$FIREBASE_CRED")${NC}"
    else
        echo -e "${YELLOW}⚠ Firebase credentials not found. Auth features may not work.${NC}"
        echo -e "${YELLOW}  Set GOOGLE_APPLICATION_CREDENTIALS or add a *firebase*adminsdk*.json file${NC}"
    fi
else
    echo -e "${GREEN}✓ Firebase credentials: $GOOGLE_APPLICATION_CREDENTIALS${NC}"
fi

# Preferred ports (will find alternatives if in use)
PREFERRED_BACKEND_PORT=${TERMIVOXED_PORT:-8000}
PREFERRED_FRONTEND_PORT=${TERMIVOXED_FRONTEND_PORT:-5173}

# Find available ports
echo -e "${CYAN}Finding available ports...${NC}"

BACKEND_PORT=$(find_available_port $PREFERRED_BACKEND_PORT)
if [ -z "$BACKEND_PORT" ]; then
    echo -e "${RED}Error: Could not find an available port for the backend (tried $PREFERRED_BACKEND_PORT-$((PREFERRED_BACKEND_PORT + 9)))${NC}"
    exit 1
fi

FRONTEND_PORT=$(find_available_port $PREFERRED_FRONTEND_PORT)
if [ -z "$FRONTEND_PORT" ]; then
    echo -e "${RED}Error: Could not find an available port for the frontend (tried $PREFERRED_FRONTEND_PORT-$((PREFERRED_FRONTEND_PORT + 9)))${NC}"
    exit 1
fi

# Show port info
if [ "$BACKEND_PORT" != "$PREFERRED_BACKEND_PORT" ]; then
    echo -e "${YELLOW}  Backend port $PREFERRED_BACKEND_PORT is in use, using port $BACKEND_PORT instead${NC}"
else
    echo -e "${GREEN}  Backend port: $BACKEND_PORT${NC}"
fi

if [ "$FRONTEND_PORT" != "$PREFERRED_FRONTEND_PORT" ]; then
    echo -e "${YELLOW}  Frontend port $PREFERRED_FRONTEND_PORT is in use, using port $FRONTEND_PORT instead${NC}"
else
    echo -e "${GREEN}  Frontend port: $FRONTEND_PORT${NC}"
fi

# Export for use by other scripts and processes
export TERMIVOXED_PORT=$BACKEND_PORT
export TERMIVOXED_FRONTEND_PORT=$FRONTEND_PORT
export TERMIVOXED_HOST

# Write port config for frontend to read
PORT_CONFIG_FILE="/tmp/termivoxed_ports_$$.json"
echo "{\"backend_port\": $BACKEND_PORT, \"frontend_port\": $FRONTEND_PORT, \"host\": \"$TERMIVOXED_HOST\"}" > "$PORT_CONFIG_FILE"

echo ""

# =============================================================================
# VIRTUAL ENVIRONMENT
# =============================================================================

# Activate venv first if it exists (in parent directory)
VENV_ACTIVATED=false
if [ -d "../venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source ../venv/bin/activate
    VENV_ACTIVATED=true
fi

# Install Python dependencies if needed (now installs into venv)
echo -e "${GREEN}Checking Python dependencies...${NC}"
# Install main project requirements first
if [ -f "../requirements.txt" ]; then
    pip install -q -r ../requirements.txt
fi
# Install web_ui specific requirements (includes LangChain packages)
pip install -q -r requirements.txt

# Install frontend dependencies if needed
echo -e "${GREEN}Checking frontend dependencies...${NC}"
cd frontend
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
cd ..

echo ""
echo -e "${GREEN}Starting TermiVoxed Web UI...${NC}"
echo ""

# =============================================================================
# CLEANUP FUNCTION (only kills OUR processes, not by port)
# =============================================================================

cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"

    # Kill backend process (by PID, not by port!)
    if [ -n "$BACKEND_PID" ]; then
        echo -e "${YELLOW}Stopping API server (PID: $BACKEND_PID)...${NC}"
        kill -TERM $BACKEND_PID 2>/dev/null || true
        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! kill -0 $BACKEND_PID 2>/dev/null; then
                break
            fi
            sleep 0.5
        done
        kill -9 $BACKEND_PID 2>/dev/null || true
    fi

    # Kill frontend process (by PID, not by port!)
    if [ -n "$FRONTEND_PID" ]; then
        echo -e "${YELLOW}Stopping frontend (PID: $FRONTEND_PID)...${NC}"
        kill -TERM $FRONTEND_PID 2>/dev/null || true
        for i in {1..5}; do
            if ! kill -0 $FRONTEND_PID 2>/dev/null; then
                break
            fi
            sleep 0.3
        done
        kill -9 $FRONTEND_PID 2>/dev/null || true
    fi

    # Clean up port config file
    rm -f "$PORT_CONFIG_FILE" 2>/dev/null || true

    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Enable job control for proper process group handling
set -m

# =============================================================================
# START SERVICES
# =============================================================================

# Start backend
echo -e "${GREEN}Starting API server on http://${TERMIVOXED_HOST}:${BACKEND_PORT}${NC}"
cd ..

# Venv should already be activated from earlier, but activate if not
if [ "$VENV_ACTIVATED" != "true" ] && [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start uvicorn in background with dynamic port
python3 -m uvicorn web_ui.api.main:app --host 0.0.0.0 --port ${BACKEND_PORT} --reload &
BACKEND_PID=$!
cd web_ui

# Wait for backend to start
echo -e "${CYAN}Waiting for backend to start...${NC}"
for i in {1..30}; do
    if curl -s "http://localhost:${BACKEND_PORT}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}Backend is ready!${NC}"
        break
    fi
    sleep 0.5
done

# Start frontend with dynamic port and backend port
echo -e "${GREEN}Starting frontend on http://${TERMIVOXED_HOST}:${FRONTEND_PORT}${NC}"
cd frontend

# Pass backend port to Vite via environment variable
VITE_BACKEND_PORT=${BACKEND_PORT} npm run dev -- --port ${FRONTEND_PORT} &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  TermiVoxed Web UI is running!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend:  ${CYAN}http://${TERMIVOXED_HOST}:${FRONTEND_PORT}${NC}"
echo -e "  API:       ${CYAN}http://${TERMIVOXED_HOST}:${BACKEND_PORT}${NC}"
echo -e "  API Docs:  ${CYAN}http://${TERMIVOXED_HOST}:${BACKEND_PORT}/docs${NC}"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all services"
echo ""

# Wait for processes
wait
