import { afterEach, describe, expect, it, vi } from 'vitest'
import { getSession, getStatus, login } from './client'

afterEach(() => vi.unstubAllGlobals())

describe('factory API client', () => {
  it('returns sanitized service state', async () => {
    const payload = { services: { database: 'ready' }, integrations: { github: 'disabled' }, secrets_exposed: false }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 })))
    await expect(getStatus()).resolves.toEqual(payload)
  })
  it('sends local login credentials only to the API', async () => {
    const result = { authenticated: true, csrf_token: 'csrf' }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(result), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(login('local-password')).resolves.toEqual(result)
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include', method: 'POST' })
  })
  it('reads current session status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ authenticated: false, auth_enabled: true }), { status: 200 })))
    await expect(getSession()).resolves.toMatchObject({ authenticated: false, auth_enabled: true })
  })
})
