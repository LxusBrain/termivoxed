/**
 * Authentication Store for TermiVoxed
 *
 * Manages user authentication state using Zustand.
 * Integrates with Firebase Authentication for secure login/logout.
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { api } from '../api/client'
import { onAuthChange, logOut as firebaseLogOut, isFirebaseConfigured, getIdToken, onSubscriptionChange } from '../lib/firebase'
import type { Unsubscribe } from '../lib/firebase'
import { getApiErrorMessage } from '../utils/errorMessages'
import { useAppStore } from './appStore'
import { queryClient } from '../lib/queryClient'

// Store for subscription listener unsubscribe function
let subscriptionUnsubscribe: Unsubscribe | null = null

/**
 * Set up real-time subscription listener for a user
 * This ensures the UI updates when subscription changes (e.g., after payment)
 */
function setupSubscriptionListener(uid: string, setSubscription: (sub: Subscription | null) => void) {
  // Clean up existing listener first
  if (subscriptionUnsubscribe) {
    subscriptionUnsubscribe()
    subscriptionUnsubscribe = null
  }

  // Set up new listener
  if (isFirebaseConfigured()) {
    subscriptionUnsubscribe = onSubscriptionChange(uid, (subData) => {
      console.log('[AUTH] Subscription updated from Firestore:', subData.tier, subData.status)

      // Get current subscription to preserve features
      const currentSub = useAuthStore.getState().subscription

      setSubscription({
        tier: subData.tier as Subscription['tier'],
        status: subData.status as Subscription['status'],
        expiresAt: subData.expiresAt,
        // Preserve features from API response, or use defaults based on tier
        features: currentSub?.features || defaultFeatures,
      })
    })
  }
}

// ============================================================================
// Types
// ============================================================================

export interface User {
  uid: string
  email: string | null
  emailVerified: boolean
  displayName: string | null
  photoUrl: string | null
}

export interface SubscriptionFeatures {
  // Core features (all tiers)
  basic_export: boolean
  subtitle_generation: boolean
  single_video_project: boolean
  basic_tts_voices: boolean

  // Individual tier features
  multi_video_projects: boolean
  custom_fonts: boolean
  basic_bgm: boolean
  export_720p: boolean
  export_1080p: boolean

  // Pro tier features
  advanced_tts_voices: boolean
  multiple_bgm_tracks: boolean
  export_4k: boolean
  batch_export: boolean
  custom_subtitle_styles: boolean
  cross_video_segments: boolean
  priority_support: boolean
  voice_cloning: boolean
  api_access: boolean

  // Enterprise tier features
  custom_branding: boolean
  sso: boolean
  team_management: boolean

  // Project limits
  max_videos_per_project: number
  max_segments_per_video: number
  max_export_duration_minutes: number
  max_bgm_tracks: number

  // Usage limits per month (optional - may not always be returned)
  max_exports_per_month?: number
  max_tts_minutes_per_month?: number
  max_ai_requests_per_month?: number
  max_storage_mb?: number
  max_devices?: number
}

export interface Subscription {
  tier: 'free_trial' | 'individual' | 'basic' | 'pro' | 'enterprise' | 'lifetime' | 'expired'
  status: 'active' | 'trial' | 'expired' | 'cancelled' | 'past_due' | 'grace_period'
  expiresAt: string | null
  features: SubscriptionFeatures
}

export interface Device {
  deviceId: string
  deviceName: string
  deviceType: string
  osVersion: string | null
  isCurrent: boolean
  lastSeen: string
  registeredAt: string
}

export interface AuthState {
  // State
  user: User | null
  subscription: Subscription | null
  devices: Device[]
  token: string | null
  isLoading: boolean
  isInitialized: boolean
  error: string | null

