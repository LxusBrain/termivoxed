import { Component, type ReactNode, type ErrorInfo } from 'react'
import { useDebugStore } from '../stores/debugStore'
import { AlertTriangle, RefreshCw, Bug, Copy, Check } from 'lucide-react'
import { useState } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

// Wrapper component for the crash UI that uses hooks
function CrashUI({ error, errorInfo, onReset }: {
  error: Error
  errorInfo: ErrorInfo | null
  onReset: () => void
}) {
  const [copied, setCopied] = useState(false)
  const { generateCrashReport, exportLogs } = useDebugStore()

  const handleCopyReport = async () => {
    try {
      const report = exportLogs()
      await navigator.clipboard.writeText(report)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (e) {
      console.error('Failed to copy report:', e)
    }
  }

  const handleDownloadReport = () => {
    const report = generateCrashReport()
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `crash-report-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-terminal-bg flex items-center justify-center p-4">
      <div className="max-w-2xl w-full bg-terminal-elevated border border-red-500/30 rounded-lg shadow-xl overflow-hidden">
        {/* Header */}
        <div className="bg-red-500/10 border-b border-red-500/30 px-6 py-4 flex items-center gap-3">
          <div className="p-2 bg-red-500/20 rounded-full">
            <AlertTriangle className="w-6 h-6 text-red-500" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-red-400">Something went wrong</h1>
            <p className="text-sm text-text-muted">The application encountered an unexpected error</p>
          </div>
        </div>

        {/* Error Details */}
        <div className="px-6 py-4 space-y-4">
          <div>
            <h2 className="text-sm font-medium text-text-secondary mb-2">Error Message</h2>
            <div className="bg-terminal-bg rounded p-3 font-mono text-sm text-red-400 overflow-x-auto">
              {error.message}
            </div>
          </div>

          {errorInfo?.componentStack && (
            <div>
              <h2 className="text-sm font-medium text-text-secondary mb-2">Component Stack</h2>
              <div className="bg-terminal-bg rounded p-3 font-mono text-xs text-text-muted overflow-x-auto max-h-40 overflow-y-auto">
                <pre>{errorInfo.componentStack}</pre>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-3 pt-2">
            <button
              onClick={onReset}
              className="flex items-center gap-2 px-4 py-2 bg-accent-red hover:bg-accent-red-light rounded text-white font-medium transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>

            <button
              onClick={() => window.location.reload()}
              className="flex items-center gap-2 px-4 py-2 bg-terminal-border hover:bg-terminal-elevated rounded text-text-primary font-medium transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Reload Page
            </button>

            <button
              onClick={handleCopyReport}
              className="flex items-center gap-2 px-4 py-2 bg-terminal-border hover:bg-terminal-elevated rounded text-text-primary font-medium transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-green-500" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy Report
                </>
              )}
            </button>

            <button
              onClick={handleDownloadReport}
              className="flex items-center gap-2 px-4 py-2 bg-terminal-border hover:bg-terminal-elevated rounded text-text-primary font-medium transition-colors"
            >
              <Bug className="w-4 h-4" />
              Download Report
            </button>
          </div>

          {/* Help text */}
          <p className="text-xs text-text-muted pt-2">
            If this problem persists, please download the crash report and share it with the developers.
            The report contains technical information that will help diagnose the issue.
          </p>
        </div>
      </div>
    </div>
  )
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log to debug store
    const debugStore = useDebugStore.getState()
    debugStore.error(`React Error Boundary caught error: ${error.message}`, error, 'ErrorBoundary')
    debugStore.log('error', 'Component Stack', errorInfo.componentStack, {
      source: 'ErrorBoundary',
      category: 'render'
    })

    this.setState({ errorInfo })

    // Call custom error handler if provided
    this.props.onError?.(error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError && this.state.error) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default crash UI
      return (
        <CrashUI
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          onReset={this.handleReset}
        />
      )
    }

    return this.props.children
  }
}

// Higher-order component for functional components
export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback?: ReactNode
) {
  return function WithErrorBoundary(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <WrappedComponent {...props} />
      </ErrorBoundary>
    )
  }
}

export default ErrorBoundary
