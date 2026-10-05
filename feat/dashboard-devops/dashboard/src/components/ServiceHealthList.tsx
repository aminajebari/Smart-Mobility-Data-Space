import type { ServiceHealth } from '../types/dashboard'
import { StatusBadge } from './StatusBadge'

export function ServiceHealthList({ services }: { services: ServiceHealth[] }) {
  return <div className="service-list">{services.map((service) => (
    <div className="service" key={service.id}>
      <div><strong>{service.name}</strong><code>{service.endpoint}</code></div>
      <div className="service__state"><span>{service.latency === null ? 'No response' : `${service.latency} ms`}</span><StatusBadge status={service.status} /></div>
    </div>
  ))}</div>
}
