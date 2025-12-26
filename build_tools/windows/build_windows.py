#!/usr/bin/env python3
"""
Windows Build and Code Signing Script for TermiVoxed

This script:
1. Builds the Windows executable using PyInstaller
2. Signs the executable with a code signing certificate
3. Creates an installer using Inno Setup
4. Signs the installer
5. Generates update manifest

Requirements:
- Windows SDK signtool.exe (for code signing)
- PyInstaller
- Inno Setup (ISCC.exe)
- Code signing certificate (.pfx or hardware token)

Environment Variables:
- TERMIVOXED_CODESIGN_CERT: Path to .pfx certificate OR "HSM" for hardware token
- TERMIVOXED_CODESIGN_PASSWORD: Password for .pfx certificate (if applicable)
- TERMIVOXED_CODESIGN_TIMESTAMP: Timestamp server URL (default: DigiCert)
"""

import os
import sys
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
BUILD_DIR = PROJECT_ROOT / "build" / "windows"
DIST_DIR = PROJECT_ROOT / "dist" / "windows"
RESOURCES_DIR = PROJECT_ROOT / "resources"

# Version info
VERSION = "1.0.0"  # Update this or read from pyproject.toml

# Code signing configuration
TIMESTAMP_SERVERS = [
    "http://timestamp.digicert.com",
    "http://timestamp.sectigo.com",
    "http://timestamp.globalsign.com",
    "http://timestamp.comodoca.com"
]


def find_signtool() -> str:
    """Find signtool.exe from Windows SDK."""
    # Common paths for Windows SDK signtool
    sdk_paths = [
        r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64\signtool.exe",
        r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe",
        r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\signtool.exe",
        r"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\signtool.exe",
    ]

    # Try environment PATH first
    signtool = shutil.which("signtool")
    if signtool:
        return signtool

    # Try common SDK locations
    for path in sdk_paths:
        if os.path.exists(path):
            return path

    # Search for any signtool in SDK
    sdk_root = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if sdk_root.exists():
        for signtool_path in sdk_root.glob("*/x64/signtool.exe"):
            return str(signtool_path)

    return None


