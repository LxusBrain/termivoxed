import { create } from 'zustand'
import type { Project, Segment, ExportProgress } from '../types'
import type { VideoAvailability } from '../api/client'

interface AppState {
  // Current project
  currentProject: Project | null
  setCurrentProject: (project: Project | null) => void

  // Active video
  activeVideoId: string | null
  setActiveVideoId: (id: string | null) => void

  // Segments
  segments: Segment[]
  setSegments: (segments: Segment[]) => void
  addSegment: (segment: Segment) => void
  updateSegment: (segmentOrId: Segment | string, data?: Partial<Segment>) => void
  removeSegment: (id: string) => void

  // Video playback
  currentTime: number
  setCurrentTime: (time: number) => void
  isPlaying: boolean
  setIsPlaying: (playing: boolean) => void

  // Selected segment for editing
  selectedSegmentId: string | null
  setSelectedSegmentId: (id: string | null) => void

  // Export progress
  exportProgress: ExportProgress | null
  setExportProgress: (progress: ExportProgress | null) => void
  isExporting: boolean
  setIsExporting: (exporting: boolean) => void

  // AI Script generation
  isGeneratingScript: boolean
  setIsGeneratingScript: (generating: boolean) => void

  // UI state
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  aiPanelOpen: boolean
  setAiPanelOpen: (open: boolean) => void

  // Video availability state
  videoAvailability: Map<string, VideoAvailability>
  setVideoAvailability: (videos: VideoAvailability[]) => void
  getVideoAvailability: (videoId: string) => VideoAvailability | undefined
  availabilityChecked: boolean
  setAvailabilityChecked: (checked: boolean) => void
  isCheckingAvailability: boolean
  setIsCheckingAvailability: (checking: boolean) => void
  resetAvailabilityState: () => void

  // Clear all state (called on logout to prevent cross-user data leakage)
  clearAllState: () => void
}

export const useAppStore = create<AppState>((set) => ({
  // Current project
  currentProject: null,
  setCurrentProject: (project) => set({ currentProject: project }),

  // Active video
  activeVideoId: null,
  setActiveVideoId: (id) => set({ activeVideoId: id }),

  // Segments
  segments: [],
  setSegments: (segments) => set({ segments }),
  addSegment: (segment) =>
    set((state) => ({ segments: [...state.segments, segment] })),
  updateSegment: (segmentOrId, data) =>
    set((state) => {
      // If first arg is a full segment object, replace the segment with that ID
      if (typeof segmentOrId === 'object' && segmentOrId !== null) {
        return {
          segments: state.segments.map((s) =>
            s.id === segmentOrId.id ? segmentOrId : s
          ),
        }
      }
      // Otherwise, update with partial data
      return {
        segments: state.segments.map((s) =>
          s.id === segmentOrId ? { ...s, ...data } : s
        ),
      }
    }),
  removeSegment: (id) =>
    set((state) => ({
      segments: state.segments.filter((s) => s.id !== id),
    })),

  // Video playback
  currentTime: 0,
  setCurrentTime: (time) => set({ currentTime: time }),
  isPlaying: false,
  setIsPlaying: (playing) => set({ isPlaying: playing }),

  // Selected segment
  selectedSegmentId: null,
  setSelectedSegmentId: (id) => set({ selectedSegmentId: id }),

  // Export progress
  exportProgress: null,
  setExportProgress: (progress) => set({ exportProgress: progress }),
  isExporting: false,
  setIsExporting: (exporting) => set({ isExporting: exporting }),

  // AI Script generation
  isGeneratingScript: false,
  setIsGeneratingScript: (generating) => set({ isGeneratingScript: generating }),

  // UI state
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  aiPanelOpen: false,
  setAiPanelOpen: (open) => set({ aiPanelOpen: open }),

  // Video availability state
  videoAvailability: new Map(),
  setVideoAvailability: (videos) =>
    set(() => {
      const map = new Map<string, VideoAvailability>()
      videos.forEach((v) => map.set(v.id, v))
      return { videoAvailability: map }
    }),
  getVideoAvailability: (videoId): VideoAvailability | undefined => {
    // This is a getter that accesses current state
    // Note: This won't trigger re-renders, use the Map directly for reactive access
    const state = useAppStore.getState()
    return state.videoAvailability.get(videoId)
  },
  availabilityChecked: false,
  setAvailabilityChecked: (checked) => set({ availabilityChecked: checked }),
  isCheckingAvailability: false,
  setIsCheckingAvailability: (checking) => set({ isCheckingAvailability: checking }),
  resetAvailabilityState: () =>
    set({
      videoAvailability: new Map(),
      availabilityChecked: false,
      isCheckingAvailability: false,
    }),

  // Clear all state on logout to prevent cross-user data leakage
  clearAllState: () =>
    set({
      currentProject: null,
      activeVideoId: null,
      segments: [],
      currentTime: 0,
      isPlaying: false,
      selectedSegmentId: null,
      exportProgress: null,
      isExporting: false,
      isGeneratingScript: false,
      sidebarOpen: true,
      aiPanelOpen: false,
      videoAvailability: new Map(),
      availabilityChecked: false,
      isCheckingAvailability: false,
    }),
}))
