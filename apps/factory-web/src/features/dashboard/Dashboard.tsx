import { useEffect, useState, type FormEvent } from 'react'
import {
  createDemand, decideApproval, getApprovals, getDemand, getDemands, getSession,
  getStatus, getTasks, login, logout, requestApproval, runFakeScheduler,
  type ServiceStatus, type StatusResponse,
} from '../../lib/api/client'
import type { DemandView, TaskView } from '../../lib/api/generated'

const apiBase = import.meta.env.VITE_FACTORY_API_URL ?? 'http://127.0.0.1:8001'
const labels: Record<string, string> = { database: 'PostgreSQL', redis: 'Redis', customer_registry: 'Customer Registry', ollama: 'Ollama', github: 'GitHub', openbot: 'OpenBot', telegram: 'Telegram', jira: 'Jira' }
const describe: Record<ServiceStatus, string> = { ready: 'Pronto', configured: 'Configurado', available: 'Disponível', unavailable: 'Indisponível', misconfigured: 'Configuração incompleta', disabled: 'Desativado' }
type Tab = 'demands' | 'tasks' | 'approvals' | 'status'
type Approval = { id: string; entity_type: string; entity_id: string; status: string; requested_by: string; payload_hash: string }

export function Dashboard() {
  const [tab, setTab] = useState<Tab>('demands')
  const [authenticated, setAuthenticated] = useState(false)
  const [authEnabled, setAuthEnabled] = useState(true)
  const [csrf, setCsrf] = useState('')
  const [password, setPassword] = useState('')
  const [data, setData] = useState<StatusResponse | null>(null)
  const [demands, setDemands] = useState<DemandView[]>([])
  const [tasks, setTasks] = useState<TaskView[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [detail, setDetail] = useState<Awaited<ReturnType<typeof getDemand>> | null>(null)
  const [events, setEvents] = useState<string[]>([])
  const [title, setTitle] = useState('')
  const [requirement, setRequirement] = useState('')
  const [acceptance, setAcceptance] = useState('')
  const [demandStatus, setDemandStatus] = useState('all')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [simulation, setSimulation] = useState('')
  const [error, setError] = useState('')

  async function refreshOperations() {
    const [nextDemands, nextTasks, nextApprovals] = await Promise.all([getDemands(), getTasks(), getApprovals()])
    setDemands(nextDemands); setTasks(nextTasks); setApprovals(nextApprovals)
  }
  async function refresh() {
    setLoading(true)
    try { setData(await getStatus()); await refreshOperations(); setError('') }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Falha ao consultar API') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    void getSession().then(async (session) => {
      setAuthenticated(session.authenticated); setAuthEnabled(session.auth_enabled)
      if (session.csrf_token) setCsrf(session.csrf_token)
      if (session.authenticated || !session.auth_enabled) {
        try { setData(await getStatus()); await refreshOperations() }
        catch (reason) { setError(reason instanceof Error ? reason.message : 'Falha ao consultar API') }
      }
    }).catch(() => setError('API indisponível. Inicie a Factory API em 127.0.0.1:8001.')).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!authenticated) return
    const stream = new EventSource(`${apiBase}/api/v1/events/stream`, { withCredentials: true })
    stream.addEventListener('update', (event) => {
      const message = JSON.parse((event as MessageEvent<string>).data) as { type: string; action?: string; to_state?: string }
      setEvents((items) => [`${message.type}: ${message.action ?? message.to_state ?? 'evento'}`, ...items].slice(0, 5))
      void refreshOperations()
    })
    return () => stream.close()
  }, [authenticated])

  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError('')
    try {
      const demand = await createDemand({ source: 'manual', external_id: crypto.randomUUID(), title,
        demand_type: 'feature', requirement, acceptance: acceptance.split('\n').map((line) => line.trim()).filter(Boolean) })
      setTitle(''); setRequirement(''); setAcceptance(''); await refreshOperations(); setDetail(await getDemand(demand.id))
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Não foi possível criar a demanda.') }
    finally { setSaving(false) }
  }
  async function signIn(event: FormEvent) {
    event.preventDefault(); setError('')
    try { const result = await login(password); setCsrf(result.csrf_token); setAuthenticated(true); setPassword(''); await refresh() }
    catch (reason) { setError(reason instanceof Error && reason.message === 'INVALID_CREDENTIALS' ? 'Senha incorreta.' : 'Não foi possível iniciar sessão.') }
  }
  async function signOut() {
    try { await logout(csrf); setAuthenticated(false); setData(null); setDemands([]); setTasks([]); setApprovals([]) }
    catch { setError('Não foi possível encerrar a sessão.') }
  }
  async function decide(id: string, decision: 'approved' | 'rejected') {
    try { await decideApproval(id, { decision, comment: decision === 'approved' ? 'Revisado pelo operador.' : 'Alterações necessárias.' }); await refreshOperations() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Falha ao registrar decisão.') }
  }

  const services = data ? { ...data.services, ...data.integrations } : {}
  return <main className="shell">
    <header><a className="wordmark" href="#home"><span className="mark">af</span> agentic factory</a><div className="header-actions">{authenticated && authEnabled && <button className="logout" onClick={() => void signOut()}>Sair</button>}<span className="local"><i /> ambiente local</span></div></header>
    <section className="hero"><p className="eyebrow">PAINEL DE OPERAÇÃO · 01</p><h1>Bom trabalho começa<br /><em>com clareza.</em></h1><p className="sub">Acompanhe demandas, tarefas e serviços locais em um só lugar.</p></section>
    {authEnabled && !authenticated ? <section className="login card"><p className="eyebrow">ACESSO DO OPERADOR</p><h2>Entre para continuar</h2><form onSubmit={(event) => void signIn(event)}><label htmlFor="password">Senha local</label><input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /><button>Entrar <span>↗</span></button></form>{error && <p role="alert" className="error">{error}</p>}</section> : <>
      <nav className="operation-tabs" aria-label="Áreas da fábrica">{(['demands', 'tasks', 'approvals', 'status'] as const).map((item) => <button key={item} aria-pressed={tab === item} onClick={() => setTab(item)}>{({ demands: 'Demandas', tasks: 'Tarefas', approvals: `Aprovações (${approvals.length})`, status: 'Serviços' })[item]}</button>)}</nav>
      {error && <p role="alert" className="banner error">{error}</p>}
      {tab === 'demands' && <section className="operations"><div className="operation-column"><h2>Demandas <span>{demands.length}</span></h2><label className="filter-label" htmlFor="demand-filter">Filtrar por estado</label><select id="demand-filter" value={demandStatus} onChange={(event) => setDemandStatus(event.target.value)}><option value="all">Todos</option>{[...new Set(demands.map((demand) => demand.status))].map((status) => <option key={status}>{status}</option>)}</select>{demands.filter((demand) => demandStatus === 'all' || demand.status === demandStatus).map((demand) => <button className="operation-row" key={demand.id} onClick={() => void getDemand(demand.id).then(setDetail).catch((reason: Error) => setError(reason.message))}><strong>{demand.title}</strong><span>{demand.status} · v{demand.version}</span></button>)}{!demands.length && <p className="empty">Ainda não há demandas.</p>}</div>
        <form className="intake card" onSubmit={(event) => void submit(event)}><p className="eyebrow">NOVA SOLICITAÇÃO</p><h2>Registrar demanda</h2><label htmlFor="demand-title">Título</label><input id="demand-title" required maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} /><label htmlFor="demand-requirement">Requisito</label><textarea id="demand-requirement" required value={requirement} onChange={(event) => setRequirement(event.target.value)} /><label htmlFor="demand-acceptance">Critérios de aceite, um por linha</label><textarea id="demand-acceptance" required value={acceptance} onChange={(event) => setAcceptance(event.target.value)} /><button disabled={saving}>{saving ? 'Salvando…' : 'Criar demanda'}</button></form>
        {detail && <article className="operation-column demand-detail"><button className="back-link" onClick={() => setDetail(null)}>← Todas as demandas</button><p className="eyebrow">DETALHE DA DEMANDA</p><h2>{detail.demand.title}</h2><p>{detail.demand.status} · versão {detail.demand.version}</p>{detail.revisions.map((revision) => <div className="revision" key={revision.id}><strong>Requisito v{revision.version}</strong><p>{revision.content}</p><ul>{revision.acceptance.map((criterion) => <li key={criterion}>{criterion}</li>)}</ul></div>)}<h3>Tarefas e dependências</h3>{detail.tasks.map((task) => <div className="task-row" key={task.id}><strong>{task.title}</strong><span>{task.owner_role} · {task.status}</span>{(task.dependencies?.length ?? 0) > 0 && <small>Bloqueada por: {(task.dependencies ?? []).map((id) => detail.tasks.find((item) => item.id === id)?.title ?? id).join(', ')}</small>}</div>)}<button onClick={() => void runFakeScheduler(detail.demand.id).then((result) => { setSimulation(result.model_called ? 'Modelo chamado.' : 'Simulação concluída sem LLM.'); return refreshOperations() }).catch((reason: Error) => setError(reason.message))}>Executar simulação local</button>{simulation && <p role="status">{simulation}</p>}<button onClick={() => void requestApproval({ entity_type: 'demand', entity_id: detail.demand.id }).then(refreshOperations).catch((reason: Error) => setError(reason.message))}>Pedir revisão humana</button></article>}
      </section>}
      {tab === 'tasks' && <section className="operation-column task-board" aria-label="Tarefas por estado"><h2>Tarefas <span>{tasks.length}</span></h2><div className="task-grid">{['proposed', 'ready', 'leased', 'running', 'review', 'done', 'blocked', 'failed'].map((status) => <section className="task-lane" key={status}><h3>{status}</h3>{tasks.filter((task) => task.status === status).map((task) => <article className="task-card" key={task.id}><strong>{task.title}</strong><span>{task.owner_role}</span>{(task.dependencies?.length ?? 0) > 0 && <small>Depende de {task.dependencies?.length ?? 0} tarefa(s)</small>}</article>)}</section>)}</div></section>}
      {tab === 'approvals' && <section className="operation-column"><h2>Caixa de revisão humana</h2>{approvals.map((item) => <article className="approval-row" key={item.id}><div><strong>{item.entity_type} · {item.entity_id.slice(0, 8)}</strong><span>Solicitado por {item.requested_by} · hash {item.payload_hash.slice(0, 12)}</span></div><button onClick={() => void decide(item.id, 'approved')}>Aprovar</button><button className="reject" onClick={() => void decide(item.id, 'rejected')}>Solicitar alterações</button></article>)}{!approvals.length && <p className="empty">Nenhuma revisão pendente.</p>}</section>}
      {tab === 'status' && <><section className="overview"><div><p className="eyebrow">STATUS DO AMBIENTE</p><h2>{loading ? 'Verificando serviços…' : error ? 'A API não respondeu.' : 'Sua fábrica local.'}</h2></div><button className="refresh" onClick={() => void refresh()} disabled={loading}>↻ Atualizar</button></section><section className="cards" aria-label="Status dos serviços">{Object.entries(services).map(([key, value]) => <article className="card service" key={key}><div className="service-top"><span className="service-icon">◇</span><span className={`state state-${value}`}><i />{describe[value]}</span></div><h3>{labels[key] ?? key}</h3><p>Estado sanitizado do serviço local</p></article>)}</section><section className="note"><span className="note-mark">i</span><p><strong>Seus segredos ficam no servidor local.</strong> Tokens e senhas nunca são enviados ao navegador.</p></section></>}
      {events.length > 0 && <aside className="live-events" aria-label="Atividade recente"><strong>Atividade ao vivo</strong>{events.map((event, index) => <span key={`${event}-${index}`}>{event}</span>)}</aside>}
    </>}
    <footer><span>AGENTIC FACTORY · LOCAL FIRST</span><span>CONTROLE SOBERANO, EXECUÇÃO LOCAL.</span></footer>
  </main>
}
