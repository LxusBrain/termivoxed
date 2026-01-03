@echo off
REM TermiVoxed - Windows Setup Script
REM Author: Santhosh T / LxusBrain
REM
REM This script sets up TermiVoxed on Windows systems with proper
REM dependency validation and error handling.

setlocal enabledelayedexpansion

echo.
echo ========================================
echo  TermiVoxed - Setup
echo  AI Voice-Over Dubbing Studio
echo ========================================
echo.

REM Track if any step failed
set "SETUP_FAILED=0"
set "SETUP_WARNINGS=0"

REM ============================================================
REM STEP 1: Check Python Installation
REM ============================================================
echo [1/7] Checking Python installation...

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH
    echo.
    echo  Please install Python 3.10 or 3.11 from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: During installation, check the box
    echo  "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM Get Python version
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%v"
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

echo        Python version: %PYTHON_VERSION%

REM Validate Python version
if not "%PY_MAJOR%"=="3" (
    echo.
    echo  ERROR: Python 3 is required, but found Python %PY_MAJOR%
    echo  Please install Python 3.10 or 3.11 from https://python.org
    echo.
    pause
    exit /b 1
)

if %PY_MINOR% lss 9 (
    echo.
    echo  ERROR: Python 3.9+ is required, but found Python 3.%PY_MINOR%
    echo  Please upgrade to Python 3.10 or 3.11
    echo.
    pause
    exit /b 1
)

if %PY_MINOR% geq 12 (
    echo.
    echo  WARNING: Python 3.%PY_MINOR% detected
    echo.
    echo  Coqui TTS (local voice synthesis) requires Python 3.9-3.11
    echo  You can still use cloud-based voice synthesis (Edge-TTS).
    echo.
    echo  For full local TTS support, consider using Python 3.10 or 3.11
    echo.
    set "SETUP_WARNINGS=1"
    set "PYTHON_TOO_NEW=1"
    timeout /t 3 >nul
) else (
    echo        [OK] Python version is compatible
)

REM ============================================================
REM STEP 2: Check pip Installation
REM ============================================================
echo.
echo [2/7] Checking pip installation...

python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: pip is not installed
    echo.
    echo  Installing pip...
    python -m ensurepip --upgrade
    if errorlevel 1 (
        echo  ERROR: Failed to install pip
        echo  Please reinstall Python with pip included
        pause
        exit /b 1
    )
)

for /f "tokens=2 delims= " %%v in ('python -m pip --version 2^>^&1') do set "PIP_VERSION=%%v"
echo        pip version: %PIP_VERSION%
echo        [OK] pip is available

REM ============================================================
REM STEP 3: Check FFmpeg Installation (REQUIRED)
REM ============================================================
echo.
echo [3/7] Checking FFmpeg installation...

ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  =====================================================
    echo   FFmpeg is REQUIRED but not installed
    echo  =====================================================
    echo.
    echo  FFmpeg is essential for video processing. Without it,
    echo  TermiVoxed cannot export videos or process audio.
    echo.
    echo  Installation options:
    echo.
    echo  Option 1 - Using Chocolatey (recommended):
    echo    1. Open PowerShell as Administrator
    echo    2. Run: choco install ffmpeg -y
    echo.
    echo  Option 2 - Using winget:
    echo    winget install FFmpeg
    echo.
    echo  Option 3 - Manual installation:
    echo    1. Download from https://ffmpeg.org/download.html
    echo       (or https://www.gyan.dev/ffmpeg/builds/)
    echo    2. Extract the ZIP file
    echo    3. Add the 'bin' folder to your system PATH
    echo.
    echo  After installing FFmpeg, run this setup script again.
    echo.
    pause
    exit /b 1
) else (
    for /f "tokens=3" %%v in ('ffmpeg -version 2^>^&1 ^| findstr /i "version"') do (
        echo        FFmpeg version: %%v
        goto :ffmpeg_done
    )
    :ffmpeg_done
    echo        [OK] FFmpeg is installed
)

REM ============================================================
REM STEP 4: Create Virtual Environment
REM ============================================================
echo.
echo [4/7] Setting up virtual environment...

if exist "venv\Scripts\activate.bat" (
    echo        Virtual environment already exists
) else (
    if exist "venv" (
        echo        Removing incomplete venv...
        rmdir /s /q venv 2>nul
    )

    echo        Creating virtual environment...
    python -m venv venv

    if errorlevel 1 (
        echo.
        echo  ERROR: Failed to create virtual environment
        echo.
        echo  Possible causes:
        echo  - Insufficient disk space
        echo  - Permission denied
        echo  - Corrupted Python installation
        echo.
        echo  Try: python -m venv --clear venv
        echo.
        pause
        exit /b 1
    )

    REM Verify venv was created
    if not exist "venv\Scripts\activate.bat" (
        echo.
        echo  ERROR: Virtual environment creation failed
        echo  The venv\Scripts\activate.bat file was not created
        echo.
        pause
        exit /b 1
    )

    echo        [OK] Virtual environment created
)

REM ============================================================
REM STEP 5: Activate and Upgrade pip
REM ============================================================
echo.
echo [5/7] Activating virtual environment...

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo  ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo        [OK] Virtual environment activated
echo.
echo        Upgrading pip...

python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo        WARNING: pip upgrade failed, continuing with existing version
    set "SETUP_WARNINGS=1"
) else (
    echo        [OK] pip upgraded
)

