import { Link } from 'react-router-dom'
import type { FolderSummary } from '../api/types'
import { formatBytes, formatPercent } from '../utils/format'

export function FolderSummaryCard({ folder }: { folder: FolderSummary }) {
  return (
    <div className="card">
      <div className="card-title">
        <Link to={`/folders/${folder.id}`}>{folder.label}</Link>
      </div>
      <div className="card-sub">{folder.path}</div>

      {!folder.has_csv ? (
        <p className="card-empty">
          Nunca analisado — <Link to={`/folders/${folder.id}`}>vá até a pasta e clique em Atualizar</Link>.
        </p>
      ) : (
        <div className="card-stats">
          <div className="stat">
            <span className="stat-label">Atual</span>
            <span className="stat-value">{formatBytes(folder.current_size_bytes!)}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Estimado (x265)</span>
            <span className="stat-value">{formatBytes(folder.estimated_size_x265_bytes!)}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Economia</span>
            <span className="stat-value stat-highlight">{formatPercent(folder.savings_x265_pct!)}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Arquivos</span>
            <span className="stat-value">{folder.file_count}</span>
          </div>
        </div>
      )}
    </div>
  )
}
