#!/bin/bash

# TermiVoxed - Unix/Linux/macOS Setup Script
# Author: Santhosh T
#
# This script sets up the TermiVoxed on Unix-like systems

echo ""
echo "========================================"
echo "TermiVoxed - Setup"
echo "========================================"
echo ""

# Check Python version (requires 3.9+)
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    python_major=$(echo "$python_version" | cut -d. -f1)
    python_minor=$(echo "$python_version" | cut -d. -f2)

    if [ "$python_major" -ge 3 ] && [ "$python_minor" -ge 9 ]; then
        echo "✓ Python version: $python_version"
    else
        echo "✗ Python version too old: $python_version (need 3.9+)"
        echo "  Please upgrade to Python 3.9+"
        exit 1
    fi
else
    echo "✗ Python not found!"
    echo "  Please install Python 3.9+"
    exit 1
fi
echo ""

# Check FFmpeg
echo "Checking FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    ffmpeg_version=$(ffmpeg -version 2>&1 | head -n 1)
    echo "✓ FFmpeg installed: $ffmpeg_version"
else
    echo "✗ FFmpeg not found!"
    echo "  Please install FFmpeg:"
    echo "    macOS: brew install ffmpeg"
    echo "    Ubuntu: sudo apt-get install ffmpeg"
    exit 1
fi
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
echo "✓ Virtual environment created"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Core dependencies installed"
echo ""

