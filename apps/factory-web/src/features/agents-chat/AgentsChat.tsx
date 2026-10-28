import { useState, type FormEvent } from 'react'

export type AgentChatMessage = {
  id: string
  author: string
  content: string
  kind: 'answer' | 'proposal' | 'approval' | 'system'
  evidence?: Array<{ label: string; href: string }>
  proposalStatus?: 'pending' | 'approved' | 'rejected'
  proposal?: { id: string; title: string; description: string; status: string; payload_hash: string; executable: boolean; requires_human_review: boolean; path_scopes?: string[]; acceptance?: string[] }
}

type Props = {
  reference: string
  messages: AgentChatMessage[]
  loading?: boolean
  busy?: boolean
  error?: string
  onSend: (input: { persona: string; reference: string; content: string }) => Promise<void>
  onAcceptProposal?: (input: { proposal_id: string; payload_hash: string; owner_role: string; path_scopes: string[]; acceptance: string[] }) => Promise<void>
  onPersonaChange?: (persona: string) => void
}

const personas = ['analyst', 'planner', 'backend', 'frontend', 'qa', 'reviewer']
const MAX_MESSAGE_LENGTH = 8_000

export function AgentsChat({
  reference,
  messages,
  loading = false,
  busy = false,
  error,
  onSend,
  onAcceptProposal,
  onPersonaChange,
}: Props) {
  const [persona, setPersona] = useState('qa')
  const [content, setContent] = useState('')
  const [validationError, setValidationError] = useState('')
  const [proposalFields, setProposalFields] = useState<Record<string, { scopes: string; acceptance: string }>>({})
  const [proposalBusy, setProposalBusy] = useState('')
  const [proposalError, setProposalError] = useState('')

  async function acceptProposal(event: FormEvent, proposal: NonNullable<AgentChatMessage['proposal']>) {
    event.preventDefault()
    const fields = proposalFields[proposal.id] ?? {
      scopes: (proposal.path_scopes ?? []).join('\n'),
      acceptance: (proposal.acceptance ?? []).join('\n'),
    }
    const path_scopes = fields.scopes.split('\n').map((value) => value.trim()).filter(Boolean)
    const acceptance = fields.acceptance.split('\n').map((value) => value.trim()).filter(Boolean)
    if (!path_scopes.length || !acceptance.length || !onAcceptProposal) {
      setProposalError('Informe pelo menos um escopo e um critério de aceite para revisão.')
      return
    }
    setProposalBusy(proposal.id)
    setProposalError('')
    try {
      await onAcceptProposal({
        proposal_id: proposal.id,
        payload_hash: proposal.payload_hash,
        owner_role: persona,
        path_scopes,
        acceptance,
      })
    } catch (reason) {
      setProposalError(reason instanceof Error ? reason.message : 'Não foi possível aceitar a proposta.')
    } finally {
      setProposalBusy('')
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!content.trim() || !reference.trim() || busy) return
    if (content.length > MAX_MESSAGE_LENGTH) {
      setValidationError('A mensagem excede o limite de 8.000 caracteres.')
      return
    }
    setValidationError('')
    try {
      await onSend({ persona, reference: reference.trim(), content: content.trim() })
      setContent('')
    } catch {
      // Preserve the draft so the user can retry after correcting the reported error.
    }
  }

  return (
    <section className="agent-chat" aria-label="Conversa com agentes">
      <header className="agent-chat__toolbar">
        <label>
          Persona
          <select value={persona} onChange={(event) => {
            setPersona(event.target.value)
            onPersonaChange?.(event.target.value)
          }}>
          {personas.map((item) => <option key={item} value={item}>@{item}</option>)}
          </select>
        </label>
        <label>
          Issue ou tarefa vinculada
          <input
            value={reference}
            readOnly
            placeholder="ISSUE-42 ou TASK-<id>"
            aria-label="Issue ou tarefa vinculada"
          />
        </label>
      </header>

      <ol className="agent-chat__messages" aria-live="polite">
        {loading && <li className="agent-chat__empty" role="status">Carregando conversa…</li>}
        {messages.map((message) => (
          <li className={`agent-chat__message agent-chat__message--${message.kind}`} key={message.id}>
            <div className="agent-chat__message-heading">
              <strong>{message.author}</strong>
              {message.kind === 'proposal' && <span>Proposta · {message.proposalStatus ?? 'pending'}</span>}
              {message.kind === 'approval' && <span>Aguardando revisão humana</span>}
            </div>
            <p>{message.content}</p>
            {message.evidence?.map((item) => (
              <a key={`${message.id}-${item.href}`} href={item.href}>{item.label}</a>
            ))}
            {message.proposal && (
              <div className="agent-chat__proposal" aria-label="Estado da TaskProposal">
                <strong>TaskProposal · {message.proposal.status}</strong>
                <span>Hash {message.proposal.payload_hash.slice(0, 12)}</span>
                <span>{message.proposal.executable ? 'Executável' : 'Não executável'} · revisão humana {message.proposal.requires_human_review ? 'obrigatória' : 'não exigida'}</span>
                {message.proposal.status === 'pending_review' && onAcceptProposal && (
                  <form onSubmit={(event) => void acceptProposal(event, message.proposal!)}>
                    <label>
                      Escopos permitidos, um por linha
                      <textarea
                        required
                        value={(proposalFields[message.proposal.id] ?? { scopes: (message.proposal.path_scopes ?? []).join('\n'), acceptance: (message.proposal.acceptance ?? []).join('\n') }).scopes}
                        onChange={(event) => setProposalFields((current) => ({ ...current, [message.proposal!.id]: { ...(current[message.proposal!.id] ?? { scopes: '', acceptance: '' }), scopes: event.target.value } }))}
                      />
                    </label>
                    <label>
                      Critérios de aceite, um por linha
                      <textarea
                        required
                        value={(proposalFields[message.proposal.id] ?? { scopes: (message.proposal.path_scopes ?? []).join('\n'), acceptance: (message.proposal.acceptance ?? []).join('\n') }).acceptance}
                        onChange={(event) => setProposalFields((current) => ({ ...current, [message.proposal!.id]: { ...(current[message.proposal!.id] ?? { scopes: '', acceptance: '' }), acceptance: event.target.value } }))}
                      />
                    </label>
                    {proposalError && <p role="alert" className="error">{proposalError}</p>}
                    <button type="submit" disabled={proposalBusy === message.proposal.id}>
                      {proposalBusy === message.proposal.id ? 'Registrando decisão…' : 'Revisar e aceitar como tarefa'}
                    </button>
                  </form>
                )}
              </div>
            )}
          </li>
        ))}
        {!loading && !messages.length && <li className="agent-chat__empty">Conversa iniciada. Envie uma mensagem para @qa.</li>}
      </ol>

      <form className="agent-chat__composer" onSubmit={submit}>
        <label htmlFor="agent-chat-message">Mensagem</label>
        <textarea
          id="agent-chat-message"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          maxLength={20_000}
          required
        />
        <small>Limite de envio: 8.000 caracteres. Arquivos não são enviados como contexto.</small>
        {validationError && <p role="alert" className="error">{validationError}</p>}
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit" disabled={busy || !reference.trim() || !content.trim()}>
          {busy ? 'Enviando…' : 'Enviar'}
        </button>
      </form>
    </section>
  )
}