  // Actions
  setToken: (token: string | null) => void
  setUser: (user: User | null) => void
  setSubscription: (subscription: Subscription | null) => void
  setDevices: (devices: Device[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  login: (idToken: string, deviceFingerprint?: string) => Promise<boolean>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
  checkAuthStatus: () => Promise<boolean>
  hasFeature: (feature: keyof SubscriptionFeatures) => boolean
  getFeatureLimit: (limitName: keyof SubscriptionFeatures) => number
  isSubscriptionActive: () => boolean
  removeDevice: (deviceId: string) => Promise<boolean>
  initialize: () => Promise<void>
}

// ============================================================================
// Default Features
// ============================================================================

// Default features for FREE_TRIAL tier (matches backend subscription/models.py)
// IMPORTANT: Keep in sync with FeatureAccess.free_trial_features() in backend
const defaultFeatures: SubscriptionFeatures = {
  // Core features
  basic_export: true,
  subtitle_generation: true,
  single_video_project: true,
  basic_tts_voices: true,

  // Individual tier features
  multi_video_projects: false,
  custom_fonts: false,
  basic_bgm: false,
  export_720p: true,
  export_1080p: true,  // Allow 1080p in trial to show value

  // Pro tier features
  advanced_tts_voices: true,  // Full TTS in trial to show value
  multiple_bgm_tracks: false,
  export_4k: false,
  batch_export: false,
  custom_subtitle_styles: false,
  cross_video_segments: false,
  priority_support: false,
  voice_cloning: false,
  api_access: false,

  // Enterprise tier features
  custom_branding: false,
  sso: false,
  team_management: false,

  // FREE_TRIAL limits (from backend models.py)
  max_videos_per_project: 3,
  max_segments_per_video: 10,
  max_export_duration_minutes: 10,
  max_bgm_tracks: 0,

  // Usage limits for trial
  max_exports_per_month: 5,
  max_tts_minutes_per_month: 10,
  max_ai_requests_per_month: 10,
  max_storage_mb: 500,
  max_devices: 1,
}

// ============================================================================
// Store
// ============================================================================

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      subscription: null,
      devices: [],
      token: null,
      isLoading: false,
      isInitialized: false,
      error: null,

      // Actions
      setToken: (token) => {
        set({ token })
        // Update axios default header
        if (token) {
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`
        } else {
          delete api.defaults.headers.common['Authorization']
        }
      },

      setUser: (user) => set({ user }),

      setSubscription: (subscription) => set({ subscription }),

      setDevices: (devices) => set({ devices }),

      setLoading: (isLoading) => set({ isLoading }),

      setError: (error) => set({ error }),

      login: async (idToken: string, deviceFingerprint?: string) => {
        const { setToken, setUser, setSubscription, setDevices, setLoading, setError } = get()

        setLoading(true)
        setError(null)

        try {
          const response = await api.post('/auth/login', {
            id_token: idToken,
            device_fingerprint: deviceFingerprint,
          })

          const data = response.data

          // Set token
          setToken(idToken)

          // Set user
          setUser({
            uid: data.uid,
            email: data.email,
            emailVerified: data.email_verified,
            displayName: data.display_name,
            photoUrl: data.photo_url,
          })

          // Set subscription
          setSubscription({
            tier: data.subscription_tier,
            status: data.subscription_status,
            expiresAt: data.subscription_expires_at,
            features: data.features || defaultFeatures,
          })

          // Set devices
          if (data.devices) {
            setDevices(
              data.devices.map((d: Record<string, unknown>) => ({
                deviceId: d.device_id as string,
                deviceName: d.device_name as string,
                deviceType: d.device_type as string,
                osVersion: d.os_version as string | null,
                isCurrent: d.is_current as boolean,
                lastSeen: d.last_seen as string,
                registeredAt: d.registered_at as string,
              }))
            )
          }

          // Set up real-time subscription listener for this user
          // This ensures the UI updates when subscription changes (e.g., after payment on lxusbrain-website)
          setupSubscriptionListener(data.uid, setSubscription)

          setLoading(false)
          return true
        } catch (error) {
          console.error('Login error:', error)
          setError(getApiErrorMessage(error))
          setLoading(false)
          return false
        }
      },

      logout: async () => {
        const { setToken, setUser, setSubscription, setDevices, setLoading } = get()

        setLoading(true)

        // Clean up subscription listener
        if (subscriptionUnsubscribe) {
          subscriptionUnsubscribe()
          subscriptionUnsubscribe = null
        }

        try {
          // Notify backend of logout
          await api.post('/auth/logout', {})
        } catch (error) {
          console.error('Backend logout error:', error)
          // Continue with local logout even if server request fails
        }

        try {
          // Sign out from Firebase
          if (isFirebaseConfigured()) {
            await firebaseLogOut()
          }
        } catch (error) {
          console.error('Firebase logout error:', error)
          // Continue with local logout even if Firebase request fails
        }

        // Clear local auth state
        setToken(null)
        setUser(null)
        setSubscription(null)
        setDevices([])
        setLoading(false)

        // CRITICAL: Clear app state to prevent cross-user data leakage
        // This must be done AFTER clearing auth state to ensure components
        // that depend on auth don't try to refetch with stale credentials
        useAppStore.getState().clearAllState()

        // Clear React Query cache to prevent stale data from previous user
        // This ensures no cached API responses leak between users
        queryClient.clear()

        console.log('[AUTH] Logout complete - cleared auth, app state, and query cache')
      },

      refreshUser: async () => {
        const { token, setUser, setSubscription, setDevices, setError } = get()

        if (!token) {
          return
        }

        try {
          const response = await api.get('/auth/me')
          const data = response.data

          setUser({
            uid: data.uid,
            email: data.email,
            emailVerified: data.email_verified,
            displayName: data.display_name,
            photoUrl: data.photo_url,
          })

          setSubscription({
            tier: data.subscription_tier,
            status: data.subscription_status,
            expiresAt: data.subscription_expires_at,
            features: data.features || defaultFeatures,
          })

          if (data.devices) {
            setDevices(
              data.devices.map((d: Record<string, unknown>) => ({
                deviceId: d.device_id as string,
                deviceName: d.device_name as string,
                deviceType: d.device_type as string,
                osVersion: d.os_version as string | null,
                isCurrent: d.is_current as boolean,
                lastSeen: d.last_seen as string,
                registeredAt: d.registered_at as string,
              }))
            )
          }
        } catch (error) {
          console.error('Refresh user error:', error)
          setError('Failed to refresh user data')
        }
      },

      checkAuthStatus: async () => {
        const { token, setLoading } = get()

        if (!token) {
          return false
        }

        setLoading(true)

        try {
          const response = await api.get('/auth/status')
          setLoading(false)
          return response.data.authenticated
        } catch (error) {
          console.error('Auth status check error:', error)
          setLoading(false)
          return false
        }
      },

      hasFeature: (feature: keyof SubscriptionFeatures) => {
        const { subscription } = get()

        if (!subscription || !subscription.features) {
          return defaultFeatures[feature] as boolean
        }

        return subscription.features[feature] as boolean
      },

      getFeatureLimit: (limitName: keyof SubscriptionFeatures) => {
        const { subscription } = get()

        if (!subscription || !subscription.features) {
          return defaultFeatures[limitName] as number
        }

        return subscription.features[limitName] as number
      },

      isSubscriptionActive: () => {
        const { subscription } = get()

        if (!subscription) {
          return false
        }

        const activeStatuses = ['active', 'trial']
        if (!activeStatuses.includes(subscription.status)) {
          return false
        }

        if (subscription.expiresAt) {
          const expiresAt = new Date(subscription.expiresAt)
          return new Date() < expiresAt
        }

        return true
      },

      removeDevice: async (deviceId: string) => {
        const { devices, setDevices, setError } = get()

        try {
          await api.delete(`/auth/devices/${deviceId}`)

          // Remove from local state
          setDevices(devices.filter((d) => d.deviceId !== deviceId))
          return true
        } catch (error) {
          console.error('Remove device error:', error)
          setError('Failed to remove device')
          return false
        }
      },

      initialize: async () => {
        const { token, setLoading, setToken, setUser, setSubscription, setDevices } = get()

        set({ isInitialized: false })
        setLoading(true)

        // Set up Firebase auth state listener for production mode
        if (isFirebaseConfigured()) {
          onAuthChange(async (firebaseUser) => {
            if (firebaseUser) {
              // User is signed in - get fresh token and sync with backend
              try {
                const newToken = await firebaseUser.getIdToken()
                if (newToken !== get().token) {
                  // Token changed (refreshed) - update the store
                  setToken(newToken)
                  api.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
                }
              } catch (error) {
                console.error('Token refresh error:', error)
              }
            } else {
              // User is signed out from Firebase - clear local state
              const currentUser = get().user
              if (currentUser) {
                setToken(null)
                setUser(null)
                setSubscription(null)
                setDevices([])
              }
            }
          })
        }

        // Restore token to axios headers and validate
        if (token) {
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`

          try {
            // Verify token is still valid
            const response = await api.get('/auth/me')
            const data = response.data

            setUser({
              uid: data.uid,
              email: data.email,
              emailVerified: data.email_verified,
              displayName: data.display_name,
              photoUrl: data.photo_url,
            })

            setSubscription({
              tier: data.subscription_tier,
              status: data.subscription_status,
              expiresAt: data.subscription_expires_at,
              features: data.features || defaultFeatures,
            })

            if (data.devices) {
              setDevices(
                data.devices.map((d: Record<string, unknown>) => ({
                  deviceId: d.device_id as string,
                  deviceName: d.device_name as string,
                  deviceType: d.device_type as string,
                  osVersion: d.os_version as string | null,
                  isCurrent: d.is_current as boolean,
                  lastSeen: d.last_seen as string,
                  registeredAt: d.registered_at as string,
                }))
              )
            }

            // Set up real-time subscription listener for this user
            setupSubscriptionListener(data.uid, setSubscription)
          } catch (error) {
            console.error('Token validation failed:', error)

            // Token might be expired - try to get a fresh one from Firebase
            if (isFirebaseConfigured()) {
              try {
                const freshToken = await getIdToken()
                if (freshToken) {
                  console.log('Got fresh token from Firebase, retrying validation...')
                  setToken(freshToken)
                  api.defaults.headers.common['Authorization'] = `Bearer ${freshToken}`

                  // Retry validation with fresh token
                  const retryResponse = await api.get('/auth/me')
                  const data = retryResponse.data

                  setUser({
                    uid: data.uid,
                    email: data.email,
                    emailVerified: data.email_verified,
                    displayName: data.display_name,
                    photoUrl: data.photo_url,
                  })

                  setSubscription({
                    tier: data.subscription_tier,
                    status: data.subscription_status,
                    expiresAt: data.subscription_expires_at,
                    features: data.features || defaultFeatures,
                  })

                  if (data.devices) {
                    setDevices(
                      data.devices.map((d: Record<string, unknown>) => ({
                        deviceId: d.device_id as string,
                        deviceName: d.device_name as string,
                        deviceType: d.device_type as string,
                        osVersion: d.os_version as string | null,
                        isCurrent: d.is_current as boolean,
                        lastSeen: d.last_seen as string,
                        registeredAt: d.registered_at as string,
                      }))
                    )
                  }

                  // Set up real-time subscription listener for this user
                  setupSubscriptionListener(data.uid, setSubscription)

                  // Successfully refreshed - skip the logout
                  setLoading(false)
                  set({ isInitialized: true })
                  return
                }
              } catch (refreshError) {
                console.error('Token refresh also failed:', refreshError)
              }
            }

            // Clear invalid token - refresh didn't work
            setToken(null)
            setUser(null)
            setSubscription(null)
            setDevices([])
          }
        }

        setLoading(false)
        set({ isInitialized: true })
      },
    }),
    {
      name: 'termivoxed-auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        token: state.token,
        // Don't persist user data - refresh on init
      }),
    }
  )
)

// ============================================================================
// Selectors (for convenience)
// ============================================================================

export const selectUser = (state: AuthState) => state.user
export const selectSubscription = (state: AuthState) => state.subscription
export const selectDevices = (state: AuthState) => state.devices
export const selectIsAuthenticated = (state: AuthState) => !!state.user && !!state.token
export const selectIsLoading = (state: AuthState) => state.isLoading
export const selectError = (state: AuthState) => state.error