# Optional: Local TTS (Coqui TTS)
echo "=========================================="
echo "Optional: Local TTS (Coqui TTS)"
echo "=========================================="
echo ""
echo "Coqui TTS enables offline voice synthesis without sending data to cloud."
echo "Benefits:"
echo "  - Complete privacy (all processing on-device)"
echo "  - No internet required for voice generation"
echo "  - Voice cloning support"
echo "  - Accurate word-level subtitles (via faster-whisper)"
echo ""
echo "Requirements:"
echo "  - ~2GB disk space for models"
echo "  - GPU recommended for real-time performance"
echo ""
read -p "Install Coqui TTS? (y/N): " install_coqui
if [[ "$install_coqui" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Installing Coqui TTS..."

    # Check for CUDA
    if command -v nvidia-smi &> /dev/null; then
        echo "✓ NVIDIA GPU detected - installing with CUDA support"
        pip install TTS[cuda]>=0.22.0 || pip install TTS>=0.22.0
    else
        echo "○ No NVIDIA GPU detected - installing CPU version"
        pip install TTS>=0.22.0
    fi

    if [ $? -eq 0 ]; then
        echo "✓ Coqui TTS installed successfully"

        # Install faster-whisper for word-level subtitle timing
        echo ""
        echo "Installing faster-whisper for accurate subtitle timing..."
        pip install faster-whisper>=1.0.0
        if [ $? -eq 0 ]; then
            echo "✓ faster-whisper installed successfully"
        else
            echo "⚠ faster-whisper installation failed - subtitles will use estimated timing"
            echo "  You can install it later: pip install faster-whisper"
        fi
    else
        echo "⚠ Coqui TTS installation failed - continuing without local TTS"
        echo "  You can install it later: pip install TTS>=0.22.0"
    fi
else
    echo "Skipping Coqui TTS installation"
    echo "  To install later: pip install TTS>=0.22.0 faster-whisper"
fi
echo ""

# Create .env file
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "✓ .env file created"
else
    echo "✓ .env file already exists"
fi
echo ""

# Create storage directories
echo "Creating storage directories..."
mkdir -p storage/{projects,temp,cache,output,fonts}
mkdir -p logs
echo "✓ Storage directories created"
echo ""

echo "=========================================="
echo "Optional: Custom Local Domain"
echo "=========================================="
echo ""
echo "You can access TermiVoxed via a custom domain instead of localhost."
echo "This adds 'termivoxed.local' to your hosts file."
echo ""
read -p "Setup custom domain (termivoxed.local)? (y/N): " setup_domain
if [[ "$setup_domain" =~ ^[Yy]$ ]]; then
    echo ""
    HOSTS_ENTRY="127.0.0.1    termivoxed.local"

    # Check if entry already exists
    if grep -q "termivoxed.local" /etc/hosts 2>/dev/null; then
        echo "✓ termivoxed.local already configured in /etc/hosts"
    else
        echo "Adding termivoxed.local to /etc/hosts (requires sudo)..."
        echo "$HOSTS_ENTRY" | sudo tee -a /etc/hosts > /dev/null
        if [ $? -eq 0 ]; then
            echo "✓ termivoxed.local added to /etc/hosts"
        else
            echo "⚠ Failed to update /etc/hosts"
            echo "  You can manually add this line to /etc/hosts:"
            echo "  $HOSTS_ENTRY"
        fi
    fi

    # Update .env with custom hostname
    if [ -f .env ]; then
        if grep -q "TERMIVOXED_HOST" .env; then
            sed -i.bak 's/^TERMIVOXED_HOST=.*/TERMIVOXED_HOST=termivoxed.local/' .env
        else
            echo "TERMIVOXED_HOST=termivoxed.local" >> .env
        fi
        echo "✓ Updated .env with TERMIVOXED_HOST=termivoxed.local"
    fi
else
    echo "Skipping custom domain setup"
    echo "  You can access via: http://localhost:8000"
fi
echo ""

echo "=========================================="
echo "Optional: Custom Ports"
echo "=========================================="
echo ""
echo "Default ports: Backend=8000, Frontend=5173"
echo "Change these if the default ports are already in use on your system."
echo ""
read -p "Configure custom ports? (y/N): " setup_ports
if [[ "$setup_ports" =~ ^[Yy]$ ]]; then
    echo ""
    read -p "Backend API port [8000]: " custom_backend_port
    custom_backend_port=${custom_backend_port:-8000}

    read -p "Frontend port [5173]: " custom_frontend_port
    custom_frontend_port=${custom_frontend_port:-5173}

    # Update .env with custom ports
    if [ -f .env ]; then
        # Update or add TERMIVOXED_PORT
        if grep -q "^TERMIVOXED_PORT=" .env; then
            sed -i.bak "s/^TERMIVOXED_PORT=.*/TERMIVOXED_PORT=$custom_backend_port/" .env
        else
            echo "TERMIVOXED_PORT=$custom_backend_port" >> .env
        fi

        # Update or add TERMIVOXED_FRONTEND_PORT
        if grep -q "^TERMIVOXED_FRONTEND_PORT=" .env; then
            sed -i.bak "s/^TERMIVOXED_FRONTEND_PORT=.*/TERMIVOXED_FRONTEND_PORT=$custom_frontend_port/" .env
        else
            echo "TERMIVOXED_FRONTEND_PORT=$custom_frontend_port" >> .env
        fi

        echo "✓ Updated .env with custom ports"
        echo "  Backend: $custom_backend_port"
        echo "  Frontend: $custom_frontend_port"
    fi
else
    echo "Using default ports (Backend: 8000, Frontend: 5173)"
fi
echo ""

# Clean up backup files created by sed
rm -f .env.bak 2>/dev/null

echo "=========================================="
echo "✓ Setup complete!"
echo ""
echo "To start TermiVoxed:"
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo "  2. Run the application:"
echo "     python main.py"
echo ""

# Determine display host and ports
display_host="localhost"
display_backend_port="${custom_backend_port:-8000}"
display_frontend_port="${custom_frontend_port:-5173}"

if [[ "$setup_domain" =~ ^[Yy]$ ]]; then
    display_host="termivoxed.local"
fi

echo "Access TermiVoxed at:"
echo "  → Frontend:  http://${display_host}:${display_frontend_port}"
echo "  → API:       http://${display_host}:${display_backend_port}"
echo "  → API Docs:  http://${display_host}:${display_backend_port}/docs"
echo ""
echo "Happy editing! 🎬"
