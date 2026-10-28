import { expect, test } from '@playwright/test'

test('manual intake, conversation TaskProposal review, status filtering and human approval', async ({ page }) => {
  let demands: Array<Record<string, unknown>> = []
  let approvals: Array<Record<string, unknown>> = []
  let chatSent = false
  let proposalAccepted = false
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
      const item = { id: 'approval-1', entity_type: body.entity_type, entity_id: body.entity_id, status: 'pending', requested_by: 'agent', payload_hash: 'a'.repeat(64), subject_current: true, subject: { title: 'Add phone field', requirement_revisions: [{ version: 1, content: 'Allow phone number', acceptance: ['Phone is saved'] }], plan: { tasks: [] } } }
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
      demand: demands[0], revisions: [{ id: 'revision-1', version: 1, content: 'Add a feature', acceptance: ['Works locally'], decision: 'proposed' }], tasks: proposalAccepted ? [{ id: 'task-proposal-1', title: 'quero alterar a cor do botão para dark', owner_role: 'planner', status: 'blocked', blocked_reason: 'Aguardando evidência de gate', dependencies: [], runs: [{ id: 'run-1', attempt: 1, status: 'failed', base_git_sha: '1'.repeat(40), result_git_sha: null, tree_hash: null, started_at: '2026-10-25T00:00:00Z', finished_at: null, gates: [{ check_name: 'unit', status: 'fail', git_sha: '1'.repeat(40), artifact_sha256: '2'.repeat(64) }], artifacts: [{ id: 'artifact-1', path: 'artifacts/run/run-1/changes.diff', sha256: '2'.repeat(64), size_bytes: 20, media_type: 'text/x-diff' }] }] }] : [],
    } })
    if (path.endsWith('/conversation/messages') && request.method() === 'POST') {
      chatSent = true
      return route.fulfill({ json: { message_id: 'chat-message-1', task_proposal: { id: 'proposal-1', status: 'pending_review', payload_hash: 'b'.repeat(64), executable: false, requires_human_review: true } } })
    }
    if (path.includes('/conversation/proposals/') && path.endsWith('/accept') && request.method() === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>
      expect(body.path_scopes).toEqual(['apps/factory-web/src/**'])
      expect(body.acceptance).toEqual(['Build and E2E pass'])
      proposalAccepted = true
      return route.fulfill({ status: 201, json: { proposal_id: 'proposal-1', task_id: 'task-proposal-1', status: 'accepted' } })
    }
    if (path.endsWith('/conversation') && request.method() === 'POST') {
      const persona = (request.postDataJSON() as { persona: string }).persona
      return route.fulfill({ json: { thread_id: `thread-${persona}`, persona, reference: 'DEMAND-demand-1', active: true, messages: [{ id: `message-${persona}`, author: persona, content: `Conversa ${persona}`, kind: 'answer' }], task_proposals: [] } })
    }
    if (path.endsWith('/conversation') && request.method() === 'GET') {
      const persona = url.searchParams.get('persona') ?? 'qa'
      const proposals = chatSent ? [{ id: 'proposal-1', title: 'quero alterar a cor do botão para dark', description: 'Ajustar o tema dark', path_scopes: [], acceptance: [], status: proposalAccepted ? 'accepted' : 'pending_review', payload_hash: 'b'.repeat(64), executable: false, requires_human_review: true }] : []
      const messages = [{ id: `message-${persona}`, author: persona, content: `Conversa ${persona}`, kind: 'answer' }]
      if (proposals.length) messages.push({ id: 'proposal-message-1', author: 'TaskProposal', content: 'Ajustar o tema dark', kind: 'proposal', proposalStatus: 'pending', proposal: proposals[0] })
      return route.fulfill({ json: { thread_id: `thread-${persona}`, persona, reference: 'DEMAND-demand-1', active: true, messages, task_proposals: proposals } })
    }
    if (path.endsWith('/run-fake')) return route.fulfill({ json: { demand_id: 'demand-1', reviewed_task_ids: ['task-1'], model_called: false, human_review_required: true } })
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
  await page.getByRole('button', { name: /Add phone field/ }).first().click()
  await page.getByRole('button', { name: 'Executar simulação local' }).click()
  await expect(page.getByRole('status')).toHaveText('Simulação encerrada; 1 tarefa(s) aguardam revisão humana.')
  await page.getByLabel('Persona').selectOption('planner')
  await expect(page.getByText('Conversa planner')).toBeVisible()
  await page.getByLabel('Mensagem').fill('quero alterar a cor do botão para dark')
  await page.getByRole('button', { name: 'Enviar' }).click()
  await expect(page.getByText('TaskProposal · pending_review')).toBeVisible()
  await page.getByLabel('Escopos permitidos, um por linha').fill('apps/factory-web/src/**')
  await page.getByRole('region', { name: 'Conversa com agentes' }).getByLabel('Critérios de aceite, um por linha').fill('Build and E2E pass')
  await page.getByRole('button', { name: 'Revisar e aceitar como tarefa' }).click()
  await expect(page.getByText('TaskProposal · accepted')).toBeVisible()
  await expect(page.getByText('quero alterar a cor do botão para dark')).toBeVisible()
  await expect(page.getByText('Bloqueio: Aguardando evidência de gate')).toBeVisible()
  await expect(page.getByText('Gate unit: fail')).toBeVisible()
  await expect(page.getByRole('link', { name: /Ver diff:.*changes.diff/ })).toBeVisible()
  await page.getByRole('button', { name: 'Pedir revisão humana' }).click()
  await page.getByRole('button', { name: '← Todas as demandas' }).click()
  await page.getByLabel('Filtrar por estado').selectOption('completed')
  await expect(page.getByRole('button', { name: /Old completed demand/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /Add phone field/ })).toHaveCount(0)
  await page.getByRole('button', { name: /Aprovações/ }).click()
  await expect(page.getByText(/Solicitado por agent/)).toBeVisible()
  await page.getByText('Inspecionar conteúdo e plano').click()
  await expect(page.getByText(/Allow phone number/)).toBeVisible()
  await page.getByRole('button', { name: 'Solicitar alterações' }).focus()
  await page.keyboard.press('Shift+Tab')
  await expect(page.getByRole('button', { name: 'Aprovar' })).toBeFocused()
  await page.getByRole('button', { name: 'Aprovar' }).click()
  await expect(page.getByText('Nenhuma revisão pendente.')).toBeVisible()
})
