import { expect, test } from '@playwright/test'

async function mockDashboard(page: import('@playwright/test').Page, benchmarkStatus: number, empty = false) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/session')) return route.fulfill({ json: { authenticated: true, auth_enabled: false } })
    if (path.endsWith('/config/status')) return route.fulfill({ json: { services: {}, integrations: {}, secrets_exposed: false } })
    if (path.endsWith('/events/stream')) return route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': heartbeat\n\n' })
    if (path.endsWith('/approvals') || path.endsWith('/demands') || path.endsWith('/tasks')) return route.fulfill({ json: [] })
    if (path.endsWith('/observability/benchmarks')) {
      if (benchmarkStatus >= 400) return route.fulfill({ status: benchmarkStatus, json: { detail: { code: 'REPORT_UNAVAILABLE' } } })
      const role = new URL(route.request().url()).searchParams.get('role')
      return route.fulfill({ json: empty || role === 'judge'
        ? { status: 'empty', filters: { role, model: null }, records: [], source: 'test' }
        : { status: 'ready', filters: { role, model: null }, source: 'test', records: [{ role: 'coding', model: 'coder:7b', route: 'direct', run_id: 'run-123', latency_ms: 250, quality: null, accepted_tasks_per_hour: 0, tokens: 12, status: 'inconclusive', trace: 'LLMG-T12/summary.json' }] } })
    }
    return route.fulfill({ status: 404, json: { detail: { code: 'NOT_FOUND' } } })
  })
}

test('benchmarks navegáveis com cartões e estado vazio', async ({ page }) => {
  await mockDashboard(page, 200)
  await page.goto('/')
  await page.getByRole('button', { name: 'Benchmarks' }).click()
  await expect(page.getByRole('heading', { name: 'Benchmarks de coding e Judge' })).toBeVisible()
  await expect(page.getByText('Coding · direct')).toBeVisible()
  await expect(page.getByText('Trace: run-123')).toBeVisible()
  await page.getByRole('button', { name: 'Judge' }).click()
  await expect(page.getByRole('status')).toHaveText('Nenhum benchmark disponível para estes filtros.')
})

test('benchmarks mostra erro da API sem quebrar a navegação', async ({ page }) => {
  await mockDashboard(page, 503)
  await page.goto('/')
  await page.getByRole('button', { name: 'Benchmarks' }).click()
  await expect(page.getByRole('status')).toHaveText('REPORT_UNAVAILABLE')
})
