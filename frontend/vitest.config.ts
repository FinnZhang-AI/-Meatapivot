import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Keep tests fast by default: a single worker, no per-test isolation
    // beyond what test files declare themselves. The CI workflow runs
    // npm test once and fails the build on any failure.
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      enabled: false, // toggle on with `vitest run --coverage` when wired
    },
  },
})
