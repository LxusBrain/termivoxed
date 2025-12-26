#!/bin/bash

# TermiVoxed Web UI - Setup Script (Unix/Linux/macOS)
# Author: Santhosh T
#
# This script sets up the TermiVoxed Web UI with all dependencies

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  $1${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
}

print_check() {
    if [ "$2" = "true" ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_header "TermiVoxed Web UI - Setup"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$SCRIPT_DIR"

echo "Project root: $PROJECT_ROOT"
echo "Web UI dir: $SCRIPT_DIR"
echo ""

# ==========================================
# Check Python
# ==========================================
print_header "Checking Python"

if command -v python3 &> /dev/null; then
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    print_check "Python installed: v$python_version" "true"
else
    print_check "Python not found!" "false"
    echo "  Please install Python 3.8+"
    exit 1
fi

# Check if main project venv exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    print_check "Main project virtual environment exists" "true"
    VENV_PATH="$PROJECT_ROOT/venv"
else
    print_warning "Main project venv not found. Creating..."
    cd "$PROJECT_ROOT"
    python3 -m venv venv
    VENV_PATH="$PROJECT_ROOT/venv"
    print_check "Virtual environment created" "true"
    cd "$SCRIPT_DIR"
fi

# Activate venv
echo ""
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"
print_check "Virtual environment activated" "true"

# ==========================================
# Check FFmpeg
# ==========================================
print_header "Checking FFmpeg"

if command -v ffmpeg &> /dev/null; then
    ffmpeg_version=$(ffmpeg -version 2>&1 | head -n 1)
    print_check "FFmpeg installed" "true"
    echo "  $ffmpeg_version"
else
    print_check "FFmpeg not found!" "false"
    echo ""
    echo "Please install FFmpeg:"
    echo "  macOS:  brew install ffmpeg"
    echo "  Ubuntu: sudo apt-get install ffmpeg"
    echo "  Fedora: sudo dnf install ffmpeg"
    exit 1
fi

if command -v ffprobe &> /dev/null; then
    print_check "FFprobe installed" "true"
else
    print_check "FFprobe not found!" "false"
    exit 1
fi

# ==========================================
# Check Node.js
# ==========================================
print_header "Checking Node.js"

NODE_REQUIRED_MAJOR=18

if command -v node &> /dev/null; then
    node_version=$(node --version | sed 's/v//')
    node_major=$(echo "$node_version" | cut -d. -f1)

    if [ "$node_major" -ge "$NODE_REQUIRED_MAJOR" ]; then
        print_check "Node.js installed: v$node_version" "true"
    else
        print_check "Node.js version too old: v$node_version (need v$NODE_REQUIRED_MAJOR+)" "false"
        echo ""
        echo "Please upgrade Node.js:"
        echo "  macOS:  brew install node"
        echo "  Or use nvm: https://github.com/nvm-sh/nvm"
        exit 1
    fi
else
    print_check "Node.js not found!" "false"
    echo ""
    echo "Please install Node.js v$NODE_REQUIRED_MAJOR or higher:"
    echo "  macOS:  brew install node"
    echo "  Ubuntu: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
    echo "  Or use nvm: https://github.com/nvm-sh/nvm"
    exit 1
fi

if command -v npm &> /dev/null; then
    npm_version=$(npm --version)
    print_check "npm installed: v$npm_version" "true"
else
    print_check "npm not found!" "false"
    exit 1
fi

# ==========================================
# Check Ollama (Optional)
# ==========================================
print_header "Checking Ollama (Optional)"

if command -v ollama &> /dev/null; then
    print_check "Ollama installed" "true"
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        print_check "Ollama service is running" "true"
        # List models
        models=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(', '.join([m['name'] for m in d.get('models',[])]))" 2>/dev/null || echo "")
        if [ -n "$models" ]; then
            echo "  Available models: $models"
        else
            print_warning "No models installed. Run: ollama pull llama3.2:3b"
        fi
    else
        print_warning "Ollama installed but not running. Start with: ollama serve"
    fi
else
    print_warning "Ollama not installed (optional - for local AI)"
    echo "  Install from: https://ollama.ai"
fi

# ==========================================
# Install Python Dependencies
# ==========================================
print_header "Installing Python Dependencies"

echo "Upgrading pip..."
pip install --upgrade pip -q

# Install main project requirements if not already installed
echo "Installing main project requirements..."
pip install -r "$PROJECT_ROOT/requirements.txt" -q
print_check "Main project dependencies installed" "true"

# Install web UI specific requirements
echo "Installing Web UI requirements..."
pip install -r "$SCRIPT_DIR/requirements.txt" -q
print_check "Web UI dependencies installed" "true"

# ==========================================
# Install Frontend Dependencies
# ==========================================
print_header "Installing Frontend Dependencies"

cd "$SCRIPT_DIR/frontend"

if [ -d "node_modules" ]; then
    print_check "node_modules exists, checking for updates..." "true"
    npm install --silent
else
    echo "Installing npm packages (this may take a minute)..."
    npm install --silent
fi

print_check "Frontend dependencies installed" "true"

# Count installed packages
pkg_count=$(ls node_modules 2>/dev/null | wc -l | tr -d ' ')
echo "  $pkg_count packages installed"

cd "$SCRIPT_DIR"

# ==========================================
# Build Frontend (Production)
# ==========================================
print_header "Building Frontend"

cd "$SCRIPT_DIR/frontend"

echo "Building production bundle..."
npm run build --silent 2>/dev/null || {
    print_warning "Build failed (may need TypeScript fixes). Dev mode will still work."
}

if [ -d "dist" ]; then
    print_check "Frontend built successfully" "true"
    dist_size=$(du -sh dist 2>/dev/null | cut -f1)
    echo "  Build size: $dist_size"
else
    print_warning "Production build not available. Use dev mode."
fi

cd "$SCRIPT_DIR"

# ==========================================
# Create Storage Directories
# ==========================================
print_header "Creating Storage Directories"

mkdir -p "$PROJECT_ROOT/storage/"{projects,temp,cache,output,fonts,uploads}
mkdir -p "$PROJECT_ROOT/logs"
print_check "Storage directories created" "true"

# ==========================================
# Create .env if needed
# ==========================================
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        print_check ".env file created from example" "true"
    fi
else
    print_check ".env file exists" "true"
fi

# ==========================================
# Summary
# ==========================================
print_header "Setup Complete!"

echo -e "${GREEN}✓ All dependencies installed successfully!${NC}"
echo ""
echo "To start the Web UI:"
echo ""
echo -e "  ${YELLOW}cd $SCRIPT_DIR${NC}"
echo -e "  ${YELLOW}./run.sh${NC}"
echo ""
echo "Or manually:"
echo "  1. Activate venv:  source $VENV_PATH/bin/activate"
echo "  2. Start backend:  cd $PROJECT_ROOT && python -m uvicorn web_ui.api.main:app --port 8000"
echo "  3. Start frontend: cd $SCRIPT_DIR/frontend && npm run dev"
echo ""
echo "Access:"
echo "  Web UI:    http://localhost:5173"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo -e "${RED}Happy editing! 🎬${NC}"
