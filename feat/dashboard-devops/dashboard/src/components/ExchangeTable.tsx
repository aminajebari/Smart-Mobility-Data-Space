import type { DataExchange } from '../types/dashboard'
import { StatusBadge } from './StatusBadge'

export function ExchangeTable({ exchanges }: { exchanges: DataExchange[] }) {
  return <div className="table-scroll"><table><thead><tr><th>Route</th><th>Dataset</th><th>Authorization</th><th>Time</th></tr></thead><tbody>{exchanges.map((exchange) => (
    <tr key={exchange.id}><td><span className="exchange-route"><b>{exchange.source}</b><i>→</i>{exchange.destination}</span></td><td>{exchange.dataset}</td><td><StatusBadge status={exchange.authorization}/></td><td className="mono">{exchange.timestamp}</td></tr>
  ))}</tbody></table></div>
}
