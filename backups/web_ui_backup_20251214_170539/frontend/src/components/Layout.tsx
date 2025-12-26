import { Outlet, Link, useLocation } from 'react-router-dom'
import { Home, Settings, Cpu, Activity } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { llmApi, ttsApi } from '../api/client'
import clsx from 'clsx'

function StatusIndicator({ status, label }: { status: boolean | null; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
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

  // Check service status
  const { data: llmHealth } = useQuery({
    queryKey: ['llm-health'],
    queryFn: () => llmApi.checkHealth(),
    refetchInterval: 30000,
  })

  const { data: ttsStatus } = useQuery({
    queryKey: ['tts-status'],
    queryFn: () => ttsApi.checkConnectivity(),
    refetchInterval: 30000,
  })

  const ollamaConnected = llmHealth?.data?.ollama_available ?? null
  const ttsConnected = ttsStatus?.data?.direct_connection || ttsStatus?.data?.proxy_connection

  return (
    <div className="min-h-screen bg-terminal-bg flex flex-col">
      {/* Header */}
      <header className="h-14 border-b border-terminal-border bg-terminal-surface flex items-center px-4 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded bg-accent-red flex items-center justify-center shadow-glow-red-sm">
              <Cpu className="w-5 h-5 text-white" />
            </div>
            <span className="font-mono font-bold text-lg tracking-tight">
              <span className="text-accent-red">Termi</span>
              <span className="text-white">Voxed</span>
            </span>
          </div>

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
          <StatusIndicator status={ollamaConnected} label="Ollama" />
          <StatusIndicator status={ttsConnected ?? null} label="TTS" />

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
