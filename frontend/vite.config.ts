import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/ui/',
  build: {
    outDir: '../src/runspace_agent/server/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/sessions': 'http://localhost:6767',
      '/run': 'http://localhost:6767',
      '/skills': 'http://localhost:6767',
    },
  },
})
