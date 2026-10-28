export type User = {
  id: string
  username: string
  name: string
  email: string
  phone: string | null
  status: 'active' | 'inactive'
  created_at: string
  updated_at: string
  tags: Tag[]
}

export type Tag = { id: string; name: string }

const API_URL = import.meta.env.VITE_REGISTRY_API_URL ?? 'http://127.0.0.1:8010'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : detail?.code
    throw new Error(message ?? `HTTP_${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const usersApi = {
  list: (search: string, tagId = '') => request<User[]>(`/api/v1/users?search=${encodeURIComponent(search)}${tagId ? `&tag_id=${encodeURIComponent(tagId)}` : ''}`),
  listTags: () => request<Tag[]>('/api/v1/tags'),
  createTag: (name: string) => request<Tag>('/api/v1/tags', { method: 'POST', body: JSON.stringify({ name }) }),
  create: (username: string, name: string, email: string, phone = '', tag_ids: string[] = []) => request<User>('/api/v1/users', {
    method: 'POST', body: JSON.stringify({ username, name, email, phone: phone || null, tag_ids }),
  }),
  update: (id: string, username: string, name: string, email: string, phone = '', tag_ids: string[] = []) => request<User>(`/api/v1/users/${id}`, {
    method: 'PATCH', body: JSON.stringify({ username, name, email, phone: phone || null, tag_ids }),
  }),
  deactivate: (id: string) => request<void>(`/api/v1/users/${id}`, { method: 'DELETE' }),
}
