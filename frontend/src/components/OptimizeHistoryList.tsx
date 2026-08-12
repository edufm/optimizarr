import type { Folder, OptimizeHistoryEntry } from '../api/types'
import { formatBytes, formatDateTime, formatDuration, formatPercent } from '../utils/format'
import { JobStatusBadge } from './JobStatusBadge'

export function OptimizeHistoryList({
  entries,
  folders,
  hasMore,
  onLoadMore,
}: {
  entries: OptimizeHistoryEntry[]
  folders: Folder[]
  hasMore: boolean
  onLoadMore: () => void
}) {
  const folderLabel = (id: string) => folders.find((f) => f.id === id)?.label ?? id

  return (
    <>
      <ol className="queue-list">
        {entries.map((entry) => (
          <li key={entry.id} className="queue-item">
            <div className="queue-info">
              <span className="queue-filename">{entry.file_path?.split('/').pop()}</span>
              <span className="card-sub">
                {folderLabel(entry.folder_id)} · {formatDateTime(entry.finished_at)}
                {entry.duration_s !== null ? ` · ${formatDuration(entry.duration_s)}` : ''}
              </span>
            </div>
            {entry.status === 'succeeded' && entry.size_before !== null && entry.size_after !== null ? (
              <span className="card-sub">
                {formatBytes(entry.size_before)} → {formatBytes(entry.size_after)} (
                {formatPercent(entry.savings_pct ?? 0)})
              </span>
            ) : null}
            <JobStatusBadge status={entry.status} />
          </li>
        ))}
      </ol>
      {hasMore && <button onClick={onLoadMore}>Carregar mais</button>}
    </>
  )
}
