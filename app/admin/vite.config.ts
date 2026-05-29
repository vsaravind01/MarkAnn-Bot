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
    host: true,
    port: 5173,
    proxy: {
      '/auth': process.env.VITE_GATEWAY_URL ?? 'http://localhost:9150',
      '/admin': process.env.VITE_GATEWAY_URL ?? 'http://localhost:9150',
    },
  },
})
