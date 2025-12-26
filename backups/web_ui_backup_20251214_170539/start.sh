#!/bin/bash

# TermiVoxed Web UI - Startup Script
# This script starts both the backend API and frontend dev server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Install Python dependencies if needed
echo -e "${GREEN}Checking Python dependencies...${NC}"
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

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"

    # Kill backend process
    if [ -n "$BACKEND_PID" ]; then
        echo -e "${YELLOW}Stopping API server (PID: $BACKEND_PID)...${NC}"
        kill -TERM $BACKEND_PID 2>/dev/null
        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! kill -0 $BACKEND_PID 2>/dev/null; then
                break
            fi
            sleep 0.5
        done
        kill -9 $BACKEND_PID 2>/dev/null
    fi

    # Kill frontend process
    if [ -n "$FRONTEND_PID" ]; then
        echo -e "${YELLOW}Stopping frontend (PID: $FRONTEND_PID)...${NC}"
        kill -TERM $FRONTEND_PID 2>/dev/null
        for i in {1..5}; do
            if ! kill -0 $FRONTEND_PID 2>/dev/null; then
                break
            fi
            sleep 0.3
        done
        kill -9 $FRONTEND_PID 2>/dev/null
    fi

    # Kill any remaining processes on the ports (handles child processes from uvicorn --reload)
    echo -e "${YELLOW}Cleaning up ports...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    lsof -ti:5173 | xargs kill -9 2>/dev/null

    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Clean up any existing processes on the ports before starting
echo -e "${YELLOW}Checking for existing processes on ports...${NC}"
if lsof -ti:8000 > /dev/null 2>&1; then
    echo -e "${YELLOW}Port 8000 is in use. Stopping existing process...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    sleep 1
fi
if lsof -ti:5173 > /dev/null 2>&1; then
    echo -e "${YELLOW}Port 5173 is in use. Stopping existing process...${NC}"
    lsof -ti:5173 | xargs kill -9 2>/dev/null
    sleep 1
fi

# Enable job control for proper process group handling
set -m

# Start backend
echo -e "${GREEN}Starting API server on http://localhost:8000${NC}"
cd ..
# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi
# Start uvicorn in background
python3 -m uvicorn web_ui.api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd web_ui

# Wait for backend to start
sleep 2

# Start frontend
echo -e "${GREEN}Starting frontend on http://localhost:5173${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  TermiVoxed Web UI is running!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend:  ${RED}http://localhost:5173${NC}"
echo -e "  API:       ${RED}http://localhost:8000${NC}"
echo -e "  API Docs:  ${RED}http://localhost:8000/docs${NC}"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all services"
echo ""

# Wait for processes
wait
