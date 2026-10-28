import { useEffect, useState, type FormEvent } from 'react'
import { getFeedbackSummary, submitRunFeedback } from '../../lib/api/client'

type FeedbackSummary = Awaited<ReturnType<typeof getFeedbackSummary>>
const emptySummary: FeedbackSummary = {
  feedback_count: 0, first_pass_rate: null, rework_count: 0, error_categories: {},
}

export function RunFeedback() {
  const [runId, setRunId] = useState('')
  const [taskId, setTaskId] = useState('')
  const [decision, setDecision] = useState<'approve' | 'reject'>('approve')
  const [category, setCategory] = useState('')
  const [comment, setComment] = useState('')
  const [promptHash, setPromptHash] = useState('')
  const [modelId, setModelId] = useState('')
  const [requirementVersion, setRequirementVersion] = useState('1')
  const [evidence, setEvidence] = useState('')
  const [message, setMessage] = useState('')
  const [summary, setSummary] = useState<FeedbackSummary>(emptySummary)
  const [busy, setBusy] = useState(false)

  async function refreshSummary() {
    try { setSummary(await getFeedbackSummary()) } catch { /* shown by the form response */ }
  }
  useEffect(() => {
    let active = true
    void getFeedbackSummary().then((next) => { if (active) setSummary(next) }).catch(() => undefined)
    return () => { active = false }
  }, [])

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage('')
    try {
      await submitRunFeedback({
        run_id: runId.trim(), task_id: taskId.trim(),
        decision, ...(decision === 'reject' ? { error_category: category } : {}),
        comment, prompt_hash: promptHash.trim(), model_id: modelId.trim(),
        requirement_version: Number(requirementVersion),
        evidence_refs: evidence.split('\n').map((item) => item.trim()).filter(Boolean),
      })
      setMessage('Feedback registrado pelo operador.')
      await refreshSummary()
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Falha ao registrar feedback.') }
    finally { setBusy(false) }
  }

  return <section className="operation-column eval-feedback">
    <h2>Feedback humano das execuções</h2>
    <p className="empty">Os registros são associados ao operador autenticado e não podem ser enviados por agentes.</p>
    <div className="cards" aria-label="Resumo de feedback">
      <article className="card"><h3>Primeira aprovação</h3><p>{summary.first_pass_rate === null ? 'n/d' : `${Math.round(summary.first_pass_rate * 100)}%`}</p></article>
      <article className="card"><h3>Retrabalho</h3><p>{summary.rework_count} de {summary.feedback_count}</p></article>
      <article className="card"><h3>Falhas categorizadas</h3><p>{Object.values(summary.error_categories).reduce((sum, value) => sum + value, 0)}</p></article>
    </div>
    <form className="login-form" onSubmit={(event) => void save(event)}>
      <label>ID da execução<input required value={runId} onChange={(event) => setRunId(event.target.value)} /></label>
      <label>ID da tarefa<input required value={taskId} onChange={(event) => setTaskId(event.target.value)} /></label>
      <label>Decisão<select value={decision} onChange={(event) => setDecision(event.target.value as 'approve' | 'reject')}><option value="approve">Aprovar</option><option value="reject">Rejeitar e pedir retrabalho</option></select></label>
      {decision === 'reject' && <label>Categoria<select required value={category} onChange={(event) => setCategory(event.target.value)}><option value="">Escolha</option>{['requirements', 'implementation', 'tests', 'policy', 'reliability', 'other'].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>}
      <label>Hash do prompt (SHA-256)<input required minLength={64} maxLength={64} pattern="[a-f0-9]{64}" value={promptHash} onChange={(event) => setPromptHash(event.target.value)} /></label>
      <label>Modelo<input required maxLength={120} value={modelId} onChange={(event) => setModelId(event.target.value)} /></label>
      <label>Versão dos requisitos<input required type="number" min="1" value={requirementVersion} onChange={(event) => setRequirementVersion(event.target.value)} /></label>
      <label>Comentário<textarea maxLength={2000} value={comment} onChange={(event) => setComment(event.target.value)} /></label>
      <label>Evidências (uma referência por linha)<textarea maxLength={4000} value={evidence} onChange={(event) => setEvidence(event.target.value)} /></label>
      <button disabled={busy}>{busy ? 'Salvando…' : 'Registrar feedback'}</button>
      {message && <p role="status">{message}</p>}
    </form>
  </section>
}
