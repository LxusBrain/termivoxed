#!/bin/bash

# TermiVoxed - Unix/Linux/macOS Setup Script
# Author: Santhosh T / LxusBrain
#
# This script sets up TermiVoxed on Unix-like systems with proper
# dependency validation and error handling.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track warnings
SETUP_WARNINGS=0
PYTHON_TOO_NEW=0

echo ""
echo "========================================"
echo "  TermiVoxed - Setup"
echo "  AI Voice-Over Dubbing Studio"
echo "========================================"
echo ""

# ============================================================
# STEP 1: Check Python Installation
# ============================================================
echo -e "${BLUE}[1/7]${NC} Checking Python installation..."

# Try python3 first, then python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    # Check if 'python' is Python 3
    py_ver=$(python --version 2>&1)
    if [[ "$py_ver" == Python\ 3* ]]; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    echo -e "${RED}  ERROR: Python 3 not found${NC}"
    echo ""
    echo "  Please install Python 3.10 or 3.11:"
    echo "    macOS:  brew install python@3.11"
    echo "    Ubuntu: sudo apt install python3.11 python3.11-venv"
    echo "    Fedora: sudo dnf install python3.11"
    echo ""
    exit 1
fi

# Get Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

echo "       Python version: $PYTHON_VERSION (using $PYTHON_CMD)"

# Validate Python version
if [ "$PYTHON_MAJOR" -ne 3 ]; then
    echo ""
    echo -e "${RED}  ERROR: Python 3 is required, but found Python $PYTHON_MAJOR${NC}"
    echo "  Please install Python 3.10 or 3.11"
    echo ""
    exit 1
fi

if [ "$PYTHON_MINOR" -lt 9 ]; then
    echo ""
    echo -e "${RED}  ERROR: Python 3.9+ is required, but found Python 3.$PYTHON_MINOR${NC}"
    echo "  Please upgrade to Python 3.10 or 3.11"
    echo ""
    exit 1
fi

if [ "$PYTHON_MINOR" -ge 12 ]; then
    echo ""
    echo -e "${YELLOW}  WARNING: Python 3.$PYTHON_MINOR detected${NC}"
    echo ""
    echo "  Coqui TTS (local voice synthesis) requires Python 3.9-3.11."
    echo "  You can still use cloud-based voice synthesis (Edge-TTS)."
    echo ""
    echo "  For full local TTS support, consider using Python 3.10 or 3.11"
    echo ""
    SETUP_WARNINGS=1
    PYTHON_TOO_NEW=1
    sleep 2
else
    echo -e "       ${GREEN}[OK]${NC} Python version is compatible"
fi

# ============================================================
# STEP 2: Check pip Installation
# ============================================================
echo ""
echo -e "${BLUE}[2/7]${NC} Checking pip installation..."

if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    echo ""
    echo -e "${YELLOW}  pip not found, attempting to install...${NC}"
    $PYTHON_CMD -m ensurepip --upgrade 2>/dev/null || {
        echo ""
        echo -e "${RED}  ERROR: Failed to install pip${NC}"
        echo "  Please install pip manually:"
        echo "    macOS:  brew install python (includes pip)"
        echo "    Ubuntu: sudo apt install python3-pip"
        echo ""
        exit 1
    }
fi

PIP_VERSION=$($PYTHON_CMD -m pip --version 2>&1 | awk '{print $2}')
echo "       pip version: $PIP_VERSION"
echo -e "       ${GREEN}[OK]${NC} pip is available"

# ============================================================
# STEP 3: Check FFmpeg Installation (REQUIRED)
# ============================================================
echo ""
echo -e "${BLUE}[3/7]${NC} Checking FFmpeg installation..."

if ! command -v ffmpeg &> /dev/null; then
    echo ""
    echo -e "${RED}  =====================================================${NC}"
    echo -e "${RED}   FFmpeg is REQUIRED but not installed${NC}"
    echo -e "${RED}  =====================================================${NC}"
    echo ""
    echo "  FFmpeg is essential for video processing. Without it,"
    echo "  TermiVoxed cannot export videos or process audio."
    echo ""
    echo "  Installation:"
    echo ""
    echo "    macOS (Homebrew):"
    echo "      brew install ffmpeg"
    echo ""
    echo "    Ubuntu/Debian:"
    echo "      sudo apt update && sudo apt install ffmpeg"
    echo ""
    echo "    Fedora:"
    echo "      sudo dnf install ffmpeg"
    echo ""
    echo "    Arch Linux:"
    echo "      sudo pacman -S ffmpeg"
    echo ""
    echo "  After installing FFmpeg, run this setup script again."
    echo ""
    exit 1
