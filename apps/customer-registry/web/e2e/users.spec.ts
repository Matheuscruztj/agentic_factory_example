import { expect, test } from '@playwright/test'

const suffix = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`
const username = `demo-${suffix}`
const fullName = `Marina Demo ${suffix}`
const updatedName = `Marina Costa ${suffix}`
const email = `marina-${suffix}@example.com`

test('creates, searches, edits and deactivates a user', async ({ page }) => {
  page.on('dialog', (dialog) => dialog.accept())
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Seus clientes/ })).toBeVisible()

  await page.getByLabel('NOME DE USUÁRIO').fill(username)
  await page.getByLabel('NOME COMPLETO').fill(fullName)
  await page.getByLabel('E-MAIL').fill(email)
  await page.getByRole('button', { name: /Adicionar cliente/ }).click()
  await expect(page.getByText(fullName)).toBeVisible()

  await page.getByLabel('Buscar clientes').fill(username)
  await expect(page.getByText(email)).toBeVisible()
  await page.getByRole('button', { name: 'Editar' }).click()
  await page.getByLabel('NOME COMPLETO').fill(updatedName)
  await page.getByRole('button', { name: 'Salvar alterações' }).click()
  await expect(page.getByText(updatedName)).toBeVisible()

  await page.getByRole('button', { name: `Desativar ${updatedName}` }).click()
  await expect(page.getByText(`${updatedName} foi desativado.`)).toBeVisible()
  await expect(page.getByRole('button', { name: `Desativar ${updatedName}` })).toHaveCount(0)
})
