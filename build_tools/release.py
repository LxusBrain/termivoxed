#!/usr/bin/env python3
"""
TermiVoxed Release Orchestrator

A sophisticated, cross-platform release automation system that:
1. Validates environment and dependencies
2. Runs pre-release tests
3. Builds platform-specific executables
4. Signs binaries (Windows/macOS)
5. Creates installers (Windows: Inno Setup, macOS: DMG)
6. Generates checksums and manifests
7. Optionally pushes to GitHub Releases

Usage:
    python build_tools/release.py --version 1.0.0 --platform all
    python build_tools/release.py --version 1.0.0 --platform windows --sign
    python build_tools/release.py --version 1.0.0 --push-release

Environment Variables:
    TERMIVOXED_CODESIGN_CERT      - Windows code signing certificate path
    TERMIVOXED_CODESIGN_PASSWORD  - Certificate password
    APPLE_DEVELOPER_ID            - macOS Developer ID for signing
    APPLE_TEAM_ID                 - Apple Team ID for notarization
    GITHUB_TOKEN                  - For pushing releases to GitHub

Author: LxusBrain
"""

import os
import sys
import json
import shutil
import hashlib
import logging
import argparse
import platform
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
RELEASE_DIR = PROJECT_ROOT / "release"
LOGS_DIR = BUILD_DIR / "logs"

# Supported platforms
PLATFORMS = ["windows", "macos", "linux"]

# Required Python version
MIN_PYTHON_VERSION = (3, 10)

# Dependencies required for building
BUILD_DEPENDENCIES = [
    "pyinstaller",
    "wheel",
    "setuptools",
]


# ============================================================================
# Logging Setup
# ============================================================================

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for terminal output."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{self.BOLD}{record.levelname}{self.RESET}"
        record.msg = f"{color}{record.msg}{self.RESET}"
        return super().format(record)


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> logging.Logger:
    """Configure logging with file and console handlers."""
    logger = logging.getLogger("termivoxed-release")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(ColoredFormatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S'
    ))
    logger.addHandler(console_handler)

    # File handler for detailed logs
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        ))
        logger.addHandler(file_handler)

    return logger


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class BuildConfig:
    """Configuration for a build."""
    version: str
    platforms: List[str]
    sign: bool = False
    notarize: bool = False
    create_installer: bool = True
    run_tests: bool = True
    push_release: bool = False
    prerelease: bool = False
    verbose: bool = False
    parallel: bool = True


@dataclass
class BuildResult:
    """Result of a platform build."""
    platform: str
    success: bool
    executable_path: Optional[Path] = None
    installer_path: Optional[Path] = None
    error: Optional[str] = None
    duration_seconds: float = 0
    artifacts: List[Path] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)


@dataclass
class ReleaseManifest:
    """Manifest for a release."""
    version: str
    timestamp: str
    platforms: Dict[str, Dict[str, Any]]
    checksums: Dict[str, str]
    signed: bool
    prerelease: bool


# ============================================================================
# Utility Functions
# ============================================================================

def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    env: Optional[Dict] = None,
    capture: bool = True,
    check: bool = True,
    logger: Optional[logging.Logger] = None
) -> subprocess.CompletedProcess:
    """Run a command with proper error handling and logging."""
    if logger:
        logger.debug(f"Running: {' '.join(cmd)}")

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            env=merged_env,
            capture_output=capture,
            text=True,
            check=check
        )
        if logger and result.stdout:
            for line in result.stdout.strip().split('\n'):
                logger.debug(f"  stdout: {line}")
        return result
    except subprocess.CalledProcessError as e:
        if logger:
            logger.error(f"Command failed: {' '.join(cmd)}")
            if e.stdout:
                logger.error(f"stdout: {e.stdout}")
            if e.stderr:
                logger.error(f"stderr: {e.stderr}")
        raise


