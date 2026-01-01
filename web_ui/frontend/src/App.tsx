import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ProjectPage from './pages/ProjectPage'
import SettingsPage from './pages/SettingsPage'
import LoginPage from './pages/auth/LoginPage'
import SignupPage from './pages/auth/SignupPage'
import ForgotPasswordPage from './pages/auth/ForgotPasswordPage'
import AccountPage from './pages/AccountPage'
import LegalPage from './pages/LegalPage'
import TTSConsentModal from './components/TTSConsentModal'
import { ErrorBoundary } from './components/ErrorBoundary'
import DebugPanel from './components/DebugPanel'
import RequireAuth from './components/RequireAuth'
import useGlobalErrorHandler from './hooks/useGlobalErrorHandler'
import { useAuthStore } from './stores/authStore'

// Component that initializes global error handling and auth
function GlobalInitializer({ children }: { children: React.ReactNode }) {
  useGlobalErrorHandler()
  const initialize = useAuthStore((state) => state.initialize)

  // Initialize auth on app load
  useEffect(() => {
    initialize()
  }, [initialize])

  return <>{children}</>
}

function App() {
  return (
    <ErrorBoundary>
      <GlobalInitializer>
        <Routes>
          {/* Public auth routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />

          {/* Account route */}
          <Route path="/account" element={<RequireAuth><AccountPage /></RequireAuth>} />

          {/* Legal pages */}
          <Route path="/legal/:type" element={<LegalPage />} />
          {/* Shortcut routes for common legal pages */}
          <Route path="/terms" element={<Navigate to="/legal/terms" replace />} />
          <Route path="/privacy" element={<Navigate to="/legal/privacy" replace />} />
          <Route path="/refund" element={<Navigate to="/legal/refund" replace />} />
          <Route path="/eula" element={<Navigate to="/legal/eula" replace />} />
          <Route path="/cookies" element={<Navigate to="/legal/cookies" replace />} />

          {/* Protected routes */}
          <Route path="/" element={<Layout />}>
            <Route
              index
              element={
                <RequireAuth>
                  <HomePage />
                </RequireAuth>
              }
            />
            <Route
              path="project/:projectName"
              element={
                <RequireAuth>
                  <ProjectPage />
                </RequireAuth>
              }
            />
            <Route
              path="settings"
              element={
                <RequireAuth>
                  <SettingsPage />
                </RequireAuth>
              }
            />
          </Route>

          {/* 404 - Not Found */}
          <Route path="*" element={
            <div className="min-h-screen flex flex-col items-center justify-center bg-terminal-bg text-text-primary">
              <h1 className="text-6xl font-bold text-accent-red mb-4">404</h1>
              <p className="text-xl text-text-secondary mb-8">Page not found</p>
              <a href="/" className="px-6 py-3 bg-accent-red hover:bg-accent-red-dark text-white rounded-lg transition-colors">
                Go Home
              </a>
            </div>
          } />
        </Routes>

        {/* Global modals */}
        <TTSConsentModal />

        {/* Debug panel - hidden by default, toggle with Ctrl+Shift+D */}
        <DebugPanel />
      </GlobalInitializer>
    </ErrorBoundary>
  )
}

export default App
