import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Job } from '../api/types'

const POLL_MS = 2000

/** Fila global de otimização (running + queued), ordenada pela ordem real de execução. */
export function useOptimizeQueue() {
  const [jobs, setJobs] = useState<Job[]>([])

  const refetch = useCallback(async () => {
    const { jobs } = await api.listJobs({ active: true })
    setJobs(
      jobs
        .filter((j) => j.type === 'optimize')
        .sort((a, b) => a.created_at.localeCompare(b.created_at)),
    )
  }, [])

  useEffect(() => {
    refetch()
    const interval = setInterval(refetch, POLL_MS)
    return () => clearInterval(interval)
  }, [refetch])

  return { jobs, refetch }
}
