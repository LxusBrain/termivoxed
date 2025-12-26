/**
 * Payment Cancel Page
 *
 * Displayed when user cancels the payment process.
 */

import { Link } from 'react-router-dom'

export function PaymentCancelPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 px-4">
      <div className="max-w-md w-full text-center">
        <div className="bg-gray-800/50 backdrop-blur-sm rounded-2xl shadow-xl p-8 border border-gray-700/50">
          <div className="w-20 h-20 bg-gray-700/50 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-10 h-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Payment Cancelled</h1>
          <p className="text-gray-400 mb-6">
            Your payment was not processed. No charges have been made to your account.
          </p>

          <div className="space-y-3">
            <Link
              to="/pricing"
              className="block w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 text-white font-medium rounded-lg transition-colors"
            >
              View Pricing Plans
            </Link>
            <Link
              to="/"
              className="block w-full py-3 px-4 bg-gray-700 hover:bg-gray-600 text-white font-medium rounded-lg transition-colors"
            >
              Continue with Free Trial
            </Link>
          </div>

          <div className="mt-8 p-4 bg-gray-700/30 rounded-lg">
            <h3 className="text-sm font-medium text-white mb-2">Why upgrade?</h3>
            <ul className="text-sm text-gray-400 space-y-1 text-left">
              <li>No watermarks on exports</li>
              <li>Advanced TTS voices</li>
              <li>4K video export</li>
              <li>Unlimited projects</li>
              <li>Priority support</li>
            </ul>
          </div>
        </div>

        <p className="mt-6 text-sm text-gray-500">
          Questions?{' '}
          <a href="mailto:support@termivoxed.com" className="text-purple-400 hover:underline">
            Contact our team
          </a>
        </p>
      </div>
    </div>
  )
}

export default PaymentCancelPage
