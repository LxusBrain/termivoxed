"""Font management API routes - Google Fonts integration and local font detection"""

import httpx
import subprocess
import platform
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List

router = APIRouter()

# Google Fonts API base URL
GOOGLE_FONTS_API = "https://www.googleapis.com/webfonts/v1/webfonts"

# Cache for fonts list (to avoid repeated API calls)
_fonts_cache: List[dict] = []
_cache_timestamp: float = 0

# Cache for local fonts
_local_fonts_cache: List[dict] = []
_local_fonts_timestamp: float = 0


class GoogleFont(BaseModel):
    """Google Font representation"""
    family: str
    category: str
    variants: List[str]
    subsets: List[str]


class GoogleFontsResponse(BaseModel):
    """Response containing list of Google Fonts"""
    fonts: List[GoogleFont]
    total: int
    cached: bool = False


class FontCheckResponse(BaseModel):
    """Response for font availability check"""
    font_name: str
    is_google_font: bool
    is_installed: bool
    install_url: Optional[str] = None
    install_instructions: str = ""


class LocalFont(BaseModel):
    """Local system font representation"""
    family: str
    style: str = "Regular"
    path: Optional[str] = None


class LocalFontsResponse(BaseModel):
    """Response containing list of local system fonts"""
    fonts: List[LocalFont]
    total: int
    platform: str
    cached: bool = False


@router.get("/google", response_model=GoogleFontsResponse)
async def get_google_fonts(
    sort: str = Query("popularity", description="Sort by: alpha, popularity, trending, date"),
    category: Optional[str] = Query(None, description="Filter by category: serif, sans-serif, display, handwriting, monospace"),
    search: Optional[str] = Query(None, description="Search fonts by name")
):
    """
    Get list of available Google Fonts.

    Returns all Google Fonts sorted by the specified criteria.
    Results can be filtered by category and searched by name.
    """
    global _fonts_cache, _cache_timestamp
    import time

    # Check cache (valid for 1 hour)
    current_time = time.time()
    if _fonts_cache and (current_time - _cache_timestamp) < 3600:
        fonts = _fonts_cache
        cached = True
    else:
        # Fetch from Google Fonts API
        try:
            # Note: Using the API without a key gives limited but sufficient results
            # For production, add your API key: ?key=YOUR_API_KEY
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    GOOGLE_FONTS_API,
                    params={"sort": sort},
                    timeout=10.0
                )

                if response.status_code != 200:
                    # Fallback to a curated list if API fails
                    return GoogleFontsResponse(
                        fonts=_get_fallback_fonts(),
                        total=len(_get_fallback_fonts()),
                        cached=False
                    )

                data = response.json()
                fonts = [
                    {
                        "family": item["family"],
                        "category": item.get("category", "sans-serif"),
                        "variants": item.get("variants", ["regular"]),
                        "subsets": item.get("subsets", ["latin"])
                    }
                    for item in data.get("items", [])
                ]

                # Update cache
                _fonts_cache = fonts
                _cache_timestamp = current_time
                cached = False

        except Exception as e:
            # Return fallback fonts on error
            return GoogleFontsResponse(
                fonts=_get_fallback_fonts(),
                total=len(_get_fallback_fonts()),
                cached=False
            )

    # Apply category filter
    if category:
        fonts = [f for f in fonts if f.get("category", "").lower() == category.lower()]

    # Apply search filter
    if search:
        search_lower = search.lower()
        fonts = [f for f in fonts if search_lower in f.get("family", "").lower()]

    return GoogleFontsResponse(
        fonts=[GoogleFont(**f) for f in fonts],
        total=len(fonts),
        cached=cached
    )