def sign_file(file_path: str, description: str = "TermiVoxed", required: bool = True) -> bool:
    """
    Sign a file using Windows code signing certificate.

    Supports:
    - Software certificate (.pfx file)
    - Hardware Security Module (HSM) tokens
    - Azure Key Vault (future)

    Args:
        file_path: Path to file to sign
        description: Description for signature
        required: If True, raises error if signing fails (default: True for production)

    Returns True if signing successful, False otherwise.
    Raises RuntimeError if required=True and signing fails.
    """
    signtool = find_signtool()
    if not signtool:
        msg = "CRITICAL: signtool.exe not found. Install Windows SDK for code signing."
        if required:
            raise RuntimeError(msg)
        print(f"WARNING: {msg}")
        return False

    cert_path = os.environ.get("TERMIVOXED_CODESIGN_CERT")
    cert_password = os.environ.get("TERMIVOXED_CODESIGN_PASSWORD", "")
    timestamp_url = os.environ.get("TERMIVOXED_CODESIGN_TIMESTAMP", TIMESTAMP_SERVERS[0])

    if not cert_path:
        msg = "CRITICAL: TERMIVOXED_CODESIGN_CERT not set. Code signing is REQUIRED for production builds."
        if required:
            raise RuntimeError(msg)
        print(f"WARNING: {msg}")
        return False

    # Build signtool command
    cmd = [signtool, "sign"]

    if cert_path.upper() == "HSM":
        # Hardware Security Module - use default certificate from Windows store
        cmd.extend(["/a"])  # Auto-select certificate
    else:
        # Software certificate (.pfx file)
        if not os.path.exists(cert_path):
            print(f"ERROR: Certificate file not found: {cert_path}")
            return False
        cmd.extend(["/f", cert_path])
        if cert_password:
            cmd.extend(["/p", cert_password])

    # Add common signing options
    cmd.extend([
        "/tr", timestamp_url,  # RFC 3161 timestamp
        "/td", "sha256",       # Timestamp digest algorithm
        "/fd", "sha256",       # File digest algorithm
        "/d", description,     # Description
    ])

    cmd.append(file_path)

    print(f"Signing: {file_path}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"  Successfully signed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: Signing failed")
        print(f"  {e.stderr}")

        # Try fallback timestamp servers
        for ts in TIMESTAMP_SERVERS[1:]:
            print(f"  Retrying with timestamp server: {ts}")
            cmd[-2] = ts  # Replace timestamp URL
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                print(f"  Successfully signed with fallback server")
                return True
            except subprocess.CalledProcessError:
                continue

        # All signing attempts failed
        if required:
            raise RuntimeError(f"CRITICAL: Code signing FAILED for {file_path}. Cannot release unsigned binaries.")
        return False


def build_executable() -> Path:
    """Build the Windows executable using PyInstaller."""
    print("\n" + "=" * 60)
    print("Building Windows Executable")
    print("=" * 60)

    # Ensure build and dist directories exist
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # PyInstaller spec content
    spec_content = f'''
# -*- mode: python ; coding: utf-8 -*-
import sys
sys.path.insert(0, r'{PROJECT_ROOT}')

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all submodules
hiddenimports = collect_submodules('backend') + collect_submodules('core') + collect_submodules('models')

# Collect data files
datas = [
    (r'{PROJECT_ROOT / "web_ui" / "frontend" / "dist"}', 'web_ui/frontend/dist'),
    (r'{PROJECT_ROOT / "web_ui" / "api" / "templates"}', 'web_ui/api/templates'),
    (r'{PROJECT_ROOT / "resources"}', 'resources'),
]

# Collect FFmpeg if bundled
# FFmpeg is bundled in vendor/ffmpeg/{platform}/bin/ by bundle_ffmpeg.py
ffmpeg_windows_path = r'{PROJECT_ROOT / "vendor" / "ffmpeg" / "windows"}'
if os.path.exists(ffmpeg_windows_path):
    datas.append((ffmpeg_windows_path, 'vendor/ffmpeg/windows'))
else:
    # Try alternate location
    ffmpeg_path = r'{PROJECT_ROOT / "vendor" / "ffmpeg"}'
    if os.path.exists(ffmpeg_path):
        datas.append((ffmpeg_path, 'vendor/ffmpeg'))

a = Analysis(
    [r'{PROJECT_ROOT / "main.py"}'],
    pathex=[r'{PROJECT_ROOT}'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports + [
        'uvicorn.logging',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TermiVoxed',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'{PROJECT_ROOT / "resources" / "icons" / "app.ico"}' if (PROJECT_ROOT / "resources" / "icons" / "app.ico").exists() else None,
    version=r'{BUILD_DIR / "version_info.py"}' if (BUILD_DIR / "version_info.py").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TermiVoxed',
)
'''

    # Write spec file
    spec_path = BUILD_DIR / "termivoxed.spec"
    spec_path.write_text(spec_content)

    # Create version info file for Windows
    version_info = f'''
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'LXUSBrain'),
        StringStruct(u'FileDescription', u'TermiVoxed - AI Video Editor'),
        StringStruct(u'FileVersion', u'{VERSION}'),
        StringStruct(u'InternalName', u'TermiVoxed'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {datetime.now().year} LXUSBrain'),
        StringStruct(u'OriginalFilename', u'TermiVoxed.exe'),
        StringStruct(u'ProductName', u'TermiVoxed'),
        StringStruct(u'ProductVersion', u'{VERSION}')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
    (BUILD_DIR / "version_info.py").write_text(version_info)

    # Run PyInstaller
    print("\nRunning PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--workpath", str(BUILD_DIR / "work"),
        "--distpath", str(DIST_DIR),
        str(spec_path)
    ]

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print("ERROR: PyInstaller build failed")
        sys.exit(1)

    exe_path = DIST_DIR / "TermiVoxed" / "TermiVoxed.exe"
    print(f"\nExecutable built: {exe_path}")

    return exe_path


def create_installer(exe_dir: Path) -> Path:
    """Create Windows installer using Inno Setup."""
    print("\n" + "=" * 60)
    print("Creating Windows Installer")
    print("=" * 60)

    # Find Inno Setup compiler
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        shutil.which("ISCC")
    ]

    iscc = None
    for path in iscc_paths:
        if path and os.path.exists(path):
            iscc = path
            break

    if not iscc:
        print("WARNING: Inno Setup not found. Skipping installer creation.")
        print("Download from: https://jrsoftware.org/isinfo.php")
        return None

    # Inno Setup script
    iss_content = f'''
; TermiVoxed Windows Installer Script
#define MyAppName "TermiVoxed"
#define MyAppVersion "{VERSION}"
#define MyAppPublisher "LXUSBrain"
#define MyAppURL "https://luxusbrain.com"
#define MyAppExeName "TermiVoxed.exe"

[Setup]
AppId={{{{B5A7C8D9-E6F1-4A2B-8C3D-E4F5A6B7C8D9}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
AppSupportURL={{#MyAppURL}}
AppUpdatesURL={{#MyAppURL}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DisableProgramGroupPage=yes
LicenseFile={PROJECT_ROOT / "LICENSE"}
OutputDir={DIST_DIR}
OutputBaseFilename=TermiVoxed-{VERSION}-Setup
SetupIconFile={RESOURCES_DIR / "icons" / "app.ico"}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[Files]
Source: "{exe_dir}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{autoprograms}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{#StringChange(MyAppName, '&', '&&')}}}}"; Flags: nowait postinstall skipifsilent
'''

    iss_path = BUILD_DIR / "termivoxed.iss"
    iss_path.write_text(iss_content)

    print("\nRunning Inno Setup Compiler...")
    result = subprocess.run([iscc, str(iss_path)], cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print("ERROR: Installer creation failed")
        return None

    installer_path = DIST_DIR / f"TermiVoxed-{VERSION}-Setup.exe"
    print(f"\nInstaller created: {installer_path}")

    return installer_path


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available. Required for production builds."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")

    if not ffmpeg or not ffprobe:
        # Check vendor directory
        vendor_dir = PROJECT_ROOT / "vendor" / "ffmpeg"
        if not vendor_dir.exists() or not list(vendor_dir.glob("ffmpeg*")):
            raise RuntimeError(
                "CRITICAL: FFmpeg not found! FFmpeg is REQUIRED for production builds.\n"
                "Either:\n"
                "  1. Add ffmpeg.exe and ffprobe.exe to PATH, OR\n"
                "  2. Run: python build_tools/bundle_ffmpeg.py to bundle FFmpeg"
            )
    return True


def main():
    print("=" * 60)
    print("TermiVoxed Windows Build System")
    print(f"Version: {VERSION}")
    print("=" * 60)

    # Check platform
    if sys.platform != "win32":
        print("WARNING: This script is designed for Windows.")
        print("Cross-compilation may not work correctly.")

    # REQUIRED: Check for FFmpeg
    print("\nChecking FFmpeg availability...")
    check_ffmpeg()
    print("  FFmpeg: OK")

    # Step 1: Build executable
    exe_path = build_executable()

    # Step 2: Sign executable
    exe_dir = exe_path.parent
    for file in exe_dir.glob("*.exe"):
        sign_file(str(file), "TermiVoxed")

    for file in exe_dir.glob("*.dll"):
        sign_file(str(file), "TermiVoxed Component")

    # Step 3: Create installer
    installer_path = create_installer(exe_dir)

    # Step 4: Sign installer
    if installer_path and installer_path.exists():
        sign_file(str(installer_path), "TermiVoxed Installer")

        # Generate manifest for auto-update
        print("\n" + "=" * 60)
        print("Generating Update Manifest")
        print("=" * 60)

        sign_script = PROJECT_ROOT / "build_tools" / "sign_release.py"
        if sign_script.exists():
            subprocess.run([
                sys.executable, str(sign_script),
                str(installer_path),
                "--version", VERSION,
                "--channel", "stable"
            ])

    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    print(f"\nOutputs:")
    print(f"  Executable: {exe_dir}")
    if installer_path:
        print(f"  Installer: {installer_path}")


if __name__ == "__main__":
    main()
