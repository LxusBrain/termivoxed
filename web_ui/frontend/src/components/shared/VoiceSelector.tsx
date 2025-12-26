/**
 * VoiceSelector - Shared component for selecting TTS voices with favorites support
 *
 * Fetches voices from the default TTS provider (e.g., Coqui for local, Edge TTS for cloud)
 */

import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Heart, PlayCircle, Loader2, StopCircle } from 'lucide-react'
import { ttsApi } from '../../api/client'
import { useFavoritesStore } from '../../stores/favoritesStore'
import { useConsentStore, useTTSConsentGate } from '../../stores/consentStore'
import { LANGUAGES } from '../../constants/languages'
import { formatVoiceName } from '../../utils/voice'
import { TTSConsentRequired } from '../TTSConsentModal'
import type { Voice } from '../../types'

// Providers that process locally and don't require consent
const LOCAL_PROVIDERS = ['coqui', 'piper']

interface VoiceSelectorProps {
  language: string
  voiceId: string
  onLanguageChange: (language: string) => void
  onVoiceChange: (voiceId: string) => void
  text?: string // For preview
  rate?: string
  volume?: string
  pitch?: string
  showLanguageSelector?: boolean
  showPreview?: boolean
  onPreview?: (audioUrl: string) => void
  isPreviewPlaying?: boolean
  onStopPreview?: () => void
  provider?: string // Optional: override default provider
}

