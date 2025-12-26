"""
py2app Setup Script for TermiVoxed macOS Build

This script configures py2app to build a macOS application bundle.

Author: Santhosh T
Build Command: python setup.py py2app

Requirements:
- py2app: pip install py2app
- Xcode Command Line Tools: xcode-select --install
"""

import os
import sys
from pathlib import Path
from setuptools import setup

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Application metadata
APP_NAME = 'TermiVoxed'
APP_VERSION = '1.0.0'
APP_BUNDLE_ID = 'com.lxusbrain.termivoxed'
APP_DESCRIPTION = 'AI Voice-Over Dubbing Tool'
APP_AUTHOR = 'LXUSBrain Technologies'
APP_COPYRIGHT = 'Copyright (C) 2025 LXUSBrain Technologies'

# Main script
APP = [str(PROJECT_ROOT / 'main.py')]

# Data files to include
DATA_FILES = [
    # Include legal documents
    ('legal', [
        str(PROJECT_ROOT / 'web_ui' / 'frontend' / 'public' / 'legal' / 'privacy-policy.html'),
        str(PROJECT_ROOT / 'web_ui' / 'frontend' / 'public' / 'legal' / 'terms-of-service.html'),
        str(PROJECT_ROOT / 'web_ui' / 'frontend' / 'public' / 'legal' / 'eula.html'),
        str(PROJECT_ROOT / 'web_ui' / 'frontend' / 'public' / 'legal' / 'refund-policy.html'),
    ]),
]

# Filter out non-existent files
DATA_FILES = [
    (dest, [f for f in files if os.path.exists(f)])
    for dest, files in DATA_FILES
]
DATA_FILES = [(dest, files) for dest, files in DATA_FILES if files]

# py2app options
OPTIONS = {
    # Bundle metadata
    'argv_emulation': False,
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleIdentifier': APP_BUNDLE_ID,
        'CFBundleVersion': APP_VERSION,
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleGetInfoString': f'{APP_NAME} {APP_VERSION}',
        'NSHumanReadableCopyright': APP_COPYRIGHT,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'TermiVoxed Project',
                'CFBundleTypeExtensions': ['tvx'],
                'CFBundleTypeRole': 'Editor',
                'LSHandlerRank': 'Owner',
            }
        ],
        'LSMinimumSystemVersion': '10.15',  # macOS Catalina minimum
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # Support dark mode
        'NSAppleEventsUsageDescription': 'TermiVoxed needs access for automation.',
        'NSMicrophoneUsageDescription': 'TermiVoxed needs microphone access for audio features.',
    },

    # Icon (must be .icns format)
    'iconfile': str(PROJECT_ROOT / 'assets' / 'icon.icns') if (PROJECT_ROOT / 'assets' / 'icon.icns').exists() else None,

    # Packages to include
    'packages': [
        'rich',
        'pydantic',
        'pydantic_settings',
        'aiohttp',
        'aiofiles',
        'edge_tts',
        'mutagen',
        'inquirer',
        'httpx',
        'requests',
        'cryptography',
    ],

    # Modules to include
    'includes': [
        'asyncio',
        'json',
        'pathlib',
        'platform',
        'uuid',
        'hashlib',
        'hmac',
    ],

    # Modules to exclude (reduce size)
    'excludes': [
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'test',
        'unittest',
        'pytest',
        'pdb',
        'doctest',
        'setuptools',
        'distutils',
    ],

    # Build options
    'strip': True,
    'optimize': 2,
    'semi_standalone': False,
    'site_packages': True,

    # Resources
    'resources': [],
}

# Remove None iconfile
if OPTIONS['iconfile'] is None:
    del OPTIONS['iconfile']

setup(
    name=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    author=APP_AUTHOR,
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
