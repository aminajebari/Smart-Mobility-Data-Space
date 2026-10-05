import { appConfig } from '../config/env'
import { ExchangeTable } from '../components/ExchangeTable'
import { KpiCard } from '../components/KpiCard'
import { PredictionCards } from '../components/PredictionCards'
import { ProviderList } from '../components/ProviderList'
import { Section } from '../components/Section'
import { ServiceHealthList } from '../components/ServiceHealthList'
import { TrafficChart } from '../components/TrafficChart'
import { useDashboardData } from '../hooks/useDashboardData'

const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

export function DashboardPage() {
  const { data, error, loading, refresh } = useDashboardData()
  if (loading && !data) return <main className="state-screen"><div className="loader"/><p>Connecting to mobility data space…</p></main>
  if (!data) return <main className="state-screen"><h1>Dashboard unavailable</h1><p>{error}</p><button onClick={() => void refresh()}>Try again</button></main>

  const live = data.mode === 'live'
  const healthy = data.services.filter((s) => s.status === 'healthy').length
  const traffic = data.traffic
  const peak = traffic.length ? traffic.reduce((max, p) => (p.density > max.density ? p : max), traffic[0]) : null
  const timeWindow = traffic.length ? `${traffic[0].time}—${traffic[traffic.length - 1].time}` : 'NO DATA YET'
  const stats = data.exchangeStats
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand__mark">S</span><div><strong>SMART MOBILITY</strong><small>DATA SPACE</small></div></div>
        <nav aria-label="Main navigation"><a className="active" href="#overview"><span>⌂</span>Overview</a><a href="#providers"><span>◇</span>Providers</a><a href="#traffic"><span>≋</span>Traffic</a><a href="#exchanges"><span>⇄</span>Data exchanges</a></nav>
        <div className="sidebar__foot"><span className={live ? 'mock-pill live-pill' : 'mock-pill'}>{live ? 'LIVE DATA SPACE' : 'MOCK ENVIRONMENT'}</span><small>Dashboard · v1.0</small></div>
      </aside>
      <main className="dashboard" id="overview">
        <header className="topbar"><div><span className="eyebrow">OPERATIONS CENTER</span><h1>Mobility Overview</h1><p>Greater Tunis urban network</p></div><div className="topbar__actions"><div className="live"><i/>{live ? 'Live monitoring' : 'Demo data'}</div><button className="refresh" onClick={() => void refresh()} disabled={loading}>{loading ? 'Refreshing…' : '↻ Refresh data'}</button></div></header>
        {error && <div className="notice notice--error"><span>!</span><p><strong>Last refresh failed</strong> {error}. Showing the previous snapshot.</p></div>}
        {live
          ? <div className="notice"><span>AI</span><p><strong>Live data space</strong> Provider data is simulated locally by each provider and reaches this dashboard only through policy-checked APIs. Predictions are computed on the edge node.</p></div>
          : <div className="notice"><span>AI</span><p><strong>Demonstration environment</strong> All values and Edge AI predictions on this dashboard are simulated mock data.</p></div>}
        <div className="kpi-grid">{data.kpis.map((kpi) => <KpiCard key={kpi.id} kpi={kpi}/>)}</div>
        <div className="two-column" id="providers">
          <Section title="Connected providers" eyebrow="DATA SOURCES" action={<span className="count">{data.providers.filter(p=>p.status==='connected').length}/{data.providers.length} online</span>} className="providers-panel"><ProviderList providers={data.providers}/></Section>
          <Section title="API health" eyebrow="SYSTEM STATUS" action={<span className="count">{healthy}/{data.services.length} healthy</span>}><ServiceHealthList services={data.services}/></Section>
        </div>
        <div id="traffic"><Section title="Network traffic & congestion" eyebrow={`${timeWindow} · TODAY`} action={peak && <span className="alert-chip">▲ Peak at {peak.time}</span>} className="wide-panel"><TrafficChart data={traffic}/></Section></div>
        <Section title="Edge AI predictions" eyebrow={live ? 'EDGE NODE · ONNX RUNTIME' : 'MOCK PREDICTIONS'} action={<span className="model-tag">{live ? 'CONGESTION MODEL · LIVE' : 'EDGE MODEL · SIMULATED'}</span>}><PredictionCards predictions={data.predictions}/></Section>
        <div id="exchanges"><Section title="Recent data space exchanges" eyebrow="GAIA-X ACTIVITY" action={<span className="count">{stats ? `${stats.allow} allowed · ${stats.deny} denied` : 'Last 15 minutes'}</span>} className="wide-panel"><ExchangeTable exchanges={data.exchanges}/></Section></div>
        <footer><span>Smart Mobility Data Space</span><span>Source: {appConfig.useMockData ? 'Mock service' : appConfig.apiBaseUrl} · Updated {clock(data.updatedAt)}</span></footer>
      </main>
    </div>
  )
}
