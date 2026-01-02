/**
 * React Query Client Configuration
 *
 * Exported separately to avoid circular dependencies.
 * Used by main.tsx for QueryClientProvider and by authStore for cache invalidation.
 */

import { QueryClient } from '@tanstack/react-query'
import type { AxiosError } from 'axios'

// Default retry delay with exponential backoff
const DEFAULT_RETRY_DELAY_MS = 1000
const MAX_RETRY_DELAY_MS = 30000

/**
 * Custom retry function that respects rate limits and auth errors
 */
function shouldRetry(failureCount: number, error: unknown): boolean {
  // Don't retry more than once
  if (failureCount >= 1) {
    return false
  }

  // Check if it's an axios error
  const axiosError = error as AxiosError
  if (axiosError?.response) {
    const status = axiosError.response.status

    // Don't retry on auth errors - user needs to re-authenticate
    if (status === 401 || status === 403) {
      return false
    }

    // Don't retry on rate limits - respect the Retry-After
    // The UI should handle this gracefully instead of immediately retrying
    if (status === 429) {
      return false
    }

    // Don't retry on client errors (4xx) except for some specific cases
    if (status >= 400 && status < 500) {
      return false
    }
  }

  // Retry on network errors and server errors (5xx)
  return true
}

/**
 * Custom retry delay with exponential backoff
 * Respects Retry-After header for rate limit responses
 */
function getRetryDelay(attemptIndex: number, error: unknown): number {
  // Check if it's an axios error with Retry-After header
  const axiosError = error as AxiosError
  if (axiosError?.response?.headers) {
    const retryAfter = axiosError.response.headers['retry-after']
    if (retryAfter) {
      // Retry-After can be in seconds
      const retryAfterSeconds = parseInt(retryAfter, 10)
      if (!isNaN(retryAfterSeconds)) {
        // Convert to milliseconds and add a small buffer
        return Math.min(retryAfterSeconds * 1000 + 500, MAX_RETRY_DELAY_MS)
      }
    }
  }

  // Exponential backoff: 1s, 2s, 4s, etc.
  const delay = Math.min(
    DEFAULT_RETRY_DELAY_MS * Math.pow(2, attemptIndex),
    MAX_RETRY_DELAY_MS
  )
  return delay
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: shouldRetry,
      retryDelay: getRetryDelay,
    },
    mutations: {
      retry: false, // Don't retry mutations by default
    },
  },
})
