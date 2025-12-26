/**
 * Authentication Store for TermiVoxed
 *
 * Manages user authentication state using Zustand.
 * Integrates with Firebase Authentication for secure login/logout.
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { api } from '../api/client'
import { onAuthChange, logOut as firebaseLogOut, isFirebaseConfigured } from '../lib/firebase'

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
  basic_export: boolean
  subtitle_generation: boolean
  single_video_project: boolean
  basic_tts_voices: boolean
  multi_video_projects: boolean
  custom_fonts: boolean
  basic_bgm: boolean
  export_720p: boolean
  export_1080p: boolean
  advanced_tts_voices: boolean
  multiple_bgm_tracks: boolean
  export_4k: boolean
  batch_export: boolean
  custom_subtitle_styles: boolean
  cross_video_segments: boolean
  priority_support: boolean
  max_videos_per_project: number
  max_segments_per_video: number
  max_export_duration_minutes: number
  max_bgm_tracks: number
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

const defaultFeatures: SubscriptionFeatures = {
  basic_export: true,
  subtitle_generation: true,
  single_video_project: true,
  basic_tts_voices: true,
  multi_video_projects: false,
  custom_fonts: false,
  basic_bgm: false,
  export_720p: true,
  export_1080p: false,
  advanced_tts_voices: false,
  multiple_bgm_tracks: false,
  export_4k: false,
  batch_export: false,
  custom_subtitle_styles: false,
  cross_video_segments: false,
  priority_support: false,
  max_videos_per_project: 1,
  max_segments_per_video: 5,
  max_export_duration_minutes: 5,
  max_bgm_tracks: 0,
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

          setLoading(false)
          return true
        } catch (error) {
          console.error('Login error:', error)
          setError(error instanceof Error ? error.message : 'Login failed')
          setLoading(false)
          return false
        }
      },

      logout: async () => {
        const { setToken, setUser, setSubscription, setDevices, setLoading } = get()

        setLoading(true)

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

        // Clear local state
        setToken(null)
        setUser(null)
        setSubscription(null)
        setDevices([])
        setLoading(false)
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
          } catch (error) {
            console.error('Token validation failed:', error)
            // Clear invalid token
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
