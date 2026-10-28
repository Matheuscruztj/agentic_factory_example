import { useEffect, useMemo, useState } from 'react'
import { getBenchmarks, type BenchmarkReport } from '../../lib/api/client'

type View = 'coding' | 'judge'

export function BenchmarkDashboard() {
  const [view, setView] = useState<View>('coding')
  const [model, setModel] = useState('')
  const [report, setReport] = useState<BenchmarkReport | null>(null)
  const [message, setMessage] = useState('Carregando avaliações…')

  async function load(nextView = view, nextModel = model) {
    try {
      const result = await getBenchmarks(nextView, nextModel || undefined)
      if (result.status === 'error') throw new Error('O relatório local está inválido.')
      setReport(result)
      setMessage(result.records.length ? '' : 'Nenhum benchmark disponível para estes filtros.')
    } catch (error) {
      setReport(null)
      setMessage(error instanceof Error ? error.message : 'Não foi possível carregar benchmarks.')
    }
  }

  useEffect(() => {
    let active = true
    getBenchmarks(view, model || undefined).then((result) => {
      if (!active) return
      if (result.status === 'error') throw new Error('O relatório local está inválido.')
      setReport(result)
      setMessage(result.records.length ? '' : 'Nenhum benchmark disponível para estes filtros.')
    }).catch((error: unknown) => {
      if (!active) return
      setReport(null)
      setMessage(error instanceof Error ? error.message : 'Não foi possível carregar benchmarks.')
    })
    return () => { active = false }
  }, [view, model])
  const records = useMemo(() => report?.records ?? [], [report])
  const models = useMemo(() => [...new Set(records.map((item) => item.model).filter((item): item is string => Boolean(item)))], [records])

  return <section className="operation-column" aria-label="Dashboard de benchmarks">
    <h2>Benchmarks de coding e Judge</h2>
    <div className="operation-tabs" aria-label="Tipo de avaliação">
      <button type="button" aria-pressed={view === 'coding'} onClick={() => setView('coding')}>Coding</button>
      <button type="button" aria-pressed={view === 'judge'} onClick={() => setView('judge')}>Judge</button>
    </div>
    <form className="login-form" onSubmit={(event) => { event.preventDefault(); void load() }}>
      <label htmlFor="benchmark-model">Filtrar por modelo</label>
      <select id="benchmark-model" value={model} onChange={(event) => setModel(event.target.value)}>
        <option value="">Todos os modelos</option>
        {models.map((name) => <option key={name} value={name}>{name}</option>)}
      </select>
      <button type="submit">Aplicar filtros</button>
    </form>
    {message && <p role="status">{message}</p>}
    {!message && <>
      <div className="cards" aria-label="Resumo de qualidade e latência">
        {records.map((item) => <article className="card" key={`${item.role}-${item.route}-${item.model}`}>
          <h3>{item.role === 'coding' ? `Coding · ${item.route}` : `Judge · ${item.route}`}</h3>
          <p>Modelo: {item.model ?? 'indisponível'}</p>
          <p>Qualidade: {item.quality == null ? 'não avaliada' : `${(item.quality * 100).toFixed(1)}%`}</p>
          <p>Latência p50: {item.latency_ms == null ? 'n/d' : `${item.latency_ms.toFixed(0)} ms`}</p>
          {item.accepted_tasks_per_hour != null && <p>Tarefas aceitas/h: {item.accepted_tasks_per_hour.toFixed(2)}</p>}
          {item.tokens != null && <p>Tokens: {item.tokens}</p>}
          <small>Trace: {item.run_id ?? item.trace} · {item.trace}</small>
        </article>)}
      </div>
      <div className="benchmark-chart" role="img" aria-label="Latência por rota; a altura das barras representa milissegundos">
        <h3>Tempo × qualidade</h3>
        <div className="benchmark-bars">{records.map((item) => <div key={`bar-${item.route}-${item.model}`}>
          <span>{item.route}</span><i style={{ height: `${Math.max(4, Math.min(100, (item.latency_ms ?? 0) / 200))}%` }} />
          <small>{item.quality == null ? 'qualidade n/a' : `${(item.quality * 100).toFixed(0)}% qualidade`}</small>
        </div>)}</div>
      </div>
      <p>Comparação de prompts: consulte “Evals e feedback”, seção de versões e comparação de releases.</p>
    </>}
  </section>
}
