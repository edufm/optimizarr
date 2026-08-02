import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { FolderFiles } from '../api/types'

export function useFolderFiles(folderId: string) {
  const [data, setData] = useState<FolderFiles | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await api.getFolderFiles(folderId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'erro desconhecido')
    } finally {
      setLoading(false)
    }
  }, [folderId])

  useEffect(() => {
    refetch()
  }, [refetch])

  return { data, loading, error, refetch }
}