else
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -n1 | awk '{print $3}')
    echo "       FFmpeg version: $FFMPEG_VERSION"
    echo -e "       ${GREEN}[OK]${NC} FFmpeg is installed"
fi

# ============================================================
# STEP 4: Create Virtual Environment
# ============================================================
echo ""
echo -e "${BLUE}[4/7]${NC} Setting up virtual environment..."

if [ -f "venv/bin/activate" ]; then
    echo "       Virtual environment already exists"
else
    # Remove incomplete venv if exists
    if [ -d "venv" ]; then
        echo "       Removing incomplete venv..."
        rm -rf venv 2>/dev/null || true
    fi

    echo "       Creating virtual environment..."
    $PYTHON_CMD -m venv venv || {
        echo ""
        echo -e "${RED}  ERROR: Failed to create virtual environment${NC}"
        echo ""
        echo "  Possible causes:"
        echo "  - python3-venv package not installed"
        echo "  - Insufficient disk space"
        echo "  - Permission denied"
        echo ""
        echo "  Try installing venv package:"
        echo "    Ubuntu: sudo apt install python3-venv"
        echo "    Fedora: sudo dnf install python3-virtualenv"
        echo ""
        exit 1
    }

    # Verify venv was created
    if [ ! -f "venv/bin/activate" ]; then
        echo ""
        echo -e "${RED}  ERROR: Virtual environment creation failed${NC}"
        echo "  The venv/bin/activate file was not created"
        echo ""
        exit 1
    fi

    echo -e "       ${GREEN}[OK]${NC} Virtual environment created"
fi

# ============================================================
# STEP 5: Activate and Upgrade pip
# ============================================================
echo ""
echo -e "${BLUE}[5/7]${NC} Activating virtual environment..."

# shellcheck disable=SC1091
source venv/bin/activate || {
    echo ""
    echo -e "${RED}  ERROR: Failed to activate virtual environment${NC}"
    exit 1
}

echo -e "       ${GREEN}[OK]${NC} Virtual environment activated"
echo ""
echo "       Upgrading pip..."

pip install --upgrade pip --quiet 2>/dev/null || {
    echo -e "       ${YELLOW}WARNING: pip upgrade failed, continuing with existing version${NC}"
    SETUP_WARNINGS=1
}

echo -e "       ${GREEN}[OK]${NC} pip ready"

# ============================================================
# STEP 6: Install Dependencies
# ============================================================
echo ""
echo -e "${BLUE}[6/7]${NC} Installing core dependencies..."
echo "       This may take a few minutes..."
echo ""

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo ""
    echo -e "${RED}  ERROR: requirements.txt not found${NC}"
    echo "  Please ensure you're running this from the project root directory"
    echo ""
    exit 1
fi

# Temporarily disable exit on error for pip install
set +e
pip install -r requirements.txt
PIP_RESULT=$?
set -e

if [ $PIP_RESULT -ne 0 ]; then
    echo ""
    echo -e "${RED}  =====================================================${NC}"
    echo -e "${RED}   ERROR: Failed to install dependencies${NC}"
    echo -e "${RED}  =====================================================${NC}"
    echo ""
    echo "  Some packages failed to install. Common causes:"
    echo "  - Network connection issues"
    echo "  - Package version conflicts"
    echo "  - Missing C/C++ compiler (for compiled packages)"
    echo ""
    echo "  Try running: pip install -r requirements.txt --verbose"
    echo "  to see detailed error messages."
    echo ""
    exit 1
else
    echo ""
    echo -e "       ${GREEN}[OK]${NC} Core dependencies installed"
fi

