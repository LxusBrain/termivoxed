#!/bin/bash
# TermiVoxed macOS Build Script
#
# This script builds TermiVoxed as a macOS application bundle
# and optionally creates a DMG installer.
#
# Author: Santhosh T
# Usage: ./build.sh [--clean] [--dmg] [--notarize]
#
# Requirements:
# - Python 3.9+
# - py2app: pip install py2app
# - Xcode Command Line Tools: xcode-select --install
# - FFmpeg: brew install ffmpeg

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/dist"
APP_NAME="TermiVoxed"
VERSION="1.0.0"

# Parse arguments
CLEAN=false
CREATE_DMG=false
NOTARIZE=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --clean) CLEAN=true ;;
        --dmg) CREATE_DMG=true ;;
        --notarize) NOTARIZE=true ;;
        --version) VERSION="$2"; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

echo "========================================"
echo " TermiVoxed macOS Build Script"
echo " Version: $VERSION"
echo "========================================"
echo ""

# Step 1: Clean previous builds
if [ "$CLEAN" = true ]; then
    echo "[1/6] Cleaning previous builds..."
    rm -rf "$BUILD_DIR/$APP_NAME.app"
    rm -rf "$BUILD_DIR/$APP_NAME-*.dmg"
    rm -rf "$PROJECT_ROOT/build"
    echo "  Clean complete!"
else
    echo "[1/6] Skipping clean (use --clean to remove previous builds)"
fi

# Step 2: Check dependencies
echo ""
echo "[2/6] Checking dependencies..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ERROR: Python 3 not found!"
    exit 1
fi
echo "  Python: $(python3 --version)"

# Check py2app
if ! python3 -c "import py2app" 2>/dev/null; then
    echo "  py2app not found, installing..."
    pip3 install py2app
fi
echo "  py2app: installed"

# Check FFmpeg - REQUIRED for production builds
if command -v ffmpeg &> /dev/null; then
    echo "  FFmpeg: $(ffmpeg -version 2>&1 | head -1)"
else
    echo "  CRITICAL ERROR: FFmpeg not found!"
    echo "  FFmpeg is REQUIRED for production builds."
    echo "  Install with: brew install ffmpeg"
    exit 1
fi

if ! command -v ffprobe &> /dev/null; then
    echo "  CRITICAL ERROR: ffprobe not found!"
    echo "  Install with: brew install ffmpeg"
    exit 1
fi
echo "  ffprobe: found"

# Check Xcode Command Line Tools
if ! xcode-select -p &> /dev/null; then
    echo "  WARNING: Xcode Command Line Tools not installed"
    echo "  Install with: xcode-select --install"
fi

# Step 3: Install dependencies
echo ""
echo "[3/6] Installing Python dependencies..."
cd "$PROJECT_ROOT"
pip3 install -r requirements.txt --quiet

# Step 4: Build application
echo ""
echo "[4/6] Building application bundle..."
echo "  This may take several minutes..."

cd "$SCRIPT_DIR"
python3 setup.py py2app --dist-dir "$BUILD_DIR"

if [ -d "$BUILD_DIR/$APP_NAME.app" ]; then
    echo "  Application bundle created!"
else
    echo "  ERROR: Build failed!"
    exit 1
fi

# Step 5: Copy FFmpeg into bundle
# FFmpeg is REQUIRED for production builds
echo ""
echo "[5/6] Bundling resources..."

RESOURCES_DIR="$BUILD_DIR/$APP_NAME.app/Contents/Resources"

# Create directory structure matching bundle_ffmpeg.py and launcher.py expectations
# Primary location: Resources/vendor/ffmpeg/macos/bin/
FFMPEG_BUNDLE_DIR="$RESOURCES_DIR/vendor/ffmpeg/macos/bin"
mkdir -p "$FFMPEG_BUNDLE_DIR"

# Also create fallback location for compatibility
FFMPEG_FALLBACK_DIR="$RESOURCES_DIR/ffmpeg"
mkdir -p "$FFMPEG_FALLBACK_DIR"

# First, try to use pre-bundled FFmpeg from vendor directory
VENDOR_FFMPEG="$PROJECT_ROOT/vendor/ffmpeg/macos/bin/ffmpeg"
VENDOR_FFPROBE="$PROJECT_ROOT/vendor/ffmpeg/macos/bin/ffprobe"

if [ -f "$VENDOR_FFMPEG" ] && [ -f "$VENDOR_FFPROBE" ]; then
    echo "  Using pre-bundled FFmpeg from vendor directory..."
    cp "$VENDOR_FFMPEG" "$FFMPEG_BUNDLE_DIR/"
    cp "$VENDOR_FFPROBE" "$FFMPEG_BUNDLE_DIR/"
    # Also copy to fallback location
    cp "$VENDOR_FFMPEG" "$FFMPEG_FALLBACK_DIR/"
    cp "$VENDOR_FFPROBE" "$FFMPEG_FALLBACK_DIR/"
    echo "  Bundled pre-downloaded ffmpeg and ffprobe"
