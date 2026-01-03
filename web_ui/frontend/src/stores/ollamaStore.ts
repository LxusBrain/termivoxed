/**
 * Ollama Store - Zustand store for Ollama setup state management
 *
 * Manages:
 * - Ollama installation/running status
 * - Model management (installed, downloading)
 * - User consent for local AI processing
 * - Setup wizard flow
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../api/client';

// Types
export interface OllamaStatus {
  installed: boolean;
  running: boolean;
  version: string | null;
  models: string[];
  endpoint: string;
  install_path: string | null;
  error: string | null;
}

export interface OllamaConsent {
  consented: boolean;
  consent_date: string | null;
  consent_version: string;
  acknowledged_items: string[];
}

export interface RecommendedModel {
  name: string;
  description: string;
  size: string;
  vram: string;
  use_case: string;
}

export interface InstallInstructions {
  platform: string;
  method: string;
  download_url: string;
  steps: string[];
  command: string | null;
  post_install: string;
}

export interface ModelDownloadProgress {
  status: string;
  digest?: string;
  total?: number;
  completed?: number;
  error?: string;
  model?: string;
}

interface OllamaState {
  // Status
  status: OllamaStatus | null;
  consent: OllamaConsent | null;
  installInstructions: InstallInstructions | null;
  recommendedModels: {
    text: RecommendedModel[];
    vision: RecommendedModel[];
  } | null;

  // UI state
  showSetupWizard: boolean;
  wizardStep: 'check' | 'install' | 'consent' | 'models' | 'complete';
  isLoading: boolean;
  error: string | null;

  // Model download state
  downloadingModel: string | null;
  downloadProgress: ModelDownloadProgress | null;

  // First run check
  firstRunData: {
    needs_setup: boolean;
    needs_ollama_install: boolean;
    needs_ollama_start: boolean;
    needs_consent: boolean;
    needs_models: boolean;
    installed_models: string[];
    recommended_action: string;
    message: string;
  } | null;

  // Actions
  checkStatus: () => Promise<void>;
  checkFirstRun: () => Promise<void>;
  loadInstallInstructions: () => Promise<void>;
  loadRecommendedModels: () => Promise<void>;
  grantConsent: (acknowledgedItems: string[]) => Promise<boolean>;
  revokeConsent: () => Promise<boolean>;
  pullModel: (modelName: string) => Promise<boolean>;
  deleteModel: (modelName: string) => Promise<boolean>;
  openDownloadPage: () => Promise<boolean>;

  // Wizard controls
  openSetupWizard: () => void;
  closeSetupWizard: () => void;
  setWizardStep: (step: OllamaState['wizardStep']) => void;
  nextWizardStep: () => void;

  // Guard function - returns true if Ollama ready, shows wizard if not
  requireOllama: () => Promise<boolean>;
}

export const useOllamaStore = create<OllamaState>()(
  persist(
    (set, get) => ({
      // Initial state
      status: null,
      consent: null,
      installInstructions: null,
      recommendedModels: null,
      showSetupWizard: false,
      wizardStep: 'check',
      isLoading: false,
      error: null,
      downloadingModel: null,
      downloadProgress: null,
      firstRunData: null,

      // Check Ollama status
      checkStatus: async () => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.get('/ollama/status');
          set({ status: response.data, isLoading: false });
        } catch (err) {
          console.error('Failed to check Ollama status:', err);
          set({
            status: {
              installed: false,
              running: false,
              version: null,
              models: [],
              endpoint: 'http://localhost:11434',
              install_path: null,
              error: 'Failed to check status',
            },
            isLoading: false,
          });
        }
      },

      // First run check
      checkFirstRun: async () => {
        try {
          const response = await api.get('/ollama/first-run-check');
          set({ firstRunData: response.data });

          // Determine if we need to show setup wizard
          const data = response.data;
          if (data.needs_setup) {
            // Determine starting step
            let step: OllamaState['wizardStep'] = 'check';
            if (data.needs_ollama_install) {
              step = 'install';
            } else if (data.needs_ollama_start) {
              step = 'install';
            } else if (data.needs_consent) {
              step = 'consent';
            } else if (data.needs_models) {
              step = 'models';
            }
            set({ wizardStep: step });
          }
        } catch (err) {
          console.error('Failed to check first run:', err);
        }
      },

      // Load installation instructions
      loadInstallInstructions: async () => {
        try {
          const response = await api.get('/ollama/install-instructions');
          set({ installInstructions: response.data });
        } catch (err) {
          console.error('Failed to load install instructions:', err);
        }
      },

      // Load recommended models
      loadRecommendedModels: async () => {
        try {
          const response = await api.get('/ollama/recommended-models');
          set({ recommendedModels: response.data });
        } catch (err) {
          console.error('Failed to load recommended models:', err);
        }
      },

      // Grant consent
      grantConsent: async (acknowledgedItems: string[]) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.post('/ollama/consent/grant', {
            acknowledged_items: acknowledgedItems,
          });
          set({
            consent: response.data,
            isLoading: false,
          });
          return true;
        } catch (err) {
          console.error('Failed to grant consent:', err);
          const axiosError = err as { response?: { data?: { detail?: string } } };
          set({
            isLoading: false,
            error: axiosError?.response?.data?.detail || 'Failed to grant consent',
          });
          return false;
        }
      },

      // Revoke consent
      revokeConsent: async () => {
        set({ isLoading: true, error: null });
        try {
          await api.post('/ollama/consent/revoke');
          set({
            consent: {
              consented: false,
              consent_date: null,
              consent_version: '1.0',
              acknowledged_items: [],
            },
            isLoading: false,
          });
          return true;
        } catch (err) {
          console.error('Failed to revoke consent:', err);
          set({ isLoading: false });
          return false;
        }
      },

      // Pull model with SSE progress
      pullModel: async (modelName: string) => {
        set({ downloadingModel: modelName, downloadProgress: null, error: null });

        try {
          // Build headers for fetch
          const headers: Record<string, string> = {
            'Content-Type': 'application/json',
          };
          // Add auth token if available
          const authHeader = api.defaults.headers.common?.['Authorization'];
          if (authHeader && typeof authHeader === 'string') {
            headers['Authorization'] = authHeader;
          }

          const response = await fetch(`${api.defaults.baseURL}/ollama/pull-model`, {
            method: 'POST',
            headers,
            body: JSON.stringify({ model_name: modelName }),
          });

          if (!response.ok) {
            throw new Error(`Failed to start download: ${response.status}`);
          }

          const reader = response.body?.getReader();
          const decoder = new TextDecoder();

          if (!reader) {
            throw new Error('No response body');
          }

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value);
            const lines = text.split('\n');

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  set({ downloadProgress: data });

                  if (data.status === 'success') {
                    // Refresh status to get updated models list
                    await get().checkStatus();
                    set({ downloadingModel: null, downloadProgress: null });
                    return true;
                  }

                  if (data.status === 'error') {
                    set({
                      error: data.error,
                      downloadingModel: null,
                      downloadProgress: null,
                    });
                    return false;
                  }
                } catch (e) {
                  // Ignore JSON parse errors
                }
              }
            }
          }

          set({ downloadingModel: null, downloadProgress: null });
          return true;
        } catch (err) {
          console.error('Failed to pull model:', err);
          const errorMessage = err instanceof Error ? err.message : 'Failed to download model';
          set({
            error: errorMessage,
            downloadingModel: null,
            downloadProgress: null,
          });
          return false;
        }
      },

      // Delete model
      deleteModel: async (modelName: string) => {
        set({ isLoading: true, error: null });
        try {
          await api.delete(`/ollama/delete-model/${encodeURIComponent(modelName)}`);
          await get().checkStatus(); // Refresh status
          set({ isLoading: false });
          return true;
        } catch (err) {
          console.error('Failed to delete model:', err);
          set({ isLoading: false });
          return false;
        }
      },

      // Open download page
      openDownloadPage: async () => {
        try {
          await api.post('/ollama/open-download-page');
          return true;
        } catch (err) {
          // Fallback to opening in browser directly
          window.open('https://ollama.com/download', '_blank');
          return true;
        }
      },

      // Wizard controls
      openSetupWizard: () => {
        const { loadInstallInstructions, loadRecommendedModels, checkStatus } = get();
        loadInstallInstructions();
        loadRecommendedModels();
        checkStatus();
        set({ showSetupWizard: true });
      },

      closeSetupWizard: () => {
        set({ showSetupWizard: false });
      },

      setWizardStep: (step) => {
        set({ wizardStep: step });
      },

      nextWizardStep: () => {
        const { wizardStep } = get();
        const steps: OllamaState['wizardStep'][] = ['check', 'install', 'consent', 'models', 'complete'];
        const currentIndex = steps.indexOf(wizardStep);
        if (currentIndex < steps.length - 1) {
          set({ wizardStep: steps[currentIndex + 1] });
        }
      },

      // Guard function
      requireOllama: async () => {
        const { checkFirstRun, openSetupWizard } = get();

        await checkFirstRun();

        const currentState = get();

        if (currentState.firstRunData && !currentState.firstRunData.needs_setup) {
          return true;
        }

        // Show setup wizard
        openSetupWizard();
        return false;
      },
    }),
    {
      name: 'termivoxed-ollama',
      partialize: (state) => ({
        consent: state.consent,
      }),
    }
  )
);
