import axios from 'axios'

const API_BASE = '/api/v1'

// Determine WebSocket base URL - in dev mode, use port 8000 directly
const getWsBaseUrl = () => {
  if (import.meta.env.DEV) {
    // Development: API runs on port 8000
    return `ws://${window.location.hostname}:8000`
  }
  // Production: same host
  return `ws://${window.location.host}`
}

export const WS_BASE_URL = getWsBaseUrl()

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
})

// Response interceptor for global error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Handle 401 Unauthorized - token expired or invalid
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      // Import authStore dynamically to avoid circular dependencies
      const { useAuthStore } = await import('../stores/authStore')
      const authState = useAuthStore.getState()

      // If user was authenticated, their token expired
      if (authState.token) {
        // Clear auth state and redirect to login
        authState.logout()

        // Only redirect if not already on auth pages
        if (!window.location.pathname.startsWith('/login') &&
            !window.location.pathname.startsWith('/signup') &&
            !window.location.pathname.startsWith('/forgot-password')) {
          window.location.href = '/login?session_expired=true'
        }
      }
    }

    // Handle 403 Forbidden - insufficient permissions
    if (error.response?.status === 403) {
      console.warn('Access forbidden:', error.response?.data?.detail || 'Insufficient permissions')
    }

    // Handle 429 Too Many Requests - rate limiting
    if (error.response?.status === 429) {
      console.warn('Rate limited. Please wait before making more requests.')
    }

    return Promise.reject(error)
  }
)

// BGM Track types
export interface BGMTrack {
  id: string
  name: string
  path: string
  start_time: number
  end_time: number
  audio_offset: number  // Offset into audio file for start trimming (like segment.audio_offset)
  volume: number
  fade_in: number
  fade_out: number
  loop: boolean
  muted: boolean
  order: number
  duration?: number
}

export interface AddBGMTrackRequest {
  path: string
  name?: string
  start_time?: number
  end_time?: number
  audio_offset?: number
  volume?: number
}

export interface UpdateBGMTrackRequest {
  name?: string
  path?: string
  start_time?: number
  end_time?: number
  audio_offset?: number  // Offset into audio file for start trimming
  volume?: number
  fade_in?: number
  fade_out?: number
  loop?: boolean
  muted?: boolean
}

// Projects API
export const projectsApi = {
  list: () => api.get('/projects'),
  get: (name: string) => api.get(`/projects/${name}`),
  create: (name: string, videoPaths: string[]) =>
    api.post('/projects', { name, video_paths: videoPaths }),
  delete: (name: string) => api.delete(`/projects/${name}`),
  // Video management
  addVideo: (name: string, videoPath: string, videoName?: string) =>
    api.post(`/projects/${name}/videos`, { video_path: videoPath, name: videoName }),
  removeVideo: (name: string, videoId: string) =>
    api.delete(`/projects/${name}/videos/${videoId}`),
  reorderVideos: (name: string, videoIds: string[]) =>
    api.post(`/projects/${name}/videos/reorder`, { video_ids: videoIds }),
  setActiveVideo: (name: string, videoId: string) =>
    api.post(`/projects/${name}/active-video`, { video_id: videoId }),
  checkCompatibility: (name: string) =>
    api.get(`/projects/${name}/compatibility`),
  updateSettings: (name: string, settings: Record<string, unknown>) =>
    api.put(`/projects/${name}/settings`, settings),

  // Video position update (REST API fallback for WebSocket)
  updateVideoPosition: (
    name: string,
    videoId: string,
    data: {
      timeline_start?: number
      timeline_end?: number
      source_start?: number
      source_end?: number
    }
  ) => api.put(`/projects/${name}/videos/${videoId}/position`, data),

  // BGM Track endpoints
  getBGMTracks: (name: string) => api.get<BGMTrack[]>(`/projects/${name}/bgm-tracks`),
  addBGMTrack: (name: string, data: AddBGMTrackRequest) =>
    api.post<BGMTrack>(`/projects/${name}/bgm-tracks`, data),
  getBGMTrack: (name: string, trackId: string) =>
    api.get<BGMTrack>(`/projects/${name}/bgm-tracks/${trackId}`),
  updateBGMTrack: (name: string, trackId: string, data: UpdateBGMTrackRequest) =>
    api.put<BGMTrack>(`/projects/${name}/bgm-tracks/${trackId}`, data),
  deleteBGMTrack: (name: string, trackId: string) =>
    api.delete(`/projects/${name}/bgm-tracks/${trackId}`),
  reorderBGMTracks: (name: string, trackIds: string[]) =>
    api.post(`/projects/${name}/bgm-tracks/reorder`, { track_ids: trackIds }),

  // Volume settings
  updateVolumeSettings: (name: string, bgmVolume?: number, ttsVolume?: number) =>
    api.put(`/projects/${name}/volume-settings`, { bgm_volume: bgmVolume, tts_volume: ttsVolume }),
}

