import type { Provider } from '../types/dashboard'
import { StatusBadge } from './StatusBadge'

const icons: Record<string, string> = { bus: '▰', signal: '⌁', parking: 'P', bike: '◎' }

export function ProviderList({ providers }: { providers: Provider[] }) {
  return <div className="provider-list">{providers.map((provider) => (
    <div className="provider" key={provider.id}>
      <span className="provider__icon">{icons[provider.icon]}</span>
      <div className="provider__identity"><strong>{provider.name}</strong><span>{provider.type} · {provider.lastSync}</span></div>
      <StatusBadge status={provider.status} />
    </div>
  ))}</div>
}
