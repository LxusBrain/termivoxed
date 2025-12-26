import { create } from 'zustand'

// Log entry types
export type LogLevel = 'error' | 'warn' | 'info' | 'debug' | 'action'

export interface LogEntry {
  id: string
  timestamp: number
  level: LogLevel
  message: string
  data?: unknown
  stack?: string
  source?: string // Component or file source
  category?: string // e.g., 'video', 'audio', 'timeline', 'api', 'render'
}

export interface SystemInfo {
  userAgent: string
  platform: string
  language: string
  viewport: { width: number; height: number }
  screenResolution: { width: number; height: number }
  timezone: string
  memory?: { usedJSHeapSize: number; totalJSHeapSize: number; jsHeapSizeLimit: number }
  connection?: { effectiveType: string; downlink: number; rtt: number }
}

export interface SessionInfo {
  sessionId: string
  startTime: number
  projectName: string | null
  lastActivity: number
}

export interface CrashReport {
  id: string
  generatedAt: number
  systemInfo: SystemInfo
  sessionInfo: SessionInfo
  logs: LogEntry[]
  recentActions: LogEntry[]
  errorCount: number
  warningCount: number
}

interface DebugState {
  // Log storage
  logs: LogEntry[]
  maxLogs: number

  // Session tracking
  sessionInfo: SessionInfo

  // UI state
  isPanelOpen: boolean

  // Actions
  log: (level: LogLevel, message: string, data?: unknown, options?: { source?: string; category?: string; stack?: string }) => void
  error: (message: string, error?: Error | unknown, source?: string) => void
  warn: (message: string, data?: unknown, source?: string) => void
  info: (message: string, data?: unknown, source?: string) => void
  debug: (message: string, data?: unknown, source?: string) => void
  action: (actionName: string, data?: unknown) => void

  // Panel control
  togglePanel: () => void
  openPanel: () => void
  closePanel: () => void

  // Session management
  setProjectName: (name: string | null) => void
  updateLastActivity: () => void

  // Export
  generateCrashReport: () => CrashReport
  exportLogs: () => string
  clearLogs: () => void

  // Get logs by level
  getLogsByLevel: (level: LogLevel) => LogEntry[]
  getRecentErrors: (count?: number) => LogEntry[]
}

// Generate unique ID
const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

// Get system info
const getSystemInfo = (): SystemInfo => {
  const nav = navigator as Navigator & {
    connection?: { effectiveType: string; downlink: number; rtt: number }
  }

  const perf = performance as Performance & {
    memory?: { usedJSHeapSize: number; totalJSHeapSize: number; jsHeapSizeLimit: number }
  }

  return {
    userAgent: navigator.userAgent,
    platform: navigator.platform,
    language: navigator.language,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    screenResolution: { width: screen.width, height: screen.height },
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    memory: perf.memory ? {
      usedJSHeapSize: perf.memory.usedJSHeapSize,
      totalJSHeapSize: perf.memory.totalJSHeapSize,
      jsHeapSizeLimit: perf.memory.jsHeapSizeLimit,
    } : undefined,
    connection: nav.connection ? {
      effectiveType: nav.connection.effectiveType,
      downlink: nav.connection.downlink,
      rtt: nav.connection.rtt,
    } : undefined,
  }
}

// Initialize session
const createSession = (): SessionInfo => ({
  sessionId: generateId(),
  startTime: Date.now(),
  projectName: null,
  lastActivity: Date.now(),
})

export const useDebugStore = create<DebugState>((set, get) => ({
  logs: [],
  maxLogs: 1000, // Keep last 1000 logs
  sessionInfo: createSession(),
  isPanelOpen: false,

  log: (level, message, data, options) => {
    const entry: LogEntry = {
      id: generateId(),
      timestamp: Date.now(),
      level,
      message,
      data,
      stack: options?.stack,
      source: options?.source,
      category: options?.category,
    }

    set((state) => {
      const logs = [entry, ...state.logs].slice(0, state.maxLogs)
      return { logs, sessionInfo: { ...state.sessionInfo, lastActivity: Date.now() } }
    })
  },

  error: (message, error, source) => {
    let stack: string | undefined
    let errorData: unknown = error

    if (error instanceof Error) {
      stack = error.stack
      errorData = {
        name: error.name,
        message: error.message,
        cause: (error as Error & { cause?: unknown }).cause,
      }
    }

    get().log('error', message, errorData, { source, stack, category: 'error' })
  },

  warn: (message, data, source) => {
    get().log('warn', message, data, { source, category: 'warning' })
  },

  info: (message, data, source) => {
    get().log('info', message, data, { source, category: 'info' })
  },

  debug: (message, data, source) => {
    get().log('debug', message, data, { source, category: 'debug' })
  },

  action: (actionName, data) => {
    get().log('action', actionName, data, { category: 'action' })
  },

  togglePanel: () => set((state) => ({ isPanelOpen: !state.isPanelOpen })),
  openPanel: () => set({ isPanelOpen: true }),
  closePanel: () => set({ isPanelOpen: false }),

  setProjectName: (name) => set((state) => ({
    sessionInfo: { ...state.sessionInfo, projectName: name }
  })),

  updateLastActivity: () => set((state) => ({
    sessionInfo: { ...state.sessionInfo, lastActivity: Date.now() }
  })),

  generateCrashReport: () => {
    const state = get()
    const errors = state.logs.filter(l => l.level === 'error')
    const warnings = state.logs.filter(l => l.level === 'warn')
    const recentActions = state.logs.filter(l => l.level === 'action').slice(0, 50)

    return {
      id: generateId(),
      generatedAt: Date.now(),
      systemInfo: getSystemInfo(),
      sessionInfo: state.sessionInfo,
      logs: state.logs.slice(0, 200), // Last 200 logs
      recentActions,
      errorCount: errors.length,
      warningCount: warnings.length,
    }
  },

  exportLogs: () => {
    const report = get().generateCrashReport()
    return JSON.stringify(report, null, 2)
  },

  clearLogs: () => set({ logs: [] }),

  getLogsByLevel: (level) => get().logs.filter(l => l.level === level),

  getRecentErrors: (count = 10) => get().logs.filter(l => l.level === 'error').slice(0, count),
}))

// Utility function to format log entry for display
export const formatLogEntry = (entry: LogEntry): string => {
  const time = new Date(entry.timestamp).toISOString()
  const level = entry.level.toUpperCase().padEnd(5)
  const source = entry.source ? `[${entry.source}]` : ''
  const data = entry.data ? ` | ${JSON.stringify(entry.data)}` : ''
  return `${time} ${level} ${source} ${entry.message}${data}`
}

// Utility to safely stringify objects (handles circular references)
export const safeStringify = (obj: unknown, indent = 2): string => {
  const seen = new WeakSet()
  return JSON.stringify(obj, (_, value) => {
    if (typeof value === 'object' && value !== null) {
      if (seen.has(value)) {
        return '[Circular]'
      }
      seen.add(value)
    }
    if (value instanceof Error) {
      return { name: value.name, message: value.message, stack: value.stack }
    }
    return value
  }, indent)
}
