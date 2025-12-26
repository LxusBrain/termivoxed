import { AlertTriangle, Mic, Play, Pause } from 'lucide-react'
import clsx from 'clsx'
import type { Segment } from '../types'
import { getAudioDuration, hasVoiceOverContent, formatOvershoot } from '../utils/voiceOverUtils'

type DragMode = 'move' | 'resize-start' | 'resize-end'

interface VoiceOverBlockProps {
  segment: Segment
  duration: number // timeline duration for percentage calculation
  videoOffset: number // offset for this segment's video in combined timeline (0 for single video)
  isSelected: boolean
  onClick: () => void
  onPlayPreview?: () => void
  onPausePreview?: () => void // New: callback to pause playback
  isPlayingPreview?: boolean // New: whether this segment is currently being previewed
  onDragStart?: (e: React.MouseEvent, mode: DragMode) => void
  isDragging?: boolean
  previewTimes?: { start: number; end: number; audioOffset?: number }
  hasOvershoot: boolean
  overshootAmount: number
  overlapsWith: string[]
  isMultiVideo?: boolean
  rowIndex?: number // Row index for stacked display (0-based)
  rowHeight?: number // Height of each row in pixels
}

export default function VoiceOverBlock({
  segment,
  duration,
  videoOffset,
  isSelected,
  onClick,
  onPlayPreview,
  onPausePreview,
  isPlayingPreview = false,
  onDragStart,
  isDragging = false,
  previewTimes,
  hasOvershoot,
  overshootAmount,
  overlapsWith,
  isMultiVideo = false,
  rowIndex = 0,
  rowHeight = 32,
}: VoiceOverBlockProps) {
  const hasContent = hasVoiceOverContent(segment)
  const audioDuration = getAudioDuration(segment)

  // Use preview times during drag
  const startTime = previewTimes?.start ?? segment.start_time
  const endTime = previewTimes?.end ?? segment.end_time
  const audioOffset = previewTimes?.audioOffset ?? segment.audio_offset ?? 0
  const segmentDuration = endTime - startTime

  // Calculate trim states
  const isTrimmedFromStart = audioOffset > 0.1
  const remainingAudio = Math.max(0, audioDuration - audioOffset)
  const isTrimmedFromEnd = hasContent && segmentDuration < remainingAudio - 0.1
  const unusedAtEnd = Math.max(0, remainingAudio - segmentDuration)

  // Calculate position
  const absoluteStartTime = videoOffset + startTime
  const leftPercent = (absoluteStartTime / duration) * 100

  // For the visual, show the FULL audio as the block width, with active portion highlighted
  // This helps users see what they're working with
  const activeWidthPercent = (segmentDuration / duration) * 100

  // If trimmed, we want to show the trimmed portions visually
  const trimmedStartWidthPercent = isTrimmedFromStart ? (audioOffset / duration) * 100 : 0
  const trimmedEndWidthPercent = isTrimmedFromEnd ? (unusedAtEnd / duration) * 100 : 0

  // Total block width includes trimmed portions for visual reference
  const totalVisualWidth = activeWidthPercent + trimmedStartWidthPercent + trimmedEndWidthPercent
  const displayWidthPercent = Math.max(totalVisualWidth, 1) // min 1% for visibility

  // Adjust left position to account for trimmed start portion
  const adjustedLeftPercent = leftPercent - trimmedStartWidthPercent

  // Warnings
  const showOverlapWarning = !isMultiVideo && overlapsWith.length > 0
  const hasWarnings = hasOvershoot || showOverlapWarning

  // Proportions within the block
  const trimmedStartPortion = trimmedStartWidthPercent / displayWidthPercent * 100
  const activePortion = activeWidthPercent / displayWidthPercent * 100
  const trimmedEndPortion = trimmedEndWidthPercent / displayWidthPercent * 100

  const getTooltipText = (): string => {
    const parts: string[] = [segment.name]
    if (!hasContent) {
      parts.push('No script')
    } else {
      parts.push(`Audio: ${audioDuration.toFixed(1)}s`)
      parts.push(`Active: ${segmentDuration.toFixed(1)}s`)
      if (isTrimmedFromStart) parts.push(`Start trim: ${audioOffset.toFixed(1)}s`)
      if (isTrimmedFromEnd) parts.push(`End trim: ${unusedAtEnd.toFixed(1)}s`)
      if (hasOvershoot) parts.push(`Exceeds by ${formatOvershoot(overshootAmount)}`)
    }
    return parts.join(' | ')
  }

  const handleMouseDown = (e: React.MouseEvent, mode: DragMode) => {
    e.preventDefault()
    e.stopPropagation()
    if (onDragStart) onDragStart(e, mode)
  }

  return (
    <div
      className={clsx(
        'absolute group select-none',
        isDragging && 'z-50'
      )}
      style={{
        top: `${rowIndex * rowHeight + 4}px`,
        height: `${rowHeight - 8}px`,
        left: `${Math.max(0, adjustedLeftPercent)}%`,
        width: `${displayWidthPercent}%`,
        minWidth: '50px',
      }}
    >
      {/* Container for all portions */}
      <div className="absolute inset-0 flex rounded overflow-hidden">

        {/* Trimmed START portion - striped/faded */}
        {isTrimmedFromStart && trimmedStartPortion > 0 && (
          <div
            className="h-full relative border border-amber-600/30 rounded-l"
            style={{
              width: `${trimmedStartPortion}%`,
              background: 'repeating-linear-gradient(45deg, rgba(217,119,6,0.1), rgba(217,119,6,0.1) 2px, rgba(217,119,6,0.2) 2px, rgba(217,119,6,0.2) 4px)',
            }}
            title={`Trimmed: ${audioOffset.toFixed(1)}s from start`}
          >
            <span className="absolute inset-0 flex items-center justify-center text-[8px] text-amber-500/60 font-mono">
              -{audioOffset.toFixed(1)}s
            </span>
          </div>
        )}

        {/* ACTIVE portion - solid color */}
        <div
          onClick={(e) => { e.stopPropagation(); onClick() }}
          title={getTooltipText()}
          className={clsx(
            'h-full relative flex items-center',
            isDragging ? 'cursor-grabbing shadow-lg' : '',
            hasContent
              ? isSelected
                ? 'bg-amber-600/40 border-y-2 border-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.3)]'
                : 'bg-gradient-to-r from-amber-600/30 to-amber-700/30 border-y border-amber-600/50 hover:border-amber-500/70'
              : 'bg-amber-500/15 border-y border-amber-400/30 border-dashed',
            // Round corners based on trim state
            !isTrimmedFromStart && 'rounded-l border-l-2',
            !isTrimmedFromEnd && 'rounded-r border-r-2',
            isTrimmedFromStart && 'border-l border-l-amber-400/50',
            isTrimmedFromEnd && 'border-r border-r-amber-400/50',
          )}
          style={{ width: `${activePortion}%` }}
        >
          {/* Left resize handle */}
          {onDragStart && (
            <div
              className="absolute left-0 top-0 bottom-0 w-3 cursor-ew-resize z-20 flex items-center justify-center hover:bg-amber-500/40 active:bg-amber-500/60"
              onMouseDown={(e) => handleMouseDown(e, 'resize-start')}
            >
              <div className="w-0.5 h-5 bg-amber-400/80 rounded" />
            </div>
          )}

          {/* Content */}
          <div
            className={clsx(
              'flex-1 h-full flex items-center gap-1 px-3',
              onDragStart ? (isDragging ? 'cursor-grabbing' : 'cursor-grab') : 'cursor-pointer'
            )}
            onMouseDown={(e) => handleMouseDown(e, 'move')}
          >
            {hasContent && (onPlayPreview || onPausePreview) && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  if (isPlayingPreview && onPausePreview) {
                    onPausePreview()
                  } else if (onPlayPreview) {
                    onPlayPreview()
                  }
                }}
                onMouseDown={(e) => e.stopPropagation()}
                className={clsx(
                  "p-0.5 rounded shrink-0 transition-colors",
                  isPlayingPreview
                    ? "bg-amber-500/40 text-amber-200 hover:bg-amber-500/60"
                    : "hover:bg-amber-600/40 text-amber-300"
                )}
                title={isPlayingPreview ? "Pause preview" : "Play preview"}
              >
                {isPlayingPreview ? (
                  <Pause className="w-3 h-3 fill-current" />
                ) : (
                  <Play className="w-3 h-3 fill-current" />
                )}
              </button>
            )}

            {hasContent && segment.audio_path && (
              <Mic className="w-3 h-3 text-amber-300 shrink-0" />
            )}

            <span className={clsx(
              'text-[10px] truncate flex-1 font-medium',
              hasContent ? 'text-amber-200' : 'text-amber-300/50'
            )}>
              {hasContent ? segment.name : 'No script'}
            </span>

            {hasWarnings && (
              <div className="flex items-center gap-0.5 shrink-0">
                {hasOvershoot && (
                  <span title={`Exceeds by ${formatOvershoot(overshootAmount)}`}>
                    <AlertTriangle className="w-3 h-3 text-orange-400" />
                  </span>
                )}
                {showOverlapWarning && (
                  <span title={`Overlaps: ${overlapsWith.join(', ')}`}>
                    <AlertTriangle className="w-3 h-3 text-red-400" />
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Right resize handle */}
          {onDragStart && (
            <div
              className="absolute right-0 top-0 bottom-0 w-3 cursor-ew-resize z-20 flex items-center justify-center hover:bg-amber-500/40 active:bg-amber-500/60"
              onMouseDown={(e) => handleMouseDown(e, 'resize-end')}
            >
              <div className="w-0.5 h-5 bg-amber-400/80 rounded" />
            </div>
          )}

          {/* Audio progress bar at bottom */}
          {hasContent && audioDuration > 0 && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-black/30">
              <div
                className="h-full bg-green-400/70"
                style={{ width: `${Math.min((segmentDuration / remainingAudio) * 100, 100)}%` }}
              />
            </div>
          )}
        </div>

        {/* Trimmed END portion - striped/faded */}
        {isTrimmedFromEnd && trimmedEndPortion > 0 && (
          <div
            className="h-full relative border border-amber-600/30 rounded-r"
            style={{
              width: `${trimmedEndPortion}%`,
              background: 'repeating-linear-gradient(-45deg, rgba(217,119,6,0.1), rgba(217,119,6,0.1) 2px, rgba(217,119,6,0.2) 2px, rgba(217,119,6,0.2) 4px)',
            }}
            title={`Trimmed: ${unusedAtEnd.toFixed(1)}s from end`}
          >
            <span className="absolute inset-0 flex items-center justify-center text-[8px] text-amber-500/60 font-mono">
              -{unusedAtEnd.toFixed(1)}s
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
