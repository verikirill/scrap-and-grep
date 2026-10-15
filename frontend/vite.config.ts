import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import icons from 'unplugin-icons/vite'
import { defineConfig } from 'vitest/config'

// In development the API is reached through the gateway of the running stack;
// in production Caddy serves the app and the API from one origin.
const API_TARGET = process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8080'

export default defineConfig({
  // Material Symbols are compiled into components at build time: only the
  // icons in use reach the bundle, and nothing is fetched at run time.
  plugins: [react(), tailwindcss(), icons({ compiler: 'jsx', jsx: 'react' })],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
    },
  },
  build: {
    target: 'es2023',
    sourcemap: false,
  },
  test: {
    // One clock everywhere: a laptop and a CI runner in UTC format dates alike.
    env: { TZ: 'Europe/Moscow' },
    // Projects inherit the plugins and aliases above (Vitest 5 default).
    projects: [
      // Pure functions: Node, no DOM.
      { test: { name: 'unit', environment: 'node', include: ['src/**/*.test.ts'] } },
      // Components and hooks: jsdom, the API answered by MSW.
      {
        test: {
          name: 'dom',
          environment: 'jsdom',
          include: ['src/**/*.test.tsx'],
          setupFiles: ['./src/test/setup.ts'],
          // vi.spyOn(window, 'confirm') and the like end with their test.
          restoreMocks: true,
          // A form of HeroUI fields takes a few seconds to drive on a busy runner.
          testTimeout: 15_000,
        },
      },
    ],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/main.tsx',
        'src/components/icons.tsx',
      ],
      // cobertura: the coverage GitLab draws on merge request diffs.
      reporter: ['text-summary', 'json-summary', 'html', 'cobertura'],
      // A little under what the suite reaches, so a change that drops tests fails.
      thresholds: { lines: 95, statements: 94, functions: 93, branches: 90 },
    },
  },
})