else
    echo "  No pre-bundled FFmpeg found, using system FFmpeg..."
    # Fallback to system FFmpeg
    if command -v ffmpeg &> /dev/null; then
        FFMPEG_PATH=$(which ffmpeg)
        FFPROBE_PATH=$(which ffprobe)

        if [ -f "$FFMPEG_PATH" ]; then
            cp "$FFMPEG_PATH" "$FFMPEG_BUNDLE_DIR/"
            cp "$FFMPEG_PATH" "$FFMPEG_FALLBACK_DIR/"
            echo "  Bundled ffmpeg (from system)"
        fi

        if [ -f "$FFPROBE_PATH" ]; then
            cp "$FFPROBE_PATH" "$FFMPEG_BUNDLE_DIR/"
            cp "$FFPROBE_PATH" "$FFMPEG_FALLBACK_DIR/"
            echo "  Bundled ffprobe (from system)"
        fi
    else
        echo "  CRITICAL ERROR: No FFmpeg found to bundle!"
        echo "  Either run 'python build_tools/bundle_ffmpeg.py --platform macos' first,"
        echo "  or install FFmpeg with 'brew install ffmpeg'"
        exit 1
    fi
fi

# Ensure executables are executable
chmod +x "$FFMPEG_BUNDLE_DIR/"* 2>/dev/null || true
chmod +x "$FFMPEG_FALLBACK_DIR/"* 2>/dev/null || true

# Step 6: Create DMG (optional)
echo ""
if [ "$CREATE_DMG" = true ]; then
    echo "[6/6] Creating DMG installer..."

    DMG_NAME="$APP_NAME-$VERSION.dmg"
    DMG_PATH="$BUILD_DIR/$DMG_NAME"

    # Remove existing DMG
    rm -f "$DMG_PATH"

    # Create temporary directory for DMG contents
    DMG_TEMP="$BUILD_DIR/dmg_temp"
    rm -rf "$DMG_TEMP"
    mkdir -p "$DMG_TEMP"

    # Copy app to temp directory
    cp -R "$BUILD_DIR/$APP_NAME.app" "$DMG_TEMP/"

    # Create Applications symlink
    ln -s /Applications "$DMG_TEMP/Applications"

    # Create DMG
    hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_TEMP" -ov -format UDZO "$DMG_PATH"

    # Cleanup
    rm -rf "$DMG_TEMP"

    if [ -f "$DMG_PATH" ]; then
        echo "  DMG created: $DMG_PATH"
        DMG_SIZE=$(ls -lh "$DMG_PATH" | awk '{print $5}')
        echo "  Size: $DMG_SIZE"
    fi
else
    echo "[6/6] Skipping DMG creation (use --dmg to create)"
fi

# Notarization - REQUIRED for production/release builds
if [ "$NOTARIZE" = true ]; then
    echo ""
    echo "Starting notarization (REQUIRED for production)..."
    echo "  NOTE: Notarization requires Apple Developer credentials"

    if [ -z "$APPLE_ID" ] || [ -z "$APPLE_TEAM_ID" ]; then
        echo "  CRITICAL ERROR: Apple Developer credentials not configured!"
        echo "  Notarization is REQUIRED for production macOS builds."
        echo "  Set the following environment variables:"
        echo "    export APPLE_ID='your@email.com'"
        echo "    export APPLE_TEAM_ID='YOUR_TEAM_ID'"
        echo "    export APPLE_APP_PASSWORD='app-specific-password'"
        echo ""
        echo "  Without notarization, macOS Gatekeeper will block the app."
        exit 1
    else
        # Run notarization script
        if ! "$SCRIPT_DIR/notarize.sh" "$BUILD_DIR/$APP_NAME.app"; then
            echo "  CRITICAL ERROR: Notarization FAILED!"
            echo "  Cannot release un-notarized macOS applications."
            exit 1
        fi
        echo "  Notarization completed successfully!"
    fi
else
    echo ""
    echo "WARNING: Skipping notarization (use --notarize for production builds)"
    echo "  Un-notarized apps will be blocked by macOS Gatekeeper."
fi

# Summary
echo ""
echo "========================================"
echo " Build Complete!"
echo "========================================"
echo ""
echo "Build Outputs:"

if [ -d "$BUILD_DIR/$APP_NAME.app" ]; then
    APP_SIZE=$(du -sh "$BUILD_DIR/$APP_NAME.app" | awk '{print $1}')
    echo "  App Bundle: $BUILD_DIR/$APP_NAME.app ($APP_SIZE)"
fi

if [ -f "$BUILD_DIR/$APP_NAME-$VERSION.dmg" ]; then
    DMG_SIZE=$(ls -lh "$BUILD_DIR/$APP_NAME-$VERSION.dmg" | awk '{print $5}')
    echo "  DMG: $BUILD_DIR/$APP_NAME-$VERSION.dmg ($DMG_SIZE)"
fi

echo ""
echo "To install, drag $APP_NAME.app to Applications folder"
echo ""
