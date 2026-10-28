import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  reporter: 'line',
  use: { ...devices['Desktop Chrome'], baseURL: process.env.FACTORY_TEST_WEB_URL ?? 'http://127.0.0.1:5173', screenshot: 'only-on-failure', trace: process.env.FACTORY_TEST_EXTERNAL_SERVER === 'true' ? 'off' : 'retain-on-failure' },
  outputDir: process.env.FACTORY_TEST_OUTPUT_DIR ?? 'test-results',
  webServer: process.env.FACTORY_TEST_EXTERNAL_SERVER === 'true' ? undefined : { command: 'pnpm dev', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI, timeout: 30_000 },
})