REM ============================================================
REM STEP 6: Install Dependencies
REM ============================================================
echo.
echo [6/7] Installing core dependencies...
echo        This may take a few minutes...
echo.

REM Check if requirements.txt exists
if not exist "requirements.txt" (
    echo.
    echo  ERROR: requirements.txt not found
    echo  Please ensure you're running this from the project root directory
    echo.
    pause
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  =====================================================
    echo   ERROR: Failed to install dependencies
    echo  =====================================================
    echo.
    echo  Some packages failed to install. Common causes:
    echo  - Network connection issues
    echo  - Package version conflicts
    echo  - Missing C++ build tools (for compiled packages)
    echo.
    echo  Try running: pip install -r requirements.txt --verbose
    echo  to see detailed error messages.
    echo.
    set "SETUP_FAILED=1"
) else (
    echo.
    echo        [OK] Core dependencies installed
)

REM ============================================================
REM STEP 7: Optional Local TTS
REM ============================================================
echo.
echo [7/7] Optional: Local TTS (Coqui TTS)
echo.
echo  Coqui TTS enables offline voice synthesis:
echo  - Complete privacy (all processing on-device)
echo  - No internet required for voice generation
echo  - Voice cloning support
echo.
echo  Requirements:
echo  - Python 3.9-3.11 (you have %PYTHON_VERSION%)
echo  - ~2GB disk space for models
echo  - GPU recommended for real-time performance
echo.

if defined PYTHON_TOO_NEW (
    echo  NOTE: Your Python version (%PYTHON_VERSION%) is too new for Coqui TTS.
    echo        You can still use cloud-based Edge-TTS voices.
    echo        To use local TTS, install Python 3.10 or 3.11.
    echo.
    echo  Skipping Coqui TTS installation.
    goto :skip_tts
)

set /p "INSTALL_TTS=Install Coqui TTS? (y/N): "
if /i not "%INSTALL_TTS%"=="y" (
    echo.
    echo  Skipping Coqui TTS (you can install later)
    echo  To install later: pip install TTS faster-whisper
    goto :skip_tts
)

echo.
echo  Installing Coqui TTS...

REM Detect NVIDIA GPU
set "USE_CUDA=0"
where nvidia-smi >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo  NVIDIA GPU detected - attempting CUDA installation
    set "USE_CUDA=1"
)

if "%USE_CUDA%"=="1" (
    pip install "TTS[cuda]>=0.22.0" 2>nul
    if errorlevel 1 (
        echo  CUDA version failed, trying CPU version...
        pip install "TTS>=0.22.0"
    )
) else (
    echo  Installing CPU version...
    pip install "TTS>=0.22.0"
)

if errorlevel 1 (
    echo.
    echo  WARNING: Coqui TTS installation failed
    echo.
    echo  This is often due to:
    echo  - Python version incompatibility (need 3.9-3.11)
    echo  - Missing Visual C++ Build Tools
    echo.
    echo  You can still use cloud-based Edge-TTS voices.
    echo  To try again later: pip install TTS
    echo.
    set "SETUP_WARNINGS=1"
) else (
    echo  [OK] Coqui TTS installed

    echo.
    echo  Installing faster-whisper for subtitle timing...
    pip install "faster-whisper>=1.0.0"
    if errorlevel 1 (
        echo  WARNING: faster-whisper installation failed
        echo  Subtitles will use estimated timing
        set "SETUP_WARNINGS=1"
    ) else (
        echo  [OK] faster-whisper installed
    )
)

:skip_tts

REM ============================================================
REM Create Storage Directories
REM ============================================================
echo.
echo Creating storage directories...

if not exist "storage\projects" mkdir "storage\projects" 2>nul
if not exist "storage\temp" mkdir "storage\temp" 2>nul
if not exist "storage\cache" mkdir "storage\cache" 2>nul
if not exist "storage\output" mkdir "storage\output" 2>nul
if not exist "storage\fonts" mkdir "storage\fonts" 2>nul
if not exist "logs" mkdir "logs" 2>nul

echo        [OK] Storage directories ready

REM ============================================================
REM Setup Environment File
REM ============================================================
echo.
echo Setting up environment configuration...

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo        [OK] .env file created from template
    ) else (
        echo        WARNING: .env.example not found
        echo        You may need to create .env manually
        set "SETUP_WARNINGS=1"
    )
) else (
    echo        [OK] .env file already exists
)

REM ============================================================
REM Final Summary
REM ============================================================
echo.
echo ========================================================

if "%SETUP_FAILED%"=="1" (
    echo  SETUP FAILED
    echo ========================================================
    echo.
    echo  Some critical steps failed. Please review the errors
    echo  above and try again after fixing the issues.
    echo.
    pause
    exit /b 1
)

if "%SETUP_WARNINGS%"=="1" (
    echo  SETUP COMPLETED WITH WARNINGS
    echo ========================================================
    echo.
    echo  TermiVoxed is installed, but some optional components
    echo  may not be available. Review the warnings above.
    echo.
) else (
    echo  SETUP COMPLETED SUCCESSFULLY
    echo ========================================================
    echo.
)

echo  To run TermiVoxed:
echo.
echo    Option 1: Run the launcher
echo      run.bat
echo.
echo    Option 2: Manual activation
echo      venv\Scripts\activate.bat
echo      python main.py
echo.
echo    Option 3: Start web UI
echo      venv\Scripts\activate.bat
echo      cd web_ui
echo      python -m uvicorn api.main:app --reload
echo.

pause
exit /b 0
