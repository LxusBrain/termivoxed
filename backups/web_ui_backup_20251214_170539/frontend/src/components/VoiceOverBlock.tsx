import { AlertTriangle, Mic } from 'lucide-react'
import clsx from 'clsx'
import type { Segment } from '../types'
import { getAudioDuration, hasVoiceOverContent, formatOvershoot } from '../utils/voiceOverUtils'

interface VoiceOverBlockProps {
  segment: Segment
  duration: number // timeline duration for percentage calculation
  videoOffset: number // offset for this segment's video in combined timeline (0 for single video)
  isSelected: boolean
  onClick: () => void
  hasOvershoot: boolean
  overshootAmount: number // seconds
  overlapsWith: string[] // segment names this overlaps with
}

export default function VoiceOverBlock({
  segment,
  duration,
  videoOffset,
  isSelected,
  onClick,
  hasOvershoot,
  overshootAmount,
  overlapsWith,
}: VoiceOverBlockProps) {
  const hasContent = hasVoiceOverContent(segment)
  const audioDuration = getAudioDuration(segment)
  const segmentDuration = segment.end_time - segment.start_time

  // Calculate absolute position in timeline (videoOffset + segment's relative time)
  const absoluteStartTime = videoOffset + segment.start_time

  // Calculate positions as percentages of total timeline duration
  const leftPercent = (absoluteStartTime / duration) * 100
  const segmentWidthPercent = (segmentDuration / duration) * 100
  const audioWidthPercent = (audioDuration / duration) * 100

  // Minimum visual width (in percentage) for clickability
  const minWidthPercent = 1
  const displayWidthPercent = Math.max(segmentWidthPercent, minWidthPercent)

  // Overshoot extends beyond segment - but clamp to not extend past timeline end
  const maxOvershootPercent = Math.max(0, 100 - leftPercent - displayWidthPercent)
  const rawOvershootWidthPercent = hasOvershoot ? ((overshootAmount / duration) * 100) : 0
  const overshootWidthPercent = Math.min(rawOvershootWidthPercent, maxOvershootPercent)

  const hasWarnings = hasOvershoot || overlapsWith.length > 0

  // Build tooltip text
  const getTooltipText = (): string => {
    const parts: string[] = []
    parts.push(segment.name)

    if (!hasContent) {
      parts.push('No script')
    } else {
      parts.push(`Audio: ${audioDuration.toFixed(1)}s`)
      if (hasOvershoot) {
        parts.push(`Exceeds by ${formatOvershoot(overshootAmount)}`)
      }
      if (overlapsWith.length > 0) {
        parts.push(`Overlaps: ${overlapsWith.join(', ')}`)
      }
    }

    return parts.join(' | ')
  }

  return (
    <div
      className="absolute top-1 bottom-1 group/voblock"
      style={{
        left: `${leftPercent}%`,
        width: `${displayWidthPercent + overshootWidthPercent}%`,
      }}
    >
      {/* Main block - shows segment duration */}
      <div
        onClick={onClick}
        title={getTooltipText()}
        className={clsx(
          'absolute top-0 bottom-0 left-0 rounded cursor-pointer transition-all',
          'flex items-center overflow-hidden',
          hasContent
            ? isSelected
              ? 'bg-amber-500/80 border border-amber-300 ring-2 ring-amber-400/50'
              : 'bg-amber-500/60 border border-amber-400 hover:bg-amber-500/70'
            : 'bg-amber-500/20 border border-amber-400/50 border-dashed hover:bg-amber-500/30'
        )}
        style={{
          width: hasOvershoot
            ? `${(segmentWidthPercent / (displayWidthPercent + overshootWidthPercent)) * 100}%`
            : '100%',
        }}
      >
        {/* Content area */}
        <div className="flex-1 px-1.5 min-w-0 flex items-center gap-1">
          {/* Mic icon for segments with audio */}
          {hasContent && segment.audio_path && (
            <Mic className="w-3 h-3 text-amber-200 flex-shrink-0" />
          )}

          {/* Segment name or "No script" */}
          <span className={clsx(
            'text-xs truncate font-medium',
            hasContent ? 'text-white' : 'text-amber-300/70'
          )}>
            {hasContent ? segment.name : 'No script'}
          </span>
        </div>

        {/* Warning icons */}
        {hasWarnings && (
          <div className="flex items-center gap-0.5 px-1 flex-shrink-0">
            {hasOvershoot && (
              <span title={`Audio exceeds segment by ${formatOvershoot(overshootAmount)}`}>
                <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
              </span>
            )}
            {overlapsWith.length > 0 && (
              <span title={`Overlaps with: ${overlapsWith.join(', ')}`}>
                <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
              </span>
            )}
          </div>
        )}
      </div>

      {/* Overshoot indicator - extends past segment end */}
      {hasOvershoot && overshootWidthPercent > 0 && (
        <div
          onClick={onClick}
          className={clsx(
            'absolute top-0 bottom-0 rounded-r cursor-pointer',
            'bg-red-500/30 border border-red-400/60 border-l-0',
            'hover:bg-red-500/40 transition-colors'
          )}
          style={{
            left: `${(segmentWidthPercent / (displayWidthPercent + overshootWidthPercent)) * 100}%`,
            width: `${(overshootWidthPercent / (displayWidthPercent + overshootWidthPercent)) * 100}%`,
          }}
          title={`Audio overshoot: ${formatOvershoot(overshootAmount)}`}
        >
          {/* Striped pattern for overshoot */}
          <div
            className="absolute inset-0 opacity-30"
            style={{
              backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(255,255,255,0.1) 3px, rgba(255,255,255,0.1) 6px)',
            }}
          />
        </div>
      )}

      {/* Audio duration indicator bar (subtle line showing actual audio length) */}
      {hasContent && !hasOvershoot && audioDuration > 0 && (
        <div
          className="absolute bottom-0 left-0 h-0.5 bg-amber-300/60 rounded-full"
          style={{
            width: `${Math.min((audioWidthPercent / displayWidthPercent) * 100, 100)}%`,
          }}
          title={`Audio duration: ${audioDuration.toFixed(1)}s`}
        />
      )}
    </div>
  )
}
