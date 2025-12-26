"""Favorites API routes for storing user's favorite voices and fonts"""

import sys
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config import settings
from utils.logger import logger
from web_ui.api.schemas.favorites_schemas import (
    FavoritesResponse,
    FavoriteToggleRequest,
    FavoriteToggleResponse,
)
from web_ui.api.middleware.auth import AuthenticatedUser, get_current_user

router = APIRouter()

# Favorites directory (per-user storage)
FAVORITES_DIR = Path(settings.STORAGE_DIR) / "user_favorites"


def _get_user_favorites_file(user_id: str) -> Path:
    """Get favorites file path for a specific user"""
    FAVORITES_DIR.mkdir(parents=True, exist_ok=True)
    return FAVORITES_DIR / f"{user_id}.json"


def load_favorites(user_id: str) -> dict:
    """Load favorites from user-specific file"""
    try:
        favorites_file = _get_user_favorites_file(user_id)
        if favorites_file.exists():
            with open(favorites_file, 'r') as f:
                data = json.load(f)
                logger.debug(f"Loaded favorites for user {user_id}")
                return data
    except Exception as e:
        logger.error(f"Failed to load favorites for user {user_id}: {e}")

    # Return default empty structure
    return {
        "favorite_voices": [],
        "favorite_fonts": []
    }


def save_favorites(user_id: str, favorites: dict) -> bool:
    """Save favorites to user-specific file"""
    try:
        favorites_file = _get_user_favorites_file(user_id)
        favorites_file.parent.mkdir(parents=True, exist_ok=True)
        with open(favorites_file, 'w') as f:
            json.dump(favorites, f, indent=2)
        logger.info(f"Saved favorites for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save favorites for user {user_id}: {e}")
        return False


@router.get("", response_model=FavoritesResponse)
async def get_favorites(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Get all user favorites.

    Returns lists of favorite voice IDs and font family names.
    Requires authentication.
    """
    favorites = load_favorites(user.uid)
    return FavoritesResponse(
        favorite_voices=favorites.get("favorite_voices", []),
        favorite_fonts=favorites.get("favorite_fonts", [])
    )


@router.post("/toggle", response_model=FavoriteToggleResponse)
async def toggle_favorite(
    request: FavoriteToggleRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Toggle a favorite item (add if not favorite, remove if already favorite).

    - **item_id**: The voice ID or font family name
    - **item_type**: Either "voice" or "font"

    Requires authentication.
    """
    favorites = load_favorites(user.uid)

    # Determine which list to update
    if request.item_type == "voice":
        items_list = favorites.get("favorite_voices", [])
        list_key = "favorite_voices"
    else:
        items_list = favorites.get("favorite_fonts", [])
        list_key = "favorite_fonts"

    # Toggle the item
    if request.item_id in items_list:
        # Remove from favorites
        items_list.remove(request.item_id)
        is_favorite = False
        message = f"Removed {request.item_type} '{request.item_id}' from favorites"
    else:
        # Add to favorites
        items_list.append(request.item_id)
        is_favorite = True
        message = f"Added {request.item_type} '{request.item_id}' to favorites"

    # Update and save
    favorites[list_key] = items_list
    if not save_favorites(user.uid, favorites):
        raise HTTPException(status_code=500, detail="Failed to save favorites")

    logger.info(message)
    return FavoriteToggleResponse(
        success=True,
        is_favorite=is_favorite,
        item_id=request.item_id,
        item_type=request.item_type,
        message=message
    )


@router.post("/add", response_model=FavoriteToggleResponse)
async def add_favorite(
    request: FavoriteToggleRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Add an item to favorites (no-op if already favorite).

    - **item_id**: The voice ID or font family name
    - **item_type**: Either "voice" or "font"

    Requires authentication.
    """
    favorites = load_favorites(user.uid)

    if request.item_type == "voice":
        items_list = favorites.get("favorite_voices", [])
        list_key = "favorite_voices"
    else:
        items_list = favorites.get("favorite_fonts", [])
        list_key = "favorite_fonts"

    if request.item_id in items_list:
        return FavoriteToggleResponse(
            success=True,
            is_favorite=True,
            item_id=request.item_id,
            item_type=request.item_type,
            message=f"{request.item_type.capitalize()} '{request.item_id}' is already a favorite"
        )

    items_list.append(request.item_id)
    favorites[list_key] = items_list

    if not save_favorites(user.uid, favorites):
        raise HTTPException(status_code=500, detail="Failed to save favorites")

    return FavoriteToggleResponse(
        success=True,
        is_favorite=True,
        item_id=request.item_id,
        item_type=request.item_type,
        message=f"Added {request.item_type} '{request.item_id}' to favorites"
    )


@router.post("/remove", response_model=FavoriteToggleResponse)
async def remove_favorite(
    request: FavoriteToggleRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Remove an item from favorites (no-op if not a favorite).

    - **item_id**: The voice ID or font family name
    - **item_type**: Either "voice" or "font"

    Requires authentication.
    """
    favorites = load_favorites(user.uid)

    if request.item_type == "voice":
        items_list = favorites.get("favorite_voices", [])
        list_key = "favorite_voices"
    else:
        items_list = favorites.get("favorite_fonts", [])
        list_key = "favorite_fonts"

    if request.item_id not in items_list:
        return FavoriteToggleResponse(
            success=True,
            is_favorite=False,
            item_id=request.item_id,
            item_type=request.item_type,
            message=f"{request.item_type.capitalize()} '{request.item_id}' is not a favorite"
        )

    items_list.remove(request.item_id)
    favorites[list_key] = items_list

    if not save_favorites(user.uid, favorites):
        raise HTTPException(status_code=500, detail="Failed to save favorites")

    return FavoriteToggleResponse(
        success=True,
        is_favorite=False,
        item_id=request.item_id,
        item_type=request.item_id,
        message=f"Removed {request.item_type} '{request.item_id}' from favorites"
    )


@router.delete("")
async def clear_all_favorites(user: AuthenticatedUser = Depends(get_current_user)):
    """
    Clear all favorites (both voices and fonts).

    Requires authentication.
    """
    favorites = {
        "favorite_voices": [],
        "favorite_fonts": []
    }

    if not save_favorites(user.uid, favorites):
        raise HTTPException(status_code=500, detail="Failed to clear favorites")

    return {"success": True, "message": "All favorites cleared"}
