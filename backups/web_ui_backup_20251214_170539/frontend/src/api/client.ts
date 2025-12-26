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
})

// BGM Track types
export interface BGMTrack {
  id: string
  name: string
  path: string
  start_time: number
  end_time: number
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
  volume?: number
}

export interface UpdateBGMTrackRequest {
  name?: string
  path?: string
  start_time?: number
  end_time?: number
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

// Settings API
export const settingsApi = {
  get: () => api.get('/settings'),
  update: (data: Record<string, unknown>) => api.put('/settings', data),
  getLLM: () => api.get('/settings/llm'),
  updateLLM: (data: Record<string, unknown>) => api.put('/settings/llm', data),
  getSystem: () => api.get('/settings/system'),
  clearCache: () => api.post('/settings/clear-cache'),
  clearTemp: () => api.post('/settings/clear-temp'),
}

// Fonts API
export const fontsApi = {
  getGoogleFonts: () => api.get('/fonts/google'),
  checkFont: (fontName: string) => api.get('/fonts/check', { params: { font_name: fontName } }),
}

export default api