# ============================================================
# STEP 7: Optional Local TTS
# ============================================================
echo ""
echo -e "${BLUE}[7/7]${NC} Optional: Local TTS (Coqui TTS)"
echo ""
echo "  Coqui TTS enables offline voice synthesis:"
echo "  - Complete privacy (all processing on-device)"
echo "  - No internet required for voice generation"
echo "  - Voice cloning support"
echo ""
echo "  Requirements:"
echo "  - Python 3.9-3.11 (you have $PYTHON_VERSION)"
echo "  - ~2GB disk space for models"
echo "  - GPU recommended for real-time performance"
echo ""

if [ "$PYTHON_TOO_NEW" -eq 1 ]; then
    echo -e "  ${YELLOW}NOTE: Your Python version ($PYTHON_VERSION) is too new for Coqui TTS.${NC}"
    echo "        You can still use cloud-based Edge-TTS voices."
    echo "        To use local TTS, install Python 3.10 or 3.11."
    echo ""
    echo "  Skipping Coqui TTS installation."
else
    read -p "  Install Coqui TTS? (y/N): " INSTALL_TTS
    if [[ "$INSTALL_TTS" =~ ^[Yy]$ ]]; then
        echo ""
        echo "  Installing Coqui TTS..."

        # Detect NVIDIA GPU
        USE_CUDA=0
        if command -v nvidia-smi &> /dev/null; then
            echo "  NVIDIA GPU detected - attempting CUDA installation"
            USE_CUDA=1
        fi

        set +e
        if [ "$USE_CUDA" -eq 1 ]; then
            pip install "TTS[cuda]>=0.22.0" 2>/dev/null
            if [ $? -ne 0 ]; then
                echo "  CUDA version failed, trying CPU version..."
                pip install "TTS>=0.22.0"
            fi
        else
            echo "  Installing CPU version..."
            pip install "TTS>=0.22.0"
        fi
        TTS_RESULT=$?
        set -e

        if [ $TTS_RESULT -ne 0 ]; then
            echo ""
            echo -e "  ${YELLOW}WARNING: Coqui TTS installation failed${NC}"
            echo ""
            echo "  This is often due to:"
            echo "  - Python version incompatibility (need 3.9-3.11)"
            echo "  - Missing build dependencies"
            echo ""
            echo "  You can still use cloud-based Edge-TTS voices."
            echo "  To try again later: pip install TTS"
            echo ""
            SETUP_WARNINGS=1
        else
            echo -e "  ${GREEN}[OK]${NC} Coqui TTS installed"

            echo ""
            echo "  Installing faster-whisper for subtitle timing..."
            set +e
            pip install "faster-whisper>=1.0.0"
            FW_RESULT=$?
            set -e

            if [ $FW_RESULT -ne 0 ]; then
                echo -e "  ${YELLOW}WARNING: faster-whisper installation failed${NC}"
                echo "  Subtitles will use estimated timing"
                SETUP_WARNINGS=1
            else
                echo -e "  ${GREEN}[OK]${NC} faster-whisper installed"
            fi
        fi
    else
        echo ""
        echo "  Skipping Coqui TTS (you can install later)"
        echo "  To install later: pip install TTS faster-whisper"
    fi
fi

# ============================================================
# Create Storage Directories
# ============================================================
echo ""
echo "Creating storage directories..."

mkdir -p storage/{projects,temp,cache,output,fonts} 2>/dev/null || true
mkdir -p logs 2>/dev/null || true

echo -e "       ${GREEN}[OK]${NC} Storage directories ready"

# ============================================================
# Setup Environment File
# ============================================================
echo ""
echo "Setting up environment configuration..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp ".env.example" ".env"
        echo -e "       ${GREEN}[OK]${NC} .env file created from template"
    else
        echo -e "       ${YELLOW}WARNING: .env.example not found${NC}"
        echo "       You may need to create .env manually"
        SETUP_WARNINGS=1
    fi
else
    echo -e "       ${GREEN}[OK]${NC} .env file already exists"
fi

# ============================================================
# Optional: Custom Domain
# ============================================================
echo ""
echo "=========================================="
echo "Optional: Custom Local Domain"
echo "=========================================="
echo ""
echo "You can access TermiVoxed via a custom domain instead of localhost."
echo "This adds 'termivoxed.local' to your hosts file."
echo ""
read -p "Setup custom domain (termivoxed.local)? (y/N): " SETUP_DOMAIN

