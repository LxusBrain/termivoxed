import { Outlet, Link, useLocation } from 'react-router-dom'
import { Home, Settings, Activity, Monitor, Cloud } from 'lucide-react'
import clsx from 'clsx'
import { useProviderStatus } from '../hooks/useProviderStatus'

function StatusIndicator({
  status,
  label,
  isLocal,
  showIcon
}: {
  status: boolean | null
  label: string
  isLocal?: boolean
  showIcon?: boolean
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      {showIcon && (
        isLocal ? (
          <Monitor className="w-3 h-3 text-text-muted" />
        ) : (
          <Cloud className="w-3 h-3 text-text-muted" />
        )
      )}
      <div
        className={clsx(
          'status-dot',
          status === true && 'status-dot-success',
          status === false && 'status-dot-error',
          status === null && 'status-dot-idle animate-pulse'
        )}
      />
      <span className="text-text-muted">{label}</span>
    </div>
  )
}

export default function Layout() {
  const location = useLocation()

  // Use shared provider status hook
  const { tts, llm } = useProviderStatus()

  // Determine LLM status
  const llmStatus = llm.isChecking ? null : llm.isConnected

  // Determine TTS status
  // For local providers, show connected if available
  // For cloud providers, show connectivity status
  const ttsStatus = tts.isChecking ? null : tts.isConnected

  return (
    <div className="min-h-screen bg-terminal-bg flex flex-col">
      {/* Header */}
      <header className="h-14 border-b border-terminal-border bg-terminal-surface flex items-center px-4 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          {/* Logo - Responsive: short logo on mobile, horizontal on larger screens */}
          <Link to="/" className="flex items-center">
            {/* Short logo for mobile/small screens */}
            <img
              src="/assets/Logo.svg"
              alt="TermiVoxed"
              className="h-8 w-auto block md:hidden"
            />
            {/* Horizontal logo for medium+ screens */}
            <img
              src="/assets/Horizontal_Logo.svg"
              alt="TermiVoxed"
              className="h-7 w-auto hidden md:block"
            />
          </Link>

          {/* Version badge */}
          <span className="text-[10px] font-mono bg-terminal-elevated px-1.5 py-0.5 rounded text-text-muted border border-terminal-border">
            v1.0.0
          </span>
        </div>

        {/* Navigation */}
        <nav className="ml-8 flex items-center gap-1">
          <Link
            to="/"
            className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-all',
              location.pathname === '/'
                ? 'bg-accent-red/10 text-accent-red border border-accent-red/30'
                : 'text-text-secondary hover:text-text-primary hover:bg-terminal-elevated'
            )}
          >
            <Home className="w-4 h-4" />
            <span>Projects</span>
          </Link>

          <Link
            to="/settings"
            className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-all',
              location.pathname === '/settings'
                ? 'bg-accent-red/10 text-accent-red border border-accent-red/30'
                : 'text-text-secondary hover:text-text-primary hover:bg-terminal-elevated'
            )}
          >
            <Settings className="w-4 h-4" />
            <span>Settings</span>
          </Link>
        </nav>

        {/* Status indicators */}
        <div className="ml-auto flex items-center gap-4">
          {/* LLM Provider Status - shows selected provider name */}
          <StatusIndicator
            status={llmStatus}
            label={llm.displayName}
            isLocal={llm.provider === 'ollama'}
            showIcon={true}
          />

          {/* TTS Provider Status */}
          {/* For local TTS (Coqui/Piper), show Monitor icon */}
          {/* For cloud TTS (Edge), show Cloud icon */}
          <StatusIndicator
            status={ttsStatus}
            label={tts.displayName}
            isLocal={tts.isLocal}
            showIcon={true}
          />

          <div className="h-4 w-px bg-terminal-border" />

          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <Activity className="w-3.5 h-3.5 text-accent-red" />
            <span className="font-mono">READY</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>

      {/* Footer status bar */}
      <footer className="h-6 border-t border-terminal-border bg-terminal-surface flex items-center px-4 text-[10px] font-mono text-text-muted">
        <span>TermiVoxed Web UI</span>
        <span className="mx-2 text-terminal-border">|</span>
        <span>AI Voice-Over Studio</span>
        <span className="ml-auto flex items-center gap-2">
          <span className="text-accent-red">●</span>
          <span>Connected</span>
        </span>
      </footer>
    </div>
  )
}
