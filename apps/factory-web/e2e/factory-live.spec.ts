import { expect, test } from '@playwright/test'

test('live dashboard creates a PostgreSQL demand, streams audit and records approval', async ({ page }) => {
  const password = process.env.FACTORY_OPERATOR_PASSWORD
  test.skip(!password, 'FACTORY_OPERATOR_PASSWORD must be injected by the local smoke command')

  await page.goto('/')
  await page.getByLabel('Senha local').fill(password!)
  await page.getByRole('button', { name: /Entrar/ }).click()
  await expect(page.getByRole('button', { name: 'Serviços' })).toBeVisible()

  const title = `Live smoke ${new Date().toISOString()} ${crypto.randomUUID().slice(0, 8)}`
  await page.getByLabel('Título').fill(title)
  await page.getByLabel('Requisito').fill('Validar dashboard com API e PostgreSQL reais')
  await page.getByLabel('Critérios de aceite, um por linha').fill('Demanda persistida e auditável')
  await page.getByRole('button', { name: 'Criar demanda' }).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
  const streamedAudit = await page.evaluate(async (apiBase) => {
    const response = await fetch(`${apiBase}/api/v1/events/stream`, { credentials: 'include' })
    if (!response.ok || !response.body) throw new Error(`SSE_HTTP_${response.status}`)
    const reader = response.body.getReader()
    const first = await reader.read()
    await reader.cancel()
    return new TextDecoder().decode(first.value)
  }, process.env.FACTORY_TEST_API_URL ?? 'http://127.0.0.1:8001')
  expect(streamedAudit).toContain('audit')
  expect(streamedAudit).toContain('demand.created')

  await page.getByRole('button', { name: 'Pedir revisão humana' }).click()
  await page.getByRole('button', { name: /Aprovações/ }).click()
  await expect(page.getByText(/Solicitado por agent/)).toBeVisible()
  await page.getByRole('button', { name: 'Aprovar' }).click()
  await expect(page.getByText('Nenhuma revisão pendente.')).toBeVisible()
})
