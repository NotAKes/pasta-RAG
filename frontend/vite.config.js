import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: [
      'resplendently-connectional-maryanna.ngrok-free.dev' // Или твой конкретный
    ],
    proxy: {
      // ⚡️ МАГИЯ ЗДЕСЬ ⚡️
      // Все запросы на /api будут перенаправлены на порт 8000
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})