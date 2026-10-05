import { appConfig } from '../config/env'
import { mockDashboardData } from '../mock/dashboardData'
import type { DashboardData } from '../types/dashboard'

export interface DashboardService {
  getDashboardData(): Promise<DashboardData>
}

class MockDashboardService implements DashboardService {
  async getDashboardData(): Promise<DashboardData> {
    await new Promise((resolve) => window.setTimeout(resolve, 180))
    return structuredClone(mockDashboardData)
  }
}

class HttpDashboardService implements DashboardService {
  async getDashboardData(): Promise<DashboardData> {
    const response = await fetch(`${appConfig.apiBaseUrl}/dashboard`)
    if (!response.ok) throw new Error(`Dashboard API returned ${response.status}`)
    return response.json() as Promise<DashboardData>
  }
}

export const dashboardService: DashboardService = appConfig.useMockData
  ? new MockDashboardService()
  : new HttpDashboardService()