// Video Availability types
export interface VideoAvailability {
  id: string
  name: string
  path: string
  available: boolean
  exists: boolean
  readable: boolean
  error: string | null
}

export interface VideoAvailabilityResponse {
  project_name: string
  all_available: boolean
  unavailable_count: number
  videos: VideoAvailability[]
}

export interface ReplaceVideoPathResponse {
  message: string
  video_id: string
  old_path: string
  new_path: string
  duration: number
  width: number
  height: number
}

// Videos API
export const videosApi = {
  get: (projectName: string, videoId: string) =>
    api.get(`/videos/${projectName}/${videoId}`),
  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/videos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  uploadAudio: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/videos/upload-audio', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getInfo: (path: string) => api.get('/videos/info', { params: { path } }),
  getKeyframes: (projectName: string, videoId: string, count = 5) =>
    api.get(`/videos/${projectName}/${videoId}/keyframes`, { params: { count } }),
  // Video availability check
  checkAvailability: (projectName: string) =>
    api.get<VideoAvailabilityResponse>(`/videos/${projectName}/availability`),
  // Replace video path (re-link missing videos)
  replacePath: (projectName: string, videoId: string, newPath: string) =>
    api.put<ReplaceVideoPathResponse>(`/videos/${projectName}/${videoId}/path`, { new_path: newPath }),
}

// Segments API
export const segmentsApi = {
  list: (projectName: string, options?: { videoId?: string; all?: boolean }) =>
    api.get(`/segments/${projectName}`, {
      params: {
        ...(options?.videoId ? { video_id: options.videoId } : {}),
        ...(options?.all ? { all: true } : {})
      }
    }),
  create: (projectName: string, segment: Record<string, unknown>, videoId?: string) =>
    api.post(`/segments/${projectName}`, segment, {
      params: videoId ? { video_id: videoId } : {},
    }),
  update: (projectName: string, segmentId: string, data: Record<string, unknown>) =>
    api.put(`/segments/${projectName}/${segmentId}`, data),
  delete: (projectName: string, segmentId: string) =>
    api.delete(`/segments/${projectName}/${segmentId}`),
  analyze: (projectName: string, segmentId: string) =>
    api.get(`/segments/${projectName}/${segmentId}/analyze`),
  createBatch: (projectName: string, segments: Record<string, unknown>[], videoId?: string) =>
    api.post(`/segments/${projectName}/batch`, segments, {
      params: videoId ? { video_id: videoId } : {},
    }),
  validate: (projectName: string, videoId?: string) =>
    api.get(`/segments/${projectName}/validate`, {
      params: videoId ? { video_id: videoId } : {},
    }),
}

// TTS Provider Types
export interface TTSProviderInfo {
  name: string
  display_name: string
  description: string
  is_local: boolean
  requires_consent: boolean
  supports_word_timing: boolean
  supports_voice_cloning: boolean
  available: boolean
  is_default: boolean
}

export interface TTSProvidersResponse {
  default_provider: string
  providers: TTSProviderInfo[]
}

// Voice Sample types
export interface VoiceSample {
  id: string
  name: string
  filename: string
  duration: number
  created_at: string
  language: string
  file_size: number
  audio_url: string
}

export interface VoiceSamplesResponse {
  samples: VoiceSample[]
  total: number
}

export interface VoiceCloneResponse {
  audio_url: string
  subtitle_url?: string
  duration: number
  voice_sample_name: string
}

export interface VoiceCloneStartResponse {
  clone_id: string
  status: string
  message: string
}

export interface VoiceCloneStatusResponse {
  clone_id: string
  status: string
  progress: number
  stage: string
  message: string
  audio_url?: string
  duration?: number
  error?: string
}

