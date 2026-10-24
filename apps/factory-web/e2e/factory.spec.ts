import { expect, test } from '@playwright/test'

test('manual intake, status filtering, detail and human approval', async ({ page }) => {
  let demands: Array<Record<string, unknown>> = []
  let approvals: Array<Record<string, unknown>> = []
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (path.endsWith('/auth/session')) return route.fulfill({ json: { authenticated: true, auth_enabled: false } })
    if (path.endsWith('/config/status')) return route.fulfill({ json: { services: { database: 'ready' }, integrations: {}, secrets_exposed: false } })
    if (path.endsWith('/events/stream')) return route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': heartbeat\n\n' })
    if (path.endsWith('/approvals') && request.method() === 'GET') return route.fulfill({ json: approvals })
    if (path.endsWith('/approvals') && request.method() === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>
      const item = { id: 'approval-1', entity_type: body.entity_type, entity_id: body.entity_id, status: 'pending', requested_by: 'agent', payload_hash: 'a'.repeat(64) }
      approvals = [item]
      return route.fulfill({ status: 201, json: item })
    }
    if (path.includes('/approvals/') && path.endsWith('/decision')) {
      approvals = []
      return route.fulfill({ json: { id: 'approval-1', status: 'approved' } })
    }
    if (path.endsWith('/demands') && request.method() === 'GET') return route.fulfill({ json: demands })
    if (path.endsWith('/demands') && request.method() === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>
      const item = { id: 'demand-1', ...body, status: 'new', version: 2, state_version: 1, risk: 'normal', repository_id: 'self' }
      demands = [item, { ...item, id: 'demand-old', title: 'Old completed demand', status: 'completed' }]
      return route.fulfill({ status: 201, json: item })
    }
    if (path.endsWith('/demands/demand-1')) return route.fulfill({ json: {
      demand: demands[0], revisions: [{ id: 'revision-1', version: 1, content: 'Add a feature', acceptance: ['Works locally'], decision: 'proposed' }], tasks: [],
    } })
    if (path.endsWith('/run-fake')) return route.fulfill({ json: { demand_id: 'demand-1', completed_task_ids: ['task-1'], model_called: false, approval_required: true } })
    if (path.endsWith('/tasks')) return route.fulfill({ json: [] })
    return route.fulfill({ status: 404, json: { detail: { code: 'NOT_FOUND' } } })
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Demandas 0' })).toBeVisible()
  await page.getByLabel('Título').fill('Add phone field')
  await page.getByLabel('Requisito').fill('Allow phone number')
  await page.getByLabel('Critérios de aceite, um por linha').fill('Phone is saved')
  await page.getByRole('button', { name: 'Criar demanda' }).click()
  await expect(page.getByRole('heading', { name: 'Add phone field' })).toBeVisible()
  await expect(page.getByText('Add a feature')).toBeVisible()
  await page.getByRole('button', { name: 'Executar simulação local' }).click()
  await expect(page.getByRole('status')).toHaveText('Simulação concluída sem LLM.')
  await page.getByRole('button', { name: 'Pedir revisão humana' }).click()
  await page.getByRole('button', { name: '← Todas as demandas' }).click()
  await page.getByLabel('Filtrar por estado').selectOption('completed')
  await expect(page.getByRole('button', { name: /Old completed demand/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /Add phone field/ })).toHaveCount(0)
  await page.getByRole('button', { name: /Aprovações/ }).click()
  await expect(page.getByText(/Solicitado por agent/)).toBeVisible()
  await page.getByRole('button', { name: 'Solicitar alterações' }).focus()
  await page.keyboard.press('Shift+Tab')
  await expect(page.getByRole('button', { name: 'Aprovar' })).toBeFocused()
  await page.getByRole('button', { name: 'Aprovar' }).click()
  await expect(page.getByText('Nenhuma revisão pendente.')).toBeVisible()
})
