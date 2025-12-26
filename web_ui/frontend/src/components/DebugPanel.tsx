import { useEffect, useState, useRef, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { useDebugStore, type LogLevel, type LogEntry } from '../stores/debugStore'
import {
  X,
  Bug,
  AlertTriangle,
  AlertCircle,
  Info,
  Terminal,
  MousePointer,
  Download,
  Copy,
  Check,
  Trash2,
  Filter,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Minimize2
} from 'lucide-react'
import clsx from 'clsx'

const LEVEL_ICONS: Record<LogLevel, typeof AlertCircle> = {
  error: AlertCircle,
  warn: AlertTriangle,
  info: Info,
  debug: Terminal,
  action: MousePointer,
}

const LEVEL_COLORS: Record<LogLevel, string> = {
  error: 'text-red-400 bg-red-500/10',
  warn: 'text-yellow-400 bg-yellow-500/10',
  info: 'text-blue-400 bg-blue-500/10',
  debug: 'text-gray-400 bg-gray-500/10',
  action: 'text-purple-400 bg-purple-500/10',
}

function LogEntryRow({ entry, isExpanded, onToggle }: {
  entry: LogEntry
  isExpanded: boolean
  onToggle: () => void
}) {
  const Icon = LEVEL_ICONS[entry.level]
  const colorClass = LEVEL_COLORS[entry.level]
  const date = new Date(entry.timestamp)
  const time = date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }) + '.' + String(date.getMilliseconds()).padStart(3, '0')

  return (
    <div className={clsx('border-b border-terminal-border/50 hover:bg-terminal-elevated/50', colorClass.split(' ')[1])}>
      <div
        className="flex items-start gap-2 px-3 py-1.5 cursor-pointer"
        onClick={onToggle}
      >
        <Icon className={clsx('w-3.5 h-3.5 mt-0.5 shrink-0', colorClass.split(' ')[0])} />
        <span className="text-[10px] font-mono text-text-muted shrink-0 w-20">{time}</span>
        {entry.source && (
          <span className="text-[10px] font-mono text-accent-primary shrink-0">[{entry.source}]</span>
        )}
        <span className="text-xs text-text-primary flex-1 truncate">{entry.message}</span>
        {(entry.data || entry.stack) && (
          isExpanded ? <ChevronUp className="w-3 h-3 text-text-muted" /> : <ChevronDown className="w-3 h-3 text-text-muted" />
        )}
      </div>

      {isExpanded && (entry.data !== undefined || entry.stack) && (
        <div className="px-3 pb-2 ml-6 space-y-1">
          {entry.data !== undefined && (
            <pre className="text-[10px] font-mono text-text-muted bg-terminal-bg rounded p-2 overflow-x-auto max-h-32 overflow-y-auto">
              {typeof entry.data === 'string' ? entry.data : JSON.stringify(entry.data, null, 2)}
            </pre>
          )}
          {entry.stack && (
            <pre className="text-[10px] font-mono text-red-300/70 bg-red-500/5 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto">
              {entry.stack}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

export default function DebugPanel() {
  const {
    logs,
    isPanelOpen,
    closePanel,
    togglePanel,
    clearLogs,
    exportLogs,
    generateCrashReport,
    sessionInfo
  } = useDebugStore()

  const [filter, setFilter] = useState<LogLevel | 'all'>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const [copied, setCopied] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const logsContainerRef = useRef<HTMLDivElement>(null)

  // Keyboard shortcut: Ctrl+Shift+D to toggle panel
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        e.preventDefault()
        togglePanel()
      }
      // ESC to close
      if (e.key === 'Escape' && isPanelOpen) {
        closePanel()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [togglePanel, closePanel, isPanelOpen])

  // Filter logs
  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      if (filter !== 'all' && log.level !== filter) return false
      if (searchTerm) {
        const searchLower = searchTerm.toLowerCase()
        return (
          log.message.toLowerCase().includes(searchLower) ||
          log.source?.toLowerCase().includes(searchLower) ||
          JSON.stringify(log.data).toLowerCase().includes(searchLower)
        )
      }
      return true
    })
  }, [logs, filter, searchTerm])

  // Count by level
  const counts = useMemo(() => ({
    error: logs.filter(l => l.level === 'error').length,
    warn: logs.filter(l => l.level === 'warn').length,
    info: logs.filter(l => l.level === 'info').length,
    debug: logs.filter(l => l.level === 'debug').length,
    action: logs.filter(l => l.level === 'action').length,
  }), [logs])

  const handleToggleExpand = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleCopyLogs = async () => {
    try {
      const report = exportLogs()
      await navigator.clipboard.writeText(report)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (e) {
      console.error('Failed to copy logs:', e)
    }
  }

  const handleDownloadReport = () => {
    const report = generateCrashReport()
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `debug-report-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  if (!isPanelOpen) return null

  const panel = (
    <div
      className={clsx(
        'fixed z-[9999] bg-terminal-bg border border-terminal-border rounded-lg shadow-2xl transition-all duration-200',
        isMinimized
          ? 'bottom-4 right-4 w-64 h-10'
          : 'bottom-4 right-4 w-[600px] h-[500px] max-w-[90vw] max-h-[80vh]'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-terminal-border bg-terminal-elevated rounded-t-lg">
        <div className="flex items-center gap-2">
          <Bug className="w-4 h-4 text-accent-red" />
          <span className="text-sm font-medium text-text-primary">Debug Console</span>
          <span className="text-[10px] text-text-muted bg-terminal-bg px-1.5 py-0.5 rounded">
            {logs.length} logs
          </span>
          {counts.error > 0 && (
            <span className="text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
              {counts.error} errors
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1 rounded hover:bg-terminal-border text-text-muted hover:text-text-primary"
            title={isMinimized ? 'Maximize' : 'Minimize'}
          >
            {isMinimized ? <Maximize2 className="w-3.5 h-3.5" /> : <Minimize2 className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={closePanel}
            className="p-1 rounded hover:bg-terminal-border text-text-muted hover:text-text-primary"
            title="Close (ESC)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Toolbar */}
          <div className="flex items-center gap-2 px-3 py-2 border-b border-terminal-border bg-terminal-elevated/50">
            {/* Level filter buttons */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => setFilter('all')}
                className={clsx(
                  'text-[10px] px-2 py-0.5 rounded transition-colors',
                  filter === 'all' ? 'bg-accent-red text-white' : 'bg-terminal-border text-text-muted hover:text-text-primary'
                )}
              >
                All
              </button>
              {(['error', 'warn', 'info', 'action'] as LogLevel[]).map(level => (
                <button
                  key={level}
                  onClick={() => setFilter(level)}
                  className={clsx(
                    'text-[10px] px-2 py-0.5 rounded transition-colors flex items-center gap-1',
                    filter === level
                      ? LEVEL_COLORS[level].replace('text-', 'bg-').replace('/10', '/30') + ' text-white'
                      : 'bg-terminal-border text-text-muted hover:text-text-primary'
                  )}
                >
                  {level}
                  {counts[level] > 0 && <span className="opacity-70">({counts[level]})</span>}
                </button>
              ))}
            </div>

            {/* Search */}
            <div className="flex-1 relative">
              <Filter className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-text-muted" />
              <input
                type="text"
                placeholder="Search logs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-terminal-bg border border-terminal-border rounded pl-7 pr-2 py-1 text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary"
              />
            </div>

            {/* Actions */}
            <button
              onClick={handleCopyLogs}
              className="p-1.5 rounded hover:bg-terminal-border text-text-muted hover:text-text-primary"
              title="Copy all logs"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={handleDownloadReport}
              className="p-1.5 rounded hover:bg-terminal-border text-text-muted hover:text-text-primary"
              title="Download debug report"
            >
              <Download className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={clearLogs}
              className="p-1.5 rounded hover:bg-terminal-border text-text-muted hover:text-red-400"
              title="Clear logs"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Session Info */}
          <div className="px-3 py-1.5 border-b border-terminal-border bg-terminal-bg/50 text-[10px] font-mono text-text-muted flex items-center gap-4">
            <span>Session: {sessionInfo.sessionId.slice(0, 8)}...</span>
            <span>Project: {sessionInfo.projectName || 'None'}</span>
            <span>Duration: {Math.round((Date.now() - sessionInfo.startTime) / 1000 / 60)}m</span>
          </div>

          {/* Logs list */}
          <div
            ref={logsContainerRef}
            className="flex-1 overflow-y-auto overflow-x-hidden"
            style={{ height: 'calc(100% - 140px)' }}
          >
            {filteredLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-text-muted">
                <Terminal className="w-8 h-8 mb-2 opacity-50" />
                <p className="text-sm">No logs to display</p>
                <p className="text-xs mt-1">Logs will appear here as the app runs</p>
              </div>
            ) : (
              filteredLogs.map(entry => (
                <LogEntryRow
                  key={entry.id}
                  entry={entry}
                  isExpanded={expandedIds.has(entry.id)}
                  onToggle={() => handleToggleExpand(entry.id)}
                />
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-3 py-1.5 border-t border-terminal-border bg-terminal-elevated/50 text-[10px] text-text-muted">
            Press <kbd className="px-1 py-0.5 bg-terminal-bg rounded border border-terminal-border font-mono">Ctrl+Shift+D</kbd> to toggle
          </div>
        </>
      )}
    </div>
  )

  // Render in portal to ensure it's on top of everything
  return createPortal(panel, document.body)
}
