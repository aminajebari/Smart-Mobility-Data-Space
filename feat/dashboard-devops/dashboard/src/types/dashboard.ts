export type ConnectionStatus = 'connected' | 'disconnected'
export type HealthStatus = 'healthy' | 'warning' | 'offline'
export type AuthorizationStatus = 'authorized' | 'pending' | 'denied'

export interface Provider {
  id: string
  name: string
  type: string
  status: ConnectionStatus
  lastSync: string
  icon: string
}

export interface ServiceHealth {
  id: string
  name: string
  endpoint: string
  status: HealthStatus
  latency: number | null
}

export interface Kpi {
  id: string
  label: string
  value: string
  detail: string
  trend: 'up' | 'down' | 'neutral'
  icon: string
}

export interface TrafficPoint {
  time: string
  density: number
  speed: number
  incident?: boolean
}

export interface EdgePrediction {
  id: string
  label: string
  value: string
  detail: string
  confidence: number
  severity: 'low' | 'medium' | 'high'
}

export interface DataExchange {
  id: string
  source: string
  destination: string
  dataset: string
  authorization: AuthorizationStatus
  timestamp: string
  reason?: string
}

export interface ExchangeStats {
  total: number
  allow: number
  deny: number
}

export interface DashboardData {
  providers: Provider[]
  services: ServiceHealth[]
  kpis: Kpi[]
  traffic: TrafficPoint[]
  predictions: EdgePrediction[]
  exchanges: DataExchange[]
  updatedAt: string
  mode?: 'live' | 'mock'
  exchangeStats?: ExchangeStats
}
