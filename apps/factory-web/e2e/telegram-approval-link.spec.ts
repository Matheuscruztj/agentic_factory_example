import { expect, test } from '@playwright/test'

test('Telegram approval link opens the authenticated approvals view', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/session')) return route.fulfill({ json: { authenticated: false, auth_enabled: false } })
    if (path.endsWith('/config/status')) return route.fulfill({ json: { services: {}, integrations: {}, secrets_exposed: false } })
    if (path.endsWith('/demands') || path.endsWith('/tasks') || path.endsWith('/approvals')) return route.fulfill({ json: [] })
    return route.fulfill({ status: 200, body: ': heartbeat\n\n' })
  })

  await page.goto('/?tab=approvals')
  await expect(page.getByRole('button', { name: /Aprovações/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('heading', { name: 'Caixa de revisão humana' })).toBeVisible()
})
