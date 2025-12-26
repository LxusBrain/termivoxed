import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load env from parent directories (web_ui and project root)
  const env = {
    ...loadEnv(mode, process.cwd(), ''),
    ...loadEnv(mode, '../../', 'TERMIVOXED_'),
  }

  const frontendPort = parseInt(env.TERMIVOXED_FRONTEND_PORT || '5173', 10)
  const backendPort = parseInt(env.TERMIVOXED_PORT || '8000', 10)
  const host = env.TERMIVOXED_HOST || 'localhost'

  return {
    plugins: [react()],
    server: {
      port: frontendPort,
      host: '0.0.0.0', // Allow connections from custom hostnames
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
