import type { EdgePrediction } from '../types/dashboard'

export function PredictionCards({ predictions }: { predictions: EdgePrediction[] }) {
  return <div className="prediction-grid">{predictions.map((item) => (
    <article className={`prediction prediction--${item.severity}`} key={item.id}>
      <span>{item.label}</span><strong>{item.value}</strong><p>{item.detail}</p>
      <div className="confidence"><span>Model confidence</span><b>{item.confidence}%</b><div><i style={{ width: `${item.confidence}%` }} /></div></div>
    </article>
  ))}</div>
}
