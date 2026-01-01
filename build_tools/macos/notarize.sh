#!/bin/bash
# TermiVoxed macOS Notarization Script
#
# This script handles code signing and notarization for macOS apps.
# Apple requires notarization for apps distributed outside the App Store
# on macOS Catalina (10.15) and later.
#
# Author: Santhosh T
# Usage: ./notarize.sh /path/to/App.app
#
# Required Environment Variables:
# - APPLE_ID: Your Apple ID email
# - APPLE_TEAM_ID: Your Apple Developer Team ID
# - APPLE_APP_PASSWORD: App-specific password (generate at appleid.apple.com)
# - SIGNING_IDENTITY: Developer ID certificate name (optional)

set -e

# Configuration
APP_PATH="$1"
APP_NAME="TermiVoxed"
BUNDLE_ID="com.lxusbrain.termivoxed"

if [ -z "$APP_PATH" ]; then
    echo "Usage: $0 /path/to/App.app"
    exit 1
fi

if [ ! -d "$APP_PATH" ]; then
    echo "Error: Application not found at $APP_PATH"
    exit 1
fi

# Validate environment
if [ -z "$APPLE_ID" ]; then
    echo "Error: APPLE_ID environment variable not set"
    exit 1
fi

if [ -z "$APPLE_TEAM_ID" ]; then
    echo "Error: APPLE_TEAM_ID environment variable not set"
    exit 1
fi

if [ -z "$APPLE_APP_PASSWORD" ]; then
    echo "Error: APPLE_APP_PASSWORD environment variable not set"
    echo "Generate an app-specific password at https://appleid.apple.com"
    exit 1
fi

# Default signing identity
SIGNING_IDENTITY="${SIGNING_IDENTITY:-Developer ID Application: LxusBrain}"

echo "========================================"
echo " TermiVoxed Notarization"
echo "========================================"
echo ""
echo "App: $APP_PATH"
echo "Bundle ID: $BUNDLE_ID"
echo "Apple ID: $APPLE_ID"
echo "Team ID: $APPLE_TEAM_ID"
echo ""

# Step 1: Code Sign the Application
echo "[1/5] Code signing application..."

# Sign all nested frameworks and binaries first
find "$APP_PATH" -type f \( -name "*.dylib" -o -name "*.so" -o -name "*.framework" \) -exec \
    codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" {} \;

# Sign helper executables
find "$APP_PATH/Contents/MacOS" -type f -perm +111 ! -name "$APP_NAME" -exec \
    codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" {} \;

# Sign the main application
codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" \
    --entitlements "$(dirname "$0")/entitlements.plist" \
    "$APP_PATH"

echo "  Code signing complete!"

# Verify signature
echo ""
echo "[2/5] Verifying code signature..."
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

if [ $? -eq 0 ]; then
    echo "  Signature verified!"
else
    echo "  ERROR: Signature verification failed!"
    exit 1
fi

# Step 3: Create ZIP for notarization
echo ""
echo "[3/5] Creating ZIP archive for notarization..."

ZIP_PATH="${APP_PATH%.app}.zip"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
echo "  Created: $ZIP_PATH"

# Step 4: Submit for notarization
echo ""
echo "[4/5] Submitting for notarization..."
echo "  This may take several minutes..."

# Submit to Apple
SUBMIT_OUTPUT=$(xcrun notarytool submit "$ZIP_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --wait 2>&1)

echo "$SUBMIT_OUTPUT"

# Extract submission ID
SUBMISSION_ID=$(echo "$SUBMIT_OUTPUT" | grep "id:" | head -1 | awk '{print $2}')

if [ -z "$SUBMISSION_ID" ]; then
    echo "  ERROR: Failed to get submission ID"
    exit 1
fi

echo "  Submission ID: $SUBMISSION_ID"

# Check status
STATUS=$(echo "$SUBMIT_OUTPUT" | grep "status:" | tail -1 | awk '{print $2}')

if [ "$STATUS" = "Accepted" ]; then
    echo "  Notarization successful!"
else
    echo "  Notarization failed with status: $STATUS"

    # Get detailed log
    echo ""
    echo "Fetching notarization log..."
    xcrun notarytool log "$SUBMISSION_ID" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APPLE_APP_PASSWORD"

    exit 1
fi

# Step 5: Staple the notarization ticket
echo ""
echo "[5/5] Stapling notarization ticket..."

xcrun stapler staple "$APP_PATH"

if [ $? -eq 0 ]; then
    echo "  Ticket stapled successfully!"
else
    echo "  WARNING: Failed to staple ticket (app will still work)"
fi

# Cleanup
rm -f "$ZIP_PATH"

# Final verification
echo ""
echo "========================================"
echo " Notarization Complete!"
echo "========================================"
echo ""
echo "Verifying final state..."

spctl -a -vvv -t install "$APP_PATH" 2>&1

echo ""
echo "Your application is now signed and notarized!"
echo "It can be distributed outside the Mac App Store."
echo ""
