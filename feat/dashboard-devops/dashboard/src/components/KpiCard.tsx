import type { Kpi } from '../types/dashboard'

const symbols: Record<string, string> = { speed: '↗', density: '≋', incident: '!', parking: 'P', provider: '⌁' }

export function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <article className="kpi-card">
      <div className={`kpi-card__icon kpi-card__icon--${kpi.id}`}>{symbols[kpi.icon]}</div>
      <div className="kpi-card__content"><span>{kpi.label}</span><strong>{kpi.value}</strong><small className={`trend trend--${kpi.trend}`}>{kpi.detail}</small></div>
    </article>
  )
}
