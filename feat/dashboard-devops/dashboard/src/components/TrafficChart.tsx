import type { TrafficPoint } from '../types/dashboard'

const width = 760, height = 270, left = 44, right = 18, top = 22, bottom = 38
const plotWidth = width - left - right, plotHeight = height - top - bottom
const point = (value: number, index: number, count: number) => ({ x: left + (index * plotWidth) / Math.max(count - 1, 1), y: top + plotHeight - (Math.min(value, 100) / 100) * plotHeight })
const pathFor = (data: TrafficPoint[], accessor: (p: TrafficPoint) => number) => data.map((p, i) => { const { x, y } = point(accessor(p), i, data.length); return `${i ? 'L' : 'M'} ${x} ${y}` }).join(' ')

/** Contiguous runs of points flagged as incident/congestion, as [startIndex, endIndex]. */
export function congestionRanges(data: TrafficPoint[]): [number, number][] {
  const ranges: [number, number][] = []
  data.forEach((p, i) => {
    if (!p.incident) return
    const last = ranges[ranges.length - 1]
    if (last && last[1] === i - 1) last[1] = i
    else ranges.push([i, i])
  })
  return ranges
}

export function TrafficChart({ data }: { data: TrafficPoint[] }) {
  if (data.length === 0) return <div className="chart-wrap"><p className="chart-empty">Waiting for traffic sensor data…</p></div>
  const densityPath = pathFor(data, (p) => p.density)
  const speedPath = pathFor(data, (p) => p.speed)
  const ranges = congestionRanges(data)
  const step = plotWidth / Math.max(data.length - 1, 1)
  const label = ranges.length
    ? `Traffic density and average speed time series showing congestion from ${data[ranges[0][0]].time} to ${data[ranges[ranges.length - 1][1]].time}`
    : 'Traffic density and average speed time series, no congestion detected'
  const labelEvery = Math.max(1, Math.ceil(data.length / 8))
  return (
    <div className="chart-wrap">
      <div className="chart-legend"><span><i className="legend-density" />Traffic density</span><span><i className="legend-speed" />Average speed</span><span className="chart-unit">Live urban network · % / km/h</span></div>
      <svg className="traffic-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
        <defs><linearGradient id="densityFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ffb547" stopOpacity=".32"/><stop offset="1" stopColor="#ffb547" stopOpacity="0"/></linearGradient></defs>
        {[0, 25, 50, 75, 100].map((value) => { const y = top + plotHeight - value / 100 * plotHeight; return <g key={value}><line x1={left} x2={width-right} y1={y} y2={y} className="grid-line"/><text x={left-10} y={y+4} textAnchor="end" className="axis-label">{value}</text></g> })}
        {ranges.map(([start, end]) => {
          const x1 = Math.max(left, point(0, start, data.length).x - step / 2)
          const x2 = Math.min(left + plotWidth, point(0, end, data.length).x + step / 2)
          return <g key={start}><rect x={x1} y={top} width={Math.max(x2 - x1, 6)} height={plotHeight} className="congestion-zone" rx="6"/>{x2 - x1 > 90 && <text x={(x1+x2)/2} y={top+16} textAnchor="middle" className="congestion-label">CONGESTION EVENT</text>}</g>
        })}
        <path d={`${densityPath} L ${left+plotWidth} ${top+plotHeight} L ${left} ${top+plotHeight} Z`} fill="url(#densityFill)"/>
        <path d={densityPath} className="line line--density"/><path d={speedPath} className="line line--speed"/>
        {data.map((p, i) => { const x=point(0,i,data.length).x; return <g key={`${p.time}-${i}`}>{i%labelEvery===0 && <text x={x} y={height-12} textAnchor="middle" className="axis-label">{p.time}</text>}<circle cx={x} cy={point(p.density,i,data.length).y} r="3" className="dot dot--density"/></g> })}
      </svg>
    </div>
  )
}
