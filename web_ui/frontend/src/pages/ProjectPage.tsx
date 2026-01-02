import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  Sparkles,
  Download,
  Video,
  Loader2,
  Plus,
  AlertTriangle,
  Check,
  Folder,
  FolderOpen,
  ChevronUp,
  ChevronDown,
  Clock,
  Trash2,
  GripVertical,
  FileVideo,
  Film,
  Info,
  Wifi,
  WifiOff,
  RefreshCw,
  Monitor,
  Smartphone,
  Square,
} from 'lucide-react'
import { projectsApi, segmentsApi, exportApi, videosApi, ttsApi, WS_BASE_URL, type BGMTrack } from '../api/client'
import { useAppStore } from '../stores/appStore'
import { useAuthStore } from '../stores/authStore'
import { useDebugStore } from '../stores/debugStore'
import { useProviderStatus } from '../hooks/useProviderStatus'
import VideoPlayer from '../components/VideoPlayer'
import MultiVideoPlayer from '../components/MultiVideoPlayer'
import Timeline from '../components/Timeline'
import SegmentEditor from '../components/SegmentEditor'
import AIScriptGenerator from '../components/AIScriptGenerator'
import AddSegmentModal from '../components/AddSegmentModal'
import type { Project, VideoInfo } from '../types'
import toast from 'react-hot-toast'
import clsx from 'clsx'

interface ValidationIssue {
  type: string
  severity: 'error' | 'warning'
  message: string
  segment_id?: string
}

interface ValidationResult {
  valid: boolean
  can_export: boolean
  segment_count: number
  bgm_count: number
  issues: ValidationIssue[]
  overlaps: number
  timing_warnings: number
  empty_segments: number
}

interface ExportProgressData {
  stage: string
  message: string
  progress: number
  current_step?: number
  total_steps?: number
  current_segment?: string
  current_voice?: string
  detail?: string
  output_path?: string
  // ETA and timing info
  eta_seconds?: number
  eta_formatted?: string
  elapsed_seconds?: number
  processing_speed?: number
}

interface DirectoryBrowserState {
  currentPath: string
  parentPath: string | null
  directories: string[]
  canGoUp: boolean
}

interface VideoItem {
  id: string
  name: string
  path: string
  order: number
  duration?: number
  width?: number
  height?: number
  orientation?: string
  segments_count: number
  file_exists: boolean
}

