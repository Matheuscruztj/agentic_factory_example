import { expect, test } from '@playwright/test'
import { randomUUID } from 'node:crypto'

const suffix = randomUUID().replaceAll('-', '').slice(0, 12)
const username = `demo-${suffix}`
const fullName = `Marina Demo ${suffix}`
const updatedName = `Marina Costa ${suffix}`
const email = `marina-${suffix}@example.com`
const phone = '+55 85 99999-0000'
const tagName = `vip-${suffix}`

test('creates, searches, edits and deactivates a user', async ({ page }) => {
  page.on('dialog', (dialog) => dialog.accept())
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Seus clientes/ })).toBeVisible()

  await page.getByLabel('NOME DE USUÁRIO').fill(username)
  await page.getByLabel('NOME COMPLETO').fill(fullName)
  await page.getByLabel('E-MAIL').fill(email)
  await page.getByLabel('TELEFONE (OPCIONAL)').fill(phone)
  await page.getByLabel('Nova etiqueta').fill(tagName)
  await page.getByRole('button', { name: 'Criar etiqueta' }).click()
  await expect(page.getByText(`Etiqueta “${tagName}” criada.`)).toBeVisible()
  await page.getByLabel('ETIQUETAS (ATÉ 10)').selectOption({ label: tagName })
  await page.getByRole('button', { name: /Adicionar cliente/ }).click()
  await expect(page.getByText(fullName)).toBeVisible()
  await expect(page.getByText(phone)).toBeVisible()
  await expect(page.locator('.user-row').filter({ hasText: email }).getByText(tagName)).toBeVisible()

  await page.getByLabel('Filtrar por etiqueta').selectOption({ label: tagName })
  await expect(page.locator('.user-row')).toHaveCount(1)
  await page.getByLabel('Filtrar por etiqueta').selectOption('')

  await page.getByLabel('Buscar clientes').fill(username)
  await expect(page.getByText(email)).toBeVisible()
  await expect(page.locator('.user-row')).toHaveCount(1)
  await page.locator('.user-row').filter({ hasText: email }).getByRole('button', { name: 'Editar' }).click()
  await page.getByLabel('NOME COMPLETO').fill(updatedName)
  await page.getByLabel('TELEFONE (OPCIONAL)').fill('+55 85 98888-0000')
  await page.getByRole('button', { name: 'Salvar alterações' }).click()
  await expect(page.getByText(updatedName)).toBeVisible()
  await expect(page.getByText('+55 85 98888-0000')).toBeVisible()

  await page.locator('.user-row').filter({ hasText: email }).getByRole('button', { name: 'Editar' }).click()
  await page.getByLabel('ETIQUETAS (ATÉ 10)').selectOption([])
  await page.getByRole('button', { name: 'Salvar alterações' }).click()
  await expect(page.locator('.user-row').filter({ hasText: email }).getByText(tagName)).toHaveCount(0)
  await expect(page.getByLabel('Filtrar por etiqueta').getByRole('option', { name: tagName })).toHaveCount(1)

  await page.locator('.user-row').filter({ hasText: email }).getByRole('button', { name: 'Editar' }).click()
  await page.getByLabel('TELEFONE (OPCIONAL)').fill('')
  await page.getByRole('button', { name: 'Salvar alterações' }).click()
  await expect(page.locator('.user-row').filter({ hasText: email }).getByText('+55 85 98888-0000')).toHaveCount(0)

  await page.getByRole('button', { name: `Desativar ${updatedName}` }).click()
  await expect(page.getByText(`${updatedName} foi desativado.`)).toBeVisible()
  await expect(page.getByRole('button', { name: `Desativar ${updatedName}` })).toHaveCount(0)
})
