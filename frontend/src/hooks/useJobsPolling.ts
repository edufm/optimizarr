import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Job } from '../api/types'

const POLL_MS = 2000

/** Faz polling de um conjunto de job ids até cada um atingir um status terminal. */
export function useJobsPolling(jobIds: string[]) {
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const trackedRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    for (const id of jobIds) trackedRef.current.add(id)
  }, [jobIds])

  useEffect(() => {
    let cancelled = false

    async function tick() {
      const ids = Array.from(trackedRef.current)
      if (ids.length === 0) return
      const results = await Promise.all(ids.map((id) => api.getJob(id).catch(() => null)))
      if (cancelled) return
      setJobs((prev) => {
        const next = { ...prev }
        results.forEach((job, i) => {
          if (!job) return
          next[ids[i]] = job
          if (job.status === 'succeeded' || job.status === 'failed') {
            trackedRef.current.delete(ids[i])
          }
        })
        return next
      })
    }

    tick()
    const interval = setInterval(tick, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  return jobs
}
