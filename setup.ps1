#!/usr/bin/env pwsh
# TermiVoxed - Windows PowerShell Setup Script
# Author: Santhosh T
#
# This script sets up the TermiVoxed on Windows systems using PowerShell

Write-Host ""
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "TermiVoxed - Setup"  -ForegroundColor Cyan
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "[1/6] Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host $pythonVersion -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8 or higher from https://www.python.org/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if FFmpeg is installed
Write-Host ""
Write-Host "[2/6] Checking FFmpeg installation..." -ForegroundColor Yellow
try {
    $ffmpegVersion = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "FFmpeg found!" -ForegroundColor Green
} catch {
    Write-Host "WARNING: FFmpeg is not installed or not in PATH" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please install FFmpeg:" -ForegroundColor Yellow
    Write-Host "  1. Download from https://ffmpeg.org/download.html"
    Write-Host "  2. Extract to a folder"
    Write-Host "  3. Add the bin folder to your system PATH"
    Write-Host ""
    Write-Host "Or use Chocolatey: choco install ffmpeg" -ForegroundColor Cyan
    Write-Host "Or use Scoop: scoop install ffmpeg" -ForegroundColor Cyan
    Write-Host ""
    Read-Host "Press Enter to continue"
}

# Create virtual environment
Write-Host ""
Write-Host "[3/6] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "Virtual environment already exists" -ForegroundColor Green
} else {
    python -m venv venv
    Write-Host "Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "[4/6] Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Upgrade pip
Write-Host ""
Write-Host "[5/6] Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

# Install dependencies
Write-Host ""
Write-Host "[6/6] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Optional: Local TTS (Coqui TTS)
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Optional: Local TTS (Coqui TTS)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Coqui TTS enables offline voice synthesis without sending data to cloud."
Write-Host "Benefits:"
Write-Host "  - Complete privacy (all processing on-device)"
Write-Host "  - No internet required for voice generation"
Write-Host "  - Voice cloning support"
Write-Host "  - Accurate word-level subtitles (via faster-whisper)"
Write-Host ""
Write-Host "Requirements:"
Write-Host "  - ~2GB disk space for models"
Write-Host "  - GPU recommended for real-time performance"
Write-Host ""

$install_coqui = Read-Host "Install Coqui TTS? (y/N)"
if ($install_coqui -eq "y" -or $install_coqui -eq "Y") {
    Write-Host ""
    Write-Host "Installing Coqui TTS..." -ForegroundColor Yellow

    # Check for NVIDIA GPU
    $hasNvidiaGpu = $null -ne (Get-Command nvidia-smi -ErrorAction SilentlyContinue)
    if ($hasNvidiaGpu) {
        Write-Host "NVIDIA GPU detected - installing with CUDA support" -ForegroundColor Green
        pip install "TTS[cuda]>=0.22.0"
        if ($LASTEXITCODE -ne 0) {
            pip install "TTS>=0.22.0"
        }
    } else {
        Write-Host "No NVIDIA GPU detected - installing CPU version" -ForegroundColor Yellow
        pip install "TTS>=0.22.0"
    }

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Coqui TTS installed successfully" -ForegroundColor Green

        # Install faster-whisper for word-level subtitle timing
        Write-Host ""
        Write-Host "Installing faster-whisper for accurate subtitle timing..." -ForegroundColor Yellow
        pip install "faster-whisper>=1.0.0"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "faster-whisper installed successfully" -ForegroundColor Green
        } else {
            Write-Host "WARNING: faster-whisper installation failed - subtitles will use estimated timing" -ForegroundColor Yellow
            Write-Host "  You can install it later: pip install faster-whisper" -ForegroundColor Yellow
        }
    } else {
        Write-Host "WARNING: Coqui TTS installation failed - continuing without local TTS" -ForegroundColor Yellow
        Write-Host "  You can install it later: pip install TTS>=0.22.0" -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping Coqui TTS installation"
    Write-Host "  To install later: pip install TTS>=0.22.0 faster-whisper" -ForegroundColor Cyan
}

# Create storage directories
Write-Host ""
Write-Host "Creating storage directories..." -ForegroundColor Yellow
$directories = @(
    "storage\projects",
    "storage\temp",
    "storage\cache",
    "storage\output",
    "storage\fonts",
    "logs"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "Storage directories created" -ForegroundColor Green

# Copy .env.example to .env if not exists
Write-Host ""
Write-Host "Setting up environment configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created from template" -ForegroundColor Green
    Write-Host "Please edit .env file if you need to customize paths" -ForegroundColor Cyan
} else {
    Write-Host ".env file already exists" -ForegroundColor Green
}

# Optional: Custom Local Domain
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Optional: Custom Local Domain" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can access TermiVoxed via a custom domain instead of localhost."
Write-Host "This adds 'termivoxed.local' to your hosts file."
Write-Host ""

$setup_domain = Read-Host "Setup custom domain (termivoxed.local)? (y/N)"
$customDomainSetup = $false

