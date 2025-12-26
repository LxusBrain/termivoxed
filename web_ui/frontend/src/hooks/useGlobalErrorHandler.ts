import { useEffect } from 'react'
import { useDebugStore } from '../stores/debugStore'

// Store original console methods
const originalConsole = {
  error: console.error.bind(console),
  warn: console.warn.bind(console),
  log: console.log.bind(console),
}

// Flag to prevent recursive logging
let isLogging = false

/**
 * Global error handler hook
 * Sets up handlers for:
 * - window.onerror (uncaught JS errors)
 * - window.onunhandledrejection (unhandled promise rejections)
 * - Console error/warn interception
 * - Performance monitoring (optional)
 */
export function useGlobalErrorHandler() {
  const { error, warn, info, debug } = useDebugStore()

  useEffect(() => {
    // Handle uncaught errors
    const handleError = (event: ErrorEvent) => {
      if (isLogging) return

      isLogging = true
      error(
        `Uncaught Error: ${event.message}`,
        {
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
          error: event.error,
        },
        'window.onerror'
      )
      isLogging = false

      // Don't prevent default - let error appear in console too
    }

    // Handle unhandled promise rejections
    const handleRejection = (event: PromiseRejectionEvent) => {
      if (isLogging) return

      isLogging = true
      const reason = event.reason
      const message = reason instanceof Error
        ? reason.message
        : typeof reason === 'string'
          ? reason
          : 'Unhandled Promise Rejection'

      error(
        `Unhandled Promise Rejection: ${message}`,
        reason instanceof Error ? reason : { reason },
        'window.onunhandledrejection'
      )
      isLogging = false
    }

    // Intercept console.error
    console.error = (...args: unknown[]) => {
      originalConsole.error(...args)

      if (isLogging) return
      isLogging = true

      const message = args.map(arg =>
        typeof arg === 'string' ? arg : JSON.stringify(arg)
      ).join(' ')

      error(message, args.length > 1 ? args.slice(1) : undefined, 'console.error')
      isLogging = false
    }

    // Intercept console.warn
    console.warn = (...args: unknown[]) => {
      originalConsole.warn(...args)

      if (isLogging) return
      isLogging = true

      const message = args.map(arg =>
        typeof arg === 'string' ? arg : JSON.stringify(arg)
      ).join(' ')

      warn(message, args.length > 1 ? args.slice(1) : undefined, 'console.warn')
      isLogging = false
    }

    // Add event listeners
    window.addEventListener('error', handleError)
    window.addEventListener('unhandledrejection', handleRejection)

    // Log session start
    info('Debug session started', {
      url: window.location.href,
      timestamp: new Date().toISOString(),
    }, 'GlobalErrorHandler')

    // Cleanup
    return () => {
      window.removeEventListener('error', handleError)
      window.removeEventListener('unhandledrejection', handleRejection)

      // Restore original console methods
      console.error = originalConsole.error
      console.warn = originalConsole.warn
    }
  }, [error, warn, info, debug])
}

/**
 * Hook to track user actions for debugging
 * Call this with action name and optional data when user performs actions
 */
export function useActionLogger() {
  const { action } = useDebugStore()

  return {
    logAction: (actionName: string, data?: unknown) => {
      action(actionName, data)
    }
  }
}

/**
 * Utility to log API calls
 */
export function logApiCall(
  method: string,
  url: string,
  status?: number,
  error?: unknown
) {
  const store = useDebugStore.getState()

  if (error) {
    store.error(`API Error: ${method} ${url}`, { status, error }, 'API')
  } else {
    store.debug(`API: ${method} ${url} -> ${status}`, { status }, 'API')
  }
}

/**
 * Utility to log component lifecycle events (for debugging render issues)
 */
export function logComponentEvent(
  component: string,
  event: 'mount' | 'unmount' | 'update' | 'error',
  data?: unknown
) {
  const store = useDebugStore.getState()
  store.debug(`${component}: ${event}`, data, 'Component')
}

/**
 * Performance monitoring utility
 */
export function logPerformance(label: string, durationMs: number, data?: unknown) {
  const store = useDebugStore.getState()

  if (durationMs > 1000) {
    store.warn(`Slow operation: ${label} took ${durationMs.toFixed(0)}ms`, data, 'Performance')
  } else if (durationMs > 100) {
    store.debug(`${label}: ${durationMs.toFixed(0)}ms`, data, 'Performance')
  }
}

export default useGlobalErrorHandler
