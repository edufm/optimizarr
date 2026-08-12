import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { OptimizeHistoryEntry } from '../api/types'

const POLL_MS = 5000
const PAGE_SIZE = 10

/** Histórico persistido de otimizações concluídas (sobrevive a redeploy, diferente da
 * fila). "Carregar mais" só aumenta o limit e busca de novo — sem cursor/offset. */
export function useOptimizeHistory() {
  const [entries, setEntries] = useState<OptimizeHistoryEntry[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [limit, setLimit] = useState(PAGE_SIZE)

  const refetch = useCallback(async (currentLimit: number) => {
    const { entries, has_more } = await api.getJobHistory(currentLimit)
    setEntries(entries)
    setHasMore(has_more)
  }, [])

  useEffect(() => {
    refetch(limit)
    const interval = setInterval(() => refetch(limit), POLL_MS)
    return () => clearInterval(interval)
  }, [limit, refetch])

  const loadMore = useCallback(() => setLimit((l) => l + PAGE_SIZE), [])

  return { entries, hasMore, loadMore }
}
