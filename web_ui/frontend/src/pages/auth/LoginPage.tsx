/**
 * Login Page for TermiVoxed
 *
 * Handles user authentication with Firebase.
 * Supports email/password and social login.
 *
 * Styled to match the LxusBrain website theme.
 */

import { useState, useEffect } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuthStore, selectIsAuthenticated } from '../../stores/authStore'
import {
  signInWithEmail,
  signInWithGoogle,
  signInWithMicrosoft,
  isFirebaseConfigured
} from '../../lib/firebase'
import { getPersistedDeviceFingerprint } from '../../lib/deviceFingerprint'
import { TermiVoxedLogo } from '../../components/logos'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const login = useAuthStore((state) => state.login)
  const isLoading = useAuthStore((state) => state.isLoading)
  const error = useAuthStore((state) => state.error)
  const setError = useAuthStore((state) => state.setError)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [localLoading, setLocalLoading] = useState(false)

  // Get redirect path from location state
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true })
    }
  }, [isAuthenticated, navigate, from])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLocalLoading(true)

    try {
      if (!isFirebaseConfigured()) {
        setError('Authentication service not configured. Please contact support.')
        return
      }

      const userCredential = await signInWithEmail(email, password)
      const token = await userCredential.user.getIdToken()

      // Get device fingerprint for device tracking
      const deviceFingerprint = getPersistedDeviceFingerprint()

      const success = await login(token, deviceFingerprint)
      if (success) {
        navigate(from, { replace: true })
      }
    } catch (err: unknown) {
      console.error('Login error:', err)
      if (err instanceof Error) {
        if (err.message.includes('user-not-found')) {
          setError('No account found with this email address.')
        } else if (err.message.includes('wrong-password')) {
          setError('Incorrect password. Please try again.')
        } else if (err.message.includes('invalid-email')) {
          setError('Please enter a valid email address.')
        } else if (err.message.includes('too-many-requests')) {
          setError('Too many failed attempts. Please try again later.')
        } else if (err.message.includes('user-disabled')) {
          setError('This account has been disabled. Contact support.')
        } else {
          setError(err.message)
        }
      } else {
        setError('Login failed. Please try again.')
      }
    } finally {
      setLocalLoading(false)
    }
  }

  const handleGoogleLogin = async () => {
    setError(null)
    setLocalLoading(true)

    try {
      if (!isFirebaseConfigured()) {
        setError('Google login will be available after Firebase configuration')
        return
      }

      const userCredential = await signInWithGoogle()
      const token = await userCredential.user.getIdToken()

      // Get device fingerprint for device tracking
      const deviceFingerprint = getPersistedDeviceFingerprint()

      const success = await login(token, deviceFingerprint)
      if (success) {
        navigate(from, { replace: true })
      }
    } catch (err: unknown) {
      console.error('Google login error:', err)
      if (err instanceof Error) {
        if (err.message.includes('popup-closed-by-user')) {
          setError('Login cancelled. Please try again.')
        } else if (err.message.includes('popup-blocked')) {
          setError('Popup blocked. Please allow popups for this site.')
        } else {
          setError(err.message)
        }
      } else {
        setError('Google login failed. Please try again.')
      }
    } finally {
      setLocalLoading(false)
    }
  }

  const handleMicrosoftLogin = async () => {
    setError(null)
    setLocalLoading(true)

    try {
      if (!isFirebaseConfigured()) {
        setError('Microsoft login will be available after Firebase configuration')
        return
      }

      const userCredential = await signInWithMicrosoft()
      const token = await userCredential.user.getIdToken()

      // Get device fingerprint for device tracking
      const deviceFingerprint = getPersistedDeviceFingerprint()

      const success = await login(token, deviceFingerprint)
      if (success) {
        navigate(from, { replace: true })
      }
    } catch (err: unknown) {
      console.error('Microsoft login error:', err)
      if (err instanceof Error) {
        if (err.message.includes('popup-closed-by-user')) {
          setError('Login cancelled. Please try again.')
        } else if (err.message.includes('account-exists-with-different-credential')) {
          setError('An account already exists with this email using a different sign-in method.')
        } else {
          setError(err.message)
        }
      } else {
        setError('Microsoft login failed. Please try again.')
      }
    } finally {
      setLocalLoading(false)
    }
  }

  const loading = isLoading || localLoading

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] px-4 relative overflow-hidden">
      {/* Background gradient effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl" />
      </div>

      <div className="max-w-md w-full relative z-10">
        {/* Logo */}
        <div className="text-center mb-6">
          <Link to="/" className="inline-block">
            <TermiVoxedLogo width={100} />
          </Link>
          <p className="mt-3 text-gray-400 text-sm">
            AI Voice-Over Dubbing Tool
          </p>
        </div>

        {/* Card */}
        <div className="bg-gray-900/50 backdrop-blur-xl rounded-2xl shadow-2xl p-8 border border-white/10">
          <h2 className="text-2xl font-semibold text-white text-center mb-6">
            Welcome Back
          </h2>

          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 bg-gray-800/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
                placeholder="you@example.com"
                required
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 bg-gray-800/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 transition-all"
                placeholder="••••••••"
                required
                disabled={loading}
              />
            </div>

            <div className="flex justify-end">
              <Link
                to="/forgot-password"
                className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                Forgot password?
              </Link>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/25"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Signing in...</span>
                </>
              ) : (
                <span>Sign In</span>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-700" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-3 bg-gray-900/50 text-gray-500">Or continue with</span>
            </div>
          </div>

          {/* Social login buttons */}
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={handleGoogleLogin}
              disabled={loading}
              className="flex items-center justify-center gap-2 py-3 px-4 bg-gray-800/50 hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed border border-gray-700 hover:border-gray-600 rounded-xl text-gray-200 font-medium transition-all"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Google
            </button>

            <button
              onClick={handleMicrosoftLogin}
              disabled={loading}
              className="flex items-center justify-center gap-2 py-3 px-4 bg-gray-800/50 hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed border border-gray-700 hover:border-gray-600 rounded-xl text-gray-200 font-medium transition-all"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#F25022" d="M1 1h10v10H1z"/>
                <path fill="#00A4EF" d="M1 13h10v10H1z"/>
                <path fill="#7FBA00" d="M13 1h10v10H13z"/>
                <path fill="#FFB900" d="M13 13h10v10H13z"/>
              </svg>
              Microsoft
            </button>
          </div>

          {/* Link to signup */}
          <p className="mt-6 text-center text-gray-400">
            Don't have an account?{' '}
            <Link
              to="/signup"
              className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
            >
              Sign up
            </Link>
          </p>
        </div>

        {/* Footer */}
        <p className="mt-6 text-center text-sm text-gray-500">
          By continuing, you agree to our{' '}
          <a href="/terms" className="text-cyan-400 hover:underline">
            Terms of Service
          </a>{' '}
          and{' '}
          <a href="/privacy" className="text-cyan-400 hover:underline">
            Privacy Policy
          </a>
        </p>
      </div>
    </div>
  )
}

export default LoginPage
