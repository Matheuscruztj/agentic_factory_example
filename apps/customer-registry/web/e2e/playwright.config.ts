import { defineConfig } from '@playwright/test'
import path from 'node:path'

const root = path.resolve(process.cwd(), '../../..')
const databasePath = path.join(root, '.runtime/e2e-customer-registry.sqlite3')

export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.ts',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: 'uv run uvicorn customer_registry.main:app --app-dir apps/customer-registry/api/src --host 127.0.0.1 --port 8010',
      cwd: root,
      url: 'http://127.0.0.1:8010/health/ready',
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        REGISTRY_SQLITE_PATH: databasePath,
        PYTHONPATH: [
          path.join(root, 'apps/customer-registry/api/src'),
          path.join(root, 'packages/shared-contracts/src'),
        ].join(path.delimiter),
      },
    },
    {
      command: 'pnpm dev --host 127.0.0.1',
      url: 'http://127.0.0.1:5174',
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
})
