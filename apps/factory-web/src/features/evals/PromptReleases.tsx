import { useState } from 'react'
import { getPromptRelease, promotePrompt, rollbackPrompt, type PromptReleaseState } from '../../lib/api/client'

const emptyState: PromptReleaseState = { active: null, history: [] }

export function PromptReleases() {
  const [state, setState] = useState(emptyState)
  const [version, setVersion] = useState('feature-candidate-v1')
  const [promptHash, setPromptHash] = useState('')
  const [experimentHash, setExperimentHash] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() {
    try { setState(await getPromptRelease()) } catch { setMessage('Entre como operador para consultar os releases.') }
  }
  async function release(event: { preventDefault: () => void }, action: 'promote' | 'rollback') {
    event.preventDefault(); setBusy(true); setMessage('')
    const payload = { version: version.trim(), prompt_hash: promptHash.trim(), experiment_sha256: experimentHash.trim() }
    try {
      if (action === 'promote') await promotePrompt(payload)
      else await rollbackPrompt(payload)
      setMessage(action === 'promote' ? 'Prompt promovido com aprovação do operador.' : 'Rollback registrado pelo operador.')
      await refresh()
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Falha ao registrar release.') }
    finally { setBusy(false) }
  }

  return <section className="operation-column">
    <h2>Promoção e rollback de prompts</h2>
    <p className="empty">A recomendação do experimento não ativa prompts. Informe os hashes e confirme a ação como operador autenticado.</p>
    <button type="button" onClick={() => void refresh()}>Carregar estado e histórico</button>
    <p>Ativo: {state.active ? `${state.active.version} · ${state.active.prompt_hash}` : 'nenhum release'}</p>
    <form className="login-form" onSubmit={(event) => void release(event, 'promote')}>
      <label>Versão<input required pattern="[a-z0-9][a-z0-9-]{0,79}" value={version} onChange={(event) => setVersion(event.target.value)} /></label>
      <label>Hash SHA-256 do prompt<input required minLength={64} maxLength={64} pattern="[a-f0-9]{64}" value={promptHash} onChange={(event) => setPromptHash(event.target.value)} /></label>
      <label>Hash SHA-256 do experimento<input required minLength={64} maxLength={64} pattern="[a-f0-9]{64}" value={experimentHash} onChange={(event) => setExperimentHash(event.target.value)} /></label>
      <button disabled={busy}>Aprovar e promover</button>
      <button type="button" disabled={busy || !state.active} onClick={(event) => void release(event, 'rollback')}>Confirmar rollback</button>
      {message && <p role="status">{message}</p>}
    </form>
    <h3>Histórico auditável</h3>
    <ul>{state.history.map((item, index) => <li key={`${item.version}-${item.created_at}-${index}`}>{item.action}: {item.version} · {item.prompt_hash} · {item.actor} · {item.created_at}</li>)}</ul>
  </section>
}
