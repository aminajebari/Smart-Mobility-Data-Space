import { useCallback, useEffect, useState } from 'react'
import { appConfig } from '../config/env'
import { dashboardService } from '../services/dashboardService'
import type { DashboardData } from '../types/dashboard'

export function useDashboardData() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      setData(await dashboardService.getDashboardData())
      setError(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load dashboard')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  // Live mode: poll the dashboard API so the congestion scenario is visible as it happens
  useEffect(() => {
    if (appConfig.useMockData || appConfig.refreshMs <= 0) return
    const timer = window.setInterval(() => { void refresh(true) }, appConfig.refreshMs)
    return () => window.clearInterval(timer)
  }, [refresh])

  return { data, error, loading, refresh }
}
