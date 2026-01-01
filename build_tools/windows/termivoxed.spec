# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for TermiVoxed
Windows Desktop Application Bundle Configuration

Author: Santhosh T
Build Command: pyinstaller --clean build_tools/windows/termivoxed.spec
"""

import os
import sys
from pathlib import Path

# Get the project root directory
spec_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.abspath(os.path.join(spec_dir, '..', '..'))

# Add project root to path for imports
sys.path.insert(0, project_root)

# Application metadata
APP_NAME = 'TermiVoxed'
APP_VERSION = '1.0.0'
APP_AUTHOR = 'LxusBrain'
APP_DESCRIPTION = 'AI Voice-Over Dubbing Tool'

# Collect all source files
source_dirs = [
    'backend',
    'core',
    'models',
    'utils',
    'subscription',
]

# Hidden imports that PyInstaller might miss
hidden_imports = [
    # Core dependencies
    'rich',
    'rich.console',
    'rich.panel',
    'rich.table',
    'rich.progress',
    'rich.prompt',
    'pydantic',
    'pydantic_settings',

    # Async support
    'asyncio',
    'aiohttp',
    'aiofiles',

    # Audio/Video processing
    'edge_tts',
    'mutagen',
    'mutagen.mp3',
    'mutagen.wave',

    # Firebase (optional)
    'firebase_admin',
    'firebase_admin.auth',
    'firebase_admin.firestore',
    'firebase_admin.credentials',

    # Payment processing (optional)
    'stripe',
    'razorpay',

    # PDF generation
    'reportlab',
    'reportlab.lib',
    'reportlab.lib.pagesizes',
    'reportlab.lib.units',
    'reportlab.platypus',

    # Email
    'sendgrid',

    # UI
    'inquirer',
    'inquirer.themes',

    # Crypto for license verification
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat.primitives',

    # HTTP client
    'httpx',
    'requests',

    # JSON/YAML
    'json',
    'yaml',

    # Platform detection
    'platform',
    'uuid',
    'hashlib',
    'hmac',
]

# Data files to include
datas = [
    # Configuration files
    (os.path.join(project_root, '.env.example'), '.'),

    # Legal documents (if exists)
    (os.path.join(project_root, 'web_ui', 'frontend', 'public', 'legal'), 'legal'),
]

# Filter out non-existent data files
datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

# Binary dependencies
binaries = []

# Check for FFmpeg in common locations
ffmpeg_paths = [
    os.path.join(project_root, 'bin', 'ffmpeg.exe'),
    os.path.join(project_root, 'ffmpeg', 'ffmpeg.exe'),
    r'C:\ffmpeg\bin\ffmpeg.exe',
]

ffprobe_paths = [
    os.path.join(project_root, 'bin', 'ffprobe.exe'),
    os.path.join(project_root, 'ffmpeg', 'ffprobe.exe'),
    r'C:\ffmpeg\bin\ffprobe.exe',
]

for path in ffmpeg_paths:
    if os.path.exists(path):
        binaries.append((path, 'bin'))
        break

for path in ffprobe_paths:
    if os.path.exists(path):
        binaries.append((path, 'bin'))
        break

# Excluded modules to reduce size
excludes = [
    'tkinter',
    'matplotlib',
    'numpy.distutils',
    'scipy',
    'PIL.ImageTk',
    'test',
    'tests',
    'unittest',
    'pytest',
    '_pytest',
    'doctest',
    'pdb',
    'difflib',
    'pydoc',
    'setuptools',
    'distutils',
    'lib2to3',
]

# Analysis configuration
a = Analysis(
    [os.path.join(project_root, 'main.py')],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate binaries and data files
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Icon path
icon_path = os.path.join(project_root, 'assets', 'icon.ico')
if not os.path.exists(icon_path):
    icon_path = None

# EXE configuration
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
    console=True,  # Console app - shows terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
    version='file_version_info.txt' if os.path.exists('file_version_info.txt') else None,
)

# Collect all files
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TermiVoxed',
)
