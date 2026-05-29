import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:9150',
      '/admin': 'http://localhost:9150',
    },
  },
})
