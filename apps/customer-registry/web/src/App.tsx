import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { usersApi, type Tag, type User } from './api'

const initialForm = { username: '', name: '', email: '', phone: '' }

function explainError(error: unknown): string {
  if (!(error instanceof Error)) return 'Ocorreu um erro inesperado.'
  if (error.message === 'EMAIL_ALREADY_EXISTS') return 'Este e-mail já está cadastrado.'
  if (error.message === 'USER_NOT_FOUND') return 'Este cadastro não existe mais.'
  if (error.message === 'Failed to fetch') return 'Não foi possível conectar à API. Confira se ela está em execução.'
  return `Não foi possível concluir a operação (${error.message}).`
}

export function App() {
  const [users, setUsers] = useState<User[]>([])
  const [search, setSearch] = useState('')
  const [tagFilter, setTagFilter] = useState('')
  const [tags, setTags] = useState<Tag[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [newTag, setNewTag] = useState('')
  const [form, setForm] = useState(initialForm)
  const [editing, setEditing] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const loadUsers = useCallback(async (term: string) => {
    setLoading(true)
    try {
      setUsers(await usersApi.list(term, tagFilter))
    } catch (reason) {
      setError(explainError(reason))
    } finally {
      setLoading(false)
    }
  }, [tagFilter])

  const loadTags = useCallback(async () => {
    try { setTags(await usersApi.listTags()) } catch (reason) { setError(explainError(reason)) }
  }, [])

  useEffect(() => { const timer = window.setTimeout(() => void loadTags(), 0); return () => window.clearTimeout(timer) }, [loadTags])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadUsers(search), 180)
    return () => window.clearTimeout(timer)
  }, [loadUsers, search])

  const activeCount = users.length
  const initials = (name: string) => name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
  const formatter = useMemo(() => new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' }), [])

  function beginEdit(user: User) {
    setEditing(user)
    setForm({ username: user.username, name: user.name, email: user.email, phone: user.phone ?? '' })
    setSelectedTags(user.tags.map((tag) => tag.id))
    setNotice('')
    document.getElementById('name')?.focus()
  }

  function resetForm() {
    setEditing(null)
    setForm(initialForm)
    setSelectedTags([])
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    try {
      if (editing) {
        await usersApi.update(editing.id, form.username.trim(), form.name.trim(), form.email.trim(), form.phone.trim(), selectedTags)
        setNotice('Cadastro atualizado.')
      } else {
        await usersApi.create(form.username.trim(), form.name.trim(), form.email.trim(), form.phone.trim(), selectedTags)
        setNotice('Cliente cadastrado.')
      }
      resetForm()
      await loadUsers(search)
    } catch (reason) {
      setError(explainError(reason))
    } finally {
      setSaving(false)
    }
  }

  async function createTag() {
    setError('')
    setNotice('')
    try {
      const tag = await usersApi.createTag(newTag)
      setTags((current) => [...current, tag])
      setSelectedTags((current) => [...current, tag.id])
      setNewTag('')
      setNotice(`Etiqueta “${tag.name}” criada.`)
      setError('')
    } catch (reason) { setError(explainError(reason)) }
  }

  async function deactivate(user: User) {
    if (!window.confirm(`Desativar o cadastro de ${user.name}?`)) return
    setError('')
    setNotice('')
    try {
      await usersApi.deactivate(user.id)
      setNotice(`${user.name} foi desativado.`)
      await loadUsers(search)
    } catch (reason) {
      setError(explainError(reason))
    }
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Registro, início">
          <span className="brand-mark" aria-hidden="true">r.</span>
          <span>registro<span className="brand-period">.</span></span>
        </a>
        <div className="topbar-meta"><span className="status-dot" /> ambiente local</div>
      </header>

      <section className="intro" id="top">
        <div className="eyebrow"><span>01</span> ESPAÇO DE TRABALHO</div>
        <h1>Pessoas, em<br /><em>boa ordem.</em></h1>
        <p className="intro-copy">Um lugar simples para manter seus contatos organizados.<br className="desktop-break" /> Sem ruído, só o que você precisa.</p>
        <div className="intro-rule"><span>CLIENTES</span><span>—</span><span>CADASTRO LOCAL</span></div>
      </section>

      <section className="workspace" aria-label="Gerenciamento de clientes">
        <div className="workspace-heading">
          <div><span className="section-kicker">VISÃO GERAL</span><h2>Seus clientes <span className="count-pill">{activeCount.toString().padStart(2, '0')}</span></h2></div>
          <div className="filters"><label className="search-box"><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => { setError(''); setSearch(event.target.value) }} placeholder="Buscar por nome ou e-mail" aria-label="Buscar clientes" /></label><label className="tag-filter">Etiqueta<select aria-label="Filtrar por etiqueta" value={tagFilter} onChange={(event) => { setError(''); setTagFilter(event.target.value) }}><option value="">Todas</option>{tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select></label></div>
        </div>

        <div className="content-grid">
          <section className="list-panel" aria-label="Lista de clientes">
            <div className="list-labels"><span>CLIENTE</span><span>CADASTRADO</span><span>AÇÕES</span></div>
            {loading ? <div className="state-panel"><span className="spinner" />Carregando cadastros…</div> : null}
            {!loading && !error && users.length === 0 ? (
              <div className="state-panel empty-state"><span className="empty-icon">＋</span><strong>{search ? 'Nenhum resultado por aqui.' : 'Sua lista começa aqui.'}</strong><span>{search ? 'Tente buscar por outro nome ou e-mail.' : 'Adicione seu primeiro cliente usando o formulário ao lado.'}</span></div>
            ) : null}
            {!loading && users.map((user, index) => (
              <article className="user-row" key={user.id}>
                <div className="person-cell"><div className={`avatar avatar-${index % 4}`}>{initials(user.name)}</div><div className="person-copy"><strong>{user.name}</strong><span>{user.email}</span>{user.phone ? <span>{user.phone}</span> : null}<span className="tag-chips">{user.tags.map((tag) => <span key={tag.id}>{tag.name}</span>)}</span></div></div>
                <time dateTime={user.created_at}>{formatter.format(new Date(user.created_at))}</time>
                <div className="row-actions"><button className="text-action" onClick={() => beginEdit(user)}>Editar</button><button className="icon-action" aria-label={`Desativar ${user.name}`} title="Desativar cadastro" onClick={() => void deactivate(user)}>×</button></div>
              </article>
            ))}
            <div className="list-footer"><span><i className="status-dot" /> {activeCount} {activeCount === 1 ? 'cadastro ativo' : 'cadastros ativos'}</span><span>DADOS LOCAIS · PRIVADOS</span></div>
          </section>

          <aside className="form-panel">
            <div className="form-heading"><span className="section-kicker">{editing ? 'ATUALIZAÇÃO' : 'NOVO REGISTRO'}</span><h3>{editing ? 'Editar pessoa' : <>Adicionar<br />pessoa<span className="brand-period">.</span></>}</h3><p>{editing ? 'Atualize os dados deste cadastro.' : 'Só precisamos do essencial para começar.'}</p></div>
            <form onSubmit={(event) => void submit(event)}>
              <label htmlFor="username">NOME DE USUÁRIO</label>
              <input id="username" name="username" autoComplete="username" minLength={3} maxLength={32} pattern="[A-Za-z0-9][A-Za-z0-9._-]{2,31}" required value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} placeholder="Ex.: ada-example" />
              <label htmlFor="name">NOME COMPLETO</label>
              <input id="name" name="name" autoComplete="name" maxLength={120} required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Marina Costa" />
              <label htmlFor="email">E-MAIL</label>
              <input id="email" name="email" type="email" autoComplete="email" maxLength={254} required value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="marina@exemplo.com" />
              <label htmlFor="phone">TELEFONE (OPCIONAL)</label>
              <input id="phone" name="phone" type="tel" autoComplete="tel" minLength={7} maxLength={32} pattern="\+?[0-9 ()-]+" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="+55 85 99999-0000" />
              <label htmlFor="tag-select">ETIQUETAS (ATÉ 10)</label>
              <select id="tag-select" multiple value={selectedTags} onChange={(event) => setSelectedTags(Array.from(event.target.selectedOptions, (option) => option.value))}>{tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select>
              <div className="tag-create"><input aria-label="Nova etiqueta" maxLength={32} value={newTag} onChange={(event) => setNewTag(event.target.value)} placeholder="Nome da etiqueta" /><button type="button" disabled={!newTag.trim()} onClick={() => void createTag()}>Criar etiqueta</button></div>
              <button className="submit-button" type="submit" disabled={saving}>{saving ? 'Salvando…' : editing ? 'Salvar alterações' : <>Adicionar cliente <span aria-hidden="true">↗</span></>}</button>
              {editing ? <button className="cancel-button" type="button" onClick={resetForm}>Cancelar edição</button> : null}
              <div className="form-footnote"><span className="lock-icon">⌑</span> Seus dados ficam neste dispositivo.</div>
            </form>
          </aside>
        </div>
        <div className="messages" aria-live="polite">{error ? <p className="error-message">{error}</p> : null}{notice ? <p className="success-message">{notice}</p> : null}</div>
      </section>

      <footer className="page-footer"><span>FEITO PARA MANTER AS COISAS EM SEU LUGAR.</span><span>REGISTRO © 2026</span></footer>
    </main>
  )
}
