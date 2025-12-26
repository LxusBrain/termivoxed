/**
 * Voice-related utility functions
 */

/**
 * Format voice name by removing common prefixes and cleaning up
 * @param name - Raw voice name (e.g., "Microsoft Server Speech Text to Speech Voice (en-US, AriaNeural)")
 * @returns Cleaned voice name (e.g., "AriaNeural")
 */
export function formatVoiceName(name: string): string {
  return name
    .replace(/^Microsoft\s+/i, '')
    .replace(/\s+Online\s*\(Natural\)/i, '')
    .trim()
}

/**
 * Extract gender from voice name
 * @param name - Voice name or ID
 * @returns 'Male' | 'Female' | 'Unknown'
 */
export function getVoiceGender(name: string): 'Male' | 'Female' | 'Unknown' {
  const lower = name.toLowerCase()
  if (lower.includes('female') || lower.includes('woman') || lower.includes('girl')) {
    return 'Female'
  }
  if (lower.includes('male') || lower.includes('man') || lower.includes('boy')) {
    return 'Male'
  }
  return 'Unknown'
}

/**
 * Format time in seconds to MM:SS.s format
 * @param seconds - Time in seconds
 * @returns Formatted time string
 */
export function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  const ms = Math.floor((seconds % 1) * 10)
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms}`
}

/**
 * Parse time string to seconds
 * @param timeStr - Time string in MM:SS.s format
 * @returns Time in seconds
 */
export function parseTime(timeStr: string): number {
  const parts = timeStr.split(':')
  if (parts.length !== 2) return 0
  const [mins, secsAndMs] = parts
  const [secs, ms] = secsAndMs.split('.')
  return parseInt(mins) * 60 + parseInt(secs) + (parseInt(ms || '0') / 10)
}

/**
 * Validate voice parameter string format
 * @param value - Parameter value (e.g., "+0%", "-50%", "+50Hz")
 * @param unit - Expected unit ('%' or 'Hz')
 * @returns True if valid
 */
export function isValidVoiceParam(value: string, unit: '%' | 'Hz'): boolean {
  const pattern = unit === '%'
    ? /^[+-]?\d+%$/
    : /^[+-]?\d+Hz$/
  return pattern.test(value)
}

/**
 * Format voice parameter value
 * @param value - Numeric value
 * @param unit - Unit to append
 * @returns Formatted string (e.g., "+25%")
 */
export function formatVoiceParam(value: number, unit: '%' | 'Hz'): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value}${unit}`
}

/**
 * Parse voice parameter string to number
 * @param value - Parameter string (e.g., "+25%")
 * @returns Numeric value
 */
export function parseVoiceParam(value: string): number {
  return parseInt(value.replace(/[+%Hz]/g, ''))
}
