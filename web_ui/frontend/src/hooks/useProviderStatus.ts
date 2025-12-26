/**
 * useProviderStatus - Shared hook for TTS and LLM provider status
 *
 * Provides unified state for:
 * - TTS provider status (local vs cloud, connectivity)
 * - LLM provider status (selected provider, connectivity)
 *
 * Used by Layout.tsx, ProjectPage.tsx, and other components that need
 * to display or check provider status.
 */

import { useQuery } from '@tanstack/react-query'
import { ttsApi, llmApi, settingsApi, TTSProviderInfo } from '../api/client'
import { LLMHealthStatus, LLMSettings } from '../types'

// Provider display names
const LLM_PROVIDER_NAMES: Record<string, string> = {
  ollama: 'Ollama',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google AI',
  azure_openai: 'Azure OpenAI',
  aws_bedrock: 'AWS Bedrock',
  huggingface: 'HuggingFace',
  custom: 'Custom LLM',
}

export interface TTSProviderStatus {
  /** Current default TTS provider name */
  provider: string
  /** Display name for the provider */
  displayName: string
  /** Whether the provider is local (no cloud connectivity needed) */
  isLocal: boolean
  /** Whether the provider is available/connected */
  isConnected: boolean
  /** Whether we're still checking status */
  isChecking: boolean
  /** All available providers */
  providers: TTSProviderInfo[]
}

export interface LLMProviderStatus {
  /** Current selected LLM provider */
  provider: string
  /** Display name for the provider */
  displayName: string
  /** Whether the provider is available/connected */
  isConnected: boolean
  /** Whether we're still checking status */
  isChecking: boolean
  /** Full health status from API */
  health: LLMHealthStatus | null
}

export interface ProviderStatusResult {
  tts: TTSProviderStatus
  llm: LLMProviderStatus
  /** Refetch all provider statuses */
  refetch: () => void
}

/**
 * Hook to get unified provider status for TTS and LLM
 *
 * @param refetchInterval - How often to refetch status (default 30000ms)
 */
export function useProviderStatus(refetchInterval = 30000): ProviderStatusResult {
  // Fetch TTS providers
  const {
    data: ttsProviders,
    isLoading: ttsProvidersLoading,
    refetch: refetchTtsProviders
  } = useQuery({
    queryKey: ['tts-providers'],
    queryFn: () => ttsApi.getProviders(),
    refetchInterval,
    staleTime: 10000,
  })

  // Fetch TTS connectivity (for cloud providers)
  const {
    data: ttsConnectivity,
    isLoading: ttsConnectivityLoading,
    refetch: refetchTtsConnectivity
  } = useQuery({
    queryKey: ['tts-connectivity'],
    queryFn: () => ttsApi.checkConnectivity(),
    refetchInterval,
    staleTime: 10000,
  })

  // Fetch LLM settings
  const {
    data: llmSettings,
    isLoading: llmSettingsLoading,
    refetch: refetchLlmSettings
  } = useQuery({
    queryKey: ['llm-settings'],
    queryFn: () => settingsApi.getLLM(),
    refetchInterval,
    staleTime: 10000,
  })

  // Fetch LLM health
  const {
    data: llmHealth,
    isLoading: llmHealthLoading,
    refetch: refetchLlmHealth
  } = useQuery({
    queryKey: ['llm-health'],
    queryFn: () => llmApi.checkHealth(),
    refetchInterval,
    staleTime: 10000,
  })

  // Parse TTS provider status
  const ttsProvidersData = ttsProviders?.data
  const defaultTtsProvider = ttsProvidersData?.default_provider || 'edge'
  const currentTtsProvider = ttsProvidersData?.providers?.find(
    (p: TTSProviderInfo) => p.name === defaultTtsProvider
  )
  const isTtsLocal = currentTtsProvider?.is_local ?? false

  // For local providers, they're always "connected" if available
  // For cloud providers, check connectivity
  const ttsConnected = isTtsLocal
    ? (currentTtsProvider?.available ?? false)
    : (ttsConnectivity?.data?.direct_connection || ttsConnectivity?.data?.proxy_connection || false)

  // Parse LLM provider status
  const llmSettingsData = llmSettings?.data as LLMSettings | undefined
  const llmHealthData = llmHealth?.data as LLMHealthStatus | undefined
  const selectedLlmProvider = llmSettingsData?.default_provider || 'ollama'

  // Check if selected LLM provider is connected/configured
  const getLlmConnected = (): boolean => {
    if (!llmHealthData) return false

    switch (selectedLlmProvider) {
      case 'ollama':
        return llmHealthData.ollama_available
      case 'openai':
        return llmHealthData.openai_configured
      case 'anthropic':
        return llmHealthData.anthropic_configured
      case 'google':
        return llmHealthData.google_configured
      case 'azure_openai':
        return llmHealthData.azure_openai_configured
      case 'aws_bedrock':
        return llmHealthData.aws_bedrock_configured
      case 'huggingface':
        return llmHealthData.huggingface_configured
      case 'custom':
        // Custom endpoint - assume configured if we have settings
        return true
      default:
        return false
    }
  }

  // Get display name for TTS provider
  const getTtsDisplayName = (): string => {
    if (currentTtsProvider?.display_name) {
      return currentTtsProvider.display_name
    }
    // Fallback display names
    const names: Record<string, string> = {
      edge: 'Edge TTS',
      coqui: 'Coqui TTS',
      piper: 'Piper TTS',
    }
    return names[defaultTtsProvider] || defaultTtsProvider
  }

  const refetch = () => {
    refetchTtsProviders()
    refetchTtsConnectivity()
    refetchLlmSettings()
    refetchLlmHealth()
  }

  return {
    tts: {
      provider: defaultTtsProvider,
      displayName: getTtsDisplayName(),
      isLocal: isTtsLocal,
      isConnected: ttsConnected,
      isChecking: ttsProvidersLoading || (!isTtsLocal && ttsConnectivityLoading),
      providers: ttsProvidersData?.providers || [],
    },
    llm: {
      provider: selectedLlmProvider,
      displayName: LLM_PROVIDER_NAMES[selectedLlmProvider] || selectedLlmProvider,
      isConnected: getLlmConnected(),
      isChecking: llmSettingsLoading || llmHealthLoading,
      health: llmHealthData || null,
    },
    refetch,
  }
}

/**
 * Check if a TTS provider is local (doesn't need cloud connectivity)
 */
export function isLocalTtsProvider(provider: string): boolean {
  const localProviders = ['coqui', 'piper']
  return localProviders.includes(provider.toLowerCase())
}

/**
 * Get display name for an LLM provider
 */
export function getLlmProviderDisplayName(provider: string): string {
  return LLM_PROVIDER_NAMES[provider] || provider
}
