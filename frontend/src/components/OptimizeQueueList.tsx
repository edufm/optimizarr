import type { Folder, Job } from '../api/types'
import { JobStatusBadge } from './JobStatusBadge'
import { ProgressBar } from './ProgressBar'

export function OptimizeQueueList({
  jobs,
  folders,
  onCancel,
}: {
  jobs: Job[]
  folders: Folder[]
  onCancel: (jobId: string) => void
}) {
  const folderLabel = (id: string) => folders.find((f) => f.id === id)?.label ?? id

  return (
    <ol className="queue-list">
      {jobs.map((job, i) => (
        <li key={job.id} className="queue-item">
          <span className="queue-position">{i + 1}</span>
          <div className="queue-info">
            <span className="queue-filename">{job.file_path?.split('/').pop()}</span>
            <span className="card-sub">{folderLabel(job.folder_id)}</span>
          </div>
          {job.status === 'running' && job.progress_pct !== null ? (
            <ProgressBar pct={job.progress_pct} />
          ) : (
            <>
              <JobStatusBadge status={job.status} />
              {job.status === 'queued' && (
                <button onClick={() => onCancel(job.id)}>Cancelar</button>
              )}
            </>
          )}
        </li>
      ))}
    </ol>
  )
}
