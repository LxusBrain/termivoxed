/**
 * Firebase Configuration for TermiVoxed
 *
 * This file initializes Firebase Auth for the frontend application.
 * Configure your Firebase project credentials in the environment variables.
 */

import { initializeApp, getApps } from 'firebase/app'
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  OAuthProvider,
  sendPasswordResetEmail,
  signOut,
  onAuthStateChanged,
  User,
  UserCredential,
} from 'firebase/auth'
import {
  getFirestore,
  doc,
  onSnapshot,
  Unsubscribe,
} from 'firebase/firestore'

// Firebase configuration from environment variables
// These should be set in .env.local for development
// and in environment configuration for production
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'termivoxed',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
}

// Check if Firebase is configured
export const isFirebaseConfigured = (): boolean => {
  return !!(firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId)
}

// Initialize Firebase only if configured and not already initialized
let app: ReturnType<typeof initializeApp> | null = null
let auth: ReturnType<typeof getAuth> | null = null
let db: ReturnType<typeof getFirestore> | null = null

if (isFirebaseConfigured()) {
  app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0]
  auth = getAuth(app)
  db = getFirestore(app)
} else {
  console.warn(
    'Firebase is not configured. Please create a .env.local file in web_ui/frontend/ with:\n' +
    '  VITE_FIREBASE_API_KEY=your-api-key\n' +
    '  VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com\n' +
    '  VITE_FIREBASE_PROJECT_ID=your-project-id\n' +
    '  VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com\n' +
    '  VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id\n' +
    '  VITE_FIREBASE_APP_ID=your-app-id'
  )
}

// Export auth (may be null if not configured)
export { auth }

// Auth providers
const googleProvider = new GoogleAuthProvider()
const microsoftProvider = new OAuthProvider('microsoft.com')

// Configure Google provider
googleProvider.addScope('email')
googleProvider.addScope('profile')

// Configure Microsoft provider
microsoftProvider.addScope('email')
microsoftProvider.addScope('profile')

/**
 * Sign in with email and password
 */
export async function signInWithEmail(email: string, password: string): Promise<UserCredential> {
  if (!isFirebaseConfigured() || !auth) {
    throw new Error('Firebase is not configured. Please set up your Firebase credentials.')
  }
  return signInWithEmailAndPassword(auth, email, password)
}

/**
 * Create a new account with email and password
 */
export async function signUpWithEmail(email: string, password: string): Promise<UserCredential> {
  if (!isFirebaseConfigured() || !auth) {
    throw new Error('Firebase is not configured. Please set up your Firebase credentials.')
  }
  return createUserWithEmailAndPassword(auth, email, password)
}

/**
 * Sign in with Google
 */
export async function signInWithGoogle(): Promise<UserCredential> {
  if (!isFirebaseConfigured() || !auth) {
    throw new Error('Firebase is not configured. Please set up your Firebase credentials.')
  }
  return signInWithPopup(auth, googleProvider)
}

/**
 * Sign in with Microsoft
 */
export async function signInWithMicrosoft(): Promise<UserCredential> {
  if (!isFirebaseConfigured() || !auth) {
    throw new Error('Firebase is not configured. Please set up your Firebase credentials.')
  }
  return signInWithPopup(auth, microsoftProvider)
}

/**
 * Send password reset email
 */
export async function resetPassword(email: string): Promise<void> {
  if (!isFirebaseConfigured() || !auth) {
    throw new Error('Firebase is not configured. Please set up your Firebase credentials.')
  }
  return sendPasswordResetEmail(auth, email)
}

/**
 * Sign out the current user
 */
export async function logOut(): Promise<void> {
  if (!auth) {
    return // Nothing to sign out from
  }
  return signOut(auth)
}

/**
 * Get the current user's ID token
 */
export async function getIdToken(): Promise<string | null> {
  if (!auth) {
    return null
  }
  const user = auth.currentUser
  if (!user) {
    return null
  }
  return user.getIdToken()
}

/**
 * Subscribe to auth state changes
 */
export function onAuthChange(callback: (user: User | null) => void): () => void {
  if (!auth) {
    // Return a no-op unsubscribe function
    callback(null)
    return () => {}
  }
  return onAuthStateChanged(auth, callback)
}

/**
 * Get the current user
 */
export function getCurrentUser(): User | null {
  if (!auth) {
    return null
  }
  return auth.currentUser
}

/**
 * Subscription data structure from Firestore
 */
export interface FirestoreSubscriptionData {
  // Priority 1: lxusbrain format (users/{uid})
  plan?: string
  planStatus?: string
  subscription_expires_at?: unknown  // Firestore Timestamp
  subscriptionExpiresAt?: unknown
  expiresAt?: unknown

  // Priority 2: termivoxed format (subscriptions/{uid})
  tier?: string
  status?: string
  currentPeriodEnd?: unknown
  periodEnd?: unknown
  trialEndsAt?: unknown

  // Legacy format (users/{uid}.subscription)
  subscription?: {
    tier?: string
    status?: string
    periodEnd?: unknown
    currentPeriodEnd?: unknown
    expiresAt?: unknown
  }
}

/**
 * Normalized subscription data returned to the caller
 */
export interface NormalizedSubscription {
  tier: string
  status: string
  expiresAt: string | null
}

/**
 * Helper to convert Firestore timestamp to ISO string
 */