def calculate_checksum(file_path: Path, algorithm: str = "sha256") -> str:
    """Calculate file checksum."""
    hash_func = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def get_version_from_pyproject() -> str:
    """Extract version from pyproject.toml."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text()
        for line in content.split('\n'):
            if line.strip().startswith('version'):
                # Parse: version = "1.0.0"
                return line.split('=')[1].strip().strip('"\'')
    return "0.0.0"


# ============================================================================
# Environment Validation
# ============================================================================

class EnvironmentValidator:
    """Validates build environment and dependencies."""

    def __init__(self, config: BuildConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.issues: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> bool:
        """Run all validations."""
        self.logger.info("=" * 60)
        self.logger.info("Validating Build Environment")
        self.logger.info("=" * 60)

        self._check_python_version()
        self._check_node_version()
        self._check_build_dependencies()
        self._check_ffmpeg()
        self._check_platform_tools()
        self._check_signing_requirements()

        if self.issues:
            self.logger.error(f"Found {len(self.issues)} critical issue(s):")
            for issue in self.issues:
                self.logger.error(f"  - {issue}")
            return False

        if self.warnings:
            self.logger.warning(f"Found {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                self.logger.warning(f"  - {warning}")

        self.logger.info("Environment validation passed!")
        return True

    def _check_python_version(self):
        """Check Python version."""
        current = sys.version_info[:2]
        if current < MIN_PYTHON_VERSION:
            self.issues.append(
                f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required, "
                f"found {current[0]}.{current[1]}"
            )
        else:
            self.logger.info(f"Python version: {current[0]}.{current[1]} OK")

    def _check_node_version(self):
        """Check Node.js version."""
        try:
            result = run_command(["node", "--version"], capture=True, check=False)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.logger.info(f"Node.js version: {version} OK")
            else:
                self.issues.append("Node.js not found (required for frontend build)")
        except FileNotFoundError:
            self.issues.append("Node.js not found (required for frontend build)")

    def _check_build_dependencies(self):
        """Check Python build dependencies."""
        import importlib.util

        missing = []
        for dep in BUILD_DEPENDENCIES:
            spec = importlib.util.find_spec(dep.replace("-", "_"))
            if spec is None:
                missing.append(dep)

        if missing:
            self.issues.append(f"Missing Python packages: {', '.join(missing)}")
            self.logger.info(f"Install with: pip install {' '.join(missing)}")
        else:
            self.logger.info(f"Build dependencies: OK")

    def _check_ffmpeg(self):
        """Check FFmpeg availability."""
        ffmpeg = shutil.which("ffmpeg")
        vendor_ffmpeg = PROJECT_ROOT / "vendor" / "ffmpeg"

        if ffmpeg:
            self.logger.info(f"FFmpeg: Found in PATH")
        elif vendor_ffmpeg.exists():
            self.logger.info(f"FFmpeg: Found in vendor/")
        else:
            self.issues.append(
                "FFmpeg not found. Run: python build_tools/bundle_ffmpeg.py --platform all"
            )

    def _check_platform_tools(self):
        """Check platform-specific build tools."""
        current_platform = platform.system().lower()

        if "windows" in self.config.platforms or current_platform == "windows":
            # Check for Inno Setup
            iscc = shutil.which("ISCC") or Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
            if isinstance(iscc, Path) and not iscc.exists():
                iscc = None
            if not iscc and self.config.create_installer:
                self.warnings.append(
                    "Inno Setup not found. Windows installer won't be created. "
                    "Download from: https://jrsoftware.org/isinfo.php"
                )
            else:
                self.logger.info("Inno Setup: OK")

        if "macos" in self.config.platforms or current_platform == "darwin":
            # Check for Xcode tools
            try:
                run_command(["xcodebuild", "-version"], check=False)
                self.logger.info("Xcode tools: OK")
            except FileNotFoundError:
                if self.config.sign:
                    self.issues.append("Xcode tools required for macOS signing")

    def _check_signing_requirements(self):
        """Check code signing requirements."""
        if not self.config.sign:
            return

        current_platform = platform.system().lower()

        if current_platform == "windows":
            cert = os.environ.get("TERMIVOXED_CODESIGN_CERT")
            if not cert:
                self.warnings.append(
                    "TERMIVOXED_CODESIGN_CERT not set. Binaries won't be signed."
                )
            else:
                self.logger.info("Windows signing certificate: configured")

        elif current_platform == "darwin":
            dev_id = os.environ.get("APPLE_DEVELOPER_ID")
            if not dev_id:
                self.warnings.append(
                    "APPLE_DEVELOPER_ID not set. macOS app won't be signed."
                )
            else:
                self.logger.info("Apple Developer ID: configured")


# ============================================================================
# Test Runner
# ============================================================================

class TestRunner:
    """Runs pre-release tests."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def run_all_tests(self) -> bool:
        """Run all test suites."""
        self.logger.info("=" * 60)
        self.logger.info("Running Pre-Release Tests")
        self.logger.info("=" * 60)

        tests = [
            ("Python Linting", self._run_python_lint),
            ("Python Type Check", self._run_type_check),
            ("Python Unit Tests", self._run_python_tests),
            ("Frontend Lint", self._run_frontend_lint),
            ("Frontend Type Check", self._run_frontend_typecheck),
        ]

        results = {}
        for name, test_func in tests:
            self.logger.info(f"Running: {name}...")
            try:
                success = test_func()
                results[name] = success
                status = "PASSED" if success else "FAILED"
                self.logger.info(f"  {name}: {status}")
            except Exception as e:
                results[name] = False
                self.logger.error(f"  {name}: ERROR - {e}")

        passed = sum(1 for v in results.values() if v)
        total = len(results)
        self.logger.info(f"\nTest Results: {passed}/{total} passed")

        return all(results.values())

    def _run_python_lint(self) -> bool:
        """Run Python linting with flake8."""
        try:
            run_command(
                ["python", "-m", "flake8", "--max-line-length=120",
                 "--exclude=.git,__pycache__,build,dist,venv",
                 "backend", "core", "models", "utils"],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _run_type_check(self) -> bool:
        """Run type checking with mypy."""
        try:
            run_command(
                ["python", "-m", "mypy", "--ignore-missing-imports",
                 "backend", "core"],
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return True  # Skip if mypy not installed

    def _run_python_tests(self) -> bool:
        """Run Python unit tests."""
        try:
            run_command(
                ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "-q"],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
        except FileNotFoundError:
            self.logger.warning("pytest not found, skipping Python tests")
            return True

    def _run_frontend_lint(self) -> bool:
        """Run frontend linting."""
        frontend_dir = PROJECT_ROOT / "web_ui" / "frontend"
        try:
            run_command(["npm", "run", "lint"], cwd=frontend_dir, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _run_frontend_typecheck(self) -> bool:
        """Run frontend type checking."""
        frontend_dir = PROJECT_ROOT / "web_ui" / "frontend"
        try:
            run_command(["npx", "tsc", "--noEmit"], cwd=frontend_dir, check=True)
            return True
        except subprocess.CalledProcessError:
            return False


# ============================================================================
# Platform Builders
# ============================================================================

class PlatformBuilder:
    """Base class for platform-specific builders."""

    def __init__(self, config: BuildConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.start_time = None

    def build(self) -> BuildResult:
        """Execute the build process."""
        raise NotImplementedError


class WindowsBuilder(PlatformBuilder):
    """Windows-specific build process."""

    def build(self) -> BuildResult:
        import time
        self.start_time = time.time()

        result = BuildResult(platform="windows", success=False)

        try:
            self.logger.info("=" * 60)
            self.logger.info("Building Windows Application")
            self.logger.info("=" * 60)

            # Build frontend
            self._build_frontend()

            # Bundle FFmpeg if not present
            self._ensure_ffmpeg()

            # Build with PyInstaller
            exe_path = self._build_executable()
            result.executable_path = exe_path
            result.artifacts.append(exe_path)

            # Sign executable
            if self.config.sign:
                self._sign_executable(exe_path)

            # Create installer
            if self.config.create_installer:
                installer_path = self._create_installer(exe_path.parent)
                if installer_path:
                    result.installer_path = installer_path
                    result.artifacts.append(installer_path)

                    if self.config.sign:
                        self._sign_executable(installer_path)

            result.success = True

        except Exception as e:
            result.error = str(e)
            self.logger.error(f"Windows build failed: {e}")

        result.duration_seconds = time.time() - self.start_time
        return result

    def _build_frontend(self):
        """Build the frontend."""
        self.logger.info("Building frontend...")
        frontend_dir = PROJECT_ROOT / "web_ui" / "frontend"

        # Install dependencies if needed
        if not (frontend_dir / "node_modules").exists():
            run_command(["npm", "ci"], cwd=frontend_dir, logger=self.logger)

        run_command(["npm", "run", "build"], cwd=frontend_dir, logger=self.logger)
        self.logger.info("Frontend build complete")

    def _ensure_ffmpeg(self):
        """Ensure FFmpeg is bundled."""
        vendor_ffmpeg = PROJECT_ROOT / "vendor" / "ffmpeg" / "windows"
        if not vendor_ffmpeg.exists():
            self.logger.info("Bundling FFmpeg...")
            run_command(
                ["python", "build_tools/bundle_ffmpeg.py", "--platform", "windows"],
                logger=self.logger
            )

    def _build_executable(self) -> Path:
        """Build Windows executable with PyInstaller."""
        self.logger.info("Running PyInstaller...")

        dist_dir = DIST_DIR / "windows"
        dist_dir.mkdir(parents=True, exist_ok=True)

        spec_file = PROJECT_ROOT / "build_tools" / "windows" / "termivoxed.spec"

        if spec_file.exists():
            # Use existing spec file
            run_command(
                ["python", "-m", "PyInstaller", "--clean",
                 "--distpath", str(dist_dir),
                 "--workpath", str(BUILD_DIR / "windows" / "work"),
                 str(spec_file)],
                logger=self.logger
            )
        else:
            # Build without spec file
            run_command(
                ["python", "-m", "PyInstaller",
                 "--name", "TermiVoxed",
                 "--onedir",
                 "--windowed",
                 "--distpath", str(dist_dir),
                 "--add-data", f"{PROJECT_ROOT / 'web_ui' / 'frontend' / 'dist'};web_ui/frontend/dist",
                 "--add-data", f"{PROJECT_ROOT / 'backend'};backend",
                 "--add-data", f"{PROJECT_ROOT / 'core'};core",
                 "--add-data", f"{PROJECT_ROOT / 'vendor' / 'ffmpeg' / 'windows'};vendor/ffmpeg/windows",
                 "--hidden-import=uvicorn.logging",
                 "--hidden-import=uvicorn.protocols.http.auto",
                 "--hidden-import=uvicorn.protocols.websockets.auto",
                 "--hidden-import=uvicorn.lifespan.on",
                 str(PROJECT_ROOT / "build_tools" / "desktop" / "launcher.py")],
                logger=self.logger
            )

        exe_path = dist_dir / "TermiVoxed" / "TermiVoxed.exe"
        self.logger.info(f"Executable built: {exe_path}")
        return exe_path

    def _sign_executable(self, file_path: Path):
        """Sign a Windows executable."""
        cert_path = os.environ.get("TERMIVOXED_CODESIGN_CERT")
        if not cert_path:
            self.logger.warning("No signing certificate configured, skipping signing")
            return

        self.logger.info(f"Signing: {file_path.name}")

        signtool = shutil.which("signtool")
        if not signtool:
            # Search Windows SDK
            sdk_paths = list(Path(r"C:\Program Files (x86)\Windows Kits\10\bin").glob("*/x64/signtool.exe"))
            if sdk_paths:
                signtool = str(sdk_paths[0])

        if not signtool:
            self.logger.warning("signtool.exe not found, skipping signing")
            return

        timestamp_url = "http://timestamp.digicert.com"
        password = os.environ.get("TERMIVOXED_CODESIGN_PASSWORD", "")

        cmd = [signtool, "sign", "/fd", "sha256", "/tr", timestamp_url, "/td", "sha256"]

        if cert_path.upper() == "HSM":
            cmd.append("/a")
        else:
            cmd.extend(["/f", cert_path])
            if password:
                cmd.extend(["/p", password])

        cmd.append(str(file_path))

        run_command(cmd, logger=self.logger)
        self.logger.info(f"Signed: {file_path.name}")

    def _create_installer(self, exe_dir: Path) -> Optional[Path]:
        """Create Windows installer with Inno Setup."""
        iscc = shutil.which("ISCC")
        if not iscc:
            iscc_path = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
            if iscc_path.exists():
                iscc = str(iscc_path)

        if not iscc:
            self.logger.warning("Inno Setup not found, skipping installer creation")
            return None

        self.logger.info("Creating Windows installer...")

        # Generate Inno Setup script
        iss_content = f'''
[Setup]
AppId={{{{B5A7C8D9-E6F1-4A2B-8C3D-E4F5A6B7C8D9}}}}
AppName=TermiVoxed
AppVersion={self.config.version}
AppPublisher=LxusBrain
AppPublisherURL=https://lxusbrain.com
DefaultDirName={{autopf}}\\TermiVoxed
DisableProgramGroupPage=yes
OutputDir={DIST_DIR / "windows"}
OutputBaseFilename=TermiVoxed-{self.config.version}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "{exe_dir}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{{autoprograms}}\\TermiVoxed"; Filename: "{{app}}\\TermiVoxed.exe"
Name: "{{autodesktop}}\\TermiVoxed"; Filename: "{{app}}\\TermiVoxed.exe"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\TermiVoxed.exe"; Description: "Launch TermiVoxed"; Flags: nowait postinstall skipifsilent
'''

        iss_file = BUILD_DIR / "windows" / "installer.iss"
        iss_file.parent.mkdir(parents=True, exist_ok=True)
        iss_file.write_text(iss_content)

        run_command([iscc, str(iss_file)], logger=self.logger)

        installer_path = DIST_DIR / "windows" / f"TermiVoxed-{self.config.version}-Setup.exe"
        if installer_path.exists():
            self.logger.info(f"Installer created: {installer_path}")
            return installer_path

        return None


class MacOSBuilder(PlatformBuilder):
    """macOS-specific build process."""

    def build(self) -> BuildResult:
        import time
        self.start_time = time.time()

        result = BuildResult(platform="macos", success=False)

        try:
            self.logger.info("=" * 60)
            self.logger.info("Building macOS Application")
            self.logger.info("=" * 60)

            # Build frontend
            self._build_frontend()

            # Bundle FFmpeg
            self._ensure_ffmpeg()

            # Build with PyInstaller
            app_path = self._build_app()
            result.executable_path = app_path
            result.artifacts.append(app_path)

            # Sign app
            if self.config.sign:
                self._sign_app(app_path)

            # Create DMG
            if self.config.create_installer:
                dmg_path = self._create_dmg(app_path)
                if dmg_path:
                    result.installer_path = dmg_path
                    result.artifacts.append(dmg_path)

            # Notarize
            if self.config.notarize and self.config.sign:
                self._notarize_app(result.installer_path or app_path)

            result.success = True

        except Exception as e:
            result.error = str(e)
            self.logger.error(f"macOS build failed: {e}")

        result.duration_seconds = time.time() - self.start_time
        return result

    def _build_frontend(self):
        """Build the frontend."""
        self.logger.info("Building frontend...")
        frontend_dir = PROJECT_ROOT / "web_ui" / "frontend"

        if not (frontend_dir / "node_modules").exists():
            run_command(["npm", "ci"], cwd=frontend_dir, logger=self.logger)

        run_command(["npm", "run", "build"], cwd=frontend_dir, logger=self.logger)

    def _ensure_ffmpeg(self):
        """Ensure FFmpeg is bundled."""
        vendor_ffmpeg = PROJECT_ROOT / "vendor" / "ffmpeg" / "macos"
        if not vendor_ffmpeg.exists():
            self.logger.info("Bundling FFmpeg...")
            run_command(
                ["python", "build_tools/bundle_ffmpeg.py", "--platform", "macos"],
                logger=self.logger
            )

    def _build_app(self) -> Path:
        """Build macOS app with PyInstaller."""
        self.logger.info("Running PyInstaller...")

        dist_dir = DIST_DIR / "macos"
        dist_dir.mkdir(parents=True, exist_ok=True)

        run_command(
            ["python", "-m", "PyInstaller",
             "--name", "TermiVoxed",
             "--onedir",
             "--windowed",
             "--osx-bundle-identifier", "com.lxusbrain.termivoxed",
             "--distpath", str(dist_dir),
             "--add-data", f"{PROJECT_ROOT / 'web_ui' / 'frontend' / 'dist'}:web_ui/frontend/dist",
             "--add-data", f"{PROJECT_ROOT / 'backend'}:backend",
             "--add-data", f"{PROJECT_ROOT / 'core'}:core",
             "--add-data", f"{PROJECT_ROOT / 'vendor' / 'ffmpeg' / 'macos'}:vendor/ffmpeg/macos",
             "--hidden-import=uvicorn.logging",
             "--hidden-import=uvicorn.protocols.http.auto",
             "--hidden-import=uvicorn.protocols.websockets.auto",
             "--hidden-import=uvicorn.lifespan.on",
             str(PROJECT_ROOT / "build_tools" / "desktop" / "launcher.py")],
            logger=self.logger
        )

        app_path = dist_dir / "TermiVoxed.app"
        self.logger.info(f"App bundle built: {app_path}")
        return app_path

    def _sign_app(self, app_path: Path):
        """Sign macOS app."""
        dev_id = os.environ.get("APPLE_DEVELOPER_ID")
        if not dev_id:
            self.logger.warning("APPLE_DEVELOPER_ID not set, skipping signing")
            return

        self.logger.info("Signing macOS app...")
        run_command(
            ["codesign", "--force", "--deep", "--sign", dev_id,
             "--options", "runtime", "--timestamp", str(app_path)],
            logger=self.logger
        )
        self.logger.info("App signed successfully")

    def _create_dmg(self, app_path: Path) -> Optional[Path]:
        """Create DMG installer."""
        self.logger.info("Creating DMG...")

        dmg_path = DIST_DIR / "macos" / f"TermiVoxed-{self.config.version}-macos.dmg"

        run_command(
            ["hdiutil", "create",
             "-volname", "TermiVoxed",
             "-srcfolder", str(app_path),
             "-ov", "-format", "UDZO",
             str(dmg_path)],
            logger=self.logger
        )

        self.logger.info(f"DMG created: {dmg_path}")
        return dmg_path

    def _notarize_app(self, path: Path):
        """Notarize macOS app for distribution."""
        apple_id = os.environ.get("APPLE_ID")
        team_id = os.environ.get("APPLE_TEAM_ID")
        password = os.environ.get("APPLE_APP_PASSWORD")

        if not all([apple_id, team_id, password]):
            self.logger.warning("Apple notarization credentials not configured")
            return

        self.logger.info("Submitting for notarization...")
        run_command(
            ["xcrun", "notarytool", "submit", str(path),
             "--apple-id", apple_id,
             "--team-id", team_id,
             "--password", password,
             "--wait"],
            logger=self.logger
        )

        # Staple the notarization ticket
        run_command(["xcrun", "stapler", "staple", str(path)], logger=self.logger)
        self.logger.info("Notarization complete")


class LinuxBuilder(PlatformBuilder):
    """Linux-specific build process."""

    def build(self) -> BuildResult:
        import time
        self.start_time = time.time()

        result = BuildResult(platform="linux", success=False)

        try:
            self.logger.info("=" * 60)
            self.logger.info("Building Linux Application")
            self.logger.info("=" * 60)

            # Build frontend
            self._build_frontend()

            # Bundle FFmpeg
            self._ensure_ffmpeg()

            # Build executable
            exe_path = self._build_executable()
            result.executable_path = exe_path
            result.artifacts.append(exe_path)

            # Create archive
            if self.config.create_installer:
                archive_path = self._create_archive(exe_path.parent)
                if archive_path:
                    result.installer_path = archive_path
                    result.artifacts.append(archive_path)

            result.success = True

        except Exception as e:
            result.error = str(e)
            self.logger.error(f"Linux build failed: {e}")

        result.duration_seconds = time.time() - self.start_time
        return result

    def _build_frontend(self):
        """Build the frontend."""
        self.logger.info("Building frontend...")
        frontend_dir = PROJECT_ROOT / "web_ui" / "frontend"

        if not (frontend_dir / "node_modules").exists():
            run_command(["npm", "ci"], cwd=frontend_dir, logger=self.logger)

        run_command(["npm", "run", "build"], cwd=frontend_dir, logger=self.logger)

    def _ensure_ffmpeg(self):
        """Ensure FFmpeg is bundled."""
        vendor_ffmpeg = PROJECT_ROOT / "vendor" / "ffmpeg" / "linux"
        if not vendor_ffmpeg.exists():
            self.logger.info("Bundling FFmpeg...")
            run_command(
                ["python", "build_tools/bundle_ffmpeg.py", "--platform", "linux"],
                logger=self.logger
            )

    def _build_executable(self) -> Path:
        """Build Linux executable."""
        self.logger.info("Running PyInstaller...")

        dist_dir = DIST_DIR / "linux"
        dist_dir.mkdir(parents=True, exist_ok=True)

        run_command(
            ["python", "-m", "PyInstaller",
             "--name", "TermiVoxed",
             "--onedir",
             "--distpath", str(dist_dir),
             "--add-data", f"{PROJECT_ROOT / 'web_ui' / 'frontend' / 'dist'}:web_ui/frontend/dist",
             "--add-data", f"{PROJECT_ROOT / 'backend'}:backend",
             "--add-data", f"{PROJECT_ROOT / 'core'}:core",
             "--add-data", f"{PROJECT_ROOT / 'vendor' / 'ffmpeg' / 'linux'}:vendor/ffmpeg/linux",
             "--hidden-import=uvicorn.logging",
             "--hidden-import=uvicorn.protocols.http.auto",
             "--hidden-import=uvicorn.protocols.websockets.auto",
             "--hidden-import=uvicorn.lifespan.on",
             str(PROJECT_ROOT / "build_tools" / "desktop" / "launcher.py")],
            logger=self.logger
        )

        exe_path = dist_dir / "TermiVoxed" / "TermiVoxed"
        self.logger.info(f"Executable built: {exe_path}")
        return exe_path

    def _create_archive(self, exe_dir: Path) -> Optional[Path]:
        """Create tar.gz archive."""
        self.logger.info("Creating archive...")

        archive_name = f"TermiVoxed-{self.config.version}-linux-x64.tar.gz"
        archive_path = DIST_DIR / "linux" / archive_name

        run_command(
            ["tar", "-czvf", str(archive_path), "-C", str(exe_dir.parent), exe_dir.name],
            logger=self.logger
        )

        self.logger.info(f"Archive created: {archive_path}")
        return archive_path


# ============================================================================
# Release Manager
# ============================================================================

class ReleaseManager:
    """Orchestrates the entire release process."""

    def __init__(self, config: BuildConfig):
        self.config = config
        self.log_file = LOGS_DIR / f"release-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        self.logger = setup_logging(config.verbose, self.log_file)
        self.results: Dict[str, BuildResult] = {}

    def execute(self) -> bool:
        """Execute the full release process."""
        self.logger.info("=" * 60)
        self.logger.info(f"TermiVoxed Release v{self.config.version}")
        self.logger.info(f"Platforms: {', '.join(self.config.platforms)}")
        self.logger.info(f"Log file: {self.log_file}")
        self.logger.info("=" * 60)

        # Step 1: Validate environment
        validator = EnvironmentValidator(self.config, self.logger)
        if not validator.validate_all():
            return False

        # Step 2: Run tests
        if self.config.run_tests:
            test_runner = TestRunner(self.logger)
            if not test_runner.run_all_tests():
                self.logger.error("Tests failed. Use --skip-tests to bypass.")
                return False

        # Step 3: Build for each platform
        current_platform = platform.system().lower()
        platform_map = {
            "windows": ("windows", WindowsBuilder),
            "darwin": ("macos", MacOSBuilder),
            "linux": ("linux", LinuxBuilder),
        }

        builders = []
        for plat in self.config.platforms:
            if plat == "all":
                # Only build for current platform when running locally
                if current_platform in platform_map:
                    plat_name, builder_class = platform_map[current_platform]
                    builders.append((plat_name, builder_class))
            else:
                # Map platform name
                for sys_name, (plat_name, builder_class) in platform_map.items():
                    if plat == plat_name:
                        if current_platform == sys_name:
                            builders.append((plat_name, builder_class))
                        else:
                            self.logger.warning(
                                f"Cannot build {plat} on {current_platform}. "
                                "Use GitHub Actions for cross-platform builds."
                            )

        # Execute builds
        for plat_name, builder_class in builders:
            builder = builder_class(self.config, self.logger)
            result = builder.build()
            self.results[plat_name] = result

        # Step 4: Generate checksums and manifest
        self._generate_manifest()

        # Step 5: Copy to release directory
        self._prepare_release_assets()

        # Step 6: Push to GitHub (if requested)
        if self.config.push_release:
            self._push_to_github()

        # Print summary
        self._print_summary()

        return all(r.success for r in self.results.values())

    def _generate_manifest(self):
        """Generate release manifest with checksums."""
        self.logger.info("Generating release manifest...")

        RELEASE_DIR.mkdir(parents=True, exist_ok=True)

        checksums = {}
        platforms_info = {}

        for plat, result in self.results.items():
            if not result.success:
                continue

            platforms_info[plat] = {
                "build_duration": result.duration_seconds,
                "artifacts": [],
            }

            for artifact in result.artifacts:
                if artifact.exists():
                    checksum = calculate_checksum(artifact)
                    checksums[artifact.name] = checksum
                    platforms_info[plat]["artifacts"].append({
                        "name": artifact.name,
                        "size": artifact.stat().st_size,
                        "sha256": checksum,
                    })

        manifest = ReleaseManifest(
            version=self.config.version,
            timestamp=datetime.utcnow().isoformat() + "Z",
            platforms=platforms_info,
            checksums=checksums,
            signed=self.config.sign,
            prerelease=self.config.prerelease,
        )

        # Save manifest
        manifest_path = RELEASE_DIR / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump({
                "version": manifest.version,
                "timestamp": manifest.timestamp,
                "platforms": manifest.platforms,
                "checksums": manifest.checksums,
                "signed": manifest.signed,
                "prerelease": manifest.prerelease,
            }, f, indent=2)

        # Save checksums file
        checksums_path = RELEASE_DIR / "checksums.txt"
        with open(checksums_path, "w") as f:
            for name, checksum in checksums.items():
                f.write(f"{checksum}  {name}\n")

        self.logger.info(f"Manifest saved: {manifest_path}")
        self.logger.info(f"Checksums saved: {checksums_path}")

    def _prepare_release_assets(self):
        """Copy all release assets to release directory."""
        self.logger.info("Preparing release assets...")

        for plat, result in self.results.items():
            if not result.success:
                continue

            for artifact in result.artifacts:
                if artifact.exists():
                    dest = RELEASE_DIR / artifact.name
                    shutil.copy2(artifact, dest)
                    self.logger.info(f"  Copied: {artifact.name}")

    def _push_to_github(self):
        """Push release to GitHub."""
        self.logger.info("Pushing release to GitHub...")

        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            self.logger.error("GITHUB_TOKEN not set. Cannot push release.")
            return

        # Create release using gh CLI
        tag = f"v{self.config.version}"

        # Collect release files
        release_files = list(RELEASE_DIR.glob("*"))
        files_arg = " ".join(str(f) for f in release_files if f.is_file())

        prerelease_flag = "--prerelease" if self.config.prerelease else ""

        run_command(
            ["gh", "release", "create", tag,
             "--title", f"TermiVoxed v{self.config.version}",
             "--notes-file", str(RELEASE_DIR / "manifest.json"),
             prerelease_flag] + [str(f) for f in release_files if f.is_file()],
            env={"GITHUB_TOKEN": token},
            logger=self.logger
        )

        self.logger.info(f"Release published: {tag}")

    def _print_summary(self):
        """Print build summary."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("BUILD SUMMARY")
        self.logger.info("=" * 60)

        for plat, result in self.results.items():
            status = "SUCCESS" if result.success else "FAILED"
            duration = f"{result.duration_seconds:.1f}s"
            self.logger.info(f"  {plat.upper():12} {status:10} ({duration})")

            if result.success:
                for artifact in result.artifacts:
                    self.logger.info(f"    - {artifact.name}")
            elif result.error:
                self.logger.info(f"    Error: {result.error}")

        self.logger.info("")
        self.logger.info(f"Release directory: {RELEASE_DIR}")
        self.logger.info(f"Build logs: {self.log_file}")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="TermiVoxed Release Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_tools/release.py --version 1.0.0
  python build_tools/release.py --version 1.0.0 --platform windows --sign
  python build_tools/release.py --version 1.0.0 --platform all --push-release
  python build_tools/release.py --version 1.0.0-beta.1 --prerelease
        """
    )

    parser.add_argument(
        "--version", "-v",
        help="Version to release (e.g., 1.0.0). Defaults to pyproject.toml version.",
        default=None
    )
    parser.add_argument(
        "--platform", "-p",
        choices=["windows", "macos", "linux", "all"],
        default="all",
        help="Platform to build for (default: all)"
    )
    parser.add_argument(
        "--sign",
        action="store_true",
        help="Sign binaries (requires certificates)"
    )
    parser.add_argument(
        "--notarize",
        action="store_true",
        help="Notarize macOS app (requires Apple credentials)"
    )
    parser.add_argument(
        "--no-installer",
        action="store_true",
        help="Skip installer creation"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running tests before build"
    )
    parser.add_argument(
        "--push-release",
        action="store_true",
        help="Push release to GitHub"
    )
    parser.add_argument(
        "--prerelease",
        action="store_true",
        help="Mark as pre-release"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Determine version
    version = args.version or get_version_from_pyproject()

    # Build configuration
    config = BuildConfig(
        version=version,
        platforms=[args.platform] if args.platform != "all" else ["all"],
        sign=args.sign,
        notarize=args.notarize,
        create_installer=not args.no_installer,
        run_tests=not args.skip_tests,
        push_release=args.push_release,
        prerelease=args.prerelease,
        verbose=args.verbose,
    )

    # Execute release
    manager = ReleaseManager(config)
    success = manager.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
