import type { ApprovalCreate, ApprovalDecision, DemandCreate, DemandView, TaskCreate, TaskView } from './generated'

export type ServiceStatus = 'ready' | 'configured' | 'available' | 'unavailable' | 'misconfigured' | 'disabled'
export type StatusResponse = { services: Record<string, ServiceStatus>; integrations: Record<string, ServiceStatus>; secrets_exposed: false }
const base = import.meta.env.VITE_FACTORY_API_URL ?? 'http://127.0.0.1:8001'
let csrfToken = ''

function rememberCsrfToken(token?: string | null) {
  csrfToken = token ?? ''
}

export async function getSession() {
  const response = await fetch(`${base}/api/v1/auth/session`, { credentials: 'include' })
  if (!response.ok) throw new Error(`HTTP_${response.status}`)
  const session = await response.json() as { authenticated: boolean; auth_enabled: boolean; csrf_token?: string | null }
  rememberCsrfToken(session.csrf_token)
  return session
}
export async function login(password: string) {
  const response = await fetch(`${base}/api/v1/auth/login`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
  if (!response.ok) throw new Error(response.status === 401 ? 'INVALID_CREDENTIALS' : `HTTP_${response.status}`)
  const result = await response.json() as { authenticated: boolean; csrf_token: string }
  rememberCsrfToken(result.csrf_token)
  return result
}
export async function logout(csrfToken: string) {
  const response = await fetch(`${base}/api/v1/auth/logout`, { method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken } })
  if (!response.ok) throw new Error(`HTTP_${response.status}`)
  rememberCsrfToken()
  return response.json() as Promise<{ authenticated: boolean }>
}
export async function getStatus() {
  const response = await fetch(`${base}/api/v1/config/status`, { credentials: 'include' })
  if (response.status === 401) throw new Error('AUTHENTICATION_REQUIRED')
  if (!response.ok) throw new Error(`HTTP_${response.status}`)
  return response.json() as Promise<StatusResponse>
}

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers = new Headers(options.headers)
  if (options.body !== undefined && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) headers.set('X-CSRF-Token', csrfToken)
  const response = await fetch(`${base}${path}`, { ...options, credentials: 'include', headers })
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
export type DemandRunView = {
  id: string; attempt: number; status: string; base_git_sha: string; result_git_sha: string | null;
  tree_hash: string | null; started_at: string; finished_at: string | null;
  gates: Array<{ check_name: string; status: string; git_sha: string; artifact_sha256: string }>;
  artifacts: Array<{ id: string; path: string; sha256: string; size_bytes: number; media_type: string }>;
}
export type DemandDetail = {
  demand: DemandView
  revisions: Array<{ id: string; version: number; content: string; acceptance: string[]; decision: string }>
  tasks: Array<Omit<TaskView, 'blocked_reason' | 'runs'> & { blocked_reason?: string | null; runs?: DemandRunView[] }>
}
export function getDemand(id: string) { return apiRequest<DemandDetail>(`/api/v1/demands/${encodeURIComponent(id)}`) }
export function getDemandArtifactUrl(demandId: string, runId: string, artifactId: string) {
  return `${base}/api/v1/demands/${encodeURIComponent(demandId)}/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`
}
export function createTask(demandId: string, payload: TaskCreate) {
  return apiRequest<TaskView>(`/api/v1/demands/${encodeURIComponent(demandId)}/tasks`, { method: 'POST', body: JSON.stringify(payload) })
}
export function runFakeScheduler(demandId: string) {
  return apiRequest<{ demand_id: string; reviewed_task_ids: string[]; model_called: false; human_review_required: true }>(
    `/api/v1/demands/${encodeURIComponent(demandId)}/run-fake`, { method: 'POST' },
  )
}
export function getTasks() { return apiRequest<TaskView[]>('/api/v1/tasks') }
export type AgentConversationMessage = {
  id: string
  author: string
  content: string
  kind: 'answer' | 'proposal' | 'approval' | 'system'
  proposalStatus?: 'pending' | 'approved' | 'rejected'
  proposal?: { id: string; title: string; description: string; status: string; payload_hash: string; executable: boolean; requires_human_review: boolean }
  created_at?: string | null
  evidence?: Array<{ label: string; href: string }>
}
export type AgentConversation = {
  thread_id: string
  persona: string
  reference: string
  active: boolean
  messages: AgentConversationMessage[]
  task_proposals: Array<{ id: string; status: string; executable: boolean; requires_human_review: boolean }>
}
export function openAgentConversation(demandId: string, persona = 'qa') {
  return apiRequest<AgentConversation>(`/api/v1/demands/${encodeURIComponent(demandId)}/conversation`, { method: 'POST', body: JSON.stringify({ persona }) })
}
export function getAgentConversation(demandId: string, persona = 'qa') {
  return apiRequest<AgentConversation>(`/api/v1/demands/${encodeURIComponent(demandId)}/conversation?persona=${encodeURIComponent(persona)}`)
}
export function sendAgentMessage(demandId: string, content: string, persona = 'qa') {
  return apiRequest<{ message_id: string; task_proposal: unknown }>(`/api/v1/demands/${encodeURIComponent(demandId)}/conversation/messages`, { method: 'POST', body: JSON.stringify({ content, persona }) })
}
export type ProposalAcceptance = {
  payload_hash: string; owner_role: string; path_scopes: string[]; acceptance: string[];
  dependencies?: string[]; risk?: 'low' | 'normal' | 'high' | 'critical'
}
export function acceptTaskProposal(demandId: string, proposalId: string, payload: ProposalAcceptance) {
  return apiRequest<{ proposal_id: string; task_id: string; status: 'accepted' }>(
    `/api/v1/demands/${encodeURIComponent(demandId)}/conversation/proposals/${encodeURIComponent(proposalId)}/accept`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}
export function getApprovals() { return apiRequest<Array<{ id: string; entity_type: string; entity_id: string; status: string; requested_by: string; payload_hash: string; subject_current: boolean; subject: Record<string, unknown> }>>('/api/v1/approvals') }
export function requestApproval(payload: ApprovalCreate) {
  return apiRequest<{ id: string; status: string; payload_hash: string }>('/api/v1/approvals', { method: 'POST', body: JSON.stringify(payload) })
}
export function decideApproval(id: string, payload: ApprovalDecision) {
  return apiRequest<{ id: string; status: string }>(`/api/v1/approvals/${encodeURIComponent(id)}/decision`, { method: 'POST', body: JSON.stringify(payload) })
}
export type RunFeedbackPayload = {
  run_id: string; task_id?: string; demand_id?: string; decision: 'approve' | 'reject';
  error_category?: string; comment: string; prompt_hash: string; model_id: string;
  requirement_version: number; evidence_refs: string[];
}
export function submitRunFeedback(payload: RunFeedbackPayload) {
  return apiRequest<{ id: string; run_id: string; decision: string; reviewer_sub: string }>(
    '/api/v1/evals/feedback', { method: 'POST', body: JSON.stringify(payload) },
  )
}
export function getFeedbackSummary() {
  return apiRequest<{ feedback_count: number; first_pass_rate: number | null; rework_count: number;
    error_categories: Record<string, number> }>('/api/v1/evals/feedback/summary')
}
export type PromptReleaseRequest = { version: string; prompt_hash: string; experiment_sha256: string }
export type PromptReleaseState = { active: { version: string; prompt_hash: string } | null; history: Array<{
  version: string; prompt_hash: string; action: 'promote' | 'rollback'; actor: string; created_at: string
}> }
export function getPromptRelease() { return apiRequest<PromptReleaseState>('/api/v1/prompts/releases') }
export function promotePrompt(payload: PromptReleaseRequest) {
  return apiRequest('/api/v1/prompts/releases/promote', { method: 'POST', body: JSON.stringify(payload) })
}
export function rollbackPrompt(payload: PromptReleaseRequest) {
  return apiRequest('/api/v1/prompts/releases/rollback', { method: 'POST', body: JSON.stringify(payload) })
}
export type ObservabilitySummary = {
  task_filter: string | null
  measured: {
    count: number; successful: number; failed: number; median_total_ms: number | null
    median_queue_wait_ms: number | null; median_load_ms: number | null; median_generation_ms: number | null
    prompt_tokens: number; completion_tokens: number; cost_usd: number | null
    hardware: null | { status: string; devices: Array<{ memory_total_mib: number | null; memory_used_mib: number | null; power_watts: number | null }> }
  }
  estimates: { cost_usd: number | null; source: string | null; status: string }
  measurement_source: string
}
export function getObservabilitySummary(taskId?: string) {
  const query = taskId ? `?task_id=${encodeURIComponent(taskId)}` : ''
  return apiRequest<ObservabilitySummary>(`/api/v1/observability/summary${query}`)
}
export type BenchmarkRecord = {
  role: 'coding' | 'judge'; model: string | null; route: string; run_id: string | null
  latency_ms: number | null; quality: number | null; accepted_tasks_per_hour: number | null
  tokens: number | null; status: string | null; trace: string
}
export type BenchmarkReport = {
  status: 'ready' | 'empty' | 'error'; code?: string; filters: { role: string | null; model: string | null }
  records: BenchmarkRecord[]; source: string
}
export function getBenchmarks(role?: string, model?: string) {
  const query = new URLSearchParams()
  if (role) query.set('role', role)
  if (model) query.set('model', model)
  return apiRequest<BenchmarkReport>(`/api/v1/observability/benchmarks${query.size ? `?${query}` : ''}`)
}
