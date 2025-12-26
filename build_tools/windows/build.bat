@echo off
REM TermiVoxed Windows Build Script (Batch Wrapper)
REM Runs the PowerShell build script
REM
REM Author: Santhosh T
REM Usage: build.bat [options]
REM   -Clean          Remove previous builds before building
REM   -SkipInstaller  Skip creating the installer (only build portable)
REM   -Version "x.y.z" Set version number

echo ========================================
echo  TermiVoxed Windows Build Script
echo ========================================
echo.

REM Check for PowerShell
where powershell >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: PowerShell is required to run this build script.
    echo Please install PowerShell or run the build.ps1 script directly.
    pause
    exit /b 1
)

REM Run PowerShell script with same arguments
powershell -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*

pause
