/**
 * Forgot Password Page for TermiVoxed
 *
 * Handles password reset requests via Firebase.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { resetPassword, isFirebaseConfigured } from '../../lib/firebase'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)

    if (!email.trim()) {
      setError('Please enter your email address')
      return
    }

    setLoading(true)

    try {
      if (!isFirebaseConfigured()) {
        setError('Password reset is not available in development mode. Firebase configuration required.')
        return
      }

      await resetPassword(email)
      setSuccess(true)
    } catch (err: unknown) {
      console.error('Password reset error:', err)
      if (err instanceof Error) {
        if (err.message.includes('user-not-found')) {
          setError('No account found with this email address.')
        } else if (err.message.includes('invalid-email')) {
          setError('Please enter a valid email address.')
        } else if (err.message.includes('too-many-requests')) {
          setError('Too many requests. Please try again later.')
        } else {
          setError(err.message)
        }
      } else {
        setError('Failed to send reset email. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 px-4">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-block">
            <h1 className="text-3xl font-bold text-white">
              <span className="text-purple-500">Termi</span>Voxed
            </h1>
          </Link>
          <p className="mt-2 text-gray-400">
            Reset your password
          </p>
        </div>

        {/* Card */}
        <div className="bg-gray-800/50 backdrop-blur-sm rounded-2xl shadow-xl p-8 border border-gray-700/50">
          {success ? (
            // Success state
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-500/20 flex items-center justify-center">
                <svg className="w-8 h-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-2xl font-semibold text-white mb-2">
                Check Your Email
              </h2>
              <p className="text-gray-400 mb-6">
                We've sent a password reset link to <span className="text-white font-medium">{email}</span>
              </p>
              <p className="text-sm text-gray-500 mb-6">
                Didn't receive the email? Check your spam folder or{' '}
                <button
                  onClick={() => setSuccess(false)}
                  className="text-purple-400 hover:text-purple-300 transition-colors"
                >
                  try again
                </button>
              </p>
              <Link
                to="/login"
                className="inline-block py-2.5 px-6 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors"
              >
                Back to Sign In
              </Link>
            </div>
          ) : (
            // Form state
            <>
              <h2 className="text-2xl font-semibold text-white text-center mb-2">
                Forgot Password?
              </h2>
              <p className="text-gray-400 text-center mb-6">
                No worries! Enter your email and we'll send you a reset link.
              </p>

              {/* Error message */}
              {error && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                  {error}
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1">
                    Email Address
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
                    autoFocus
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-600/50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Sending...</span>
                    </>
                  ) : (
                    <span>Send Reset Link</span>
                  )}
                </button>
              </form>

              {/* Back to login */}
              <p className="mt-6 text-center text-gray-400">
                Remember your password?{' '}
                <Link
                  to="/login"
                  className="text-purple-400 hover:text-purple-300 font-medium transition-colors"
                >
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>

        {/* Help text */}
        <p className="mt-6 text-center text-sm text-gray-500">
          Need help?{' '}
          <a href="mailto:support@termivoxed.com" className="text-purple-400 hover:underline">
            Contact Support
          </a>
        </p>
      </div>
    </div>
  )
}

export default ForgotPasswordPage
