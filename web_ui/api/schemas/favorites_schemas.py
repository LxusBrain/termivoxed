"""Favorites API schemas for storing user's favorite voices and fonts"""

from typing import List, Literal
from pydantic import BaseModel


class FavoritesResponse(BaseModel):
    """Response containing all user favorites"""
    favorite_voices: List[str]  # List of voice IDs (e.g., "en-US-AriaNeural")
    favorite_fonts: List[str]   # List of font family names (e.g., "Roboto")


class FavoriteToggleRequest(BaseModel):
    """Request to toggle a favorite item"""
    item_id: str  # Voice ID or font family name
    item_type: Literal["voice", "font"]


class FavoriteToggleResponse(BaseModel):
    """Response after toggling a favorite"""
    success: bool
    is_favorite: bool  # True if item is now a favorite, False if removed
    item_id: str
    item_type: Literal["voice", "font"]
    message: str


class FavoriteAddRequest(BaseModel):
    """Request to add a favorite"""
    item_id: str
    item_type: Literal["voice", "font"]


class FavoriteRemoveRequest(BaseModel):
    """Request to remove a favorite"""
    item_id: str
    item_type: Literal["voice", "font"]
