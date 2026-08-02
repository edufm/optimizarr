import { Link } from 'react-router-dom'
import { useDashboard } from '../hooks/useDashboard'
import { DiskUsageCard } from '../components/DiskUsageCard'
import { FolderSummaryCard } from '../components/FolderSummaryCard'

export function DashboardPage() {
  const { dashboard, loading, error } = useDashboard()

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
    </div>
  )
}
