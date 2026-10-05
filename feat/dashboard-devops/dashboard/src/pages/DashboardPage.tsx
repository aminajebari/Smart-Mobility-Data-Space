import { appConfig } from '../config/env'
import { ExchangeTable } from '../components/ExchangeTable'
import { KpiCard } from '../components/KpiCard'
import { PredictionCards } from '../components/PredictionCards'
import { ProviderList } from '../components/ProviderList'
import { Section } from '../components/Section'
import { ServiceHealthList } from '../components/ServiceHealthList'
import { TrafficChart } from '../components/TrafficChart'
import { useDashboardData } from '../hooks/useDashboardData'

export function DashboardPage() {
  const { data, error, loading, refresh } = useDashboardData()
  if (loading && !data) return <main className="state-screen"><div className="loader"/><p>Connecting to mobility data space…</p></main>
  if (error || !data) return <main className="state-screen"><h1>Dashboard unavailable</h1><p>{error}</p><button onClick={() => void refresh()}>Try again</button></main>

  const healthy = data.services.filter((s) => s.status === 'healthy').length
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand__mark">S</span><div><strong>SMART MOBILITY</strong><small>DATA SPACE</small></div></div>
        <nav aria-label="Main navigation"><a className="active" href="#overview"><span>⌂</span>Overview</a><a href="#providers"><span>◇</span>Providers</a><a href="#traffic"><span>≋</span>Traffic</a><a href="#exchanges"><span>⇄</span>Data exchanges</a></nav>
        <div className="sidebar__foot"><span className="mock-pill">MOCK ENVIRONMENT</span><small>Dashboard prototype · v0.1</small></div>
      </aside>
      <main className="dashboard" id="overview">
        <header className="topbar"><div><span className="eyebrow">OPERATIONS CENTER</span><h1>Mobility Overview</h1><p>Greater Tunis urban network</p></div><div className="topbar__actions"><div className="live"><i/>Live monitoring</div><button className="refresh" onClick={() => void refresh()} disabled={loading}>{loading ? 'Refreshing…' : '↻ Refresh data'}</button></div></header>
        <div className="notice"><span>AI</span><p><strong>Demonstration environment</strong> All values and Edge AI predictions on this dashboard are simulated mock data.</p></div>
        <div className="kpi-grid">{data.kpis.map((kpi) => <KpiCard key={kpi.id} kpi={kpi}/>)}</div>
        <div className="two-column">
          <Section title="Connected providers" eyebrow="DATA SOURCES" action={<span className="count">{data.providers.filter(p=>p.status==='connected').length}/{data.providers.length} online</span>} className="providers-panel"><ProviderList providers={data.providers}/></Section>
          <Section title="API health" eyebrow="SYSTEM STATUS" action={<span className="count">{healthy}/{data.services.length} healthy</span>}><ServiceHealthList services={data.services}/></Section>
        </div>
        <Section title="Network traffic & congestion" eyebrow="06:00—11:30 · TODAY" action={<span className="alert-chip">▲ Peak at 09:00</span>} className="wide-panel" ><TrafficChart data={data.traffic}/></Section>
        <Section title="Edge AI predictions" eyebrow="MOCK PREDICTIONS" action={<span className="model-tag">EDGE MODEL · SIMULATED</span>}><PredictionCards predictions={data.predictions}/></Section>
        <Section title="Recent data space exchanges" eyebrow="GAIA-X ACTIVITY" action={<span className="count">Last 15 minutes</span>} className="wide-panel" ><ExchangeTable exchanges={data.exchanges}/></Section>
        <footer><span>Smart Mobility Data Space</span><span>Source: {appConfig.useMockData ? 'Mock service' : appConfig.apiBaseUrl} · Updated 08:42 CET</span></footer>
      </main>
    </div>
  )
}
