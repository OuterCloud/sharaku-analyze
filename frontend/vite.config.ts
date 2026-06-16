import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backendPort = process.env.BACKEND_PORT || '3335'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': `http://localhost:${backendPort}`,
      '/health': `http://localhost:${backendPort}`,
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
