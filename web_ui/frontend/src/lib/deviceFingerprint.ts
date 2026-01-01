/**
 * Device Fingerprint Utility for TermiVoxed
 *
 * Generates a unique fingerprint for the current device/browser
 * to enable device tracking and limit enforcement.
 */

/**
 * Generate a simple hash from a string
 */
function simpleHash(str: string): string {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash = hash & hash // Convert to 32bit integer
  }
  return Math.abs(hash).toString(16).padStart(8, '0')
}

/**
 * Get browser-based device fingerprint components
 */
function getDeviceComponents(): string[] {
  const components: string[] = []

  // User agent
  components.push(navigator.userAgent)

  // Screen properties
  components.push(`${screen.width}x${screen.height}x${screen.colorDepth}`)

  // Timezone
  components.push(Intl.DateTimeFormat().resolvedOptions().timeZone)

  // Language
  components.push(navigator.language)

  // Platform
  components.push(navigator.platform)

  // Hardware concurrency (CPU cores)
  if (navigator.hardwareConcurrency) {
    components.push(`cores:${navigator.hardwareConcurrency}`)
  }

  // Device memory (if available)
  if ('deviceMemory' in navigator) {
    components.push(`mem:${(navigator as Navigator & { deviceMemory?: number }).deviceMemory}`)
  }

  // Touch support
  components.push(`touch:${navigator.maxTouchPoints}`)

  // WebGL renderer (graphics card info)
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
    if (gl && gl instanceof WebGLRenderingContext) {
      const debugInfo = gl.getExtension('WEBGL_debug_renderer_info')
      if (debugInfo) {
        components.push(gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || '')
      }
    }
  } catch {
    // WebGL not available
  }

  return components
}

/**
 * Generate a device fingerprint
 *
 * This creates a reasonably unique identifier for the device/browser.
 * Note: This is not perfect and can change if user updates browser,
 * but it's good enough for basic device tracking.
 *
 * @returns A unique device fingerprint string
 */
export function generateDeviceFingerprint(): string {
  const components = getDeviceComponents()
  const combined = components.join('|')
  return `web-${simpleHash(combined)}`
}

/**
 * Get device name based on platform/user agent
 */
export function getDeviceName(): string {
  const ua = navigator.userAgent

  // Try to get OS name
  let os = 'Unknown'
  if (ua.includes('Windows')) os = 'Windows'
  else if (ua.includes('Mac')) os = 'macOS'
  else if (ua.includes('Linux')) os = 'Linux'
  else if (ua.includes('Android')) os = 'Android'
  else if (ua.includes('iPhone') || ua.includes('iPad')) os = 'iOS'

  // Try to get browser name
  let browser = 'Browser'
  if (ua.includes('Firefox')) browser = 'Firefox'
  else if (ua.includes('Edg/')) browser = 'Edge'
  else if (ua.includes('Chrome')) browser = 'Chrome'
  else if (ua.includes('Safari')) browser = 'Safari'

  return `${os} - ${browser}`
}

/**
 * Get device type
 */
export function getDeviceType(): string {
  const ua = navigator.userAgent

  if (ua.includes('Mobile') || ua.includes('Android')) {
    return 'MOBILE'
  } else if (ua.includes('Tablet') || ua.includes('iPad')) {
    return 'TABLET'
  }
  return 'WEB'
}

/**
 * Get or create a persistent device ID stored in localStorage
 *
 * This ensures the same device gets the same ID across sessions.
 */
export function getPersistedDeviceFingerprint(): string {
  const STORAGE_KEY = 'termivoxed-device-id'

  // Check if we already have a stored fingerprint
  let fingerprint = localStorage.getItem(STORAGE_KEY)

  if (!fingerprint) {
    // Generate new fingerprint and store it
    fingerprint = generateDeviceFingerprint()
    localStorage.setItem(STORAGE_KEY, fingerprint)
  }

  return fingerprint
}
