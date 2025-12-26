/**
 * Signup Page for TermiVoxed
 *
 * Handles new user registration with Firebase.
 * Supports email/password and social signup.
 */

import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore, selectIsAuthenticated } from '../../stores/authStore'
import {
  signUpWithEmail,
  signInWithGoogle,
  signInWithGithub,
  isFirebaseConfigured
} from '../../lib/firebase'

export function SignupPage() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const login = useAuthStore((state) => state.login)
  const setError = useAuthStore((state) => state.setError)
  const error = useAuthStore((state) => state.error)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [acceptedTerms, setAcceptedTerms] = useState(false)

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const validateForm = (): string | null => {
    if (!name.trim()) {
      return 'Please enter your name'
    }
    if (!email.trim()) {
      return 'Please enter your email'
    }
    if (password.length < 8) {
      return 'Password must be at least 8 characters'
    }
    if (password !== confirmPassword) {
      return 'Passwords do not match'
    }
    if (!acceptedTerms) {
      return 'Please accept the Terms of Service and Privacy Policy'
    }
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const validationError = validateForm()
    if (validationError) {
      setError(validationError)
      return
    }

    setLoading(true)

    try {
      if (!isFirebaseConfigured()) {
        // Firebase not configured - show error instead of dev bypass
        setError('Authentication service is not configured. Please contact support.')
        setLoading(false)
        return
      }

      // Create account with Firebase
      const userCredential = await signUpWithEmail(email, password)
      const token = await userCredential.user.getIdToken()

      const success = await login(token)
      if (success) {
        navigate('/', { replace: true })
      }
    } catch (err: unknown) {
      console.error('Signup error:', err)
      if (err instanceof Error) {
        // Handle Firebase-specific error messages
        if (err.message.includes('email-already-in-use')) {
          setError('An account with this email already exists. Please sign in instead.')
        } else if (err.message.includes('weak-password')) {
          setError('Password is too weak. Please use a stronger password.')
        } else if (err.message.includes('invalid-email')) {
          setError('Please enter a valid email address.')
        } else {
          setError(err.message)
        }
      } else {
        setError('Failed to create account. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSignup = async () => {
    setError(null)
    setLoading(true)

    try {
      if (!isFirebaseConfigured()) {
        setError('Google signup will be available after Firebase configuration')
        return
      }

      const userCredential = await signInWithGoogle()
      const token = await userCredential.user.getIdToken()

      const success = await login(token)
      if (success) {
        navigate('/', { replace: true })
      }
    } catch (err: unknown) {
      console.error('Google signup error:', err)
      setError(err instanceof Error ? err.message : 'Google signup failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGitHubSignup = async () => {
    setError(null)
    setLoading(true)

    try {
      if (!isFirebaseConfigured()) {
        setError('GitHub signup will be available after Firebase configuration')
        return
      }

      const userCredential = await signInWithGithub()
      const token = await userCredential.user.getIdToken()

      const success = await login(token)
      if (success) {
        navigate('/', { replace: true })
      }
    } catch (err: unknown) {
      console.error('GitHub signup error:', err)
      setError(err instanceof Error ? err.message : 'GitHub signup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 px-4 py-8">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-block">
            <h1 className="text-3xl font-bold text-white">
              <span className="text-purple-500">Termi</span>Voxed
            </h1>
          </Link>
          <p className="mt-2 text-gray-400">
            Create your account to get started
          </p>
        </div>

        {/* Card */}
        <div className="bg-gray-800/50 backdrop-blur-sm rounded-2xl shadow-xl p-8 border border-gray-700/50">
          <h2 className="text-2xl font-semibold text-white text-center mb-6">
            Create Account
          </h2>

          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-1">
                Full Name
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                placeholder="John Doe"
                required
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                placeholder="you@example.com"
                required
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                placeholder="At least 8 characters"
                required
                minLength={8}
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-300 mb-1">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                placeholder="Confirm your password"
                required
                disabled={loading}
              />
            </div>

            {/* Terms checkbox */}
            <div className="flex items-start gap-3">
              <input
                id="terms"
                type="checkbox"
                checked={acceptedTerms}
                onChange={(e) => setAcceptedTerms(e.target.checked)}
                className="mt-1 w-4 h-4 bg-gray-700 border-gray-600 rounded focus:ring-purple-500 focus:ring-2"
                disabled={loading}
              />
              <label htmlFor="terms" className="text-sm text-gray-400">
                I agree to the{' '}
                <a href="/terms" className="text-purple-400 hover:underline">
                  Terms of Service
                </a>{' '}
                and{' '}
                <a href="/privacy" className="text-purple-400 hover:underline">
                  Privacy Policy
                </a>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-600/50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Creating account...</span>
                </>
              ) : (
                <span>Create Account</span>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-600" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-gray-800/50 text-gray-400">Or sign up with</span>
            </div>
          </div>

          {/* Social signup buttons */}
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={handleGoogleSignup}
              disabled={loading}
              className="flex items-center justify-center gap-2 py-2.5 px-4 bg-gray-700/50 hover:bg-gray-700 disabled:bg-gray-700/30 disabled:cursor-not-allowed border border-gray-600 rounded-lg text-gray-200 font-medium transition-colors"
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
              onClick={handleGitHubSignup}
              disabled={loading}
              className="flex items-center justify-center gap-2 py-2.5 px-4 bg-gray-700/50 hover:bg-gray-700 disabled:bg-gray-700/30 disabled:cursor-not-allowed border border-gray-600 rounded-lg text-gray-200 font-medium transition-colors"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0012 2z"
                />
              </svg>
              GitHub
            </button>
          </div>

          {/* Link to login */}
          <p className="mt-6 text-center text-gray-400">
            Already have an account?{' '}
            <Link
              to="/login"
              className="text-purple-400 hover:text-purple-300 font-medium transition-colors"
            >
              Sign in
            </Link>
          </p>
        </div>

        {/* Free trial info */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-500">
            Start with a <span className="text-purple-400 font-medium">7-day free trial</span>
          </p>
          <p className="text-xs text-gray-600 mt-1">
            No credit card required
          </p>
        </div>
      </div>
    </div>
  )
}

export default SignupPage