// Video Manager Panel Component
function VideoManagerPanel({
  projectName,
  videos,
  activeVideoId,
  onRefresh,
}: {
  projectName: string
  videos: VideoItem[]
  activeVideoId: string | null
  onRefresh: () => void
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [showAddVideo, setShowAddVideo] = useState(false)
  const [videoToDelete, setVideoToDelete] = useState<VideoItem | null>(null)
  const [uploadingVideo, setUploadingVideo] = useState(false)
  const [videoToRelink, setVideoToRelink] = useState<VideoItem | null>(null)
  const [relinkingVideo, setRelinkingVideo] = useState(false)

  // Get availability state from store
  const { resetAvailabilityState } = useAppStore()

  // Count missing videos
  const missingVideos = videos.filter(v => !v.file_exists)
  const hasMissingVideos = missingVideos.length > 0

  // Re-link video mutation
  const relinkMutation = useMutation({
    mutationFn: async ({ videoId, file }: { videoId: string; file: File }) => {
      // Upload the new video file
      const uploadResponse = await videosApi.upload(file)
      const uploadedPath = uploadResponse.data.path
      // Update the video path
      return videosApi.replacePath(projectName, videoId, uploadedPath)
    },
    onSuccess: () => {
      toast.success('Video re-linked successfully')
      setVideoToRelink(null)
      setRelinkingVideo(false)
      // Reset availability state to trigger re-check
      resetAvailabilityState()
      onRefresh()
    },
    onError: () => {
      toast.error('Failed to re-link video')
      setRelinkingVideo(false)
    },
  })

  // Handle re-link file upload
  const handleRelinkUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !videoToRelink) return

    setRelinkingVideo(true)
    relinkMutation.mutate({ videoId: videoToRelink.id, file })
  }

  // Set active video mutation
  const setActiveMutation = useMutation({
    mutationFn: (videoId: string) => projectsApi.setActiveVideo(projectName, videoId),
    onSuccess: () => {
      toast.success('Active video changed')
      onRefresh()
    },
    onError: () => toast.error('Failed to change active video'),
  })

  // Remove video mutation
  const removeMutation = useMutation({
    mutationFn: (videoId: string) => projectsApi.removeVideo(projectName, videoId),
    onSuccess: () => {
      toast.success('Video removed')
      setVideoToDelete(null)
      onRefresh()
    },
    onError: () => toast.error('Failed to remove video'),
  })

  // Handle file upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadingVideo(true)
    try {
      // Upload the video file
      const uploadResponse = await videosApi.upload(file)
      const uploadedPath = uploadResponse.data.path
      const uploadedOrientation = uploadResponse.data.orientation
      const uploadedWidth = uploadResponse.data.width
      const uploadedHeight = uploadResponse.data.height

      // Add to project
      const addResponse = await projectsApi.addVideo(projectName, uploadedPath, file.name.replace(/\.[^/.]+$/, ''))

      // Show video info in success message
      const dimensionInfo = uploadedWidth && uploadedHeight
        ? ` (${uploadedWidth}×${uploadedHeight}, ${uploadedOrientation || 'unknown'})`
        : ''
      toast.success(`Video added${dimensionInfo}`)

      // Check for compatibility warnings
      const warnings = addResponse.data.compatibility_warnings
      if (warnings && warnings.length > 0) {
        // Show compatibility warning toast that stays longer
        toast.error(
          <div>
            <strong className="flex items-center gap-1"><AlertTriangle className="w-4 h-4" /> Video Compatibility Warning</strong>
            <ul className="mt-1 text-sm list-disc list-inside">
              {warnings.slice(0, 3).map((w: string, i: number) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
            <p className="mt-1 text-xs">Videos with different orientations may not export correctly.</p>
          </div>,
          { duration: 8000 }
        )
      }

      setShowAddVideo(false)
      onRefresh()
    } catch {
      toast.error('Failed to add video')
    } finally {
      setUploadingVideo(false)
    }
  }

  // Sort videos by order
  const sortedVideos = [...videos].sort((a, b) => a.order - b.order)

  return (
    <div className="border-b border-terminal-border bg-terminal-surface">
      {/* Header - always visible */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2 flex items-center justify-between hover:bg-terminal-elevated transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <Film className="w-4 h-4 text-accent-red" />
          <span className="text-sm font-medium">Videos ({videos.length})</span>
          {hasMissingVideos && (
            <span className="flex items-center gap-1 text-xs text-yellow-500">
              <AlertTriangle className="w-3 h-3" />
              {missingVideos.length} missing
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation()
              setShowAddVideo(true)
            }}
            className="p-1 rounded hover:bg-terminal-bg text-text-muted hover:text-accent-red"
            title="Add video"
          >
            <Plus className="w-4 h-4" />
          </button>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-text-muted" />
          ) : (
            <ChevronDown className="w-4 h-4 text-text-muted" />
          )}
        </div>
      </div>

      {/* Expanded content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-3 space-y-2">
              {sortedVideos.map((video) => (
                <div
                  key={video.id}
                  className={clsx(
                    'flex items-center gap-3 p-2 rounded border transition-colors',
                    video.id === activeVideoId
                      ? 'bg-accent-red/10 border-accent-red/50'
                      : 'bg-terminal-bg border-terminal-border hover:border-terminal-border-hover',
                    !video.file_exists && 'border-yellow-500/50'
                  )}
                >
                  <GripVertical className="w-4 h-4 text-text-muted cursor-grab" />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <FileVideo className={clsx(
                        'w-4 h-4',
                        video.file_exists ? 'text-accent-red' : 'text-yellow-500'
                      )} />
                      <span className="text-sm font-medium truncate">{video.name}</span>
                      {video.id === activeVideoId && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-red text-white">Active</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 text-xs text-text-muted">
                      {video.duration && (
                        <span>{Math.floor(video.duration / 60)}:{String(Math.floor(video.duration % 60)).padStart(2, '0')}</span>
                      )}
                      {video.width && video.height && (
                        <>
                          <span className="text-terminal-border">•</span>
                          <span>{video.width}×{video.height}</span>
                        </>
                      )}
                      {video.orientation && (
                        <>
                          <span className="text-terminal-border">•</span>
                          <span className={`flex items-center gap-1 ${
                            video.orientation === 'horizontal' ? 'text-blue-400' :
                            video.orientation === 'vertical' ? 'text-purple-400' :
                            'text-green-400'
                          }`}>
                            {video.orientation === 'horizontal' ? <Monitor className="w-3 h-3" /> : video.orientation === 'vertical' ? <Smartphone className="w-3 h-3" /> : <Square className="w-3 h-3" />} {video.orientation}
                          </span>
                        </>
                      )}
                      <span className="text-terminal-border">•</span>
                      <span>{video.segments_count} segments</span>
                      {!video.file_exists && (
                        <>
                          <span className="text-terminal-border">•</span>
                          <span className="text-yellow-500">File missing</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    {/* Re-link button for missing videos */}
                    {!video.file_exists && (
                      <button
                        onClick={() => setVideoToRelink(video)}
                        className="p-1.5 rounded hover:bg-yellow-500/20 text-yellow-500 hover:text-yellow-400"
                        title="Re-link video file"
                      >
                        <RefreshCw className="w-3 h-3" />
                      </button>
                    )}
                    {video.id !== activeVideoId && video.file_exists && (
                      <button
                        onClick={() => setActiveMutation.mutate(video.id)}
                        disabled={setActiveMutation.isPending}
                        className="p-1.5 rounded hover:bg-terminal-elevated text-text-muted hover:text-accent-red text-xs"
                        title="Set as active"
                      >
                        <Check className="w-3 h-3" />
                      </button>
                    )}
                    {videos.length > 1 && (
                      <button
                        onClick={() => setVideoToDelete(video)}
                        className="p-1.5 rounded hover:bg-red-500/20 text-text-muted hover:text-red-500"
                        title="Remove video"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Add Video Modal */}
      <AnimatePresence>
        {showAddVideo && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/70" onClick={() => !uploadingVideo && setShowAddVideo(false)} />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative bg-terminal-surface border border-terminal-border rounded-lg w-full max-w-md mx-4 p-6"
            >
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Plus className="w-5 h-5 text-accent-red" />
                Add Video to Project
              </h3>

              <div className="space-y-4">
                <div
                  className="border-2 border-dashed border-terminal-border rounded-lg p-8 text-center hover:border-accent-red/50 transition-colors cursor-pointer"
                  onClick={() => document.getElementById('add-video-input')?.click()}
                >
                  {uploadingVideo ? (
                    <div className="flex flex-col items-center gap-2">
                      <Loader2 className="w-8 h-8 animate-spin text-accent-red" />
                      <span className="text-sm text-text-muted">Uploading video...</span>
                    </div>
                  ) : (
                    <>
                      <FileVideo className="w-10 h-10 mx-auto text-text-muted mb-2" />
                      <p className="text-sm text-text-muted">Click to select video file</p>
                      <p className="text-xs text-text-muted mt-1">MP4, MOV, AVI, MKV, WebM</p>
                    </>
                  )}
                </div>
                <input
                  id="add-video-input"
                  type="file"
                  accept="video/*"
                  onChange={handleFileUpload}
                  className="hidden"
                  disabled={uploadingVideo}
                />
              </div>

              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setShowAddVideo(false)}
                  disabled={uploadingVideo}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {videoToDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/70" onClick={() => setVideoToDelete(null)} />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative bg-terminal-surface border border-terminal-border rounded-lg w-full max-w-md mx-4 p-6"
            >
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-500" />
                Remove Video
              </h3>

              <p className="text-sm text-text-muted mb-2">
                Are you sure you want to remove <strong className="text-text-primary">{videoToDelete.name}</strong> from this project?
              </p>

              {videoToDelete.segments_count > 0 && (
                <div className="p-3 rounded bg-red-500/10 border border-red-500/30 mb-4">
                  <p className="text-sm text-red-400">
                    This video has {videoToDelete.segments_count} segment{videoToDelete.segments_count > 1 ? 's' : ''} that will also be removed.
                  </p>
                </div>
              )}

              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setVideoToDelete(null)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={() => removeMutation.mutate(videoToDelete.id)}
                  disabled={removeMutation.isPending}
                  className="btn-primary bg-red-600 hover:bg-red-700 flex items-center gap-2"
                >
                  {removeMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  Remove
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Re-link Video Modal */}
      <AnimatePresence>
        {videoToRelink && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/70" onClick={() => !relinkingVideo && setVideoToRelink(null)} />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative bg-terminal-surface border border-terminal-border rounded-lg w-full max-w-md mx-4 p-6"
            >
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <RefreshCw className="w-5 h-5 text-yellow-500" />
                Re-link Video
              </h3>

              <p className="text-sm text-text-muted mb-4">
                The video file for <strong className="text-text-primary">{videoToRelink.name}</strong> is missing.
                Select a replacement video file to restore this video.
              </p>

              <div className="p-3 rounded bg-yellow-500/10 border border-yellow-500/30 mb-4">
                <p className="text-xs text-yellow-400">
                  <strong>Note:</strong> The replacement video should ideally have similar duration and content to preserve segment timing.
                </p>
              </div>

              <div className="space-y-4">
                <div
                  className="border-2 border-dashed border-terminal-border rounded-lg p-8 text-center hover:border-yellow-500/50 transition-colors cursor-pointer"
                  onClick={() => document.getElementById('relink-video-input')?.click()}
                >
                  {relinkingVideo ? (
                    <div className="flex flex-col items-center gap-2">
                      <Loader2 className="w-8 h-8 animate-spin text-yellow-500" />
                      <span className="text-sm text-text-muted">Re-linking video...</span>
                    </div>
                  ) : (
                    <>
                      <FileVideo className="w-10 h-10 mx-auto text-yellow-500 mb-2" />
                      <p className="text-sm text-text-muted">Click to select replacement video</p>
                      <p className="text-xs text-text-muted mt-1">MP4, MOV, AVI, MKV, WebM</p>
                    </>
                  )}
                </div>
                <input
                  id="relink-video-input"
                  type="file"
                  accept="video/*"
                  onChange={handleRelinkUpload}
                  className="hidden"
                  disabled={relinkingVideo}
                />
              </div>

              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setVideoToRelink(null)}
                  disabled={relinkingVideo}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}

function ExportModal({
  isOpen,
  onClose,
  projectName,
  backgroundMusicPath: projectBgmPath,
  videoCount = 1,
}: {
  isOpen: boolean
  onClose: () => void
  projectName: string
  backgroundMusicPath?: string | null
  videoCount?: number
}) {
  const [quality, setQuality] = useState<'balanced' | 'high' | 'lossless'>('balanced')
  const [includeSubtitles, setIncludeSubtitles] = useState(true)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  const [outputPath, setOutputPath] = useState<string>('')
  const [outputFilename, setOutputFilename] = useState<string>('')
  const [exportCompleted, setExportCompleted] = useState(false)
  const { exportProgress, setExportProgress, isExporting, setIsExporting } = useAppStore()

  // Video compatibility state
  const [compatibility, setCompatibility] = useState<{ compatible: boolean; warnings: string[] } | null>(null)
  const [isCheckingCompatibility, setIsCheckingCompatibility] = useState(false)

  // Directory browser state
  const [showDirectoryBrowser, setShowDirectoryBrowser] = useState(false)
  const [directoryState, setDirectoryState] = useState<DirectoryBrowserState | null>(null)
  const [isLoadingDirs, setIsLoadingDirs] = useState(false)

  // Get TTS provider status from shared hook
  const { tts: ttsProviderStatus } = useProviderStatus()

  // TTS connectivity state for cloud providers
  const [cloudTtsStatus, setCloudTtsStatus] = useState<{
    connected: boolean
    checking: boolean
    mode: string | null
    error: string | null
  }>({ connected: false, checking: true, mode: null, error: null })

  // Computed TTS status based on provider type
  // For local providers (Coqui, Piper): always ready, no connectivity check needed
  // For cloud providers (Edge TTS): check connectivity
  const ttsStatus = useMemo(() => {
    if (ttsProviderStatus.isLocal) {
      return {
        connected: ttsProviderStatus.isConnected,
        checking: ttsProviderStatus.isChecking,
        mode: 'local' as const,
        error: ttsProviderStatus.isConnected ? null : 'Local TTS not available',
        isLocal: true,
        providerName: ttsProviderStatus.displayName,
      }
    }
    return {
      ...cloudTtsStatus,
      isLocal: false,
      providerName: ttsProviderStatus.displayName,
    }
  }, [ttsProviderStatus, cloudTtsStatus])

  // Check TTS connectivity when modal opens (only for cloud providers)
  useEffect(() => {
    if (isOpen && !isExporting && !ttsProviderStatus.isLocal) {
      setCloudTtsStatus(prev => ({ ...prev, checking: true, error: null }))
      ttsApi.checkConnectivity()
        .then((response) => {
          const data = response.data
          const isConnected = data.direct_connection || data.proxy_connection
          const mode = data.direct_connection ? 'direct' : data.proxy_connection ? 'proxy' : null
          setCloudTtsStatus({
            connected: isConnected,
            checking: false,
            mode,
            error: isConnected ? null : 'TTS service unavailable'
          })
        })
        .catch((err) => {
          setCloudTtsStatus({
            connected: false,
            checking: false,
            mode: null,
            error: err.message || 'Failed to check TTS connectivity'
          })
        })
    } else if (isOpen && !isExporting && ttsProviderStatus.isLocal) {
      // For local providers, mark as not checking
      setCloudTtsStatus(prev => ({ ...prev, checking: false }))
    }
  }, [isOpen, isExporting, ttsProviderStatus.isLocal])

  // Retry TTS connectivity check (only for cloud providers)
  const retryTtsCheck = () => {
    if (ttsProviderStatus.isLocal) return

    setCloudTtsStatus(prev => ({ ...prev, checking: true, error: null }))
    ttsApi.checkConnectivity()
      .then((response) => {
        const data = response.data
        const isConnected = data.direct_connection || data.proxy_connection
        const mode = data.direct_connection ? 'direct' : data.proxy_connection ? 'proxy' : null
        setCloudTtsStatus({
          connected: isConnected,
          checking: false,
          mode,
          error: isConnected ? null : 'TTS service unavailable'
        })
        if (isConnected) {
          toast.success('TTS service connected!')
        }
      })
      .catch((err) => {
        setCloudTtsStatus({
          connected: false,
          checking: false,
          mode: null,
          error: err.message || 'Failed to check TTS connectivity'
        })
      })
  }

  // Fetch default output directory
  useEffect(() => {
    if (isOpen) {
      exportApi.getOutputDir().then((response) => {
        setOutputPath(response.data.output_dir)
      }).catch(() => {})
    }
  }, [isOpen])

  // Validate timeline when modal opens
  useEffect(() => {
    if (isOpen && !isExporting) {
      setIsValidating(true)
      setExportCompleted(false)
      segmentsApi.validate(projectName)
        .then((response) => {
          setValidation(response.data)
        })
        .catch(() => {
          toast.error('Failed to validate timeline')
        })
        .finally(() => {
          setIsValidating(false)
        })
    }
  }, [isOpen, projectName, isExporting])

  // Check video compatibility when modal opens (for multi-video projects)
  useEffect(() => {
    if (isOpen && !isExporting && videoCount > 1) {
      setIsCheckingCompatibility(true)
      projectsApi.checkCompatibility(projectName)
        .then((response) => {
          setCompatibility(response.data)
        })
        .catch(() => {
          // Silently fail - compatibility check is non-critical
          console.warn('Failed to check video compatibility')
        })
        .finally(() => {
          setIsCheckingCompatibility(false)
        })
    } else if (videoCount <= 1) {
      // Single video - always compatible
      setCompatibility({ compatible: true, warnings: [] })
    }
  }, [isOpen, projectName, isExporting, videoCount])

  // Load directory contents
  const browseDirectory = async (path?: string) => {
    setIsLoadingDirs(true)
    try {
      const response = await exportApi.browseDirectories(path)
      setDirectoryState({
        currentPath: response.data.current_path,
        parentPath: response.data.parent_path,
        directories: response.data.directories,
        canGoUp: response.data.can_go_up,
      })
    } catch {
      toast.error('Failed to load directories')
    } finally {
      setIsLoadingDirs(false)
    }
  }

  // Open directory browser
  const openDirectoryBrowser = () => {
    setShowDirectoryBrowser(true)
    browseDirectory(outputPath)
  }

  // Select current directory
  const selectDirectory = () => {
    if (directoryState) {
      setOutputPath(directoryState.currentPath)
      setShowDirectoryBrowser(false)
    }
  }

  const exportMutation = useMutation({
    mutationFn: async () => {
      const response = await exportApi.start({
        project_name: projectName,
        config: {
          quality,
          include_subtitles: includeSubtitles,
          output_path: outputPath || undefined,
          output_filename: outputFilename || undefined,
        },
        export_type: videoCount > 1 ? 'combined' : 'single',
      })

      // Store output path
      if (response.data.output_path) {
        setOutputPath(response.data.output_path)
      }

      // Connect to WebSocket for progress
      const exportId = response.data.export_id
      const ws = new WebSocket(
        `${WS_BASE_URL}/api/v1/export/progress/${exportId}`
      )

      // Polling fallback for when WebSocket disconnects
      let pollInterval: ReturnType<typeof setInterval> | null = null
      const startPolling = async () => {
        if (pollInterval) return
        console.log('Starting polling fallback for export status')
        pollInterval = setInterval(async () => {
          try {
            // Use exportApi.getStatus() instead of raw fetch() to include auth headers
            const statusRes = await exportApi.getStatus(exportId)
            const status = statusRes.data
            if (status.status === 'completed') {
              setExportProgress({ stage: 'completed', message: 'Export completed!', progress: 100, output_path: status.output_path })
              setExportCompleted(true)
              setIsExporting(false)
              toast.success('Export completed!')
              if (pollInterval) clearInterval(pollInterval)
            } else if (status.status === 'failed') {
              setExportProgress({ stage: 'error', message: status.error || 'Export failed', progress: 0 })
              setIsExporting(false)
              toast.error(status.error || 'Export failed')
              if (pollInterval) clearInterval(pollInterval)
            } else {
              setExportProgress({ stage: status.current_stage || 'processing', message: status.current_detail || 'Processing...', progress: status.progress || 0 })
            }
          } catch (e) {
            console.error('Polling error:', e)
          }
        }, 2000)
      }

      ws.onopen = () => {
        console.log('WebSocket connected for export progress')
      }

      ws.onmessage = (event) => {
        try {
          const data: ExportProgressData = JSON.parse(event.data)
          console.log('Export progress:', data)
          setExportProgress(data)

          if (data.output_path) {
            setOutputPath(data.output_path)
          }

          if (data.stage === 'completed') {
            toast.success('Export completed!')
            setIsExporting(false)
            setExportCompleted(true)
            if (pollInterval) clearInterval(pollInterval)
            ws.close()
          } else if (data.stage === 'error') {
            toast.error(data.message || 'Export failed')
            setIsExporting(false)
            if (pollInterval) clearInterval(pollInterval)
            ws.close()
          }
        } catch {
          // Handle ping/pong messages
          if (event.data === 'ping') {
            ws.send('pong')
          }
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        // Start polling as fallback
        startPolling()
      }

      ws.onclose = () => {
        console.log('WebSocket closed')
        // Start polling as fallback - the polling will check status and stop if complete
        startPolling()
      }

      return response.data
    },
    onMutate: () => {
      setIsExporting(true)
      setExportCompleted(false)
      setExportProgress({ stage: 'starting', message: 'Starting export...', progress: 0 })
    },
    onError: () => {
      setIsExporting(false)
      toast.error('Failed to start export')
    },
  })

  // Get stage label for display
  const getStageLabel = (stage: string) => {
    const stages: Record<string, string> = {
      preprocessing: 'Preprocessing',
      fonts: 'Checking Fonts',
      tts: 'Generating Audio',
      segments: 'Processing Video',
      combining: 'Combining',
      voiceover: 'Adding Voice-overs',
      subtitles: 'Burning Subtitles',
      bgm: 'Background Music',
      ffmpeg: 'Encoding Video',
      cleanup: 'Cleanup',
      completed: 'Completed',
      error: 'Error',
    }
    return stages[stage] || stage
  }

  if (!isOpen) return null

  const progress = exportProgress as ExportProgressData | null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={!isExporting ? onClose : undefined} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative bg-terminal-surface border border-terminal-border rounded-lg w-full max-w-lg mx-4 p-6"
      >
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Download className="w-5 h-5 text-accent-red" />
          Export Video
        </h3>

        {/* Directory Browser Overlay */}
        <AnimatePresence>
          {showDirectoryBrowser && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-terminal-surface rounded-lg z-10 p-4 flex flex-col"
            >
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium flex items-center gap-2">
                  <FolderOpen className="w-4 h-4 text-accent-red" />
                  Select Output Directory
                </h4>
                <button
                  onClick={() => setShowDirectoryBrowser(false)}
                  className="text-text-muted hover:text-text-primary"
                >
                  Cancel
                </button>
              </div>

              {/* Current path display */}
              <div className="p-2 rounded bg-terminal-bg border border-terminal-border mb-3 font-mono text-xs break-all">
                {directoryState?.currentPath || 'Loading...'}
              </div>

              {/* Directory listing */}
              <div className="flex-1 overflow-y-auto border border-terminal-border rounded bg-terminal-bg">
                {isLoadingDirs ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin text-accent-red" />
                  </div>
                ) : (
                  <div className="divide-y divide-terminal-border">
                    {/* Go up button */}
                    {directoryState?.canGoUp && (
                      <button
                        onClick={() => browseDirectory(directoryState.parentPath || undefined)}
                        className="w-full p-2 text-left hover:bg-terminal-elevated flex items-center gap-2 text-sm"
                      >
                        <ChevronUp className="w-4 h-4 text-text-muted" />
                        <span className="text-text-muted">..</span>
                      </button>
                    )}

                    {/* Directory items */}
                    {directoryState?.directories.map((dir) => (
                      <button
                        key={dir}
                        onClick={() => browseDirectory(`${directoryState.currentPath}/${dir}`)}
                        className="w-full p-2 text-left hover:bg-terminal-elevated flex items-center gap-2 text-sm"
                      >
                        <Folder className="w-4 h-4 text-accent-red" />
                        <span>{dir}</span>
                      </button>
                    ))}

                    {directoryState?.directories.length === 0 && (
                      <div className="p-4 text-center text-text-muted text-sm">
                        No subdirectories
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Select button */}
              <div className="mt-3 flex justify-end gap-2">
                <button
                  onClick={() => setShowDirectoryBrowser(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={selectDirectory}
                  className="btn-primary flex items-center gap-2"
                >
                  <Check className="w-4 h-4" />
                  Select This Directory
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {exportCompleted ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-green-400">
              <Check className="w-6 h-6" />
              <span className="font-medium">Export Completed!</span>
            </div>

            <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border">
              <p className="text-xs text-text-muted mb-1">Output saved to:</p>
              <p className="text-sm font-mono break-all text-accent-red">{outputPath}</p>
            </div>

            <div className="flex justify-end gap-2 mt-4">
              <button onClick={onClose} className="btn-primary">
                Done
              </button>
            </div>
          </div>
        ) : isExporting ? (
          <div className="space-y-4">
            {/* Stage indicator */}
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 animate-spin text-accent-red" />
              <div>
                <span className="font-medium">{getStageLabel(progress?.stage || '')}</span>
                {progress?.current_step && progress?.total_steps && (
                  <span className="text-text-muted ml-2">
                    ({progress.current_step}/{progress.total_steps})
                  </span>
                )}
              </div>
            </div>

            {/* Current operation details */}
            <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border text-sm">
              <p>{progress?.message || 'Processing...'}</p>
              {progress?.current_segment && (
                <p className="text-text-muted mt-1">
                  Segment: <span className="text-accent-red">{progress.current_segment}</span>
                </p>
              )}
              {progress?.current_voice && (
                <p className="text-text-muted">
                  Voice: <span className="text-text-primary">{progress.current_voice}</span>
                </p>
              )}
              {progress?.detail && (
                <p className="text-xs text-text-muted mt-2 font-mono">{progress.detail}</p>
              )}
            </div>

            {/* Progress bar */}
            <div className="loading-bar">
              <div
                className="loading-bar-fill transition-all duration-300"
                style={{ width: `${progress?.progress || 0}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-sm text-text-muted">
              <span>{progress?.progress || 0}% complete</span>
              {progress?.eta_formatted && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  ETA: {progress.eta_formatted}
                </span>
              )}
              {progress?.processing_speed && progress.processing_speed > 0 && (
                <span className="text-xs font-mono">
                  {progress.processing_speed.toFixed(1)}x speed
                </span>
              )}
            </div>

            {/* Output path preview */}
            {outputPath && (
              <div className="text-xs text-text-muted">
                Output: <span className="font-mono">{outputPath}</span>
              </div>
            )}
          </div>
        ) : isValidating ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-accent-red" />
            <span className="ml-2">Validating timeline...</span>
          </div>
        ) : (
          <>
            {/* Validation Results */}
            {validation && validation.issues.length > 0 && (
              <div className="mb-4 p-3 rounded-lg bg-terminal-bg border border-terminal-border">
                <div className="flex items-center gap-2 mb-2">
                  {validation.can_export ? (
                    <AlertTriangle className="w-4 h-4 text-yellow-500" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-red-500" />
                  )}
                  <span className="text-sm font-medium">
                    {validation.can_export ? 'Warnings found' : 'Issues must be fixed'}
                  </span>
                </div>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {validation.issues.map((issue, i) => (
                    <div
                      key={i}
                      className={clsx(
                        'text-xs p-2 rounded',
                        issue.severity === 'error' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'
                      )}
                    >
                      {issue.message}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Video Compatibility Warning */}
            {videoCount > 1 && compatibility && !compatibility.compatible && (
              <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  <span className="text-sm font-medium text-red-400">Video Compatibility Issue</span>
                </div>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {compatibility.warnings.map((warning, i) => (
                    <div key={i} className="text-xs p-2 rounded bg-red-500/10 text-red-400">
                      {warning}
                    </div>
                  ))}
                </div>
                <p className="text-xs text-red-400/80 mt-2">
                  Export may fail or produce unexpected results. Use videos with the same orientation for best results.
                </p>
              </div>
            )}

            {/* Compatibility checking indicator */}
            {videoCount > 1 && isCheckingCompatibility && (
              <div className="mb-4 p-3 rounded-lg bg-terminal-bg border border-terminal-border">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-text-muted" />
                  <span className="text-sm text-text-muted">Checking video compatibility...</span>
                </div>
              </div>
            )}

            {/* TTS Service Status */}
            <div className={clsx(
              'mb-4 p-3 rounded-lg border',
              ttsStatus.checking ? 'bg-terminal-bg border-terminal-border' :
              ttsStatus.connected ? 'bg-green-500/10 border-green-500/30' :
              'bg-red-500/10 border-red-500/30'
            )}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {ttsStatus.checking ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-text-muted" />
                      <span className="text-sm text-text-muted">
                        {ttsStatus.isLocal ? 'Checking local TTS...' : 'Checking TTS service...'}
                      </span>
                    </>
                  ) : ttsStatus.connected ? (
                    <>
                      {ttsStatus.isLocal ? (
                        <Monitor className="w-4 h-4 text-green-400" />
                      ) : (
                        <Wifi className="w-4 h-4 text-green-400" />
                      )}
                      <span className="text-sm text-green-400">
                        {ttsStatus.isLocal
                          ? `${ttsStatus.providerName} ready (Local)`
                          : `${ttsStatus.providerName} connected ${ttsStatus.mode === 'proxy' ? '(via proxy)' : ''}`
                        }
                      </span>
                    </>
                  ) : (
                    <>
                      <WifiOff className="w-4 h-4 text-red-400" />
                      <span className="text-sm text-red-400">
                        {ttsStatus.error || `${ttsStatus.providerName} unavailable`}
                      </span>
                    </>
                  )}
                </div>
                {/* Only show retry for cloud providers */}
                {!ttsStatus.checking && !ttsStatus.connected && !ttsStatus.isLocal && (
                  <button
                    onClick={retryTtsCheck}
                    className="flex items-center gap-1 text-xs text-accent-red hover:text-accent-red/80 transition-colors"
                  >
                    <RefreshCw className="w-3 h-3" />
                    Retry
                  </button>
                )}
              </div>
              {!ttsStatus.connected && !ttsStatus.checking && validation && validation.segment_count > 0 && (
                <p className="text-xs text-red-400/80 mt-2">
                  {ttsStatus.isLocal
                    ? `Local TTS (${ttsStatus.providerName}) is not available. Please check if the TTS service is running.`
                    : 'Export requires TTS service for voice-over generation. Please check your internet connection or proxy settings.'
                  }
                </p>
              )}
            </div>

            {/* No segments warning - only show if no BGM either */}
            {validation && validation.segment_count === 0 && validation.bgm_count === 0 && (
              <div className="mb-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-500" />
                  <span className="text-sm text-yellow-400">No segments or BGM tracks to export</span>
                </div>
              </div>
            )}

            {/* BGM only info */}
            {validation && validation.segment_count === 0 && validation.bgm_count > 0 && (
              <div className="mb-4 p-3 rounded-lg bg-blue-500/10 border border-blue-500/30">
                <div className="flex items-center gap-2">
                  <Info className="w-4 h-4 text-blue-400" />
                  <span className="text-sm text-blue-400">
                    No voice-over segments. Video will be exported with {validation.bgm_count} BGM track{validation.bgm_count > 1 ? 's' : ''} only.
                  </span>
                </div>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="section-header">Quality</label>
                <select
                  value={quality}
                  onChange={(e) => setQuality(e.target.value as typeof quality)}
                  className="input-base w-full"
                >
                  <option value="balanced">Balanced (Recommended)</option>
                  <option value="high">High Quality</option>
                  <option value="lossless">Lossless (Large file)</option>
                </select>
              </div>

              <div>
                <label className="section-header">Filename (optional)</label>
                <input
                  type="text"
                  value={outputFilename}
                  onChange={(e) => setOutputFilename(e.target.value)}
                  placeholder={`${projectName}_export`}
                  className="input-base w-full"
                />
                <p className="text-xs text-text-muted mt-1">
                  Leave empty to use default (project name + timestamp)
                </p>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeSubtitles}
                  onChange={(e) => setIncludeSubtitles(e.target.checked)}
                  className="w-4 h-4 accent-accent-red"
                />
                <span className="text-sm">Include subtitles</span>
              </label>

              {/* Background Music Info */}
              {projectBgmPath && (
                <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border">
                  <div className="flex items-center gap-2 mb-1">
                    <Check className="w-4 h-4 text-green-500" />
                    <span className="text-sm font-medium text-green-400">Background Music</span>
                  </div>
                  <p className="text-xs font-mono text-text-muted break-all">
                    {projectBgmPath.split('/').pop()}
                  </p>
                  <p className="text-[10px] text-text-muted mt-1">
                    Will be mixed with voiceover at reduced volume
                  </p>
                </div>
              )}

              {/* Output Directory Picker */}
              <div>
                <label className="section-header">Output Directory</label>
                <div className="flex gap-2">
                  <div className="flex-1 p-2 rounded bg-terminal-bg border border-terminal-border font-mono text-xs break-all">
                    {outputPath || 'Select directory...'}
                  </div>
                  <button
                    onClick={openDirectoryBrowser}
                    className="btn-secondary px-3 flex items-center gap-2"
                  >
                    <FolderOpen className="w-4 h-4" />
                    Browse
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button onClick={onClose} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => exportMutation.mutate()}
                disabled={
                  !validation?.can_export ||
                  (validation?.segment_count === 0 && validation?.bgm_count === 0) ||
                  ttsStatus.checking ||
                  // Require TTS if there are segments that need voice-over
                  (validation?.segment_count > 0 && !ttsStatus.connected)
                }
                className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download className="w-4 h-4" />
                {!validation?.can_export
                  ? 'Fix Issues First'
                  : ttsStatus.checking
                    ? 'Checking TTS...'
                    : (validation?.segment_count > 0 && !ttsStatus.connected)
                      ? 'TTS Unavailable'
                      : 'Start Export'
                }
              </button>
            </div>
          </>
        )}
      </motion.div>
    </div>
  )
}

export default function ProjectPage() {
  const { projectName } = useParams<{ projectName: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const authToken = useAuthStore((state) => state.token)

  const {
    setCurrentProject,
    setSegments,
    segments,
    selectedSegmentId,
    setSelectedSegmentId,
    aiPanelOpen,
    setAiPanelOpen,
    currentTime,
    setCurrentTime,
    setIsPlaying,
    // Video availability state
    setVideoAvailability,
    availabilityChecked,
    setAvailabilityChecked,
    isCheckingAvailability,
    setIsCheckingAvailability,
    resetAvailabilityState,
  } = useAppStore()

  const [showExport, setShowExport] = useState(false)
  const [addSegmentAt, setAddSegmentAt] = useState<number | null>(null)
  const [addSegmentVideoId, setAddSegmentVideoId] = useState<string | null>(null)
  const [backgroundMusicPath, setBackgroundMusicPath] = useState<string | null>(null)
  const [segmentVideoFilter, setSegmentVideoFilter] = useState<'all' | string>('all')
  const [bgmTracks, setBgmTracks] = useState<BGMTrack[]>([])
  const [bgmVolume, setBgmVolume] = useState(100)
  const [ttsVolume, setTtsVolume] = useState(100)
  // Local videos state for optimistic updates (avoids lag when dragging on timeline)
  const [videos, setVideos] = useState<VideoInfo[]>([])

  // Fetch project
  const { data: projectData, isLoading: isLoadingProject } = useQuery({
    queryKey: ['project', projectName],
    queryFn: () => projectsApi.get(projectName!),
    enabled: !!projectName,
  })

  const project: Project | undefined = projectData?.data
  const activeVideo = project?.videos?.find((v) => v.id === project.active_video_id)

  // Fetch segments - always fetch all segments for multi-video timeline support
  const { data: segmentsData } = useQuery({
    queryKey: ['segments', projectName],
    queryFn: () => segmentsApi.list(projectName!, { all: true }),
    enabled: !!projectName,
  })

  // Debug store for logging
  const { setProjectName: setDebugProjectName, action: logAction } = useDebugStore()

  // Sync project and segments with store
  useEffect(() => {
    if (project) {
      setCurrentProject(project)
      setBackgroundMusicPath(project.background_music_path)
      // Load BGM tracks from project response (typed as any since API response includes them now)
      const projectWithBgm = project as typeof project & { bgm_tracks?: BGMTrack[], bgm_volume?: number, tts_volume?: number }
      setBgmTracks(projectWithBgm.bgm_tracks || [])
      setBgmVolume(projectWithBgm.bgm_volume || 100)
      setTtsVolume(projectWithBgm.tts_volume || 100)
      // Sync videos for optimistic updates
      setVideos(project.videos || [])
      // Track project in debug store
      setDebugProjectName(project.name)
      logAction('Project Loaded', { name: project.name, videos: project.videos?.length, segments: segmentsData?.data?.length })
    }
  }, [project, setCurrentProject, setDebugProjectName, logAction, segmentsData])

  useEffect(() => {
    if (segmentsData?.data) {
      setSegments(segmentsData.data)
    }
  }, [segmentsData, setSegments])

  // Check video availability when project loads
  useEffect(() => {
    if (project && projectName && !availabilityChecked && !isCheckingAvailability) {
      setIsCheckingAvailability(true)

      videosApi.checkAvailability(projectName)
        .then(response => {
          setVideoAvailability(response.data.videos)
          setAvailabilityChecked(true)

          // Show warning toast if any videos are unavailable
          if (!response.data.all_available) {
            const count = response.data.unavailable_count
            toast.error(
              `${count} video${count > 1 ? 's are' : ' is'} unavailable. Check the Video Manager panel.`,
              { duration: 5000 }
            )
          }
        })
        .catch(() => {
          // Silently fail - availability check is non-critical
          console.warn('Failed to check video availability')
        })
        .finally(() => {
          setIsCheckingAvailability(false)
        })
    }
  }, [project, projectName, availabilityChecked, isCheckingAvailability, setVideoAvailability, setAvailabilityChecked, setIsCheckingAvailability])

  // Reset availability state when leaving the project
  useEffect(() => {
    return () => {
      resetAvailabilityState()
    }
  }, [projectName, resetAvailabilityState])

  // Get selected segment
  const selectedSegment = segments.find((s) => s.id === selectedSegmentId) || null

  // Filter segments by video when multiple videos exist
  const hasMultipleVideos = (project?.videos.length || 0) > 1
  const filteredSegments = segmentVideoFilter === 'all'
    ? segments
    : segments.filter(s => s.video_id === segmentVideoFilter)

  // Helper to get video name by id
  const getVideoName = (videoId: string | null) => {
    if (!videoId || !project?.videos) return null
    const video = project.videos?.find(v => v.id === videoId)
    return video?.name || null
  }

  // Handle setting active video from timeline
  const handleSetActiveVideo = useCallback(async (videoId: string) => {
    if (!projectName) return
    try {
      await projectsApi.setActiveVideo(projectName, videoId)
      queryClient.invalidateQueries({ queryKey: ['project', projectName] })
      toast.success('Active video changed')
    } catch (error) {
      toast.error('Failed to change active video')
    }
  }, [projectName, queryClient])

  // Compute which video the playhead is currently in (local only, no API calls)
  // This provides a Premiere Pro-like experience where the playhead determines the displayed video
  // NOTE: This hook must be called before any early returns to follow Rules of Hooks
  // IMPORTANT: Uses local `videos` state (not project.videos) to stay consistent with optimistic updates
  const playheadVideoId = useMemo(() => {
    if (!project || videos.length <= 1) return project?.active_video_id || null

    const sortedVideos = [...videos].sort((a, b) => a.order - b.order)

    // Check if any video has timeline_start set (user has repositioned videos)
    const hasTimelinePositions = sortedVideos.some(v => v.timeline_start !== null && v.timeline_start !== undefined)

    if (hasTimelinePositions) {
      // Use timeline positions to find which video contains the playhead
      for (const video of sortedVideos) {
        const videoStart = video.timeline_start ?? 0
        const videoEnd = video.timeline_end ?? (videoStart + (video.duration || 0))
        if (currentTime >= videoStart && currentTime < videoEnd) {
          return video.id
        }
      }
    } else {
      // Fallback: use order-based cumulative time
      let cumulativeTime = 0
      for (const video of sortedVideos) {
        const videoDuration = video.duration || 0
        if (currentTime >= cumulativeTime && currentTime < cumulativeTime + videoDuration) {
          return video.id
        }
        cumulativeTime += videoDuration
      }
    }

    // Fallback to stored active video
    return project.active_video_id
  }, [currentTime, project, videos])

  // The effective active video for display - based on playhead position, not server state
  // IMPORTANT: Uses local `videos` state for consistency with optimistic updates
  const effectiveActiveVideo = useMemo(() => {
    if (!project || videos.length === 0) return null
    return videos.find(v => v.id === playheadVideoId) || activeVideo || videos[0]
  }, [project, videos, playheadVideoId, activeVideo])

  // Calculate video offset for combined multi-video timeline
  // Uses timeline_start if set (from user repositioning), otherwise falls back to order-based calculation
  // IMPORTANT: Uses local `videos` state for consistency with optimistic updates
  // NOTE: Single videos CAN have timeline_start if user repositions them (creates empty space before)
  const videoOffset = useMemo(() => {
    if (!project || !effectiveActiveVideo) return 0

    // If timeline_start is explicitly set on this video, use it directly
    // This works for BOTH single and multi-video mode - single video with empty space before it
    if (effectiveActiveVideo.timeline_start !== null && effectiveActiveVideo.timeline_start !== undefined) {
      return effectiveActiveVideo.timeline_start
    }

    // For single video without explicit timeline_start, no offset needed
    if (videos.length <= 1) return 0

    // Fallback for multi-video: calculate based on order and cumulative durations
    let offset = 0
    const sortedVideos = [...videos].sort((a, b) => a.order - b.order)

    for (const video of sortedVideos) {
      if (video.id === effectiveActiveVideo.id) break
      // Use timeline position if set, otherwise use duration
      if (video.timeline_start !== null && video.timeline_start !== undefined) {
        // If this video has timeline_start, add its effective duration on timeline
        const videoEnd = video.timeline_end ?? (video.timeline_start + (video.duration || 0))
        offset = Math.max(offset, videoEnd)
      } else {
        offset += video.duration || 0
      }
    }

    return offset
  }, [project, videos, effectiveActiveVideo])

  // Calculate total timeline duration for multi-video playback
  // IMPORTANT: Uses local `videos` state for consistency with optimistic updates
  const totalTimelineDuration = useMemo(() => {
    if (!project || videos.length === 0) return 0

    const hasTimelinePositions = videos.some(v => v.timeline_start !== null && v.timeline_start !== undefined)

    if (hasTimelinePositions) {
      // Find the maximum timeline_end
      return Math.max(...videos.map(v => {
        const start = v.timeline_start ?? 0
        const end = v.timeline_end ?? (start + (v.duration || 0))
        return end
      }))
    } else {
      // Sum all video durations
      return videos.reduce((sum, v) => sum + (v.duration || 0), 0)
    }
  }, [project, videos])

  if (isLoadingProject) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-accent-red" />
      </div>
    )
  }

  if (!project || !effectiveActiveVideo) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <h2 className="text-xl font-bold mb-2">Project not found</h2>
          <button onClick={() => navigate('/')} className="btn-secondary">
            Go back home
          </button>
        </div>
      </div>
    )
  }

  const baseVideoUrl = `/api/v1/videos/${projectName}/${effectiveActiveVideo.id}/stream`
  const videoUrl = authToken ? `${baseVideoUrl}?token=${encodeURIComponent(authToken)}` : baseVideoUrl
  const videoDuration = effectiveActiveVideo.duration || 0

  return (
    <div className="min-h-[calc(100vh-5rem)] flex flex-col">
      {/* Project header */}
      <div className="border-b border-terminal-border bg-terminal-surface px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 rounded hover:bg-terminal-elevated text-text-muted hover:text-text-primary"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>

            <div>
              <h1 className="font-semibold">{project.name}</h1>
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <Video className="w-3 h-3" />
                <span>{effectiveActiveVideo.name}</span>
                <span className="text-terminal-border">•</span>
                <span>{Math.floor(videoDuration / 60)}:{String(Math.floor(videoDuration % 60)).padStart(2, '0')}</span>
                <span className="text-terminal-border">•</span>
                <span>{effectiveActiveVideo.orientation}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setAiPanelOpen(true)}
              className="btn-secondary flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4 text-accent-red" />
              AI Script
            </button>

            <button
              onClick={() => setShowExport(true)}
              className="btn-primary flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Export
            </button>
          </div>
        </div>
      </div>

      {/* Video Manager Panel */}
      <VideoManagerPanel
        projectName={projectName!}
        videos={(project?.videos || []).map(v => ({
          id: v.id,
          name: v.name,
          path: v.path,
          order: v.order,
          duration: v.duration ?? undefined,
          width: v.width ?? undefined,
          height: v.height ?? undefined,
          orientation: v.orientation ?? undefined,
          segments_count: v.segments_count,
          file_exists: v.file_exists,
        }))}
        activeVideoId={project?.active_video_id}
        onRefresh={() => {
          queryClient.invalidateQueries({ queryKey: ['project', projectName] })
          queryClient.invalidateQueries({ queryKey: ['segments', projectName] })
        }}
      />

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Video and Timeline */}
        <div className="flex-1 flex flex-col p-4 overflow-hidden">
          {videos.length > 1 ? (
            <MultiVideoPlayer
              projectName={projectName!}
              videos={videos}
              totalDuration={totalTimelineDuration}
              bgmTracks={bgmTracks}
            />
          ) : (
            <VideoPlayer videoUrl={videoUrl} duration={videoDuration} videoOffset={videoOffset} bgmTracks={bgmTracks} />
          )}

          <div className="mt-4">
            <Timeline
              duration={videoDuration}
              projectName={projectName!}
              onAddSegment={(time, videoId) => {
                setAddSegmentAt(time)
                // For multi-video projects, videoId can be undefined for generic segments
                // These are project-level segments using timeline positions
                setAddSegmentVideoId(videoId ?? null)
              }}
              backgroundMusicPath={backgroundMusicPath}
              onBackgroundMusicChange={(path) => {
                setBackgroundMusicPath(path)
                // Update project settings
                projectsApi.updateSettings(projectName!, { background_music_path: path })
                  .then(() => queryClient.invalidateQueries({ queryKey: ['project', projectName] }))
                  .catch(() => toast.error('Failed to update background music'))
              }}
              bgmTracks={bgmTracks}
              bgmVolume={bgmVolume}
              ttsVolume={ttsVolume}
              onBGMTracksChange={() => {
                // Refetch project to get updated BGM tracks
                queryClient.invalidateQueries({ queryKey: ['project', projectName] })
              }}
              onBGMTrackUpdate={(trackId, updates) => {
                // Update local state immediately for instant feedback (no lag)
                // Handles position updates (start_time, end_time, audio_offset) and volume/mute
                setBgmTracks(prev => prev.map(track =>
                  track.id === trackId ? { ...track, ...updates } : track
                ))
              }}
              // Multi-video props
              videos={videos}
              activeVideoId={project?.active_video_id || null}
              onSetActiveVideo={handleSetActiveVideo}
              onVideoPositionChange={() => {
                // Refetch project to get updated video timeline positions
                queryClient.invalidateQueries({ queryKey: ['project', projectName] })
              }}
              onVideoPositionUpdate={(videoId, updates) => {
                // Update local state immediately for instant feedback (no lag)
                setVideos(prev => prev.map(video =>
                  video.id === videoId ? { ...video, ...updates } : video
                ))
              }}
              onPlayPreview={(timelineTime, segmentId) => {
                // Set time and start playback for segment preview
                setCurrentTime(timelineTime)
                setIsPlaying(true)
                // Select the segment
                setSelectedSegmentId(segmentId)
              }}
            />
          </div>

          {/* Segments list */}
          <div className="mt-4 flex-1 overflow-hidden console-card">
            <div className="p-3 border-b border-terminal-border flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <span className="section-header mb-0 shrink-0">Segments ({filteredSegments.length}{segmentVideoFilter !== 'all' && `/${segments.length}`})</span>
                {hasMultipleVideos && (
                  <select
                    value={segmentVideoFilter}
                    onChange={(e) => setSegmentVideoFilter(e.target.value)}
                    className="text-xs bg-terminal-elevated border border-terminal-border rounded px-1.5 py-0.5 text-text-secondary min-w-0 truncate"
                  >
                    <option value="all">All Videos</option>
                    {project?.videos.map((v) => (
                      <option key={v.id} value={v.id}>{v.name}</option>
                    ))}
                  </select>
                )}
              </div>
              <button
                onClick={() => setAddSegmentAt(0)}
                className="btn-secondary text-xs py-1 px-2 shrink-0"
              >
                <Plus className="w-3 h-3" />
              </button>
            </div>

            <div className="max-h-48 overflow-y-auto">
              {filteredSegments.length === 0 ? (
                <div className="p-4 text-center text-text-muted text-sm">
                  <p>No segments{segmentVideoFilter !== 'all' ? ' for this video' : ''} yet</p>
                  <button
                    onClick={() => setAiPanelOpen(true)}
                    className="text-accent-red hover:underline mt-1"
                  >
                    Generate with AI
                  </button>
                </div>
              ) : (
                <div className="divide-y divide-terminal-border">
                  {filteredSegments.map((seg) => (
                    <button
                      key={seg.id}
                      onClick={() => setSelectedSegmentId(seg.id)}
                      className={clsx(
                        'w-full p-3 text-left hover:bg-terminal-elevated transition-colors',
                        selectedSegmentId === seg.id && 'bg-accent-red/10 border-l-2 border-l-accent-red'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span className="font-medium text-sm truncate">{seg.name}</span>
                          {hasMultipleVideos && segmentVideoFilter === 'all' && seg.video_id && (
                            <span className="text-[10px] px-1 py-0.5 rounded bg-terminal-elevated text-text-muted shrink-0">
                              {getVideoName(seg.video_id)?.slice(0, 12) || 'Unknown'}
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-text-muted font-mono shrink-0 ml-2">
                          {seg.start_time.toFixed(1)}s - {seg.end_time.toFixed(1)}s
                        </span>
                      </div>
                      <p className="text-xs text-text-muted mt-1 truncate">
                        {seg.text}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: Segment Editor - Sticky to stay visible while scrolling */}
        <div className="w-96 border-l border-terminal-border overflow-y-auto">
          <div className="sticky top-0 p-4 bg-terminal-bg max-h-screen overflow-y-auto">
            <SegmentEditor
              projectName={projectName!}
              segment={selectedSegment}
              onClose={() => setSelectedSegmentId(null)}
            />
          </div>
        </div>
      </div>

      {/* Modals */}
      <ExportModal
        isOpen={showExport}
        onClose={() => setShowExport(false)}
        projectName={projectName!}
        backgroundMusicPath={backgroundMusicPath}
        videoCount={project?.videos.length || 1}
      />

      {addSegmentAt !== null && (
        <AddSegmentModal
          isOpen
          onClose={() => {
            setAddSegmentAt(null)
            setAddSegmentVideoId(null)
          }}
          projectName={projectName!}
          videoId={addSegmentVideoId || (!hasMultipleVideos && project?.videos[0]?.id) || null}
          startTime={addSegmentAt}
          videoDuration={
            addSegmentVideoId
              ? (project?.videos?.find(v => v.id === addSegmentVideoId)?.duration || videoDuration)
              : hasMultipleVideos
                ? totalTimelineDuration  // Use total timeline duration for generic segments in multi-video
                : videoDuration  // Use single video duration
          }
          existingSegments={
            addSegmentVideoId
              ? segments.filter(s => s.video_id === addSegmentVideoId)
              : hasMultipleVideos
                ? segments.filter(s => s.video_id === null)  // Generic segments only for multi-video
                : segments  // All segments for single video
          }
          isMultiVideo={hasMultipleVideos}
        />
      )}

      <AIScriptGenerator
        projectName={projectName!}
        videoId={effectiveActiveVideo.id}
        videoDuration={videoDuration}
        isOpen={aiPanelOpen}
        onClose={() => setAiPanelOpen(false)}
        videos={project?.videos || []}
        videoPath={effectiveActiveVideo.path}
      />
    </div>
  )
}
