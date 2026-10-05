import type { DashboardData } from '../types/dashboard'

export const mockDashboardData: DashboardData = {
  updatedAt: '2026-09-15T08:42:00+01:00',
  providers: [
    { id: 'bus', name: 'Tunis Bus Network', type: 'Public transit', status: 'connected', lastSync: '12 sec ago', icon: 'bus' },
    { id: 'traffic', name: 'Urban Traffic Sensors', type: 'Road telemetry', status: 'connected', lastSync: '4 sec ago', icon: 'signal' },
    { id: 'parking', name: 'Smart Parking Tunis', type: 'Parking network', status: 'connected', lastSync: '28 sec ago', icon: 'parking' },
    { id: 'micro', name: 'Medina Micro-Mobility', type: 'Bikes & scooters', status: 'disconnected', lastSync: '18 min ago', icon: 'bike' },
  ],
  services: [
    { id: 'simulation', name: 'Mobility Simulation', endpoint: '/simulation', status: 'healthy', latency: 42 },
    { id: 'gateway', name: 'Data Space Gateway', endpoint: '/gateway', status: 'healthy', latency: 68 },
    { id: 'governance', name: 'Gaia-X Governance', endpoint: '/governance', status: 'warning', latency: 184 },
    { id: 'edge-ai', name: 'Edge AI Prediction', endpoint: '/predictions', status: 'healthy', latency: 31 },
    { id: 'parking-api', name: 'Parking Service', endpoint: '/parking', status: 'offline', latency: null },
  ],
  kpis: [
    { id: 'speed', label: 'Average speed', value: '28.4 km/h', detail: '−12% from usual', trend: 'down', icon: 'speed' },
    { id: 'density', label: 'Traffic density', value: '76%', detail: 'High on 3 corridors', trend: 'up', icon: 'density' },
    { id: 'incidents', label: 'Active incidents', value: '7', detail: '2 require attention', trend: 'up', icon: 'incident' },
    { id: 'parking', label: 'Parking occupancy', value: '82%', detail: '1,146 / 1,398 spaces', trend: 'up', icon: 'parking' },
    { id: 'providers', label: 'Active providers', value: '3 / 4', detail: '1 connection offline', trend: 'neutral', icon: 'provider' },
  ],
  traffic: [
    { time: '06:00', density: 24, speed: 48 }, { time: '06:30', density: 30, speed: 46 },
    { time: '07:00', density: 41, speed: 41 }, { time: '07:30', density: 55, speed: 36 },
    { time: '08:00', density: 72, speed: 29 }, { time: '08:30', density: 88, speed: 19 },
    { time: '09:00', density: 92, speed: 16 }, { time: '09:30', density: 81, speed: 23 },
    { time: '10:00', density: 68, speed: 30 }, { time: '10:30', density: 57, speed: 35 },
    { time: '11:00', density: 52, speed: 38 }, { time: '11:30', density: 48, speed: 40 },
  ],
  predictions: [
    { id: 'probability', label: 'Congestion probability', value: '87%', detail: 'Next 30 minutes', confidence: 91, severity: 'high' },
    { id: 'level', label: 'Predicted traffic level', value: 'Severe', detail: 'Avenue de la République', confidence: 88, severity: 'high' },
    { id: 'travel', label: 'Estimated travel time', value: '34 min', detail: 'Centre → Lac 1 · +11 min', confidence: 84, severity: 'medium' },
  ],
  exchanges: [
    { id: 'ex-1', source: 'Traffic Sensors', destination: 'Edge AI', dataset: 'Road flow telemetry', authorization: 'authorized', timestamp: '08:41:52' },
    { id: 'ex-2', source: 'Smart Parking', destination: 'Dashboard', dataset: 'Occupancy snapshot', authorization: 'authorized', timestamp: '08:41:34' },
    { id: 'ex-3', source: 'Bus Provider', destination: 'Data Space', dataset: 'GTFS real-time', authorization: 'authorized', timestamp: '08:40:18' },
    { id: 'ex-4', source: 'Micro-Mobility', destination: 'Edge AI', dataset: 'Vehicle availability', authorization: 'pending', timestamp: '08:37:05' },
    { id: 'ex-5', source: 'Traffic Sensors', destination: 'Bus Provider', dataset: 'Incident alerts', authorization: 'denied', timestamp: '08:32:41' },
  ],
}