export default function VoiceSelector({
  language,
  voiceId,
  onLanguageChange,
  onVoiceChange,
  text = '',
  rate = '+0%',
  volume = '+0%',
  pitch = '+0Hz',
  showLanguageSelector = true,
  showPreview = true,
  onPreview,
  isPreviewPlaying = false,
  onStopPreview,
  provider: propProvider,
}: VoiceSelectorProps) {
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)

  // Favorites store
  const { favoriteVoices, toggleFavoriteVoice, isFavoriteVoice, fetchFavorites, isInitialized } =
    useFavoritesStore()

  // TTS Consent
  const { checkConsent: checkTTSConsent, showConsentModal } = useTTSConsentGate()
  const { hasTTSConsent } = useConsentStore()

  // Fetch favorites on mount
  useEffect(() => {
    if (!isInitialized) {
      fetchFavorites()
    }
  }, [isInitialized, fetchFavorites])

  // Fetch default provider if not specified
  const { data: providersData } = useQuery({
    queryKey: ['tts-providers'],
    queryFn: () => ttsApi.getProviders(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Use prop provider or default provider from API
  const activeProvider = propProvider || providersData?.data?.default_provider || 'edge_tts'

  // Check if this provider requires consent (cloud providers)
  const requiresConsent = !LOCAL_PROVIDERS.includes(activeProvider?.toLowerCase() || '')
  const needsConsentGate = requiresConsent && !hasTTSConsent

  // Fetch provider-specific languages (only if consent granted for cloud providers)
  const { data: providerLanguagesData } = useQuery({
    queryKey: ['provider-languages', activeProvider],
    queryFn: () => ttsApi.getProviderLanguages(activeProvider),
    enabled: !!activeProvider && !needsConsentGate,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })

  // Use provider-specific languages if available, fallback to LANGUAGES constant
  const providerLanguages = providerLanguagesData?.data?.languages || []
  const availableLanguages = providerLanguages.length > 0 ? providerLanguages : LANGUAGES

  // Fetch voices for selected language from the active provider (only if consent granted for cloud providers)
  const { data: voicesData, isLoading: isLoadingVoices } = useQuery({
    queryKey: ['provider-voices', activeProvider, language],
    queryFn: () => ttsApi.getProviderVoices(activeProvider, language),
    enabled: !!language && !!activeProvider && !needsConsentGate,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Ensure voices is always an array - handle various API response shapes
  const voices: Voice[] = useMemo(() => {
    const data = voicesData?.data
    if (Array.isArray(data)) return data
    if (data && typeof data === 'object' && 'voices' in data && Array.isArray(data.voices)) {
      return data.voices
    }
    return []
  }, [voicesData])

  // Sort voices with favorites at the top
  const sortedVoices = useMemo(() => {
    const favorites = voices.filter((v) => favoriteVoices.includes(v.short_name))
    const nonFavorites = voices.filter((v) => !favoriteVoices.includes(v.short_name))
    return { favorites, nonFavorites, all: voices }
  }, [voices, favoriteVoices])

  // Get currently selected voice
  const selectedVoice = voices.find((v) => v.short_name === voiceId)

  // Handle voice preview
  const handlePreview = async () => {
    if (!voiceId || !text.trim() || isLoadingPreview) return

    // Check TTS consent before generating preview
    const hasConsent = await checkTTSConsent()
    if (!hasConsent) return

    setIsLoadingPreview(true)
    try {
      const previewText = text.slice(0, 100) // Limit to 100 chars
      const response = await ttsApi.preview(voiceId, previewText, rate, volume, pitch)
      if (response.data?.audio_url && onPreview) {
        onPreview(response.data.audio_url)
      }
    } catch (error) {
      console.error('Preview failed:', error)
    } finally {
      setIsLoadingPreview(false)
    }
  }

  // If cloud provider and no consent, show consent required message
  if (needsConsentGate) {
    return (
      <TTSConsentRequired onRequestConsent={showConsentModal} />
    )
  }

  return (
    <div className="space-y-3">
      {/* Language Selector */}
      {showLanguageSelector && (
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            Language
            {activeProvider === 'coqui' && (
              <span className="text-xs text-purple-400 ml-2">(16 languages)</span>
            )}
          </label>
          <select
            value={language}
            onChange={(e) => {
              onLanguageChange(e.target.value)
              onVoiceChange('') // Reset voice when language changes
            }}
            className="console-input w-full"
          >
            {availableLanguages.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Quick Favorites Picker - Only show favorites that exist in current provider's voices */}
      {sortedVoices.favorites.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1.5">
            <Heart className="w-3 h-3 inline mr-1 fill-red-500 text-red-500" />
            Quick Pick
          </label>
          <div className="flex flex-wrap gap-1.5">
            {sortedVoices.favorites.slice(0, 6).map((voice) => {
              const isSelected = voiceId === voice.short_name

              return (
                <button
                  key={voice.short_name}
                  onClick={() => onVoiceChange(voice.short_name)}
                  className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
                    isSelected
                      ? 'bg-accent-red border-accent-red text-white'
                      : 'bg-terminal-bg border-terminal-border text-text-secondary hover:border-accent-red/50 hover:text-text-primary'
                  }`}
                  title={`${voice.name} (${voice.gender})`}
                >
                  {formatVoiceName(voice.name)}
                </button>
              )
            })}
            {sortedVoices.favorites.length > 6 && (
              <span className="px-2 py-1 text-xs text-text-muted">
                +{sortedVoices.favorites.length - 6} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Voice Selector */}
      <div>
        <label className="block text-sm font-medium text-text-secondary mb-1">Voice</label>
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <select
              value={voiceId}
              onChange={(e) => onVoiceChange(e.target.value)}
              className="console-input w-full pr-10"
              disabled={isLoadingVoices}
            >
              <option value="">
                {isLoadingVoices ? 'Loading voices...' : 'Select a voice'}
              </option>

              {/* Favorites Section */}
              {sortedVoices.favorites.length > 0 && (
                <optgroup label="★ Favorites">
                  {sortedVoices.favorites.map((voice) => (
                    <option key={voice.short_name} value={voice.short_name}>
                      ♥ {formatVoiceName(voice.name)} ({voice.gender})
                    </option>
                  ))}
                </optgroup>
              )}

              {/* All Voices Section */}
              {sortedVoices.nonFavorites.length > 0 && (
                <optgroup label="All Voices">
                  {sortedVoices.nonFavorites.map((voice) => (
                    <option key={voice.short_name} value={voice.short_name}>
                      {formatVoiceName(voice.name)} ({voice.gender})
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>

          {/* Favorite Button */}
          {voiceId && (
            <button
              onClick={() => toggleFavoriteVoice(voiceId)}
              className="p-2 rounded-lg border border-terminal-border hover:bg-terminal-bg/50 transition-colors"
              title={isFavoriteVoice(voiceId) ? 'Remove from favorites' : 'Add to favorites'}
            >
              <Heart
                className={`w-5 h-5 ${
                  isFavoriteVoice(voiceId)
                    ? 'fill-red-500 text-red-500'
                    : 'text-text-muted hover:text-red-400'
                }`}
              />
            </button>
          )}

          {/* Preview Button */}
          {showPreview && (
            <button
              onClick={isPreviewPlaying ? onStopPreview : handlePreview}
              disabled={!voiceId || !text.trim() || isLoadingPreview}
              className="p-2 rounded-lg border border-terminal-border hover:bg-terminal-bg/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title={isPreviewPlaying ? 'Stop preview' : 'Preview voice'}
            >
              {isLoadingPreview ? (
                <Loader2 className="w-5 h-5 animate-spin text-accent-primary" />
              ) : isPreviewPlaying ? (
                <StopCircle className="w-5 h-5 text-red-500" />
              ) : (
                <PlayCircle className="w-5 h-5 text-accent-primary" />
              )}
            </button>
          )}
        </div>

        {/* Selected Voice Info */}
        {selectedVoice && (
          <p className="text-xs text-text-muted mt-1">
            {formatVoiceName(selectedVoice.name)} • {selectedVoice.gender} •{' '}
            {selectedVoice.locale}
          </p>
        )}
      </div>
    </div>
  )
}
