import { expect, test } from '@playwright/test'
import { randomUUID } from 'node:crypto'

test('tag catalog, associations and filtering persist through the PostgreSQL API on mobile', async ({ page }) => {
  const suffix = randomUUID().replaceAll('-', '').slice(0, 12)
  const username = `tag-e2e-${suffix}`
  const fullName = `Tag E2E ${suffix}`
  const email = `tag-e2e-${suffix}@example.com`
  const firstTag = `vip-${suffix}`
  const secondTag = `beta-${suffix}`

  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Seus clientes/ })).toBeVisible()

  await page.getByLabel('Nova etiqueta').fill(firstTag)
  await page.getByRole('button', { name: 'Criar etiqueta' }).click()
  await expect(page.getByText(`Etiqueta “${firstTag}” criada.`)).toBeVisible()
  await page.getByLabel('Nova etiqueta').fill(firstTag)
  await page.getByRole('button', { name: 'Criar etiqueta' }).click()
  await expect(page.getByText(/TAG_ALREADY_EXISTS/)).toBeVisible()
  await page.getByLabel('Nova etiqueta').fill(secondTag)
  await page.getByRole('button', { name: 'Criar etiqueta' }).click()
  await expect(page.getByText(`Etiqueta “${secondTag}” criada.`)).toBeVisible()

  await page.getByLabel('Filtrar por etiqueta').selectOption({ label: firstTag })
  await expect(page.getByText('Sua lista começa aqui.')).toBeVisible()
  await page.getByLabel('Filtrar por etiqueta').selectOption('')

  const tagSelect = page.getByLabel('ETIQUETAS (ATÉ 10)')
  await tagSelect.selectOption([{ label: firstTag }, { label: secondTag }])
  await page.getByLabel('NOME DE USUÁRIO').fill(username)
  await page.getByLabel('NOME COMPLETO').fill(fullName)
  await page.getByLabel('E-MAIL').fill(email)
  await page.getByRole('button', { name: /Adicionar cliente/ }).click()
  await expect(page.getByText(fullName)).toBeVisible()
  const row = page.locator('.user-row').filter({ hasText: email })
  await expect(row.getByText(firstTag)).toBeVisible()
  await expect(row.getByText(secondTag)).toBeVisible()

  await page.getByLabel('Filtrar por etiqueta').selectOption({ label: firstTag })
  await expect(row).toBeVisible()
  await page.getByLabel('Buscar clientes').fill('sem-resultado')
  await expect(page.locator('.user-row')).toHaveCount(0)
  await expect(page.getByText('Nenhum resultado por aqui.')).toBeVisible()
  await page.getByLabel('Buscar clientes').fill(username)
  await expect(row).toBeVisible()

  await row.getByRole('button', { name: 'Editar' }).click()
  await tagSelect.selectOption({ label: firstTag })
  await page.getByRole('button', { name: 'Salvar alterações' }).click()
  await expect(row.getByText(firstTag)).toBeVisible()
  await expect(row.getByText(secondTag)).toHaveCount(0)

  await page.reload()
  await expect(page.getByLabel('Filtrar por etiqueta').getByRole('option', { name: firstTag })).toHaveCount(1)
  await expect(page.locator('.user-row').filter({ hasText: email }).getByText(firstTag)).toBeVisible()
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).resolves.toBe(true)

  await page.getByLabel('NOME DE USUÁRIO').fill(`${username}-keyboard`)
  await page.getByLabel('NOME COMPLETO').fill(`${fullName} Keyboard`)
  await page.getByLabel('E-MAIL').fill(`keyboard-${email}`)
  const submit = page.getByRole('button', { name: /Adicionar cliente/ })
  await page.getByRole('main').click({ position: { x: 2, y: 2 } })
  let keyboardFocused = false
  for (let index = 0; index < 30; index += 1) {
    await page.keyboard.press('Tab')
    if (await submit.evaluate((element) => document.activeElement === element)) {
      keyboardFocused = true
      break
    }
  }
  expect(keyboardFocused).toBe(true)
  await expect.poll(() => submit.evaluate((element) => getComputedStyle(element).outlineStyle)).toBe('solid')
})
