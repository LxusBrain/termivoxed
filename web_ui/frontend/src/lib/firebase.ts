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
  GithubAuthProvider,
  sendPasswordResetEmail,
  signOut,
  onAuthStateChanged,
  User,
  UserCredential,
} from 'firebase/auth'

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

if (isFirebaseConfigured()) {
  app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0]
  auth = getAuth(app)
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
const githubProvider = new GithubAuthProvider()

// Configure Google provider
googleProvider.addScope('email')
googleProvider.addScope('profile')

// Configure GitHub provider
githubProvider.addScope('user:email')

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
 * Sign in with GitHub
 */
export async function signInWithGithub(): Promise<UserCredential> {
  if (!isFirebaseConfigured() || !auth) {
    throw new Error('Firebase is not configured. Please set up your Firebase credentials.')
  }
  return signInWithPopup(auth, githubProvider)
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

// Export types
export type { User, UserCredential }
