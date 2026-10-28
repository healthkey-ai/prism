import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Where the app is served. '/' normally; set VITE_BASE_PATH (e.g. '/analytics/')
// at build time to serve PRism under a path prefix on a host shared with another
// app. Asset URLs and the API client's base URL both follow it.
const base = (process.env.VITE_BASE_PATH || '/').replace(/\/?$/, '/')

export default defineConfig({
  base,
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
