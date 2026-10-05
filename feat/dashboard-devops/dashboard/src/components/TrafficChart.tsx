import type { TrafficPoint } from '../types/dashboard'

const width = 760, height = 270, left = 44, right = 18, top = 22, bottom = 38
const plotWidth = width - left - right, plotHeight = height - top - bottom
const point = (value: number, index: number, count: number) => ({ x: left + (index * plotWidth) / (count - 1), y: top + plotHeight - (value / 100) * plotHeight })
const pathFor = (data: TrafficPoint[], accessor: (p: TrafficPoint) => number) => data.map((p, i) => { const { x, y } = point(accessor(p), i, data.length); return `${i ? 'L' : 'M'} ${x} ${y}` }).join(' ')

export function TrafficChart({ data }: { data: TrafficPoint[] }) {
  const densityPath = pathFor(data, (p) => p.density)
  const speedPath = pathFor(data, (p) => p.speed)
  const peakStart = point(0, 4, data.length).x
  const peakEnd = point(0, 7, data.length).x
  return (
    <div className="chart-wrap">
      <div className="chart-legend"><span><i className="legend-density" />Traffic density</span><span><i className="legend-speed" />Average speed</span><span className="chart-unit">Live urban network · % / km/h</span></div>
      <svg className="traffic-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Traffic density and average speed time series showing congestion from 8 to 9:30">
        <defs><linearGradient id="densityFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ffb547" stopOpacity=".32"/><stop offset="1" stopColor="#ffb547" stopOpacity="0"/></linearGradient></defs>
        {[0, 25, 50, 75, 100].map((value) => { const y = top + plotHeight - value / 100 * plotHeight; return <g key={value}><line x1={left} x2={width-right} y1={y} y2={y} className="grid-line"/><text x={left-10} y={y+4} textAnchor="end" className="axis-label">{value}</text></g> })}
        <rect x={peakStart} y={top} width={peakEnd-peakStart} height={plotHeight} className="congestion-zone" rx="6"/>
        <text x={(peakStart+peakEnd)/2} y={top+16} textAnchor="middle" className="congestion-label">CONGESTION EVENT</text>
        <path d={`${densityPath} L ${left+plotWidth} ${top+plotHeight} L ${left} ${top+plotHeight} Z`} fill="url(#densityFill)"/>
        <path d={densityPath} className="line line--density"/><path d={speedPath} className="line line--speed"/>
        {data.map((p, i) => { const x=point(0,i,data.length).x; return <g key={p.time}>{i%2===0 && <text x={x} y={height-12} textAnchor="middle" className="axis-label">{p.time}</text>}<circle cx={x} cy={point(p.density,i,data.length).y} r="3" className="dot dot--density"/></g> })}
      </svg>
    </div>
  )
}