function timestampToISOString(value: unknown): string | null {
  if (!value) return null

  // Firestore Timestamp object
  if (typeof value === 'object' && value !== null && 'seconds' in value) {
    const seconds = (value as { seconds: number }).seconds
    return new Date(seconds * 1000).toISOString()
  }

  // JavaScript Date object
  if (value instanceof Date) {
    return value.toISOString()
  }

  // ISO string
  if (typeof value === 'string') {
    return value
  }

  return null
}

/**
 * Parse and normalize subscription data from Firestore
 * Matches the priority order used in backend auth.py
 */
function normalizeSubscriptionData(data: FirestoreSubscriptionData | null): NormalizedSubscription {
  const defaultResult: NormalizedSubscription = {
    tier: 'free_trial',
    status: 'trial',
    expiresAt: null,
  }

  if (!data) return defaultResult

  // Priority 1: lxusbrain format (plan, planStatus)
  if (data.plan) {
    let tier = data.plan.toLowerCase()
    let status = (data.planStatus || 'active').toLowerCase()

    // Normalize tier
    if (tier === 'free' || tier === 'trial') tier = 'free_trial'
    if (tier === 'basic') tier = 'individual'

    // For active paid subscriptions, use ACTIVE status (not TRIAL)
    if (tier !== 'free_trial' && status === 'trial') {
      status = 'active'
    }

    // Get expiry date
    const expiresAt = timestampToISOString(
      data.subscription_expires_at || data.subscriptionExpiresAt || data.expiresAt
    )

    return { tier, status, expiresAt }
  }

  // Priority 2: termivoxed format (tier, status) - from subscriptions/{uid}
  if (data.tier) {
    let tier = data.tier.toLowerCase()
    let status = (data.status || 'active').toLowerCase()

    // Normalize tier
    if (tier === 'free' || tier === 'trial') tier = 'free_trial'
    if (tier === 'basic') tier = 'individual'

    // For active paid subscriptions, use ACTIVE status (not TRIAL)
    if (tier !== 'free_trial' && status === 'trial') {
      status = 'active'
    }

    // Get expiry date - check expiresAt first (what Cloud Functions write)
    const expiresAt = timestampToISOString(
      data.expiresAt || data.currentPeriodEnd || data.periodEnd || data.trialEndsAt
    )

    return { tier, status, expiresAt }
  }

  // Priority 3: Legacy format (subscription nested object)
  if (data.subscription) {
    const sub = data.subscription
    let tier = (sub.tier || 'free_trial').toLowerCase()
    let status = (sub.status || 'trial').toLowerCase()

    // Normalize tier
    if (tier === 'free' || tier === 'trial') tier = 'free_trial'
    if (tier === 'basic') tier = 'individual'

    // For active paid subscriptions, use ACTIVE status (not TRIAL)
    if (tier !== 'free_trial' && status === 'trial') {
      status = 'active'
    }

    const expiresAt = timestampToISOString(
      sub.periodEnd || sub.currentPeriodEnd || sub.expiresAt
    )

    return { tier, status, expiresAt }
  }

  return defaultResult
}

/**
 * Subscribe to real-time subscription changes for a user
 * Listens to both users/{uid} and subscriptions/{uid} documents
 *
 * @param uid User ID to listen for
 * @param callback Called when subscription data changes
 * @returns Unsubscribe function to stop listening
 */
export function onSubscriptionChange(
  uid: string,
  callback: (subscription: NormalizedSubscription) => void
): Unsubscribe {
  if (!db || !uid) {
    // Return no-op if Firebase not configured
    return () => {}
  }

  let unsubUsers: Unsubscribe | null = null
  let unsubSubscriptions: Unsubscribe | null = null
  let latestUserData: FirestoreSubscriptionData | null = null
  let latestSubData: FirestoreSubscriptionData | null = null

  const processUpdate = () => {
    // Combine data with priority: users (lxusbrain) > subscriptions (termivoxed)
    // Check users document first for "plan" field
    if (latestUserData?.plan) {
      callback(normalizeSubscriptionData(latestUserData))
      return
    }

    // Fall back to subscriptions collection
    if (latestSubData?.tier) {
      callback(normalizeSubscriptionData(latestSubData))
      return
    }

    // Check users document for legacy nested subscription
    if (latestUserData?.subscription) {
      callback(normalizeSubscriptionData(latestUserData))
      return
    }

    // No subscription data found - return defaults
    callback(normalizeSubscriptionData(null))
  }

  // Listen to users/{uid} document (lxusbrain format + legacy format)
  const userDocRef = doc(db, 'users', uid)
  unsubUsers = onSnapshot(userDocRef, (snapshot) => {
    if (snapshot.exists()) {
      latestUserData = snapshot.data() as FirestoreSubscriptionData
    } else {
      latestUserData = null
    }
    processUpdate()
  }, (error) => {
    console.error('[FIREBASE] Error listening to user document:', error)
  })

  // Listen to subscriptions/{uid} document (termivoxed Cloud Functions format)
  const subDocRef = doc(db, 'subscriptions', uid)
  unsubSubscriptions = onSnapshot(subDocRef, (snapshot) => {
    if (snapshot.exists()) {
      latestSubData = snapshot.data() as FirestoreSubscriptionData
    } else {
      latestSubData = null
    }
    processUpdate()
  }, (error) => {
    console.error('[FIREBASE] Error listening to subscriptions document:', error)
  })

  // Return combined unsubscribe function
  return () => {
    if (unsubUsers) unsubUsers()
    if (unsubSubscriptions) unsubSubscriptions()
  }
}

// Export types
export type { User, UserCredential, Unsubscribe }
