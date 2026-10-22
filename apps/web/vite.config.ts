/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: { react: ['react', 'react-dom'], motion: ['motion/react'], query: ['@tanstack/react-query'] },
      },
    },
  },
  server: {
    port: 5180,
    proxy: { '/api': 'http://127.0.0.1:8010' },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
