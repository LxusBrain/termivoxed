import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load env from multiple locations
  const env = {
    ...loadEnv(mode, process.cwd(), ''),
    ...loadEnv(mode, '../../', 'TERMIVOXED_'),
    ...process.env, // Include runtime env vars (from start.sh)
  }

  // Backend port - check multiple sources
  // Priority: VITE_BACKEND_PORT (from start.sh) > TERMIVOXED_PORT > default
  const backendPort = parseInt(
    env.VITE_BACKEND_PORT || env.TERMIVOXED_PORT || '8000',
    10
  )

  // Frontend port - Vite will use --port flag, but we need this for config
  const frontendPort = parseInt(
    env.TERMIVOXED_FRONTEND_PORT || '5173',
    10
  )

  const host = env.TERMIVOXED_HOST || 'localhost'

  console.log(`[Vite Config] Backend: http://${host}:${backendPort}`)
  console.log(`[Vite Config] Frontend: http://${host}:${frontendPort}`)

  return {
    plugins: [react()],

    // Make backend port available to frontend code
    define: {
      'import.meta.env.VITE_BACKEND_PORT': JSON.stringify(backendPort.toString()),
    },

    server: {
      port: frontendPort,
      strictPort: false, // Allow fallback to next available port
      host: '0.0.0.0', // Allow connections from custom hostnames
      // COOP header required for Firebase popup auth
      headers: {
        'Cross-Origin-Opener-Policy': 'same-origin-allow-popups',
      },
      proxy: {
        '/api': {
          target: `http://${host}:${backendPort}`,
          changeOrigin: true,
        },
        '/storage': {
          target: `http://${host}:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