if [[ "$SETUP_DOMAIN" =~ ^[Yy]$ ]]; then
    HOSTS_ENTRY="127.0.0.1    termivoxed.local"

    if grep -q "termivoxed.local" /etc/hosts 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC} termivoxed.local already configured"
    else
        echo "Adding termivoxed.local to /etc/hosts (requires sudo)..."
        echo "$HOSTS_ENTRY" | sudo tee -a /etc/hosts > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[OK]${NC} termivoxed.local added to /etc/hosts"
        else
            echo -e "${YELLOW}WARNING: Failed to update /etc/hosts${NC}"
            echo "  You can manually add: $HOSTS_ENTRY"
            SETUP_WARNINGS=1
        fi
    fi

    # Update .env
    if [ -f .env ]; then
        if grep -q "TERMIVOXED_HOST" .env; then
            sed -i.bak 's/^TERMIVOXED_HOST=.*/TERMIVOXED_HOST=termivoxed.local/' .env
        else
            echo "TERMIVOXED_HOST=termivoxed.local" >> .env
        fi
        rm -f .env.bak 2>/dev/null
    fi
else
    echo "Skipping custom domain setup"
fi

# ============================================================
# Optional: Custom Ports
# ============================================================
echo ""
echo "=========================================="
echo "Optional: Custom Ports"
echo "=========================================="
echo ""
echo "Default ports: Backend=8000, Frontend=5173"
echo ""
read -p "Configure custom ports? (y/N): " SETUP_PORTS

BACKEND_PORT="8000"
FRONTEND_PORT="5173"

if [[ "$SETUP_PORTS" =~ ^[Yy]$ ]]; then
    read -p "Backend API port [8000]: " CUSTOM_BACKEND
    read -p "Frontend port [5173]: " CUSTOM_FRONTEND

    BACKEND_PORT=${CUSTOM_BACKEND:-8000}
    FRONTEND_PORT=${CUSTOM_FRONTEND:-5173}

    if [ -f .env ]; then
        if grep -q "^TERMIVOXED_PORT=" .env; then
            sed -i.bak "s/^TERMIVOXED_PORT=.*/TERMIVOXED_PORT=$BACKEND_PORT/" .env
        else
            echo "TERMIVOXED_PORT=$BACKEND_PORT" >> .env
        fi

        if grep -q "^TERMIVOXED_FRONTEND_PORT=" .env; then
            sed -i.bak "s/^TERMIVOXED_FRONTEND_PORT=.*/TERMIVOXED_FRONTEND_PORT=$FRONTEND_PORT/" .env
        else
            echo "TERMIVOXED_FRONTEND_PORT=$FRONTEND_PORT" >> .env
        fi
        rm -f .env.bak 2>/dev/null
        echo -e "${GREEN}[OK]${NC} Custom ports configured"
    fi
else
    echo "Using default ports"
fi

# ============================================================
# Final Summary
# ============================================================
echo ""
echo "========================================================"

if [ "$SETUP_WARNINGS" -eq 1 ]; then
    echo -e "${YELLOW}  SETUP COMPLETED WITH WARNINGS${NC}"
    echo "========================================================"
    echo ""
    echo "  TermiVoxed is installed, but some optional components"
    echo "  may not be available. Review the warnings above."
    echo ""
else
    echo -e "${GREEN}  SETUP COMPLETED SUCCESSFULLY${NC}"
    echo "========================================================"
    echo ""
fi

# Determine display host
DISPLAY_HOST="localhost"
if [[ "$SETUP_DOMAIN" =~ ^[Yy]$ ]]; then
    DISPLAY_HOST="termivoxed.local"
fi

echo "  To run TermiVoxed:"
echo ""
echo "    Option 1: Use the start script"
echo "      ./start.sh"
echo ""
echo "    Option 2: Manual activation"
echo "      source venv/bin/activate"
echo "      python main.py"
echo ""
echo "    Option 3: Start web UI"
echo "      source venv/bin/activate"
echo "      cd web_ui && python -m uvicorn api.main:app --reload"
echo ""
echo "  Access TermiVoxed at:"
echo "    Frontend:  http://${DISPLAY_HOST}:${FRONTEND_PORT}"
echo "    API:       http://${DISPLAY_HOST}:${BACKEND_PORT}"
echo "    API Docs:  http://${DISPLAY_HOST}:${BACKEND_PORT}/docs"
echo ""
