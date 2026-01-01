# TermiVoxed Windows Build Script
# PowerShell script for building Windows installer
#
# Author: Santhosh T
# Usage: .\build.ps1 [-Clean] [-SkipInstaller] [-Version "1.0.0"]

param(
    [switch]$Clean,
    [switch]$SkipInstaller,
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$BuildDir = Join-Path $ProjectRoot "dist"
$SpecFile = Join-Path $PSScriptRoot "termivoxed.spec"
$InstallerScript = Join-Path $PSScriptRoot "installer.iss"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " TermiVoxed Windows Build Script" -ForegroundColor Cyan
Write-Host " Version: $Version" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Clean previous builds
if ($Clean) {
    Write-Host "[1/6] Cleaning previous builds..." -ForegroundColor Yellow

    $pathsToClean = @(
        (Join-Path $BuildDir "TermiVoxed"),
        (Join-Path $BuildDir "installer"),
        (Join-Path $ProjectRoot "build")
    )

    foreach ($path in $pathsToClean) {
        if (Test-Path $path) {
            Remove-Item -Recurse -Force $path
            Write-Host "  Removed: $path" -ForegroundColor Gray
        }
    }

    Write-Host "  Clean complete!" -ForegroundColor Green
} else {
    Write-Host "[1/6] Skipping clean (use -Clean to remove previous builds)" -ForegroundColor Gray
}

# Step 2: Check dependencies
Write-Host ""
Write-Host "[2/6] Checking dependencies..." -ForegroundColor Yellow

# Check Python
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "  Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found!" -ForegroundColor Red
    exit 1
}

# Check PyInstaller
try {
    $pyinstallerVersion = & python -m PyInstaller --version 2>&1
    Write-Host "  PyInstaller: $pyinstallerVersion" -ForegroundColor Green
} catch {
    Write-Host "  PyInstaller not found, installing..." -ForegroundColor Yellow
    & pip install pyinstaller
}

# Check FFmpeg
$ffmpegPath = $null
$ffmpegLocations = @(
    "ffmpeg",
    (Join-Path $ProjectRoot "bin\ffmpeg.exe"),
    "C:\ffmpeg\bin\ffmpeg.exe"
)

foreach ($loc in $ffmpegLocations) {
    try {
        $null = & $loc -version 2>&1
        $ffmpegPath = $loc
        break
    } catch {}
}

if ($ffmpegPath) {
    Write-Host "  FFmpeg: Found at $ffmpegPath" -ForegroundColor Green
} else {
    Write-Host "  WARNING: FFmpeg not found. Users will need to install it separately." -ForegroundColor Yellow
}

# Check Inno Setup
$innoPath = $null
$innoLocations = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

foreach ($loc in $innoLocations) {
    if (Test-Path $loc) {
        $innoPath = $loc
        break
    }
}

if ($innoPath -and -not $SkipInstaller) {
    Write-Host "  Inno Setup: Found at $innoPath" -ForegroundColor Green
} elseif (-not $SkipInstaller) {
    Write-Host "  WARNING: Inno Setup not found. Installer creation will be skipped." -ForegroundColor Yellow
    $SkipInstaller = $true
}

# Step 3: Install Python dependencies
Write-Host ""
Write-Host "[3/6] Installing Python dependencies..." -ForegroundColor Yellow

Push-Location $ProjectRoot
try {
    & pip install -r requirements.txt --quiet
    Write-Host "  Dependencies installed!" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Some dependencies may have failed to install" -ForegroundColor Yellow
}
Pop-Location

# Step 4: Create version info file
Write-Host ""
Write-Host "[4/6] Creating version info..." -ForegroundColor Yellow

$versionInfo = @"
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($($Version.Replace('.', ', ')), 0),
    prodvers=($($Version.Replace('.', ', ')), 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'LxusBrain'),
          StringStruct(u'FileDescription', u'TermiVoxed - AI Voice-Over Dubbing Tool'),
          StringStruct(u'FileVersion', u'$Version'),
          StringStruct(u'InternalName', u'TermiVoxed'),
          StringStruct(u'LegalCopyright', u'Copyright (C) 2025 LxusBrain'),
          StringStruct(u'OriginalFilename', u'TermiVoxed.exe'),
          StringStruct(u'ProductName', u'TermiVoxed'),
          StringStruct(u'ProductVersion', u'$Version')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"@

$versionFile = Join-Path $PSScriptRoot "file_version_info.txt"
Set-Content -Path $versionFile -Value $versionInfo -Encoding UTF8
Write-Host "  Version info created: $versionFile" -ForegroundColor Green

# Step 5: Build with PyInstaller
Write-Host ""
Write-Host "[5/6] Building with PyInstaller..." -ForegroundColor Yellow
Write-Host "  This may take several minutes..." -ForegroundColor Gray

Push-Location $ProjectRoot
try {
    & python -m PyInstaller --clean --noconfirm $SpecFile

    if (Test-Path (Join-Path $BuildDir "TermiVoxed\TermiVoxed.exe")) {
        Write-Host "  PyInstaller build complete!" -ForegroundColor Green
    } else {
        throw "Build output not found"
    }
} catch {
    Write-Host "  ERROR: PyInstaller build failed!" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
Pop-Location

# Step 6: Create installer
Write-Host ""
if (-not $SkipInstaller) {
    Write-Host "[6/6] Creating Windows installer..." -ForegroundColor Yellow

    # Create installer output directory
    $installerDir = Join-Path $BuildDir "installer"
    if (-not (Test-Path $installerDir)) {
        New-Item -ItemType Directory -Path $installerDir | Out-Null
    }

    try {
        & $innoPath $InstallerScript

        $installerPath = Get-ChildItem -Path $installerDir -Filter "*.exe" | Select-Object -First 1
        if ($installerPath) {
            Write-Host "  Installer created: $($installerPath.FullName)" -ForegroundColor Green
        } else {
            throw "Installer file not found"
        }
    } catch {
        Write-Host "  ERROR: Installer creation failed!" -ForegroundColor Red
        Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    }
} else {
    Write-Host "[6/6] Skipping installer creation" -ForegroundColor Gray
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Build Outputs:" -ForegroundColor White

if (Test-Path (Join-Path $BuildDir "TermiVoxed")) {
    $size = (Get-ChildItem -Recurse (Join-Path $BuildDir "TermiVoxed") | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host "  Portable: $(Join-Path $BuildDir "TermiVoxed") ($([math]::Round($size, 2)) MB)" -ForegroundColor Gray
}

$installerPath = Get-ChildItem -Path (Join-Path $BuildDir "installer") -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($installerPath) {
    $size = $installerPath.Length / 1MB
    Write-Host "  Installer: $($installerPath.FullName) ($([math]::Round($size, 2)) MB)" -ForegroundColor Gray
}

Write-Host ""
