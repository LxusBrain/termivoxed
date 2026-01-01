@echo off
REM TermiVoxed Web UI - Startup Script (Windows)
REM This script starts both the backend API and frontend dev server
REM
REM SAFE PORT HANDLING: This script finds available ports instead of killing
REM existing processes. It never terminates other applications.

setlocal enabledelayedexpansion

echo.
echo   _____                   _ _   __     __                    _
echo  ^|_   _^|__ _ __ _ __ ___ (_) \  / /____  _____  __  __^| ^|
echo    ^| ^|/ _ \ '__^| '_ ` _ \^| ^|\ \/ / _ \ \/ / _ \/ _^|^| / _` ^|
echo    ^| ^|  __/ ^|  ^| ^| ^| ^| ^| ^| ^| \  / (_) ^>  ^<  __/ (_^| ^| (_^| ^|
echo    ^|_^|\___^|_^|  ^|_^| ^|_^| ^|_^|_^|  \/ \___/_/\_\___^|\__,_^|\__,_^|
echo.
echo   AI Voice-Over Studio - Web UI
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM Check if we're in the right directory
if not exist "%SCRIPT_DIR%api\main.py" (
    echo Error: Please run this script from the web_ui directory
    exit /b 1
)

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Python 3 is required
    exit /b 1
)

REM Check Node.js
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Node.js is required for the frontend
    exit /b 1
)

REM Check FFmpeg
where ffmpeg >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Warning: FFmpeg not found. Video processing will not work.
)

REM Check Ollama
where ollama >nul 2>nul
if %ERRORLEVEL% equ 0 (
    curl -s http://localhost:11434/api/tags >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        echo [OK] Ollama is running
    ) else (
        echo [!] Ollama is installed but not running. Start with: ollama serve
    )
) else (
    echo [!] Ollama not found. Local AI features will be unavailable.
)

echo.

REM Activate virtual environment
if exist "%PROJECT_ROOT%\venv\Scripts\activate.bat" (
    call "%PROJECT_ROOT%\venv\Scripts\activate.bat"
    echo [OK] Virtual environment activated
) else (
    echo [!] Virtual environment not found. Run setup.bat first.
    exit /b 1
)

REM Install Python dependencies if needed
echo Checking Python dependencies...
pip install -q -r "%SCRIPT_DIR%requirements.txt"

REM Install frontend dependencies if needed
echo Checking frontend dependencies...
cd /d "%SCRIPT_DIR%frontend"
if not exist "node_modules" (
    echo Installing frontend dependencies...
    npm install
)
cd /d "%SCRIPT_DIR%"

echo.
echo Finding available ports...

REM Find available backend port (starting from 8000)
set "BACKEND_PORT=8000"
:find_backend_port
netstat -an | find ":%BACKEND_PORT% " | find "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   Port %BACKEND_PORT% is in use, trying next...
    set /a BACKEND_PORT+=1
    if %BACKEND_PORT% gtr 8009 (
        echo Error: Could not find available port for backend
        exit /b 1
    )
    goto find_backend_port
)
echo   Backend port: %BACKEND_PORT%

REM Find available frontend port (starting from 5173)
set "FRONTEND_PORT=5173"
:find_frontend_port
netstat -an | find ":%FRONTEND_PORT% " | find "LISTENING" >nul
if %ERRORLEVEL% equ 0 (
    echo   Port %FRONTEND_PORT% is in use, trying next...
    set /a FRONTEND_PORT+=1
    if %FRONTEND_PORT% gtr 5182 (
        echo Error: Could not find available port for frontend
        exit /b 1
    )
    goto find_frontend_port
)
echo   Frontend port: %FRONTEND_PORT%

echo.
echo Starting TermiVoxed Web UI...
echo.

REM Start backend in a new window with dynamic port
echo Starting API server on http://localhost:%BACKEND_PORT%
start "TermiVoxed API" cmd /c "cd /d %PROJECT_ROOT% && python -m uvicorn web_ui.api.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in a new window with dynamic ports
echo Starting frontend on http://localhost:%FRONTEND_PORT%
start "TermiVoxed Frontend" cmd /c "cd /d %SCRIPT_DIR%frontend && set VITE_BACKEND_PORT=%BACKEND_PORT% && npm run dev -- --port %FRONTEND_PORT%"

echo.
echo ===============================================
echo   TermiVoxed Web UI is starting!
echo ===============================================
echo.
echo   Frontend:  http://localhost:%FRONTEND_PORT%
echo   API:       http://localhost:%BACKEND_PORT%
echo   API Docs:  http://localhost:%BACKEND_PORT%/docs
echo.
echo   Close the command windows to stop the servers.
echo.

REM Open browser after a short delay
timeout /t 5 /nobreak >nul
start http://localhost:%FRONTEND_PORT%

endlocal
