/**
 * VoiceParameters - Shared component for voice rate, volume, and pitch controls
 *
 * Note: These controls only work with Edge TTS (cloud provider).
 * Coqui TTS (local) doesn't support rate/volume/pitch adjustments.
 */

import { ChevronDown, ChevronUp, Gauge } from 'lucide-react'
import { useState } from 'react'

// Providers that don't support voice parameters
const UNSUPPORTED_PROVIDERS = ['coqui', 'piper']

interface VoiceParametersProps {
  rate: string
  volume: string
  pitch: string
  onRateChange: (rate: string) => void
  onVolumeChange: (volume: string) => void
  onPitchChange: (pitch: string) => void
  collapsible?: boolean
  defaultExpanded?: boolean
  provider?: string // Current TTS provider - hides component for unsupported providers
}

export default function VoiceParameters({
  rate,
  volume,
  pitch,
  onRateChange,
  onVolumeChange,
  onPitchChange,
  collapsible = true,
  defaultExpanded = false,
  provider,
}: VoiceParametersProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)

  // Hide component for providers that don't support voice parameters
  if (provider && UNSUPPORTED_PROVIDERS.includes(provider.toLowerCase())) {
    return null
  }

  // Parse numeric value from string (e.g., "+25%" -> 25, "-10Hz" -> -10)
  const parseValue = (value: string): number => {
    return parseInt(value.replace(/[+%Hz]/g, '')) || 0
  }

  // Format value with sign and unit
  const formatValue = (value: number, unit: '%' | 'Hz'): string => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${value}${unit}`
  }

  const content = (
    <div className="space-y-4">
      {/* Rate Slider */}
      <div>
        <div className="flex justify-between text-xs text-text-muted mb-1">
          <span>Slow</span>
          <span>Rate: {rate}</span>
          <span>Fast</span>
        </div>
        <input
          type="range"
          min="-50"
          max="100"
          value={parseValue(rate)}
          onChange={(e) => onRateChange(formatValue(parseInt(e.target.value), '%'))}
          className="w-full h-2 bg-terminal-border rounded-lg appearance-none cursor-pointer accent-accent-primary"
        />
      </div>

      {/* Volume Slider */}
      <div>
        <div className="flex justify-between text-xs text-text-muted mb-1">
          <span>Quiet</span>
          <span>Volume: {volume}</span>
          <span>Loud</span>
        </div>
        <input
          type="range"
          min="-50"
          max="50"
          value={parseValue(volume)}
          onChange={(e) => onVolumeChange(formatValue(parseInt(e.target.value), '%'))}
          className="w-full h-2 bg-terminal-border rounded-lg appearance-none cursor-pointer accent-accent-primary"
        />
      </div>

      {/* Pitch Slider */}
      <div>
        <div className="flex justify-between text-xs text-text-muted mb-1">
          <span>Lower</span>
          <span>Pitch: {pitch}</span>
          <span>Higher</span>
        </div>
        <input
          type="range"
          min="-50"
          max="50"
          value={parseValue(pitch)}
          onChange={(e) => onPitchChange(formatValue(parseInt(e.target.value), 'Hz'))}
          className="w-full h-2 bg-terminal-border rounded-lg appearance-none cursor-pointer accent-accent-primary"
        />
      </div>
    </div>
  )

  if (!collapsible) {
    return content
  }

  return (
    <div className="border border-terminal-border rounded-lg">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-terminal-bg/50 transition-colors"
      >
        <div className="flex items-center gap-2 text-sm">
          <Gauge className="w-4 h-4 text-accent-primary" />
          <span>Voice Parameters</span>
          {(parseValue(rate) !== 0 || parseValue(volume) !== 0 || parseValue(pitch) !== 0) && (
            <span className="text-xs text-text-muted">
              (Rate: {rate}, Vol: {volume}, Pitch: {pitch})
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-text-muted" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-muted" />
        )}
      </button>
      {isExpanded && <div className="p-3 pt-0 border-t border-terminal-border">{content}</div>}
    </div>
  )
}
