import { useEffect, useRef, useCallback, useState } from 'react'
import { WS_BASE_URL } from '../api/client'
import { useAuthStore } from '../stores/authStore'

export interface VideoTimelineState {
  id: string
  name: string
  duration: number | null
  order: number
  timeline_start: number | null
  timeline_end: number | null
  source_start: number  // Where to start reading from source video
  source_end: number | null  // Where to stop reading from source video
  width: number | null
  height: number | null
  orientation: string | null
}

export interface BGMTimelineState {
  id: string
  name: string
  start_time: number
  end_time: number
  volume: number
  fade_in: number
  fade_out: number
  loop: boolean
  muted: boolean
  duration: number | null
}

export interface TimelineState {
  videos: VideoTimelineState[]
  bgm_tracks: BGMTimelineState[]
  active_video_id: string | null
}

interface WebSocketMessage {
  type: string
  data?: unknown
  message?: string
  success?: boolean
}

interface UseTimelineWebSocketOptions {
  onStateUpdate?: (state: TimelineState) => void
  onVideoPositionUpdate?: (data: { video_id: string; timeline_start: number | null; timeline_end: number | null }) => void
  onBGMUpdate?: (data: { track_id: string; start_time: number; end_time: number; volume: number }) => void
  onSegmentUpdate?: (data: { segment_id: string; start_time: number; end_time: number; audio_offset: number }) => void
  onError?: (error: string) => void
}

// Message queue item for offline/failed messages
interface QueuedMessage {
  type: string
  data: Record<string, unknown>
  timestamp: number
  retries: number
}

const MAX_QUEUE_SIZE = 50
const MESSAGE_EXPIRY_MS = 30000 // Discard messages older than 30 seconds

