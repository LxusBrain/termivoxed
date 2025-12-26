/**
 * SubtitlePreview - Live preview of subtitle styling
 */

import { useEffect, useState } from 'react'
import { Check, AlertCircle } from 'lucide-react'
import { getSampleText } from '../../constants/languages'

interface SubtitlePreviewProps {
  text: string
  language: string
  font: string
  size: number
  color: string
  outlineWidth?: number
  outlineColor?: string
  shadow?: number
  shadowColor?: string
  isLocalFont?: boolean
}

export default function SubtitlePreview({
  text,
  language,
  font,
  size,
  color,
  outlineWidth = 0,
  outlineColor = '#000000',
  shadow = 0,
  shadowColor = '#000000',
  isLocalFont = false,
}: SubtitlePreviewProps) {
  const [fontLoaded, setFontLoaded] = useState(false)
  const [fontError, setFontError] = useState(false)

  // Get sample text for the language
  const sampleText = getSampleText(language)

  // Display text - use provided text or fall back to sample
  const displayText = text?.trim() ? text.slice(0, 50) : sampleText

  // Load Google Font dynamically
  useEffect(() => {
    if (!font || isLocalFont) {
      setFontLoaded(true)
      setFontError(false)
      return
    }

    // Check if font is already loaded
    const existingLink = document.querySelector(`link[data-font="${font}"]`)
    if (existingLink) {
      setFontLoaded(true)
      return
    }

    // Create link element for Google Font
    const link = document.createElement('link')
    link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(font)}:wght@400;700&display=swap`
    link.rel = 'stylesheet'
    link.setAttribute('data-font', font)

    link.onload = () => {
      setFontLoaded(true)
      setFontError(false)
    }

    link.onerror = () => {
      setFontLoaded(true)
      setFontError(true)
    }

    document.head.appendChild(link)

    return () => {
      // Don't remove - fonts might be used elsewhere
    }
  }, [font, isLocalFont])

  // Build text shadow CSS
  const buildTextShadow = (): string => {
    const shadows: string[] = []

    // Outline effect (multiple shadows for thickness)
    if (outlineWidth > 0) {
      const outlineSteps = Math.ceil(outlineWidth * 4)
      for (let i = 0; i < outlineSteps; i++) {
        const angle = (i / outlineSteps) * 2 * Math.PI
        const x = Math.cos(angle) * outlineWidth
        const y = Math.sin(angle) * outlineWidth
        shadows.push(`${x.toFixed(1)}px ${y.toFixed(1)}px 0 ${outlineColor}`)
      }
    }

    // Drop shadow
    if (shadow > 0) {
      shadows.push(`${shadow}px ${shadow}px ${shadow}px ${shadowColor}`)
    }

    return shadows.join(', ') || 'none'
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-text-secondary">Preview</label>
        <div className="flex items-center gap-2 text-xs">
          {isLocalFont ? (
            <span className="flex items-center gap-1 text-green-400">
              <Check className="w-3 h-3" />
              Installed locally
            </span>
          ) : fontError ? (
            <span className="flex items-center gap-1 text-yellow-400">
              <AlertCircle className="w-3 h-3" />
              Font may not render
            </span>
          ) : !fontLoaded ? (
            <span className="text-text-muted">Loading font...</span>
          ) : null}
        </div>
      </div>

      {/* Preview Area */}
      <div
        className="relative bg-black rounded-lg overflow-hidden"
        style={{ minHeight: '80px' }}
      >
        {/* Dark video-like background */}
        <div className="absolute inset-0 bg-gradient-to-b from-gray-900 to-black" />

        {/* Subtitle text */}
        <div className="relative flex items-end justify-center p-4 h-full" style={{ minHeight: '80px' }}>
          <p
            style={{
              fontFamily: `"${font}", sans-serif`,
              fontSize: `${size}px`,
              color: color,
              textShadow: buildTextShadow(),
              textAlign: 'center',
              lineHeight: 1.3,
              wordBreak: 'break-word',
              maxWidth: '100%',
            }}
          >
            {displayText}
          </p>
        </div>
      </div>

      {/* Font info */}
      <p className="text-xs text-text-muted">
        Font: {font} • Size: {size}px
      </p>
    </div>
  )
}