if ($setup_domain -eq "y" -or $setup_domain -eq "Y") {
    $hostsFile = "$env:SystemRoot\System32\drivers\etc\hosts"
    $hostsEntry = "127.0.0.1    termivoxed.local"

    # Check if entry already exists
    $hostsContent = Get-Content $hostsFile -ErrorAction SilentlyContinue
    if ($hostsContent -match "termivoxed\.local") {
        Write-Host "termivoxed.local already configured in hosts file" -ForegroundColor Green
        $customDomainSetup = $true
    } else {
        # Check if running as admin
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

        if ($isAdmin) {
            try {
                Add-Content -Path $hostsFile -Value "`n$hostsEntry" -ErrorAction Stop
                Write-Host "termivoxed.local added to hosts file" -ForegroundColor Green
                $customDomainSetup = $true
            } catch {
                Write-Host "Failed to update hosts file: $_" -ForegroundColor Red
            }
        } else {
            Write-Host ""
            Write-Host "Administrator privileges required to modify hosts file." -ForegroundColor Yellow
            Write-Host "Please run this command in an elevated PowerShell:" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "  Add-Content -Path `"$hostsFile`" -Value `"$hostsEntry`"" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "Or manually add this line to $hostsFile :" -ForegroundColor Yellow
            Write-Host "  $hostsEntry" -ForegroundColor White
        }
    }

    # Update .env with custom hostname
    if (Test-Path ".env") {
        $envContent = Get-Content ".env" -Raw
        if ($envContent -match "TERMIVOXED_HOST") {
            $envContent = $envContent -replace "TERMIVOXED_HOST=.*", "TERMIVOXED_HOST=termivoxed.local"
        } else {
            $envContent += "`nTERMIVOXED_HOST=termivoxed.local"
        }
        Set-Content ".env" $envContent
        Write-Host "Updated .env with TERMIVOXED_HOST=termivoxed.local" -ForegroundColor Green
    }
} else {
    Write-Host "Skipping custom domain setup"
    Write-Host "  You can access via: http://localhost:8000" -ForegroundColor Cyan
}

# Optional: Custom Ports
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Optional: Custom Ports" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Default ports: Backend=8000, Frontend=5173"
Write-Host "Change these if the default ports are already in use on your system."
Write-Host ""

$setup_ports = Read-Host "Configure custom ports? (y/N)"
$customBackendPort = "8000"
$customFrontendPort = "5173"

if ($setup_ports -eq "y" -or $setup_ports -eq "Y") {
    Write-Host ""
    $inputBackendPort = Read-Host "Backend API port [8000]"
    if ($inputBackendPort) { $customBackendPort = $inputBackendPort }

    $inputFrontendPort = Read-Host "Frontend port [5173]"
    if ($inputFrontendPort) { $customFrontendPort = $inputFrontendPort }

    # Update .env with custom ports
    if (Test-Path ".env") {
        $envContent = Get-Content ".env" -Raw

        # Update or add TERMIVOXED_PORT
        if ($envContent -match "TERMIVOXED_PORT=") {
            $envContent = $envContent -replace "TERMIVOXED_PORT=.*", "TERMIVOXED_PORT=$customBackendPort"
        } else {
            $envContent += "`nTERMIVOXED_PORT=$customBackendPort"
        }

        # Update or add TERMIVOXED_FRONTEND_PORT
        if ($envContent -match "TERMIVOXED_FRONTEND_PORT=") {
            $envContent = $envContent -replace "TERMIVOXED_FRONTEND_PORT=.*", "TERMIVOXED_FRONTEND_PORT=$customFrontendPort"
        } else {
            $envContent += "`nTERMIVOXED_FRONTEND_PORT=$customFrontendPort"
        }

        Set-Content ".env" $envContent
        Write-Host "Updated .env with custom ports" -ForegroundColor Green
        Write-Host "  Backend: $customBackendPort" -ForegroundColor White
        Write-Host "  Frontend: $customFrontendPort" -ForegroundColor White
    }
} else {
    Write-Host "Using default ports (Backend: 8000, Frontend: 5173)"
}

Write-Host ""
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "Setup Complete!"  -ForegroundColor Green
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""
Write-Host "To run the application:" -ForegroundColor Yellow
Write-Host "  1. Activate virtual environment: .\venv\Scripts\Activate.ps1"
Write-Host "  2. Run the editor: python main.py"
Write-Host ""
Write-Host "Or simply run: .\run.ps1" -ForegroundColor Cyan
Write-Host ""

# Determine display host
$displayHost = "localhost"
if ($customDomainSetup -or ($setup_domain -eq "y" -or $setup_domain -eq "Y")) {
    $displayHost = "termivoxed.local"
}

Write-Host "Access TermiVoxed at:" -ForegroundColor Green
Write-Host "  -> Frontend:  http://${displayHost}:${customFrontendPort}" -ForegroundColor White
Write-Host "  -> API:       http://${displayHost}:${customBackendPort}" -ForegroundColor White
Write-Host "  -> API Docs:  http://${displayHost}:${customBackendPort}/docs" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to exit"