export function useTimelineWebSocket(
  projectName: string | null,
  options: UseTimelineWebSocketOptions = {}
) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [lastState, setLastState] = useState<TimelineState | null>(null)
  const isConnectingRef = useRef(false)
  const mountedRef = useRef(true)
  const messageQueueRef = useRef<QueuedMessage[]>([])

  // Get auth token from store
  const token = useAuthStore((state) => state.token)

  // Store callbacks in refs to avoid dependency changes causing reconnections
  const optionsRef = useRef(options)
  optionsRef.current = options

  const connect = useCallback(() => {
    if (!projectName) return

    // Require authentication token
    if (!token) {
      console.log('[TimelineWS] No auth token available, skipping connection')
      return
    }

    // Prevent multiple simultaneous connection attempts
    if (isConnectingRef.current) {
      console.log('[TimelineWS] Already connecting, skipping...')
      return
    }

    // Check if already connected
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('[TimelineWS] Already connected, skipping...')
      return
    }

    isConnectingRef.current = true

    // Close existing connection cleanly
    if (wsRef.current) {
      wsRef.current.close(1000, 'Reconnecting')
      wsRef.current = null
    }

    // Include auth token as query parameter
    const wsUrl = `${WS_BASE_URL}/ws/timeline/${encodeURIComponent(projectName)}?token=${encodeURIComponent(token)}`
    console.log('[TimelineWS] Connecting to:', wsUrl.replace(token, '[REDACTED]'))

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      console.log('[TimelineWS] Connected')
      setIsConnected(true)
      isConnectingRef.current = false

      // Flush queued messages on reconnect
      const now = Date.now()
      const queue = messageQueueRef.current
      messageQueueRef.current = []

      let flushedCount = 0
      for (const msg of queue) {
        // Skip expired messages
        if (now - msg.timestamp > MESSAGE_EXPIRY_MS) {
          console.log(`[TimelineWS] Discarding expired queued message: ${msg.type}`)
          continue
        }

        // Send with latest state
        try {
          ws.send(JSON.stringify({ type: msg.type, data: msg.data }))
          flushedCount++
        } catch (e) {
          console.error('[TimelineWS] Failed to flush queued message:', e)
        }
      }

      if (flushedCount > 0) {
        console.log(`[TimelineWS] Flushed ${flushedCount} queued messages`)
      }
    }

    ws.onmessage = (event) => {
      if (!mountedRef.current) return
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        console.log('[TimelineWS] Received:', message.type)

        switch (message.type) {
          case 'state':
            const state = message.data as TimelineState
            setLastState(state)
            optionsRef.current.onStateUpdate?.(state)
            break

          case 'video_position_update':
            optionsRef.current.onVideoPositionUpdate?.(message.data as { video_id: string; timeline_start: number | null; timeline_end: number | null })
            break

          case 'video_resize_update':
            optionsRef.current.onVideoPositionUpdate?.(message.data as { video_id: string; timeline_start: number | null; timeline_end: number | null })
            break

          case 'bgm_update':
            optionsRef.current.onBGMUpdate?.(message.data as { track_id: string; start_time: number; end_time: number; volume: number })
            break

          case 'segment_update':
            optionsRef.current.onSegmentUpdate?.(message.data as { segment_id: string; start_time: number; end_time: number; audio_offset: number })
            break

          case 'ack':
            // Acknowledgment of our update - already applied optimistically
            break

          case 'error':
            console.error('[TimelineWS] Error:', message.message)
            optionsRef.current.onError?.(message.message || 'Unknown error')
            break

          case 'pong':
            // Heartbeat response
            break
        }
      } catch (e) {
        console.error('[TimelineWS] Failed to parse message:', e)
      }
    }

    ws.onclose = (event) => {
      if (!mountedRef.current) return
      console.log('[TimelineWS] Disconnected:', event.code, event.reason)
      setIsConnected(false)
      isConnectingRef.current = false

      // Attempt to reconnect after 3 seconds (unless intentional close or unmounted)
      if (event.code !== 1000 && mountedRef.current) {
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
        }
        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) {
            console.log('[TimelineWS] Attempting reconnect...')
            connect()
          }
        }, 3000)
      }
    }

    ws.onerror = (error) => {
      console.error('[TimelineWS] WebSocket error:', error)
      isConnectingRef.current = false
      optionsRef.current.onError?.('WebSocket connection error')
    }
  }, [projectName, token]) // Depend on projectName and token for authentication

  // Connect when project or token changes
  useEffect(() => {
    mountedRef.current = true

    if (projectName && token) {
      // Small delay to prevent rapid reconnections during React StrictMode
      const connectTimeout = setTimeout(() => {
        if (mountedRef.current) {
          connect()
        }
      }, 100)

      return () => {
        clearTimeout(connectTimeout)
      }
    }
  }, [projectName, token, connect])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting')
        wsRef.current = null
      }
    }
  }, [])

  // Send message helper with queuing for offline messages
  const sendMessage = useCallback((type: string, data: Record<string, unknown>, queueIfOffline = true) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type, data }))
        return true
      } catch (e) {
        console.error('[TimelineWS] Send error:', e)
        // Fall through to queue the message
      }
    }

    // Queue message for later if we should queue
    if (queueIfOffline) {
      // Don't queue if queue is full (prevent memory issues)
      if (messageQueueRef.current.length < MAX_QUEUE_SIZE) {
        messageQueueRef.current.push({
          type,
          data,
          timestamp: Date.now(),
          retries: 0
        })
        console.log(`[TimelineWS] Queued message (offline): ${type}`)
        return 'queued'
      } else {
        console.warn('[TimelineWS] Message queue full, dropping message')
        return false
      }
    }

    console.warn('[TimelineWS] Cannot send - not connected')
    return false
  }, [])

  // Update video position (for drag/move)
  const updateVideoPosition = useCallback((
    videoId: string,
    timelineStart: number | null,
    timelineEnd: number | null
  ) => {
    return sendMessage('video_position', {
      video_id: videoId,
      timeline_start: timelineStart,
      timeline_end: timelineEnd
    })
  }, [sendMessage])

  // Update video resize (for trimming)
  const updateVideoResize = useCallback((
    videoId: string,
    timelineStart: number | null,
    timelineEnd: number | null,
    sourceStart?: number,
    sourceEnd?: number | null
  ) => {
    return sendMessage('video_resize', {
      video_id: videoId,
      timeline_start: timelineStart,
      timeline_end: timelineEnd,
      source_start: sourceStart,
      source_end: sourceEnd
    })
  }, [sendMessage])

  // Update BGM track
  const updateBGMTrack = useCallback((
    trackId: string,
    updates: Partial<{
      start_time: number
      end_time: number
      audio_offset: number
      volume: number
      fade_in: number
      fade_out: number
      loop: boolean
      muted: boolean
    }>
  ) => {
    return sendMessage('bgm_update', {
      track_id: trackId,
      ...updates
    })
  }, [sendMessage])

  // Update segment (position, audio_offset)
  const updateSegment = useCallback((
    segmentId: string,
    updates: Partial<{
      start_time: number
      end_time: number
      audio_offset: number
    }>
  ) => {
    return sendMessage('segment_update', {
      segment_id: segmentId,
      ...updates
    })
  }, [sendMessage])

  // Request current state
  const requestState = useCallback(() => {
    return sendMessage('get_state', {})
  }, [sendMessage])

  // Ping for keepalive
  const ping = useCallback(() => {
    return sendMessage('ping', {})
  }, [sendMessage])

  return {
    isConnected,
    lastState,
    updateVideoPosition,
    updateVideoResize,
    updateBGMTrack,
    updateSegment,
    requestState,
    ping,
    reconnect: connect
  }
}
