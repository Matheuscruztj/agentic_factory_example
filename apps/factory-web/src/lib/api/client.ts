import type { ApprovalCreate, ApprovalDecision, DemandCreate, DemandView, TaskCreate, TaskView } from './generated'

export type ServiceStatus = 'ready' | 'configured' | 'available' | 'unavailable' | 'misconfigured' | 'disabled'
export type StatusResponse = { services: Record<string, ServiceStatus>; integrations: Record<string, ServiceStatus>; secrets_exposed: false }
const base = import.meta.env.VITE_FACTORY_API_URL ?? 'http://127.0.0.1:8001'
export async function getSession() {
  const response = await fetch(`${base}/api/v1/auth/session`, { credentials: 'include' })
  if (!response.ok) throw new Error(`HTTP_${response.status}`)
  return response.json() as Promise<{ authenticated: boolean; auth_enabled: boolean; csrf_token?: string | null }>
}
export async function login(password: string) {
  const response = await fetch(`${base}/api/v1/auth/login`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
  if (!response.ok) throw new Error(response.status === 401 ? 'INVALID_CREDENTIALS' : `HTTP_${response.status}`)
  return response.json() as Promise<{ authenticated: boolean; csrf_token: string }>
}
export async function logout(csrfToken: string) {
  const response = await fetch(`${base}/api/v1/auth/logout`, { method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken } })
  if (!response.ok) throw new Error(`HTTP_${response.status}`)
  return response.json() as Promise<{ authenticated: boolean }>
}
export async function getStatus() {
  const response = await fetch(`${base}/api/v1/config/status`, { credentials: 'include' })
  if (response.status === 401) throw new Error('AUTHENTICATION_REQUIRED')
  if (!response.ok) throw new Error(`HTTP_${response.status}`)
  return response.json() as Promise<StatusResponse>
}

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${base}${path}`, { ...options, credentials: 'include', headers: { 'Content-Type': 'application/json', ...options.headers } })
  if (!response.ok) {
    let code = `HTTP_${response.status}`
    try { code = (await response.json()).detail?.code ?? code } catch { /* response has no JSON body */ }
    throw new Error(code)
  }
  return response.json() as Promise<T>
}

export function getDemands() { return apiRequest<DemandView[]>('/api/v1/demands') }
export function createDemand(payload: DemandCreate) {
  return apiRequest<DemandView>('/api/v1/demands', { method: 'POST', body: JSON.stringify(payload) })
}
export function getDemand(id: string) { return apiRequest<{ demand: DemandView; revisions: Array<{ id: string; version: number; content: string; acceptance: string[]; decision: string }>; tasks: TaskView[] }>(`/api/v1/demands/${encodeURIComponent(id)}`) }
export function createTask(demandId: string, payload: TaskCreate) {
  return apiRequest<TaskView>(`/api/v1/demands/${encodeURIComponent(demandId)}/tasks`, { method: 'POST', body: JSON.stringify(payload) })
}
export function runFakeScheduler(demandId: string) {
  return apiRequest<{ demand_id: string; completed_task_ids: string[]; model_called: false; approval_required: true }>(
    `/api/v1/demands/${encodeURIComponent(demandId)}/run-fake`, { method: 'POST' },
  )
}
export function getTasks() { return apiRequest<TaskView[]>('/api/v1/tasks') }
export function getApprovals() { return apiRequest<Array<{ id: string; entity_type: string; entity_id: string; status: string; requested_by: string; payload_hash: string }>>('/api/v1/approvals') }
export function requestApproval(payload: ApprovalCreate) {
  return apiRequest<{ id: string; status: string; payload_hash: string }>('/api/v1/approvals', { method: 'POST', body: JSON.stringify(payload) })
}
export function decideApproval(id: string, payload: ApprovalDecision) {
  return apiRequest<{ id: string; status: string }>(`/api/v1/approvals/${encodeURIComponent(id)}/decision`, { method: 'POST', body: JSON.stringify(payload) })
}
