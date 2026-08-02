import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Dashboard } from '../api/types'

export function useDashboard() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setDashboard(await api.getDashboard())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'erro desconhecido')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  return { dashboard, loading, error, refetch }
}