// TTS API
export const ttsApi = {
  getVoices: (language?: string) =>
    api.get('/tts/voices', { params: language ? { language } : {} }),
  getBestVoices: () => api.get('/tts/voices/best'),
  preview: (voiceId: string, text?: string, rate?: string, volume?: string, pitch?: string) =>
    api.post('/tts/preview', { voice_id: voiceId, text, rate, volume, pitch }),
  generate: (data: Record<string, unknown>) => api.post('/tts/generate', data),
  checkConnectivity: () => api.get('/tts/connectivity'),
  estimateDuration: (text: string, language = 'en') =>
    api.post('/tts/estimate-duration', { text, language }),
  getLanguages: () => api.get('/tts/languages'),

  // Provider management
  getProviders: () => api.get<TTSProvidersResponse>('/tts/providers'),
  getProviderInfo: () => api.get('/tts/providers/info'),
  getProviderStatus: (provider: string) => api.get(`/tts/providers/${provider}/status`),
  getProviderVoices: (provider: string, language?: string) =>
    api.get(`/tts/providers/${provider}/voices`, {
      params: language ? { language } : {}
    }),
  getProviderLanguages: (provider: string) =>
    api.get<{ provider: string; languages: { code: string; name: string }[] }>(
      `/tts/providers/${provider}/languages`
    ),
  setDefaultProvider: (provider: string) =>
    api.post('/tts/providers/default', { provider }),
  generateWithProvider: (data: Record<string, unknown>) =>
    api.post('/tts/generate-with-provider', data),

  // Voice cloning (Coqui TTS only)
  getVoiceSamples: () => api.get<VoiceSamplesResponse>('/tts/voice-samples'),
  getVoiceSample: (sampleId: string) => api.get<VoiceSample>(`/tts/voice-samples/${sampleId}`),
  uploadVoiceSample: (file: File, name: string, language = 'en') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name)
    formData.append('language', language)
    return api.post('/tts/voice-samples', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteVoiceSample: (sampleId: string) => api.delete(`/tts/voice-samples/${sampleId}`),
  cloneVoice: (data: {
    voice_sample_id: string
    text: string
    language?: string
    project_name?: string
    segment_name?: string
    orientation?: string
  }) => api.post<VoiceCloneResponse>('/tts/clone-voice', data),
  previewClonedVoice: (voiceSampleId: string, text?: string, language?: string) => {
    const formData = new FormData()
    formData.append('voice_sample_id', voiceSampleId)
    if (text) formData.append('text', text)
    if (language) formData.append('language', language)
    return api.post<VoiceCloneStartResponse>('/tts/clone-voice/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getCloneStatus: (cloneId: string) =>
    api.get<VoiceCloneStatusResponse>(`/tts/clone-voice/status/${cloneId}`),
  cancelClone: (cloneId: string) =>
    api.delete(`/tts/clone-voice/cancel/${cloneId}`),
}

// LLM API
export const llmApi = {
  checkHealth: () => api.get('/llm/health'),
  listOllamaModels: () => api.get('/llm/ollama/models'),
  // Vision model availability check
  checkVisionModels: () => api.get('/llm/ollama/vision-models'),
  // Analyze video with AI vision
  analyzeVideo: (videoPath: string, visionModel = 'qwen3-vl:8b', numFrames = 4) =>
    api.post('/llm/analyze-video', null, {
      params: { video_path: videoPath, vision_model: visionModel, num_frames: numFrames }
    }),
  generateScript: (data: Record<string, unknown>) => api.post('/llm/generate-script', data),
  refineScript: (data: Record<string, unknown>) => api.post('/llm/refine-script', data),
  estimateDuration: (text: string, language = 'en') =>
    api.post('/llm/estimate-duration', { text, language }),
  getProviders: () => api.get('/llm/providers'),
  getPromptTemplates: () => api.get('/llm/prompt-templates'),
  autoSegment: (data: Record<string, unknown>) => api.post('/llm/auto-segment', data),
  // Intelligent auto-segment with streaming progress (supports video analysis)
  intelligentAutoSegment: (data: Record<string, unknown>) =>
    api.post('/llm/intelligent-auto-segment', data),
  // Streaming version for SSE progress updates
  intelligentAutoSegmentStream: (_data: Record<string, unknown>): EventSource => {
    // For SSE, we need to use fetch with the request body
    const url = '/api/v1/llm/intelligent-auto-segment'
    // Create a hidden form to POST and get SSE response
    // Using a custom approach since EventSource only supports GET
    return new EventSource(url) // This won't work for POST, see below
  },
}

// Export API
export const exportApi = {
  start: (data: Record<string, unknown>) => api.post('/export/start', data),
  getStatus: (exportId: string) => api.get(`/export/status/${exportId}`),
  getQueue: () => api.get('/export/queue'),
  cancel: (exportId: string) => api.delete(`/export/cancel/${exportId}`),
  preview: (projectName: string, segmentIndex: number) =>
    api.post('/export/preview', { project_name: projectName, segment_index: segmentIndex }),
  getOutputDir: () => api.get('/export/output-dir'),
  browseDirectories: (path?: string) => api.post('/export/browse-directories', { path }),
  setOutputDir: (path: string) => api.post('/export/set-output-dir', { path }),
  generateSegmentAudio: (projectName: string, segmentId: string) =>
    api.post('/export/segment-audio', { project_name: projectName, segment_id: segmentId }),
  previewSegmentAudio: (data: {
    project_name: string
    text: string
    voice_id: string
    language: string
    rate?: string
    volume?: string
    pitch?: string
  }) => api.post('/export/preview-segment-audio', data),
}

// App Configuration Types
export interface AppConfig {
  server_host: string
  server_port: number
  tts_cache_enabled: boolean
  max_concurrent_tts: number
  tts_proxy_enabled: boolean
  tts_proxy_url: string | null
  default_video_codec: 'libx264' | 'libx265' | 'libvpx-vp9'
  default_audio_codec: 'aac' | 'mp3' | 'opus'
  default_crf: number
  default_preset: 'ultrafast' | 'superfast' | 'veryfast' | 'faster' | 'fast' | 'medium' | 'slow' | 'slower' | 'veryslow'
  lossless_crf: number
  high_crf: number
  balanced_crf: number
  tts_volume_boost: number
  bgm_volume_reduction: number
  fade_duration: number
  log_level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
}

export type AppConfigUpdate = Partial<AppConfig>

export interface AppConfigDefaults {
  defaults: AppConfig
  schema: Record<string, {
    type: string
    description: string
    min?: number
    max?: number
    options?: string[]
    unit?: string
  }>
}

// Settings API
export const settingsApi = {
  get: () => api.get('/settings'),
  update: (data: Record<string, unknown>) => api.put('/settings', data),
  getLLM: () => api.get('/settings/llm'),
  updateLLM: (data: Record<string, unknown>) => api.put('/settings/llm', data),
  getConfiguredProviders: () => api.get('/settings/llm/configured'),
  getSystem: () => api.get('/settings/system'),
  clearCache: () => api.post('/settings/clear-cache'),
  clearTemp: () => api.post('/settings/clear-temp'),
  // Storage path settings
  getStorage: () => api.get('/settings/storage'),
  updateStorage: (storagePath: string) => api.put('/settings/storage', { storage_path: storagePath }),
  resetStorage: () => api.post('/settings/storage/reset'),
  // App Configuration
  getAppConfig: () => api.get<AppConfig>('/settings/app-config'),
  updateAppConfig: (data: AppConfigUpdate) => api.put<AppConfig>('/settings/app-config', data),
  resetAppConfig: () => api.post<{ message: string; config: AppConfig; restart_required: boolean }>('/settings/app-config/reset'),
  getAppConfigDefaults: () => api.get<AppConfigDefaults>('/settings/app-config/defaults'),
}

// Fonts API
export const fontsApi = {
  getGoogleFonts: () => api.get('/fonts/google'),
  getLocalFonts: (refresh?: boolean) => api.get('/fonts/local', { params: refresh ? { refresh: true } : {} }),
  checkFont: (fontName: string) => api.get('/fonts/check', { params: { font_name: fontName } }),
}

// Favorites API - for storing user's favorite voices and fonts
export const favoritesApi = {
  get: () => api.get('/favorites'),
  toggle: (itemId: string, itemType: 'voice' | 'font') =>
    api.post('/favorites/toggle', { item_id: itemId, item_type: itemType }),
  add: (itemId: string, itemType: 'voice' | 'font') =>
    api.post('/favorites/add', { item_id: itemId, item_type: itemType }),
  remove: (itemId: string, itemType: 'voice' | 'font') =>
    api.post('/favorites/remove', { item_id: itemId, item_type: itemType }),
  clearAll: () => api.delete('/favorites'),
}

// Models API - for TTS model management (voice cloning models)
export interface VoiceCloningModel {
  model_id: string
  name: string
  description: string
  size_mb: number
  downloaded: boolean
  downloading: boolean
  download_progress: number
  languages: string[]
  recommended: boolean
  error: string | null
}

export interface ModelDownloadProgress {
  type: 'progress' | 'error' | 'complete' | 'status'
  stage: string
  message: string
  progress: number
  speed_mbps?: number
  eta_seconds?: number
  downloaded_mb?: number
  total_mb?: number
  details?: string
}

export const modelsApi = {
  // Get all voice cloning models with status
  getVoiceCloningModels: () => api.get<{ models: VoiceCloningModel[] }>('/models/voice-cloning'),

  // Start model download
  startDownload: (modelId: string) =>
    api.post<{ download_id: string; status: string; message: string }>(
      '/models/voice-cloning/download',
      { model_id: modelId }
    ),

  // Get download status
  getDownloadStatus: (downloadId: string) => api.get(`/models/voice-cloning/status/${downloadId}`),

  // Cancel download
  cancelDownload: (downloadId: string) => api.delete(`/models/voice-cloning/cancel/${downloadId}`),

  // Quick check if model is ready
  checkModel: (modelKey: string) =>
    api.get<{ model_key: string; downloaded: boolean; ready: boolean }>(
      `/models/voice-cloning/check/${modelKey}`
    ),

  // Create WebSocket for download progress
  createProgressWebSocket: (downloadId: string): WebSocket => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = import.meta.env.DEV ? `${window.location.hostname}:8000` : window.location.host
    return new WebSocket(`${wsProtocol}//${wsHost}/api/v1/models/voice-cloning/progress/${downloadId}`)
  },
}

export default api