@router.get("/check", response_model=FontCheckResponse)
async def check_font(font_name: str = Query(..., description="Font name to check")):
    """
    Check if a font is available and provide installation instructions.

    Checks if the font is a Google Font and provides installation instructions
    for use in video exports.
    """
    # Check if it's in the cache (Google Font)
    global _fonts_cache

    is_google_font = False
    if _fonts_cache:
        is_google_font = any(
            f.get("family", "").lower() == font_name.lower()
            for f in _fonts_cache
        )

    # For now, we can't easily check if a font is installed on the system
    # This would require system-specific checks
    is_installed = False  # Assume not installed for now

    # Generate installation instructions
    if is_google_font:
        install_url = f"https://fonts.google.com/specimen/{font_name.replace(' ', '+')}"
        install_instructions = f"""
To use "{font_name}" in your video exports:

1. Download the font from: {install_url}
2. Install the font on your system:
   - **macOS**: Double-click the .ttf file and click "Install Font"
   - **Windows**: Right-click the .ttf file and select "Install"
   - **Linux**: Copy to ~/.fonts/ and run 'fc-cache -fv'

3. Restart the application to detect the new font.

Note: For subtitle rendering, the font must be installed on your system.
"""
    else:
        install_url = None
        install_instructions = f"""
"{font_name}" was not found in Google Fonts.

If it's a custom font:
1. Ensure the font file (.ttf or .otf) is installed on your system
2. Restart the application to detect the font

If you meant a different font, try searching in the font dropdown.
"""

    return FontCheckResponse(
        font_name=font_name,
        is_google_font=is_google_font,
        is_installed=is_installed,
        install_url=install_url,
        install_instructions=install_instructions.strip()
    )


@router.get("/local", response_model=LocalFontsResponse)
async def get_local_fonts(
    search: Optional[str] = Query(None, description="Search fonts by name"),
    refresh: bool = Query(False, description="Force refresh the font cache")
):
    """
    Get list of fonts installed on the local system.

    Detects fonts installed on macOS, Windows, or Linux.
    Results are cached for 5 minutes unless refresh=true.
    """
    global _local_fonts_cache, _local_fonts_timestamp
    import time

    current_time = time.time()
    cache_valid = _local_fonts_cache and (current_time - _local_fonts_timestamp) < 300  # 5 min cache

    if cache_valid and not refresh:
        fonts = _local_fonts_cache
        cached = True
    else:
        fonts = _detect_system_fonts()
        _local_fonts_cache = fonts
        _local_fonts_timestamp = current_time
        cached = False

    # Apply search filter
    if search:
        search_lower = search.lower()
        fonts = [f for f in fonts if search_lower in f.get("family", "").lower()]

    return LocalFontsResponse(
        fonts=[LocalFont(**f) for f in fonts],
        total=len(fonts),
        platform=platform.system(),
        cached=cached
    )


def _detect_system_fonts() -> List[dict]:
    """Detect fonts installed on the system based on OS"""
    system = platform.system()

    if system == "Darwin":  # macOS
        return _detect_macos_fonts()
    elif system == "Windows":
        return _detect_windows_fonts()
    elif system == "Linux":
        return _detect_linux_fonts()
    else:
        return []


