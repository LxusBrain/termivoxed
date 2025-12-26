@echo off
REM TermiVoxed Web UI - Setup Script (Windows)
REM Author: Santhosh T
REM
REM This script sets up the TermiVoxed Web UI with all dependencies

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   TermiVoxed Web UI - Setup
echo ========================================
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

cd /d "%SCRIPT_DIR%"

echo Project root: %PROJECT_ROOT%
echo Web UI dir: %SCRIPT_DIR%
echo.

REM ==========================================
REM Check Python
REM ==========================================
echo ========================================
echo   Checking Python
echo ========================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [X] Python not found!
    echo     Please install Python 3.8+ from https://python.org
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set python_version=%%i
echo [OK] Python installed: v%python_version%

REM Check if main project venv exists
if exist "%PROJECT_ROOT%\venv" (
    echo [OK] Main project virtual environment exists
    set "VENV_PATH=%PROJECT_ROOT%\venv"
) else (
    echo [!] Main project venv not found. Creating...
    cd /d "%PROJECT_ROOT%"
    python -m venv venv
    set "VENV_PATH=%PROJECT_ROOT%\venv"
    echo [OK] Virtual environment created
    cd /d "%SCRIPT_DIR%"
)

REM Activate venv
echo.
echo Activating virtual environment...
call "%VENV_PATH%\Scripts\activate.bat"
echo [OK] Virtual environment activated
echo.

REM ==========================================
REM Check FFmpeg
REM ==========================================
echo ========================================
echo   Checking FFmpeg
echo ========================================
echo.

where ffmpeg >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [X] FFmpeg not found!
    echo.
    echo Please install FFmpeg:
    echo   1. Download from: https://ffmpeg.org/download.html
    echo   2. Or use chocolatey: choco install ffmpeg
    echo   3. Or use winget: winget install FFmpeg
    echo   4. Add ffmpeg to your PATH
    exit /b 1
)

echo [OK] FFmpeg installed
ffmpeg -version 2>&1 | findstr /r "^ffmpeg"

where ffprobe >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [X] FFprobe not found!
    exit /b 1
)
echo [OK] FFprobe installed
echo.

REM ==========================================
REM Check Node.js
REM ==========================================
echo ========================================
echo   Checking Node.js
echo ========================================
echo.

where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [X] Node.js not found!
    echo.
    echo Please install Node.js v18 or higher:
    echo   1. Download from: https://nodejs.org
    echo   2. Or use chocolatey: choco install nodejs
    echo   3. Or use winget: winget install OpenJS.NodeJS
    exit /b 1
)

for /f "tokens=1" %%i in ('node --version') do set node_version=%%i
echo [OK] Node.js installed: %node_version%

where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [X] npm not found!
    exit /b 1
)

for /f "tokens=1" %%i in ('npm --version') do set npm_version=%%i
echo [OK] npm installed: v%npm_version%
echo.

REM ==========================================
REM Check Ollama (Optional)
REM ==========================================
echo ========================================
echo   Checking Ollama (Optional)
echo ========================================
echo.

where ollama >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [OK] Ollama installed
    curl -s http://localhost:11434/api/tags >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        echo [OK] Ollama service is running
    ) else (
        echo [!] Ollama installed but not running. Start with: ollama serve
    )
) else (
    echo [!] Ollama not installed (optional - for local AI)
    echo     Install from: https://ollama.ai
)
echo.

REM ==========================================
REM Install Python Dependencies
REM ==========================================
echo ========================================
echo   Installing Python Dependencies
echo ========================================
echo.

echo Upgrading pip...
pip install --upgrade pip -q

echo Installing main project requirements...
pip install -r "%PROJECT_ROOT%\requirements.txt" -q
echo [OK] Main project dependencies installed

echo Installing Web UI requirements...
pip install -r "%SCRIPT_DIR%requirements.txt" -q
echo [OK] Web UI dependencies installed
echo.

REM ==========================================
REM Install Frontend Dependencies
REM ==========================================
echo ========================================
echo   Installing Frontend Dependencies
echo ========================================
echo.

cd /d "%SCRIPT_DIR%frontend"

if exist "node_modules" (
    echo [OK] node_modules exists, checking for updates...
    npm install --silent
) else (
    echo Installing npm packages (this may take a minute)...
    npm install --silent
)

echo [OK] Frontend dependencies installed
echo.

cd /d "%SCRIPT_DIR%"

REM ==========================================
REM Build Frontend (Production)
REM ==========================================
echo ========================================
echo   Building Frontend
echo ========================================
echo.

cd /d "%SCRIPT_DIR%frontend"

echo Building production bundle...
npm run build --silent 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Build failed (may need TypeScript fixes). Dev mode will still work.
)

if exist "dist" (
    echo [OK] Frontend built successfully
) else (
    echo [!] Production build not available. Use dev mode.
)

cd /d "%SCRIPT_DIR%"
echo.

REM ==========================================
REM Create Storage Directories
REM ==========================================
echo ========================================
echo   Creating Storage Directories
echo ========================================
echo.

if not exist "%PROJECT_ROOT%\storage\projects" mkdir "%PROJECT_ROOT%\storage\projects"
if not exist "%PROJECT_ROOT%\storage\temp" mkdir "%PROJECT_ROOT%\storage\temp"
if not exist "%PROJECT_ROOT%\storage\cache" mkdir "%PROJECT_ROOT%\storage\cache"
if not exist "%PROJECT_ROOT%\storage\output" mkdir "%PROJECT_ROOT%\storage\output"
if not exist "%PROJECT_ROOT%\storage\fonts" mkdir "%PROJECT_ROOT%\storage\fonts"
if not exist "%PROJECT_ROOT%\storage\uploads" mkdir "%PROJECT_ROOT%\storage\uploads"
if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"
echo [OK] Storage directories created
echo.

REM ==========================================
REM Create .env if needed
REM ==========================================
if not exist "%PROJECT_ROOT%\.env" (
    if exist "%PROJECT_ROOT%\.env.example" (
        copy "%PROJECT_ROOT%\.env.example" "%PROJECT_ROOT%\.env" >nul
        echo [OK] .env file created from example
    )
) else (
    echo [OK] .env file exists
)
echo.

REM ==========================================
REM Summary
REM ==========================================
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo [OK] All dependencies installed successfully!
echo.
echo To start the Web UI:
echo.
echo   cd %SCRIPT_DIR%
echo   run.bat
echo.
echo Or manually:
echo   1. Activate venv:  %VENV_PATH%\Scripts\activate.bat
echo   2. Start backend:  cd %PROJECT_ROOT% ^&^& python -m uvicorn web_ui.api.main:app --port 8000
echo   3. Start frontend: cd %SCRIPT_DIR%frontend ^&^& npm run dev
echo.
echo Access:
echo   Web UI:    http://localhost:5173
echo   API Docs:  http://localhost:8000/docs
echo.
echo Happy editing!
echo.

endlocal
