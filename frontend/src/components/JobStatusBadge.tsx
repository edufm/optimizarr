import type { JobStatus } from '../api/types'

const LABELS: Record<JobStatus, string> = {
  queued: 'Na fila',
  running: 'Rodando',
  succeeded: 'Concluído',
  failed: 'Falhou',
  cancelled: 'Cancelado',
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <span className={`badge badge-${status}`}>{LABELS[status]}</span>
}
