/**
 * RequireAuth - Protected Route Component
 *
 * Wraps routes that require authentication.
 * Redirects to login page if user is not authenticated.
 */

import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore, selectIsAuthenticated, selectIsLoading } from '../stores/authStore'

interface RequireAuthProps {
  children: React.ReactNode
  requiredFeature?: string
}

export function RequireAuth({ children, requiredFeature }: RequireAuthProps) {
  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const isLoading = useAuthStore(selectIsLoading)
  const isInitialized = useAuthStore((state) => state.isInitialized)
  const hasFeature = useAuthStore((state) => state.hasFeature)
  const location = useLocation()

  // Show loading state while initializing
  if (!isInitialized || isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Check for required feature if specified
  if (requiredFeature && !hasFeature(requiredFeature as never)) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="max-w-md p-6 bg-gray-800 rounded-lg shadow-lg text-center">
          <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center bg-yellow-500/20 rounded-full">
            <svg
              className="w-8 h-8 text-yellow-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">
            Feature Not Available
          </h2>
          <p className="text-gray-400 mb-4">
            This feature requires a higher subscription tier.
          </p>
          <a
            href="https://lxusbrain.com/termivoxed/subscription"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-6 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            Upgrade Now
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

export default RequireAuth
