import type { Segment } from '../types'

/**
 * Voice Over timing information for overlap detection
 */
export interface VoiceOverTiming {
  segmentId: string
  segmentName: string
  videoId: string
  startTime: number
  segmentEndTime: number
  audioEndTime: number // startTime + estimated_audio_duration
}

/**
 * Estimate audio duration from text using word count
 * Fallback when estimated_audio_duration is not available
 * Average speaking rate: ~150 words per minute = 0.4s per word
 */
export function estimateAudioDuration(text: string): number {
  if (!text || text.trim().length === 0) return 0
  const wordCount = text.trim().split(/\s+/).length
  return wordCount * 0.4 // 0.4 seconds per word average
}

/**
 * Get the audio duration for a segment
 * Uses estimated_audio_duration if available, otherwise calculates from text
 */
export function getAudioDuration(segment: Segment): number {
  if (segment.estimated_audio_duration !== null && segment.estimated_audio_duration > 0) {
    return segment.estimated_audio_duration
  }
  return estimateAudioDuration(segment.text)
}

/**
 * Check if a segment's audio overshoots its duration
 */
export function hasAudioOvershoot(segment: Segment): boolean {
  const audioDuration = getAudioDuration(segment)
  const segmentDuration = segment.end_time - segment.start_time
  return audioDuration > segmentDuration
}

/**
 * Get the overshoot amount in seconds
 * Returns 0 if audio fits within segment
 */
export function getOvershootAmount(segment: Segment): number {
  const audioDuration = getAudioDuration(segment)
  const segmentDuration = segment.end_time - segment.start_time
  const overshoot = audioDuration - segmentDuration
  return overshoot > 0 ? overshoot : 0
}

/**
 * Detect voice over audio overlaps between segments
 * Returns a map of segment IDs to arrays of segment names they overlap with
 * Note: Only compares segments within the same video (different videos have independent timelines)
 */
export function detectVoiceOverOverlaps(segments: Segment[]): Map<string, string[]> {
  const overlaps = new Map<string, string[]>()

  // Group segments by video_id first (segments from different videos can't overlap)
  // Use 'unknown' for segments without video_id (legacy segments)
  const segmentsByVideo = new Map<string, Segment[]>()
  for (const seg of segments) {
    const videoId = seg.video_id ?? 'unknown'
    if (!segmentsByVideo.has(videoId)) {
      segmentsByVideo.set(videoId, [])
    }
    segmentsByVideo.get(videoId)!.push(seg)
  }

  // Process each video's segments independently
  for (const [videoId, videoSegments] of segmentsByVideo) {
    // Sort segments by start time within this video
    const sortedSegments = [...videoSegments].sort((a, b) => a.start_time - b.start_time)

    // Build timing info for each segment
    const timings: VoiceOverTiming[] = sortedSegments.map(seg => ({
      segmentId: seg.id,
      segmentName: seg.name,
      videoId: videoId,
      startTime: seg.start_time,
      segmentEndTime: seg.end_time,
      audioEndTime: seg.start_time + getAudioDuration(seg)
    }))

    // Check each segment against subsequent segments (within same video)
    for (let i = 0; i < timings.length; i++) {
      const current = timings[i]
      const overlapsWith: string[] = []

      // Only check subsequent segments
      for (let j = i + 1; j < timings.length; j++) {
        const next = timings[j]

        // Check if current segment's audio extends into next segment's audio time
        // An overlap occurs when:
        // 1. Current audio end time > next audio start time
        // AND
        // 2. Current audio start time < next audio end time
        if (current.audioEndTime > next.startTime) {
          overlapsWith.push(next.segmentName)
        }
      }

      if (overlapsWith.length > 0) {
        overlaps.set(current.segmentId, overlapsWith)
      }
    }
  }

  return overlaps
}

/**
 * Check if a segment has any voice over content (text)
 */
export function hasVoiceOverContent(segment: Segment): boolean {
  return segment.text !== null && segment.text.trim().length > 0
}

/**
 * Format overshoot amount for display
 */
export function formatOvershoot(seconds: number): string {
  if (seconds < 1) {
    return `${Math.round(seconds * 10) / 10}s`
  }
  return `${Math.round(seconds * 10) / 10}s`
}
