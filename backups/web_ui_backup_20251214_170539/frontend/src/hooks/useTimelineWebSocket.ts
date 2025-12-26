import { useEffect, useRef, useCallback, useState } from 'react'
import { WS_BASE_URL } from '../api/client'

export interface VideoTimelineState {
  id: string
  name: string
  duration: number | null
  order: number
  timeline_start: number | null
  timeline_end: number | null
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
  onError?: (error: string) => void
}

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

  // Store callbacks in refs to avoid dependency changes causing reconnections
  const optionsRef = useRef(options)
  optionsRef.current = options

  const connect = useCallback(() => {
    if (!projectName) return

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

    const wsUrl = `${WS_BASE_URL}/ws/timeline/${encodeURIComponent(projectName)}`
    console.log('[TimelineWS] Connecting to:', wsUrl)

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      console.log('[TimelineWS] Connected')
      setIsConnected(true)
      isConnectingRef.current = false
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
  }, [projectName]) // Only depend on projectName, not callbacks

  // Connect when project changes
  useEffect(() => {
    mountedRef.current = true

    if (projectName) {
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
  }, [projectName, connect])

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

  // Send message helper
  const sendMessage = useCallback((type: string, data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }))
      return true
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
    timelineEnd: number | null
  ) => {
    return sendMessage('video_resize', {
      video_id: videoId,
      timeline_start: timelineStart,
      timeline_end: timelineEnd
    })
  }, [sendMessage])

  // Update BGM track
  const updateBGMTrack = useCallback((
    trackId: string,
    updates: Partial<{
      start_time: number
      end_time: number
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
    requestState,
    ping,
    reconnect: connect
  }
}