def _detect_macos_fonts() -> List[dict]:
    """Detect fonts on macOS using system_profiler or font directories"""
    fonts = []
    seen_families = set()

    # Method 1: Try using fc-list (if fontconfig is installed via Homebrew)
    try:
        result = subprocess.run(
            ["fc-list", "--format", "%{family}\n"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line and line not in seen_families:
                    # fc-list may return comma-separated family names
                    for family in line.split(","):
                        family = family.strip()
                        if family and family not in seen_families:
                            seen_families.add(family)
                            fonts.append({"family": family, "style": "Regular"})
            if fonts:
                return sorted(fonts, key=lambda x: x["family"].lower())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Method 2: Scan font directories directly
    font_dirs = [
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
        Path.home() / "Library/Fonts",
    ]

    for font_dir in font_dirs:
        if font_dir.exists():
            for font_file in font_dir.rglob("*"):
                if font_file.suffix.lower() in [".ttf", ".otf", ".ttc", ".dfont"]:
                    family = font_file.stem
                    # Clean up font name
                    family = family.replace("-", " ").replace("_", " ")
                    # Remove common suffixes
                    for suffix in ["Regular", "Bold", "Italic", "Light", "Medium", "Thin", "Black", "Heavy"]:
                        if family.endswith(suffix):
                            family = family[:-len(suffix)].strip()

                    if family and family not in seen_families:
                        seen_families.add(family)
                        fonts.append({
                            "family": family,
                            "style": "Regular",
                            "path": str(font_file)
                        })

    return sorted(fonts, key=lambda x: x["family"].lower())


def _detect_windows_fonts() -> List[dict]:
    """Detect fonts on Windows"""
    fonts = []
    seen_families = set()

    # Windows font directories
    font_dirs = [
        Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts",
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
    ]

    for font_dir in font_dirs:
        if font_dir.exists():
            for font_file in font_dir.glob("*"):
                if font_file.suffix.lower() in [".ttf", ".otf", ".ttc"]:
                    family = font_file.stem
                    # Clean up font name
                    family = family.replace("-", " ").replace("_", " ")
                    for suffix in ["Regular", "Bold", "Italic", "Light", "Medium"]:
                        if family.endswith(suffix):
                            family = family[:-len(suffix)].strip()

                    if family and family not in seen_families:
                        seen_families.add(family)
                        fonts.append({
                            "family": family,
                            "style": "Regular",
                            "path": str(font_file)
                        })

    return sorted(fonts, key=lambda x: x["family"].lower())


def _detect_linux_fonts() -> List[dict]:
    """Detect fonts on Linux using fc-list"""
    fonts = []
    seen_families = set()

    # Method 1: Use fc-list (fontconfig)
    try:
        result = subprocess.run(
            ["fc-list", "--format", "%{family}\n"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    for family in line.split(","):
                        family = family.strip()
                        if family and family not in seen_families:
                            seen_families.add(family)
                            fonts.append({"family": family, "style": "Regular"})
            return sorted(fonts, key=lambda x: x["family"].lower())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Method 2: Scan common font directories
    font_dirs = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path.home() / ".local/share/fonts",
    ]

    for font_dir in font_dirs:
        if font_dir.exists():
            for font_file in font_dir.rglob("*"):
                if font_file.suffix.lower() in [".ttf", ".otf"]:
                    family = font_file.stem
                    family = family.replace("-", " ").replace("_", " ")

                    if family and family not in seen_families:
                        seen_families.add(family)
                        fonts.append({
                            "family": family,
                            "style": "Regular",
                            "path": str(font_file)
                        })

    return sorted(fonts, key=lambda x: x["family"].lower())


def _get_fallback_fonts() -> List[dict]:
    """Return a curated list of popular Google Fonts as fallback"""
    return [
        {"family": "Roboto", "category": "sans-serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Open Sans", "category": "sans-serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Lato", "category": "sans-serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Montserrat", "category": "sans-serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Poppins", "category": "sans-serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Oswald", "category": "sans-serif", "variants": ["regular", "bold"], "subsets": ["latin"]},
        {"family": "Raleway", "category": "sans-serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Ubuntu", "category": "sans-serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Nunito", "category": "sans-serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Playfair Display", "category": "serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Merriweather", "category": "serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Lora", "category": "serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "PT Serif", "category": "serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Crimson Text", "category": "serif", "variants": ["regular", "bold", "italic"], "subsets": ["latin"]},
        {"family": "Source Code Pro", "category": "monospace", "variants": ["regular", "bold"], "subsets": ["latin"]},
        {"family": "Fira Code", "category": "monospace", "variants": ["regular", "bold"], "subsets": ["latin"]},
        {"family": "JetBrains Mono", "category": "monospace", "variants": ["regular", "bold"], "subsets": ["latin"]},
        {"family": "Roboto Mono", "category": "monospace", "variants": ["regular", "bold"], "subsets": ["latin"]},
        {"family": "Dancing Script", "category": "handwriting", "variants": ["regular", "bold"], "subsets": ["latin"]},
        {"family": "Pacifico", "category": "handwriting", "variants": ["regular"], "subsets": ["latin"]},
        {"family": "Caveat", "category": "handwriting", "variants": ["regular", "bold"], "subsets": ["latin"]},
        {"family": "Bebas Neue", "category": "display", "variants": ["regular"], "subsets": ["latin"]},
        {"family": "Lobster", "category": "display", "variants": ["regular"], "subsets": ["latin"]},
        {"family": "Anton", "category": "display", "variants": ["regular"], "subsets": ["latin"]},
        {"family": "Abril Fatface", "category": "display", "variants": ["regular"], "subsets": ["latin"]},
        {"family": "Righteous", "category": "display", "variants": ["regular"], "subsets": ["latin"]},
        {"family": "Bangers", "category": "display", "variants": ["regular"], "subsets": ["latin"]},
        {"family": "Permanent Marker", "category": "handwriting", "variants": ["regular"], "subsets": ["latin"]},
        {"family": "Satisfy", "category": "handwriting", "variants": ["regular"], "subsets": ["latin"]},
        {"family": "Great Vibes", "category": "handwriting", "variants": ["regular"], "subsets": ["latin"]},
    ]
