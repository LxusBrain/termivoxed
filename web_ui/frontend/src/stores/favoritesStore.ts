/**
 * Favorites Store - Zustand store for managing user's favorite voices and fonts
 *
 * Manages:
 * - Favorite voices (TTS voice IDs)
 * - Favorite fonts (font family names)
 * - Syncs with backend API for cross-device persistence
 */

import { create } from 'zustand'
import { favoritesApi } from '../api/client'

interface FavoritesState {
  // Data
  favoriteVoices: string[]
  favoriteFonts: string[]

  // Loading states
  isLoading: boolean
  isInitialized: boolean
  error: string | null

  // Actions
  fetchFavorites: () => Promise<void>
  toggleFavoriteVoice: (voiceId: string) => Promise<void>
  toggleFavoriteFont: (fontFamily: string) => Promise<void>
  addFavoriteVoice: (voiceId: string) => Promise<void>
  addFavoriteFont: (fontFamily: string) => Promise<void>
  removeFavoriteVoice: (voiceId: string) => Promise<void>
  removeFavoriteFont: (fontFamily: string) => Promise<void>

  // Helpers
  isFavoriteVoice: (voiceId: string) => boolean
  isFavoriteFont: (fontFamily: string) => boolean
}

export const useFavoritesStore = create<FavoritesState>()((set, get) => ({
  // Initial state
  favoriteVoices: [],
  favoriteFonts: [],
  isLoading: false,
  isInitialized: false,
  error: null,

  // Fetch all favorites from backend
  fetchFavorites: async () => {
    // Don't fetch if already loading
    if (get().isLoading) return

    set({ isLoading: true, error: null })

    try {
      const response = await favoritesApi.get()
      set({
        favoriteVoices: response.data.favorite_voices || [],
        favoriteFonts: response.data.favorite_fonts || [],
        isLoading: false,
        isInitialized: true,
      })
    } catch (err) {
      console.error('Failed to fetch favorites:', err)
      set({
        isLoading: false,
        isInitialized: true,
        error: 'Failed to load favorites',
      })
    }
  },

  // Toggle a voice favorite (add if not favorite, remove if favorite)
  toggleFavoriteVoice: async (voiceId: string) => {
    // Optimistic update
    const currentFavorites = get().favoriteVoices
    const isFavorite = currentFavorites.includes(voiceId)
    const newFavorites = isFavorite
      ? currentFavorites.filter((v) => v !== voiceId)
      : [...currentFavorites, voiceId]

    set({ favoriteVoices: newFavorites })

    try {
      await favoritesApi.toggle(voiceId, 'voice')
    } catch (err) {
      // Revert on error
      console.error('Failed to toggle voice favorite:', err)
      set({ favoriteVoices: currentFavorites })
    }
  },

  // Toggle a font favorite
  toggleFavoriteFont: async (fontFamily: string) => {
    // Optimistic update
    const currentFavorites = get().favoriteFonts
    const isFavorite = currentFavorites.includes(fontFamily)
    const newFavorites = isFavorite
      ? currentFavorites.filter((f) => f !== fontFamily)
      : [...currentFavorites, fontFamily]

    set({ favoriteFonts: newFavorites })

    try {
      await favoritesApi.toggle(fontFamily, 'font')
    } catch (err) {
      // Revert on error
      console.error('Failed to toggle font favorite:', err)
      set({ favoriteFonts: currentFavorites })
    }
  },

  // Add a voice to favorites
  addFavoriteVoice: async (voiceId: string) => {
    const currentFavorites = get().favoriteVoices
    if (currentFavorites.includes(voiceId)) return

    // Optimistic update
    set({ favoriteVoices: [...currentFavorites, voiceId] })

    try {
      await favoritesApi.add(voiceId, 'voice')
    } catch (err) {
      // Revert on error
      console.error('Failed to add voice favorite:', err)
      set({ favoriteVoices: currentFavorites })
    }
  },

  // Add a font to favorites
  addFavoriteFont: async (fontFamily: string) => {
    const currentFavorites = get().favoriteFonts
    if (currentFavorites.includes(fontFamily)) return

    // Optimistic update
    set({ favoriteFonts: [...currentFavorites, fontFamily] })

    try {
      await favoritesApi.add(fontFamily, 'font')
    } catch (err) {
      // Revert on error
      console.error('Failed to add font favorite:', err)
      set({ favoriteFonts: currentFavorites })
    }
  },

  // Remove a voice from favorites
  removeFavoriteVoice: async (voiceId: string) => {
    const currentFavorites = get().favoriteVoices
    if (!currentFavorites.includes(voiceId)) return

    // Optimistic update
    set({ favoriteVoices: currentFavorites.filter((v) => v !== voiceId) })

    try {
      await favoritesApi.remove(voiceId, 'voice')
    } catch (err) {
      // Revert on error
      console.error('Failed to remove voice favorite:', err)
      set({ favoriteVoices: currentFavorites })
    }
  },

  // Remove a font from favorites
  removeFavoriteFont: async (fontFamily: string) => {
    const currentFavorites = get().favoriteFonts
    if (!currentFavorites.includes(fontFamily)) return

    // Optimistic update
    set({ favoriteFonts: currentFavorites.filter((f) => f !== fontFamily) })

    try {
      await favoritesApi.remove(fontFamily, 'font')
    } catch (err) {
      // Revert on error
      console.error('Failed to remove font favorite:', err)
      set({ favoriteFonts: currentFavorites })
    }
  },

  // Check if a voice is favorited
  isFavoriteVoice: (voiceId: string) => {
    return get().favoriteVoices.includes(voiceId)
  },

  // Check if a font is favorited
  isFavoriteFont: (fontFamily: string) => {
    return get().favoriteFonts.includes(fontFamily)
  },
}))

// Hook to initialize favorites on app load
export const useInitializeFavorites = () => {
  const { fetchFavorites, isInitialized } = useFavoritesStore()

  // Fetch favorites if not initialized
  if (!isInitialized) {
    fetchFavorites()
  }
}
