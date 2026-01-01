/**
 * Consent Store - Zustand store for privacy consent state management
 *
 * Manages:
 * - TTS consent status (required for voice generation)
 * - Consent modal visibility
 * - Consent API interactions
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../api/client';

// Types
export interface TTSConsentDialogContent {
  title: string;
  icon: string;
  introduction: string;
  details: {
    what_is_sent: {
      title: string;
      items: string[];
    };
    where_is_sent: {
      title: string;
      provider: string;
      privacy_policy: string;
      note: string;
    };
    recommendations: {
      title: string;
      items: string[];
    };
  };
  warning_banner: {
    icon: string;
    text: string;
    style: string;
  };
  buttons: {
    accept: { label: string; style: string };
    decline: { label: string; style: string };
    learn_more: { label: string; url: string; style: string };
  };
  remember_choice: {
    label: string;
    default: boolean;
  };
  footer_text: string;
}

export interface TTSWarningBanner {
  icon: string;
  title: string;
  message: string;
  link_text: string;
  link_action: string;
}

interface ConsentState {
  // TTS Consent state
  hasTTSConsent: boolean;
  needsTTSConsent: boolean;
  ttsConsentStatus: 'not_asked' | 'granted' | 'denied' | 'withdrawn';

  // TTS Provider preference (user's chosen default)
  preferredProvider: string | null;

  // UI state
  showTTSConsentModal: boolean;
  showTTSConsentDetails: boolean;
  isLoading: boolean;
  error: string | null;

  // Cached dialog content
  ttsDialogContent: TTSConsentDialogContent | null;
  ttsWarningBanner: TTSWarningBanner | null;

  // Actions
  checkTTSConsent: () => Promise<void>;
  recordTTSConsent: (granted: boolean) => Promise<boolean>;
  loadTTSDialogContent: () => Promise<void>;
  loadTTSWarningBanner: () => Promise<void>;

  // Provider preference
  setPreferredProvider: (provider: string) => void;
  getPreferredProvider: () => string | null;

  // Modal controls
  openTTSConsentModal: () => void;
  closeTTSConsentModal: () => void;
  openTTSConsentDetails: () => void;
  closeTTSConsentDetails: () => void;

  // Guard function - returns true if consent granted, shows modal if not
  requireTTSConsent: () => Promise<boolean>;

  // Check if consent is needed for a specific provider
  needsConsentForProvider: (provider: string) => boolean;
}

// Providers that don't require consent (local processing only)
const LOCAL_PROVIDERS = ['coqui', 'piper'];

export const useConsentStore = create<ConsentState>()(
  persist(
    (set, get) => ({
      // Initial state
      hasTTSConsent: false,
      needsTTSConsent: true,
      ttsConsentStatus: 'not_asked',
      preferredProvider: null,
      showTTSConsentModal: false,
      showTTSConsentDetails: false,
      isLoading: false,
      error: null,
      ttsDialogContent: null,
      ttsWarningBanner: null,

      // Check TTS consent status from backend
      checkTTSConsent: async () => {
        try {
          const response = await api.get('/consent/tts/status');
          const data = response.data;

          set({
            hasTTSConsent: data.has_consent,
            needsTTSConsent: data.needs_consent,
            ttsConsentStatus: data.status,
          });
        } catch (err) {
          console.error('Failed to check TTS consent:', err);
          // On error, assume consent is needed
          set({
            hasTTSConsent: false,
            needsTTSConsent: true,
          });
        }
      },

      // Record TTS consent decision
      recordTTSConsent: async (granted: boolean) => {
        set({ isLoading: true, error: null });

        try {
          await api.post('/consent/tts/record', {
            granted,
            remember_choice: true,
          });

          set({
            hasTTSConsent: granted,
            needsTTSConsent: false,
            ttsConsentStatus: granted ? 'granted' : 'denied',
            showTTSConsentModal: false,
            isLoading: false,
            error: null,
          });

          return granted;
        } catch (err) {
          console.error('Failed to record TTS consent:', err);
          const axiosError = err as { response?: { data?: { detail?: string } } };
          set({
            isLoading: false,
            error: axiosError?.response?.data?.detail || 'Network error. Please try again.',
          });
          return false;
        }
      },

      // Load TTS dialog content from backend
      loadTTSDialogContent: async () => {
        try {
          const response = await api.get('/consent/tts/dialog-content');
          set({ ttsDialogContent: response.data });
        } catch (err) {
          console.error('Failed to load TTS dialog content:', err);
        }
      },

      // Load TTS warning banner content from backend
      loadTTSWarningBanner: async () => {
        try {
          const response = await api.get('/consent/tts/warning-banner');
          set({ ttsWarningBanner: response.data });
        } catch (err) {
          console.error('Failed to load TTS warning banner:', err);
        }
      },

      // Modal controls
      openTTSConsentModal: () => {
        const { loadTTSDialogContent, ttsDialogContent } = get();
        if (!ttsDialogContent) {
          loadTTSDialogContent();
        }
        set({ showTTSConsentModal: true });
      },

      closeTTSConsentModal: () => {
        set({ showTTSConsentModal: false });
      },

      openTTSConsentDetails: () => {
        set({ showTTSConsentDetails: true });
      },

      closeTTSConsentDetails: () => {
        set({ showTTSConsentDetails: false });
      },

      // Provider preference management
      setPreferredProvider: (provider: string) => {
        set({ preferredProvider: provider });
      },

      getPreferredProvider: () => {
        return get().preferredProvider;
      },

      // Check if consent is needed for a specific provider
      needsConsentForProvider: (provider: string) => {
        // Local providers don't need consent
        if (LOCAL_PROVIDERS.includes(provider.toLowerCase())) {
          return false;
        }
        // Cloud providers need consent
        return !get().hasTTSConsent;
      },

      // Guard function - use this before any TTS operation
      requireTTSConsent: async () => {
        const { checkTTSConsent, openTTSConsentModal } = get();

        // First, refresh status from backend
        await checkTTSConsent();

        // Re-check after refresh
        const currentState = get();

        if (currentState.hasTTSConsent) {
          return true;
        }

        if (currentState.needsTTSConsent) {
          // Show consent modal
          openTTSConsentModal();
          return false;
        }

        // Consent was denied - don't show modal again, just return false
        return false;
      },
    }),
    {
      name: 'termivoxed-consent',
      partialize: (state) => ({
        hasTTSConsent: state.hasTTSConsent,
        needsTTSConsent: state.needsTTSConsent,
        ttsConsentStatus: state.ttsConsentStatus,
        preferredProvider: state.preferredProvider,
      }),
    }
  )
);

// Utility hook for TTS consent gate
export const useTTSConsentGate = () => {
  const {
    hasTTSConsent,
    needsTTSConsent,
    ttsConsentStatus,
    requireTTSConsent,
    openTTSConsentModal,
  } = useConsentStore();

  const checkConsent = async (): Promise<boolean> => {
    return await requireTTSConsent();
  };

  const showConsentModal = () => {
    openTTSConsentModal();
  };

  return {
    hasConsent: hasTTSConsent,
    needsConsent: needsTTSConsent,
    status: ttsConsentStatus,
    checkConsent,
    showConsentModal,
  };
};
