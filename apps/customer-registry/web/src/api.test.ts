import { afterEach, describe, expect, it, vi } from 'vitest'
import { usersApi } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('usersApi', () => {
  it('encodes search terms and returns the user list', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(usersApi.list('ana silva')).resolves.toEqual([])
    expect(fetchMock.mock.calls[0][0]).toBe('http://127.0.0.1:8010/api/v1/users?search=ana%20silva')
  })

  it('sends create data as JSON', async () => {
    const user = { id: '1', username: 'ana', name: 'Ana', email: 'ana@example.com', phone: null, status: 'active' }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(user), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(usersApi.create('ana', 'Ana', 'ana@example.com', '', [])).resolves.toEqual(user)
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ username: 'ana', name: 'Ana', email: 'ana@example.com', phone: null, tag_ids: [] }),
    })
  })

  it('surfaces API error codes for duplicate emails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: { code: 'EMAIL_ALREADY_EXISTS' } }), { status: 409 },
    )))

    await expect(usersApi.create('ana', 'Ana', 'ana@example.com', '', [])).rejects.toThrow('EMAIL_ALREADY_EXISTS')
  })
})
