/**
 * Payment Cancel Page
 *
 * Displayed when user cancels the payment process.
 *
 * Styled to match the LxusBrain website theme.
 */

import { Link } from 'react-router-dom'
import { TermiVoxedLogo } from '../../components/logos'

export function PaymentCancelPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] px-4 relative overflow-hidden">
      {/* Background gradient effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl" />
      </div>

      <div className="max-w-md w-full text-center relative z-10">
        {/* Logo */}
        <div className="mb-8">
          <Link to="/" className="inline-block">
            <TermiVoxedLogo width={120} />
          </Link>
        </div>

        <div className="bg-gray-900/50 backdrop-blur-xl rounded-2xl shadow-2xl p-8 border border-white/10">
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
              className="block w-full py-3 px-4 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white font-medium rounded-xl transition-all shadow-lg shadow-cyan-500/25"
            >
              View Pricing Plans
            </Link>
            <Link
              to="/"
              className="block w-full py-3 px-4 bg-gray-800/50 hover:bg-gray-800 text-white font-medium rounded-xl transition-all border border-gray-700"
            >
              Continue with Free Trial
            </Link>
          </div>

          <div className="mt-8 p-4 bg-gray-800/30 rounded-xl border border-gray-700/50">
            <h3 className="text-sm font-medium text-white mb-2">Why upgrade?</h3>
            <ul className="text-sm text-gray-400 space-y-1 text-left">
              <li className="flex items-center gap-2">
                <svg className="w-4 h-4 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                No watermarks on exports
              </li>
              <li className="flex items-center gap-2">
                <svg className="w-4 h-4 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Advanced TTS voices
              </li>
              <li className="flex items-center gap-2">
                <svg className="w-4 h-4 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                4K video export
              </li>
              <li className="flex items-center gap-2">
                <svg className="w-4 h-4 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Unlimited projects
              </li>
              <li className="flex items-center gap-2">
                <svg className="w-4 h-4 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Priority support
              </li>
            </ul>
          </div>
        </div>

        <p className="mt-6 text-sm text-gray-500">
          Questions?{' '}
          <a href="mailto:lxusbrain@gmail.com" className="text-cyan-400 hover:underline">
            Contact our team
          </a>
        </p>
      </div>
    </div>
  )
}

export default PaymentCancelPage
