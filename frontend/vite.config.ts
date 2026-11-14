import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// In development, pass API calls and frame PNGs through to the FastAPI backend
// (uvicorn backend.app:app --reload, on port 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/frames': 'http://127.0.0.1:8000',
    },
  },
})
