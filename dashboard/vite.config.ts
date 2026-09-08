import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Research dashboard dev server. Proxies API calls to the local FastAPI
// inference service (scripts/run_api.py) so the browser sees a same-origin
// API during development (UI_UX_BLUEPRINT §31.1).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
