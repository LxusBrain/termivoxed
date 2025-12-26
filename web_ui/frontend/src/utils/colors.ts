/**
 * Color conversion utilities for ASS subtitle format
 */

/**
 * Convert BGR ASS color format (&HAABBGGRR) to hex (#RRGGBB)
 * @param bgr - BGR color string in ASS format (e.g., &H00FFFFFF or &H80000000)
 * @returns Hex color string (e.g., #FFFFFF)
 */
export function bgrToHex(bgr: string): string {
  // Handle format like &H00FFFFFF or &H80000000
  const match = bgr.match(/&H([0-9A-Fa-f]{2})?([0-9A-Fa-f]{6})/)
  if (!match) return '#FFFFFF'
  const color = match[2]
  const r = color.substring(4, 6)
  const g = color.substring(2, 4)
  const b = color.substring(0, 2)
  return `#${r}${g}${b}`.toUpperCase()
}

/**
 * Convert hex (#RRGGBB) to BGR ASS format (&H00BBGGRR)
 * @param hex - Hex color string (e.g., #FFFFFF or FFFFFF)
 * @param alpha - Alpha value in hex (00 = opaque, 80 = semi-transparent, FF = transparent)
 * @returns BGR color string in ASS format
 */
export function hexToBgr(hex: string, alpha = '00'): string {
  const clean = hex.replace('#', '')
  const r = clean.substring(0, 2)
  const g = clean.substring(2, 4)
  const b = clean.substring(4, 6)
  return `&H${alpha}${b}${g}${r}`.toUpperCase()
}

/**
 * Validate hex color format
 * @param hex - Color string to validate
 * @returns True if valid hex color
 */
export function isValidHexColor(hex: string): boolean {
  return /^#?[0-9A-Fa-f]{6}$/.test(hex)
}

/**
 * Ensure hex color has # prefix
 * @param hex - Hex color string
 * @returns Hex color with # prefix
 */
export function normalizeHexColor(hex: string): string {
  const clean = hex.replace('#', '')
  return `#${clean.toUpperCase()}`
}
