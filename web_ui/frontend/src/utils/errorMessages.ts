/**
 * Error Message Utilities
 *
 * Converts technical error messages to user-friendly messages.
 * Professional applications never show raw technical errors to users.
 */

/**
 * Maps technical error messages/codes to user-friendly messages
 */
export function getHumanReadableError(error: unknown): string {
  // Handle null/undefined
  if (!error) {
    return 'An unexpected error occurred. Please try again.'
  }

  // Extract error message and code
  const errorMessage = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase()
  const errorCode = (error as { code?: string })?.code?.toLowerCase() || ''

  // Network/Connection errors
  if (
    errorMessage.includes('timeout') ||
    errorMessage.includes('econnaborted') ||
    errorCode === 'econnaborted'
  ) {
    return 'Connection timed out. Please check your internet connection and try again.'
  }

  if (
    errorMessage.includes('network error') ||
    errorMessage.includes('econnrefused') ||
    errorMessage.includes('enotfound') ||
    errorMessage.includes('failed to fetch') ||
    errorCode === 'err_network'
  ) {
    return 'Unable to connect to server. Please check your internet connection.'
  }

  if (errorMessage.includes('econnreset') || errorMessage.includes('connection reset')) {
    return 'Connection was interrupted. Please try again.'
  }

  // Server errors
  if (errorMessage.includes('500') || errorMessage.includes('internal server error')) {
    return 'Server error. Please try again later.'
  }

  if (errorMessage.includes('502') || errorMessage.includes('bad gateway')) {
    return 'Server is temporarily unavailable. Please try again in a moment.'
  }

  if (errorMessage.includes('503') || errorMessage.includes('service unavailable')) {
    return 'Service is temporarily unavailable. Please try again later.'
  }

  if (errorMessage.includes('504') || errorMessage.includes('gateway timeout')) {
    return 'Server took too long to respond. Please try again.'
  }

  // Authentication errors
  if (errorMessage.includes('401') || errorMessage.includes('unauthorized')) {
    return 'Your session has expired. Please log in again.'
  }

  if (errorMessage.includes('403') || errorMessage.includes('forbidden')) {
    return 'Access denied. You don\'t have permission for this action.'
  }

  // Firebase Auth errors (these are usually handled separately but just in case)
  if (errorMessage.includes('user-not-found') || errorMessage.includes('auth/user-not-found')) {
    return 'No account found with this email address.'
  }

  if (errorMessage.includes('wrong-password') || errorMessage.includes('auth/wrong-password')) {
    return 'Incorrect password. Please try again.'
  }

  if (errorMessage.includes('invalid-email') || errorMessage.includes('auth/invalid-email')) {
    return 'Please enter a valid email address.'
  }

  if (errorMessage.includes('email-already-in-use') || errorMessage.includes('auth/email-already-in-use')) {
    return 'An account with this email already exists.'
  }

  if (errorMessage.includes('weak-password') || errorMessage.includes('auth/weak-password')) {
    return 'Password is too weak. Please use a stronger password.'
  }

  if (errorMessage.includes('too-many-requests') || errorMessage.includes('auth/too-many-requests')) {
    return 'Too many attempts. Please wait a moment and try again.'
  }

  if (errorMessage.includes('user-disabled') || errorMessage.includes('auth/user-disabled')) {
    return 'This account has been disabled. Please contact support.'
  }

  if (errorMessage.includes('popup-closed-by-user')) {
    return 'Login was cancelled. Please try again.'
  }

  if (errorMessage.includes('popup-blocked')) {
    return 'Popup was blocked. Please allow popups for this site.'
  }

  if (errorMessage.includes('account-exists-with-different-credential')) {
    return 'An account already exists with this email using a different sign-in method.'
  }

  // Rate limiting
  if (errorMessage.includes('429') || errorMessage.includes('rate limit')) {
    return 'Too many requests. Please wait a moment and try again.'
  }

  // Validation errors
  if (errorMessage.includes('400') || errorMessage.includes('bad request')) {
    return 'Invalid request. Please check your input and try again.'
  }

  if (errorMessage.includes('404') || errorMessage.includes('not found')) {
    return 'The requested resource was not found.'
  }

  // SSL/Certificate errors
  if (errorMessage.includes('cert') || errorMessage.includes('ssl') || errorMessage.includes('tls')) {
    return 'Secure connection failed. Please try again.'
  }

  // If the error message is already user-friendly (doesn't contain technical terms)
  // and is reasonably short, use it directly
  const technicalPatterns = [
    /\d{5}ms/,           // Time in ms
    /axios/i,            // Library names
    /xhr/i,
    /http/i,
    /\[.*\]/,            // Bracketed codes
    /econnection/i,
    /esocket/i,
    /dns/i,
    /port \d+/i,
    /0x[0-9a-f]+/i,      // Hex codes
  ]

  const originalMessage = error instanceof Error ? error.message : String(error)
  const isTechnical = technicalPatterns.some(pattern => pattern.test(originalMessage))

  if (!isTechnical && originalMessage.length < 150) {
    // The message might already be user-friendly (e.g., from backend)
    return originalMessage
  }

  // Default fallback
  return 'Something went wrong. Please try again.'
}

/**
 * Extracts a user-friendly message from an Axios error response
 */
export function getApiErrorMessage(error: unknown): string {
  // Check if it's an Axios error with response data
  const axiosError = error as {
    response?: {
      data?: {
        detail?: string
        message?: string
        error?: string
      }
      status?: number
    }
    message?: string
    code?: string
  }

  // First, try to get message from response data (backend error messages)
  if (axiosError?.response?.data) {
    const data = axiosError.response.data
    const backendMessage = data.detail || data.message || data.error

    if (backendMessage && typeof backendMessage === 'string') {
      // Backend messages are usually already user-friendly
      return backendMessage
    }
  }

  // Fall back to generic error handling
  return getHumanReadableError(error)
}
