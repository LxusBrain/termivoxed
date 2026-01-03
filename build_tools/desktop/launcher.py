#!/usr/bin/env python3
"""
TermiVoxed Desktop Launcher

This is the main entry point for the desktop application.
When built with PyInstaller, this becomes TermiVoxed.exe / TermiVoxed.app

IMPORTANT: This file handles finding bundled dependencies.
The key concept: We check if we're running as a frozen executable,
and if so, we use the BUNDLED dependencies, not system ones.
"""

import sys
import os
import subprocess
import threading
import time
import webbrowser
from pathlib import Path


def is_frozen():
    """Check if we're running as a PyInstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_app_dir():
    """
    Get the directory where our application files are.

    When running as .exe:
        sys._MEIPASS points to the temp extraction directory
        sys.executable points to the .exe location

    When running from source:
        __file__ points to this script
    """
    if is_frozen():
        # Running as compiled .exe / .app
        # _MEIPASS is where PyInstaller extracted our files
        return Path(sys._MEIPASS)
    else:
        # Running from source
        return Path(__file__).parent.parent.parent


def get_data_dir():
    """
    Get the directory for user data (projects, settings, etc.)

    This is SEPARATE from the app installation directory.
    User data persists across updates.
    """
    if sys.platform == 'win32':
        # Windows: C:\Users\Username\AppData\Local\TermiVoxed
        base = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
        return base / 'TermiVoxed'
    elif sys.platform == 'darwin':
        # macOS: ~/Library/Application Support/TermiVoxed
        return Path.home() / 'Library' / 'Application Support' / 'TermiVoxed'
    else:
        # Linux: ~/.local/share/termivoxed
        return Path.home() / '.local' / 'share' / 'termivoxed'


def get_bundled_python():
    """
    Get path to our bundled Python interpreter.

    This is NOT the system Python. This is OUR Python, bundled inside the app.
    """
    if is_frozen():
        # When frozen, Python is already running embedded
        return sys.executable
    else:
        return sys.executable


def get_bundled_ffmpeg():
    """
    Get path to our bundled FFmpeg binary.

    This is NOT the system FFmpeg. This is OUR FFmpeg, bundled inside the app.

    FFmpeg is bundled in vendor/ffmpeg/{platform}/bin/ by bundle_ffmpeg.py
    """
    app_dir = get_app_dir()

    # Determine platform-specific paths
    if sys.platform == 'win32':
        platform_name = 'windows'
        binary_name = 'ffmpeg.exe'
    elif sys.platform == 'darwin':
        platform_name = 'macos'
        binary_name = 'ffmpeg'
    else:
        platform_name = 'linux'
        binary_name = 'ffmpeg'

    # Path structure from bundle_ffmpeg.py: vendor/ffmpeg/{platform}/bin/
    possible_paths = [
        # Standard bundled path
        app_dir / 'vendor' / 'ffmpeg' / platform_name / 'bin' / binary_name,
        # Simplified path (for manual bundling)
        app_dir / 'ffmpeg' / binary_name,
        # Direct in vendor
        app_dir / 'vendor' / 'ffmpeg' / 'bin' / binary_name,
        # Flat structure
        app_dir / 'ffmpeg' / 'bin' / binary_name,
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    # Fallback to system FFmpeg only in development
    if not is_frozen():
        import shutil
        system_ffmpeg = shutil.which('ffmpeg')
        if system_ffmpeg:
            return system_ffmpeg

    return None


def setup_environment():
    """
    Configure environment variables for bundled dependencies.

    This ensures our bundled FFmpeg, models, etc. are used
    instead of anything on the system.
    """
    app_dir = get_app_dir()
    data_dir = get_data_dir()

    # Create user data directories
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / 'storage').mkdir(exist_ok=True)
    (data_dir / 'storage' / 'projects').mkdir(exist_ok=True)
    (data_dir / 'models').mkdir(exist_ok=True)
    (data_dir / 'logs').mkdir(exist_ok=True)

    # Set environment variables
    os.environ['TERMIVOXED_APP_DIR'] = str(app_dir)
    os.environ['TERMIVOXED_DATA_DIR'] = str(data_dir)
    os.environ['TERMIVOXED_STORAGE_DIR'] = str(data_dir / 'storage')
    os.environ['TERMIVOXED_MODELS_DIR'] = str(data_dir / 'models')
    os.environ['TERMIVOXED_LOGS_DIR'] = str(data_dir / 'logs')

    # Point to bundled FFmpeg
    ffmpeg_path = get_bundled_ffmpeg()
    if ffmpeg_path:
        ffmpeg_dir = str(Path(ffmpeg_path).parent)
        # Prepend to PATH so our FFmpeg is found first
        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
        os.environ['FFMPEG_BINARY'] = ffmpeg_path

    # Point to bundled models directory (may need to download on first run)
    os.environ['COQUI_TTS_MODELS_DIR'] = str(data_dir / 'models' / 'tts')

    # Disable GPU if not available (prevents CUDA errors)
    if not check_gpu_available():
        os.environ['CUDA_VISIBLE_DEVICES'] = ''


def check_gpu_available():
    """Check if GPU is available for TTS acceleration."""
    try:
        import torch
        return torch.cuda.is_available()
    except:
        return False


def check_first_run():
    """Check if this is the first time the app is running."""
    data_dir = get_data_dir()
    marker = data_dir / '.initialized'

    if not marker.exists():
        # First run - may need to download models, show welcome screen, etc.
        return True
    return False


def mark_initialized():
    """Mark that first-run setup is complete."""
    marker = get_data_dir() / '.initialized'
    marker.write_text(f'Initialized at {time.strftime("%Y-%m-%d %H:%M:%S")}')


def find_available_port(start_port=8000, max_attempts=10):
    """Find an available port starting from the given port.

    This is SAFE - it never kills existing processes, just finds
    the next available port.
    """
    import socket

    for offset in range(max_attempts):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue

    # If no port found in range, let the OS assign one
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def start_backend(port=None):
    """Start the FastAPI backend server."""
    app_dir = get_app_dir()

    # Add app directory to Python path
    sys.path.insert(0, str(app_dir))

    # Find available port if not specified
    if port is None:
        port = find_available_port()

    # Import and run uvicorn
    import uvicorn
    from web_ui.api.main import app

    config = uvicorn.Config(
        app,
        host='127.0.0.1',
        port=port,
        log_level='info',
    )
    server = uvicorn.Server(config)
    return server, port


def open_browser(url, delay=2):
    """Open browser after a delay to let server start."""
    time.sleep(delay)
    webbrowser.open(url)


def main():
    """Main entry point for TermiVoxed desktop application."""
    print("=" * 60)
    print("  TermiVoxed - AI Voice-Over Dubbing Studio")
    print("  By LxusBrain")
    print("=" * 60)

    # Setup environment for bundled dependencies
    print("[1/5] Setting up environment...")
    setup_environment()

    # Check if first run
    if check_first_run():
        print("[2/5] First run detected - initializing...")
        # TODO: Show first-run wizard for model download
        mark_initialized()
    else:
        print("[2/5] Loading configuration...")

    # Verify bundled dependencies
    print("[3/5] Verifying dependencies...")
    ffmpeg = get_bundled_ffmpeg()
    if ffmpeg:
        print(f"       FFmpeg: {ffmpeg}")
    else:
        print("       WARNING: FFmpeg not found!")

    # Find available port (SAFE - never kills existing processes)
    print("[4/5] Finding available port...")
    port = find_available_port(start_port=8000, max_attempts=10)
    if port != 8000:
        print(f"       Port 8000 is in use, using port {port} instead")
    else:
        print(f"       Using port {port}")

    # Start backend server
    print("[5/5] Starting backend server...")

    try:
        # Import here after environment is set up
        import uvicorn
        sys.path.insert(0, str(get_app_dir()))

        # Start server in background thread with dynamic port
        def run_server():
            from web_ui.api.main import app
            uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Open browser with correct port
        url = f"http://127.0.0.1:{port}"
        threading.Thread(target=open_browser, args=(url, 2), daemon=True).start()

        print()
        print(f"TermiVoxed is running at: {url}")
        print("Press Ctrl+C to stop")
        print()

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        # Log error to file for debugging
        error_log = get_data_dir() / 'logs' / 'startup_error.log'
        error_log.parent.mkdir(parents=True, exist_ok=True)

        import traceback
        error_details = traceback.format_exc()

        with open(error_log, 'w') as f:
            f.write(f"TermiVoxed Startup Error - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Error: {e}\n\n")
            f.write("Full Traceback:\n")
            f.write(error_details)
            f.write("\n\nEnvironment:\n")
            f.write(f"  Python: {sys.version}\n")
            f.write(f"  Platform: {sys.platform}\n")
            f.write(f"  Frozen: {is_frozen()}\n")
            f.write(f"  App Dir: {get_app_dir()}\n")
            f.write(f"  Data Dir: {get_data_dir()}\n")

        print(f"\nError starting server: {e}")
        print(f"\nError details have been saved to:\n{error_log}")

        # On Windows, show a message box for better UX
        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"TermiVoxed failed to start.\n\nError: {e}\n\nCheck the log file for details:\n{error_log}",
                    "TermiVoxed Error",
                    0x10  # MB_ICONERROR
                )
            except:
                pass
        else:
            input("Press Enter to exit...")


if __name__ == '__main__':
    main()
