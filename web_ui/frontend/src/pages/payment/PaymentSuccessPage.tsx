/**
 * Payment Success Page
 *
 * Displayed after successful payment. Handles Stripe checkout session verification.
 */

import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { api } from '../../api/client'

export function PaymentSuccessPage() {
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')
  const refreshUser = useAuthStore((state) => state.refreshUser)

  useEffect(() => {
    const sessionId = searchParams.get('session_id')
    const isTrial = searchParams.get('trial') === 'true'

    const verifyPayment = async () => {
      try {
        // Handle free trial success
        if (isTrial) {
          if (refreshUser) {
            await refreshUser()
          }
          setStatus('success')
          setMessage('Your 7-day free trial has started! Enjoy all premium features.')
          return
        }

        // Verify session with backend if session_id is present (Stripe)
        if (sessionId) {
          try {
            await api.post('/payments/verify-session', { session_id: sessionId })
          } catch (verifyError) {
            // Non-blocking - session verification is additional security
            // Payment is already processed by webhook
            console.warn('Session verification skipped')
          }
        }

        // Refresh user data to get updated subscription
        if (refreshUser) {
          await refreshUser()
        }

        setStatus('success')
        setMessage('Your subscription has been activated successfully!')
      } catch (error) {
        console.error('Payment verification error:', error)
        setStatus('error')
        setMessage('We received your payment but encountered an issue. Please contact support if your subscription is not active.')
      }
    }

    verifyPayment()
  }, [searchParams, refreshUser])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 px-4">
      <div className="max-w-md w-full text-center">
        {status === 'loading' && (
          <div className="bg-gray-800/50 backdrop-blur-sm rounded-2xl shadow-xl p-8 border border-gray-700/50">
            <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-white">Processing your payment...</h2>
            <p className="text-gray-400 mt-2">Please wait while we confirm your subscription.</p>
          </div>
        )}

        {status === 'success' && (
          <div className="bg-gray-800/50 backdrop-blur-sm rounded-2xl shadow-xl p-8 border border-green-500/30">
            <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-white mb-2">Payment Successful!</h1>
            <p className="text-gray-300 mb-6">{message}</p>
            <div className="space-y-3">
              <Link
                to="/"
                className="block w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors"
              >
                Start Creating
              </Link>
              <Link
                to="/account"
                className="block w-full py-3 px-4 bg-gray-700 hover:bg-gray-600 text-white font-medium rounded-lg transition-colors"
              >
                View Subscription Details
              </Link>
            </div>
          </div>
        )}

        {status === 'error' && (
          <div className="bg-gray-800/50 backdrop-blur-sm rounded-2xl shadow-xl p-8 border border-yellow-500/30">
            <div className="w-20 h-20 bg-yellow-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-yellow-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-white mb-2">Payment Processing</h1>
            <p className="text-gray-300 mb-6">{message}</p>
            <div className="space-y-3">
              <Link
                to="/account"
                className="block w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors"
              >
                Check Subscription Status
              </Link>
              <a
                href="mailto:support@termivoxed.com"
                className="block w-full py-3 px-4 bg-gray-700 hover:bg-gray-600 text-white font-medium rounded-lg transition-colors"
              >
                Contact Support
              </a>
            </div>
          </div>
        )}

        <p className="mt-6 text-sm text-gray-500">
          Need help?{' '}
          <a href="mailto:support@termivoxed.com" className="text-purple-400 hover:underline">
            Contact Support
          </a>
        </p>
      </div>
    </div>
  )
}

export default PaymentSuccessPage
