import { expect, test } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

function contrastRatio(foreground: string, background: string): number {
  const luminance = (color: string) => {
    const channels = color.match(/[\d.]+/g)?.slice(0, 3).map(Number) ?? []
    const linear = channels.map((channel) => {
      const value = channel / 255
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * (linear[0] ?? 0) + 0.7152 * (linear[1] ?? 0) + 0.0722 * (linear[2] ?? 0)
  }
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
  return ((values[0] ?? 0) + 0.05) / ((values[1] ?? 0) + 0.05)
}

test('Cadastro button uses the dark palette with accessible interactive states', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')

  const button = page.getByRole('button', { name: /Adicionar cliente/ })
  await expect(button).toBeVisible()
  const normal = await button.evaluate((element) => ({
    background: getComputedStyle(element).backgroundColor,
    color: getComputedStyle(element).color,
  }))
  expect(normal.background).toBe('rgb(32, 38, 34)')
  expect(normal.color).toBe('rgb(255, 255, 255)')
  expect(contrastRatio(normal.color, normal.background)).toBeGreaterThanOrEqual(4.5)
  expect(await page.locator('html').evaluate((element) => getComputedStyle(element).backgroundColor))
    .toBe('rgb(245, 247, 244)')

  await button.hover()
  await expect.poll(
    () => button.evaluate((element) => getComputedStyle(element).backgroundColor),
  ).toBe('rgb(17, 24, 19)')
  const hover = await button.evaluate((element) => ({
    background: getComputedStyle(element).backgroundColor,
    color: getComputedStyle(element).color,
  }))
  expect(hover.background).toBe('rgb(17, 24, 19)')
  expect(contrastRatio(hover.color, hover.background)).toBeGreaterThanOrEqual(4.5)

  await page.getByRole('main').click({ position: { x: 2, y: 2 } })
  let focused = false
  for (let index = 0; index < 30; index += 1) {
    await page.keyboard.press('Tab')
    if (await button.evaluate((element) => document.activeElement === element)) {
      focused = true
      break
    }
  }
  expect(focused).toBe(true)
  const focusOutline = await button.evaluate((element) => {
    const style = getComputedStyle(element)
    return { style: style.outlineStyle, width: style.outlineWidth }
  })
  expect(focusOutline).toEqual({ style: 'solid', width: '3px' })
  const screenshot = fileURLToPath(
    new URL('../../../../.runtime/artifacts/real-journeys/dark-button-mobile-focus.png', import.meta.url),
  )
  await mkdir(dirname(screenshot), { recursive: true })
  const bounds = await button.boundingBox()
  expect(bounds).not.toBeNull()
  await page.screenshot({
    path: screenshot,
    clip: {
      x: Math.max(0, (bounds?.x ?? 0) - 6),
      y: Math.max(0, (bounds?.y ?? 0) - 6),
      width: (bounds?.width ?? 0) + 12,
      height: (bounds?.height ?? 0) + 12,
    },
  })

  await button.evaluate((element: HTMLButtonElement) => { element.disabled = true })
  await expect.poll(
    () => button.evaluate((element) => getComputedStyle(element).backgroundColor),
  ).toBe('rgb(109, 117, 111)')
  const disabled = await button.evaluate((element) => ({
    background: getComputedStyle(element).backgroundColor,
    color: getComputedStyle(element).color,
    cursor: getComputedStyle(element).cursor,
    bounds: element.getBoundingClientRect().toJSON(),
  }))
  expect(disabled.background).toBe('rgb(109, 117, 111)')
  expect(disabled.color).toBe('rgb(255, 255, 255)')
  expect(disabled.cursor).toBe('not-allowed')
  expect(contrastRatio(disabled.color, disabled.background)).toBeGreaterThanOrEqual(4.5)
  expect(disabled.bounds.x).toBeGreaterThanOrEqual(0)
  expect(disabled.bounds.right).toBeLessThanOrEqual(375)
})
