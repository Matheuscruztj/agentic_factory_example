import { useState } from 'react'
import { getObservabilitySummary, type ObservabilitySummary } from '../../lib/api/client'

export function MetricsDashboard() {
  const [summary, setSummary] = useState<ObservabilitySummary | null>(null)
  const [taskId, setTaskId] = useState('')
  const [message, setMessage] = useState('Carregando métricas locais…')

  async function refresh(filter = taskId) {
    try {
      setSummary(await getObservabilitySummary(filter.trim() || undefined))
      setMessage('')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Métricas indisponíveis.')
    }
  }

  const measured = summary?.measured
  return <section className="operation-column" aria-label="Dashboard de observabilidade">
    <h2>Observabilidade e custo</h2>
    <form className="login-form" onSubmit={(event) => { event.preventDefault(); void refresh() }}>
      <label>Filtrar por ID da tarefa<input value={taskId} onChange={(event) => setTaskId(event.target.value)} /></label>
      <button>Carregar métricas</button>
    </form>
    <h3>Valores medidos localmente</h3>
    <div className="cards">
      <article className="card"><h4>Chamadas</h4><p>{measured?.count ?? 'n/d'} ({measured?.successful ?? 0} OK, {measured?.failed ?? 0} falhas)</p></article>
      <article className="card"><h4>Espera mediana</h4><p>{formatMs(measured?.median_queue_wait_ms)}</p></article>
      <article className="card"><h4>Carregamento mediano</h4><p>{formatMs(measured?.median_load_ms)}</p></article>
      <article className="card"><h4>Geração mediana</h4><p>{formatMs(measured?.median_generation_ms)}</p></article>
      <article className="card"><h4>Tokens de entrada / saída</h4><p>{measured ? `${measured.prompt_tokens} / ${measured.completion_tokens}` : 'n/d'}</p></article>
      <article className="card"><h4>VRAM / potência</h4><p>{hardwareText(measured?.hardware)}</p></article>
      <article className="card"><h4>Custo medido</h4><p>{measured?.cost_usd == null ? 'n/d' : `$${measured.cost_usd.toFixed(6)}`}</p></article>
    </div>
    <h3>Estimativas</h3>
    <p>Custo estimado: {summary?.estimates.cost_usd == null ? 'indisponível (sem fonte de preços configurada)' : `$${summary.estimates.cost_usd.toFixed(6)}`}</p>
    {message && <p role="status">{message}</p>}
  </section>
}

function formatMs(value: number | null | undefined) { return value == null ? 'n/d' : `${value.toFixed(1)} ms` }
function hardwareText(hardware: ObservabilitySummary['measured']['hardware'] | undefined) {
  if (!hardware || hardware.status !== 'available') return 'indisponível'
  return hardware.devices.map((device) => `${device.memory_used_mib ?? 'n/d'}/${device.memory_total_mib ?? 'n/d'} MiB · ${device.power_watts ?? 'n/d'} W`).join('; ')
}
