import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useDashboard } from '../hooks/useDashboard'
import { useFolders } from '../hooks/useFolders'
import { useOptimizeQueue } from '../hooks/useOptimizeQueue'
import { useOptimizeHistory } from '../hooks/useOptimizeHistory'
import { api, ApiError } from '../api/client'
import { DiskUsageCard } from '../components/DiskUsageCard'
import { FolderSummaryCard } from '../components/FolderSummaryCard'
import { OptimizeQueueList } from '../components/OptimizeQueueList'
import { OptimizeHistoryList } from '../components/OptimizeHistoryList'

export function DashboardPage() {
  const { dashboard, loading, error } = useDashboard()
  const { folders } = useFolders()
  const { jobs: queueJobs, refetch: refetchQueue } = useOptimizeQueue()
  const { entries: historyEntries, hasMore: historyHasMore, loadMore: loadMoreHistory } = useOptimizeHistory()
  const [cancelError, setCancelError] = useState<string | null>(null)

  async function handleCancel(jobId: string) {
    if (!confirm('Cancelar esse item da fila? Ele ainda não foi iniciado.')) return
    setCancelError(null)
    try {
      await api.cancelJob(jobId)
      refetchQueue()
    } catch (err) {
      setCancelError(err instanceof ApiError ? err.message : 'erro ao cancelar')
    }
  }

  if (loading) return <p className="hint">Carregando…</p>
  if (error) return <p className="error">Erro: {error}</p>
  if (!dashboard) return null

  return (
    <div className="page">
      <h1>Dashboard</h1>

      {dashboard.disks.length > 0 && (
        <section>
          <h2>Discos</h2>
          <div className="card-grid">
            {dashboard.disks.map((disk) => (
              <DiskUsageCard key={disk.mount} disk={disk} />
            ))}
          </div>
        </section>
      )}

      <section>
        <h2>Pastas</h2>
        {dashboard.folders.length === 0 ? (
          <p className="hint">
            Nenhuma pasta configurada ainda. Vá em <Link to="/settings">Configurações</Link> pra adicionar uma.
          </p>
        ) : (
          <div className="card-grid">
            {dashboard.folders.map((folder) => (
              <FolderSummaryCard key={folder.id} folder={folder} />
            ))}
          </div>
        )}
      </section>

      {(queueJobs.length > 0 || historyEntries.length > 0) && (
        <section>
          <h2>Fila de otimização</h2>
          {cancelError && <p className="error">{cancelError}</p>}
          {queueJobs.length > 0 && (
            <OptimizeQueueList jobs={queueJobs} folders={folders} onCancel={handleCancel} />
          )}
          {historyEntries.length > 0 && (
            <>
              <h3>Concluídos recentemente</h3>
              <OptimizeHistoryList
                entries={historyEntries}
                folders={folders}
                hasMore={historyHasMore}
                onLoadMore={loadMoreHistory}
              />
            </>
          )}
        </section>
      )}
    </div>
  )
}
