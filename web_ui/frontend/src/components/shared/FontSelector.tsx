/**
 * FontSelector - Shared component for selecting fonts with favorites support
 */

import { useState, useEffect, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Heart, Search, Check, ChevronDown } from 'lucide-react'
import { fontsApi } from '../../api/client'
import { useFavoritesStore } from '../../stores/favoritesStore'

interface GoogleFont {
  family: string
  category: string
  variants: string[]
  subsets: string[]
}

interface FontSelectorProps {
  selectedFont: string
  onFontChange: (font: string) => void
}

type FontCategory = 'all' | 'sans-serif' | 'serif' | 'display' | 'handwriting' | 'monospace' | 'local'

export default function FontSelector({
  selectedFont,
  onFontChange,
}: FontSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<FontCategory>('all')
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Favorites store
  const { favoriteFonts, toggleFavoriteFont, isFavoriteFont, fetchFavorites, isInitialized } =
    useFavoritesStore()

  // Fetch favorites on mount
  useEffect(() => {
    if (!isInitialized) {
      fetchFavorites()
    }
  }, [isInitialized, fetchFavorites])

  // Fetch Google fonts
  const { data: googleFontsData } = useQuery({
    queryKey: ['google-fonts'],
    queryFn: () => fontsApi.getGoogleFonts(),
    staleTime: 60 * 60 * 1000, // 1 hour
  })

  // Fetch local fonts
  const { data: localFontsData } = useQuery({
    queryKey: ['local-fonts'],
    queryFn: () => fontsApi.getLocalFonts(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  const googleFonts: GoogleFont[] = googleFontsData?.data?.fonts || []

  // Ensure localFonts is always an array of strings - handle various API response shapes
  const localFonts: string[] = useMemo(() => {
    const fonts = localFontsData?.data?.fonts
    if (!Array.isArray(fonts)) return []
    return fonts.map((f: unknown) => {
      if (typeof f === 'string') return f
      if (f && typeof f === 'object' && 'family' in f) return String((f as { family: string }).family)
      if (f && typeof f === 'object' && 'name' in f) return String((f as { name: string }).name)
      return String(f)
    }).filter(Boolean)
  }, [localFontsData])

  const localFontSet = useMemo(() => new Set(localFonts.map((f) => f.toLowerCase())), [localFonts])

  // Check if a font is installed locally
  const isLocalFont = (fontFamily: string): boolean => {
    return localFontSet.has(fontFamily.toLowerCase())
  }

  // Filter and sort fonts
  const filteredFonts = useMemo(() => {
    let fonts: { family: string; category: string; isLocal: boolean }[] = []

    if (category === 'local') {
      // Only local fonts
      fonts = localFonts.map((f) => ({ family: f, category: 'local', isLocal: true }))
    } else {
      // Google fonts with category filter
      fonts = googleFonts
        .filter((f) => category === 'all' || f.category === category)
        .map((f) => ({
          family: f.family,
          category: f.category,
          isLocal: isLocalFont(f.family),
        }))

      // Add local fonts that aren't in Google fonts
      if (category === 'all') {
        const googleFontSet = new Set(googleFonts.map((f) => f.family.toLowerCase()))
        localFonts.forEach((f) => {
          if (!googleFontSet.has(f.toLowerCase())) {
            fonts.push({ family: f, category: 'local', isLocal: true })
          }
        })
      }
    }

    // Apply search filter
    if (search.trim()) {
      const searchLower = search.toLowerCase()
      fonts = fonts.filter((f) => f.family.toLowerCase().includes(searchLower))
    }

    // Sort: favorites first, then alphabetically
    const favorites = fonts.filter((f) => favoriteFonts.includes(f.family))
    const nonFavorites = fonts.filter((f) => !favoriteFonts.includes(f.family))

    favorites.sort((a, b) => a.family.localeCompare(b.family))
    nonFavorites.sort((a, b) => a.family.localeCompare(b.family))

    return { favorites, nonFavorites, total: fonts.length }
  }, [googleFonts, localFonts, category, search, favoriteFonts, localFontSet])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Stats
  const localCount = localFonts.length
  const googleCount = googleFonts.length

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-text-secondary">Font</label>

      <div className="relative" ref={dropdownRef}>
        {/* Selected Font Display */}
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="console-input w-full text-left flex items-center justify-between"
        >
          <span className="flex items-center gap-2">
            {isFavoriteFont(selectedFont) && (
              <Heart className="w-4 h-4 fill-red-500 text-red-500" />
            )}
            <span style={{ fontFamily: `"${selectedFont}", sans-serif` }}>
              {selectedFont || 'Select a font'}
            </span>
            {selectedFont && isLocalFont(selectedFont) && (
              <Check className="w-4 h-4 text-green-400" />
            )}
          </span>
          <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {/* Dropdown */}
        {isOpen && (
          <div className="absolute z-50 w-full mt-1 bg-terminal-bg border border-terminal-border rounded-lg shadow-xl max-h-80 overflow-hidden">
            {/* Search */}
            <div className="p-2 border-b border-terminal-border">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="text"
                  placeholder="Search fonts..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="console-input w-full pl-9 py-1.5 text-sm"
                  autoFocus
                />
              </div>
            </div>

            {/* Category Filters */}
            <div className="p-2 border-b border-terminal-border flex gap-1 flex-wrap">
              {(['all', 'local', 'sans-serif', 'serif', 'display', 'handwriting', 'monospace'] as FontCategory[]).map(
                (cat) => (
                  <button
                    key={cat}
                    onClick={() => setCategory(cat)}
                    className={`px-2 py-0.5 text-xs rounded transition-colors ${
                      category === cat
                        ? 'bg-accent-primary text-white'
                        : 'bg-terminal-bg hover:bg-terminal-border text-text-muted'
                    }`}
                  >
                    {cat === 'all' ? 'All' : cat === 'local' ? `Local (${localCount})` : cat}
                  </button>
                )
              )}
            </div>

            {/* Font List */}
            <div className="overflow-y-auto max-h-48">
              {/* Favorites Section */}
              {filteredFonts.favorites.length > 0 && (
                <>
                  <div className="px-3 py-1 text-xs font-medium text-accent-primary bg-terminal-bg/50 sticky top-0">
                    ★ FAVORITES
                  </div>
                  {filteredFonts.favorites.map((font) => (
                    <FontItem
                      key={font.family}
                      font={font}
                      isSelected={selectedFont === font.family}
                      isFavorite={true}
                      onSelect={() => {
                        onFontChange(font.family)
                        setIsOpen(false)
                      }}
                      onToggleFavorite={() => toggleFavoriteFont(font.family)}
                    />
                  ))}
                </>
              )}

              {/* All Fonts Section */}
              {filteredFonts.nonFavorites.length > 0 && (
                <>
                  <div className="px-3 py-1 text-xs font-medium text-text-muted bg-terminal-bg/50 sticky top-0">
                    ALL FONTS ({filteredFonts.total})
                  </div>
                  {filteredFonts.nonFavorites.slice(0, 100).map((font) => (
                    <FontItem
                      key={font.family}
                      font={font}
                      isSelected={selectedFont === font.family}
                      isFavorite={false}
                      onSelect={() => {
                        onFontChange(font.family)
                        setIsOpen(false)
                      }}
                      onToggleFavorite={() => toggleFavoriteFont(font.family)}
                    />
                  ))}
                  {filteredFonts.nonFavorites.length > 100 && (
                    <div className="px-3 py-2 text-xs text-text-muted text-center">
                      Showing first 100 fonts. Use search to find more.
                    </div>
                  )}
                </>
              )}

              {filteredFonts.favorites.length === 0 && filteredFonts.nonFavorites.length === 0 && (
                <div className="px-3 py-4 text-sm text-text-muted text-center">
                  No fonts found
                </div>
              )}
            </div>

            {/* Stats */}
            <div className="px-3 py-2 text-xs text-text-muted border-t border-terminal-border">
              {localCount} installed • {googleCount} Google Fonts
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Font Item Component
interface FontItemProps {
  font: { family: string; category: string; isLocal: boolean }
  isSelected: boolean
  isFavorite: boolean
  onSelect: () => void
  onToggleFavorite: () => void
}

function FontItem({ font, isSelected, isFavorite, onSelect, onToggleFavorite }: FontItemProps) {
  return (
    <div
      className={`flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-terminal-border/50 ${
        isSelected ? 'bg-accent-primary/20' : ''
      }`}
    >
      <button
        onClick={onSelect}
        className="flex-1 text-left flex items-center gap-2"
        style={{ fontFamily: `"${font.family}", sans-serif` }}
      >
        <span className="truncate">{font.family}</span>
        {font.isLocal && <Check className="w-3 h-3 text-green-400 flex-shrink-0" />}
      </button>
      <button
        onClick={(e) => {
          e.stopPropagation()
          onToggleFavorite()
        }}
        className="p-1 hover:bg-terminal-bg rounded"
      >
        <Heart
          className={`w-4 h-4 ${
            isFavorite ? 'fill-red-500 text-red-500' : 'text-text-muted hover:text-red-400'
          }`}
        />
      </button>
    </div>
  )
}
