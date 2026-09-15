import { useCallback, useEffect, useState } from 'react'
import { dashboardService } from '../services/dashboardService'
import type { DashboardData } from '../types/dashboard'

export function useDashboardData() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await dashboardService.getDashboardData())
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  return { data, error, loading, refresh }
}
