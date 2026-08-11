import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useFolders } from '../hooks/useFolders'
import { useFolderFiles } from '../hooks/useFolderFiles'
import { useJobsPolling } from '../hooks/useJobsPolling'
import { SortableTable, type Column } from '../components/SortableTable'
import { JobStatusBadge } from '../components/JobStatusBadge'
import { formatBytes, formatDateTime, formatPercent } from '../utils/format'
import type { FileRow } from '../api/types'

export function FolderPage() {
  const { folderId } = useParams<{ folderId: string }>()
  const { folders } = useFolders()
  const { data, loading, error, refetch } = useFolderFiles(folderId!)

  const [trackedJobIds, setTrackedJobIds] = useState<string[]>([])
  const [optimizedPaths, setOptimizedPaths] = useState<Set<string>>(new Set())
  const [actionError, setActionError] = useState<string | null>(null)
  const jobs = useJobsPolling(trackedJobIds)

  const folder = folders.find((f) => f.id === folderId)

  // reconecta jobs em andamento após reload de página (jobs só vivem na memória do backend)
  useEffect(() => {
    if (!folderId) return
    api.listJobs({ folderId, active: true }).then(({ jobs }) => {
      if (jobs.length > 0) {
        setTrackedJobIds((prev) => Array.from(new Set([...prev, ...jobs.map((j) => j.id)])))
      }
    })
  }, [folderId])

  const trackedJobs = trackedJobIds.map((id) => jobs[id]).filter((j) => j !== undefined)
  const analyzeJob = trackedJobs.find((j) => j.type === 'analyze' && (j.status === 'running' || j.status === 'queued'))
  const activeOptimizeJobs = trackedJobs.filter(
    (j) => j.type === 'optimize' && (j.status === 'running' || j.status === 'queued'),
  )
  // a pasta não aceita Atualizar enquanto está sendo analisada OU tem otimização pendente
  // (mesma regra do backend) — mas "Otimizar" continua liberado linha a linha.
  const analyzeBlocked = Boolean(analyzeJob) || activeOptimizeJobs.length > 0

  useEffect(() => {
    for (const job of trackedJobs) {
      if (job.status === 'succeeded' && job.type === 'analyze') refetch()
      if (job.status === 'succeeded' && job.type === 'optimize' && job.file_path) {
        setOptimizedPaths((prev) => new Set(prev).add(job.file_path!))
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs])

  async function handleAnalyze() {
    if (!folderId) return
    setActionError(null)
    try {
      const { job_id } = await api.analyzeFolder(folderId)
      setTrackedJobIds((prev) => [...prev, job_id])
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'erro ao atualizar pasta')
    }
  }

  async function handleOptimize(row: FileRow) {
    if (!folderId) return
    if (!confirm(`Otimizar "${row.filename}"? Isso substitui o arquivo original depois de validar o resultado.`)) return
    setActionError(null)
    try {
      const { job_id } = await api.optimizeFile(folderId, row.path)
      setTrackedJobIds((prev) => [...prev, job_id])
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'erro ao otimizar arquivo')
    }
  }

  const columns: Column<FileRow>[] = useMemo(
    () => [
      { key: 'filename', label: 'Arquivo' },
      { key: 'codec', label: 'Codec' },
      { key: 'width', label: 'Largura', align: 'right' },
      { key: 'height', label: 'Altura', align: 'right' },
      { key: 'fps', label: 'FPS', align: 'right', format: (v) => (v as number).toFixed(2) },
      { key: 'duration', label: 'Duração (s)', align: 'right', format: (v) => (v as number).toFixed(0) },
      { key: 'size', label: 'Tamanho', align: 'right', format: (v) => formatBytes(v as number) },
      { key: 'bpp', label: 'BPP', align: 'right', format: (v) => (v as number).toFixed(3) },
      { key: 'gb_per_hour', label: 'GB/h', align: 'right', format: (v) => (v as number).toFixed(2) },
      { key: 'savings', label: 'Ganho', align: 'right', format: (v) => formatPercent(v as number) },
      { key: 'savings_gb', label: 'Ganho GB', align: 'right', format: (v) => (v as number).toFixed(2) },
      { key: 'profile', label: 'Profile' },
      { key: 'pix_fmt', label: 'Pix fmt' },
      { key: 'color_space', label: 'Color space' },
      { key: 'color_transfer', label: 'Color transfer' },
      { key: 'color_primaries', label: 'Color primaries' },
      { key: 'field_order', label: 'Field order' },
    ],
    [],
  )

  if (loading) return <p className="hint">Carregando…</p>
  if (error) return <p className="error">Erro: {error}</p>
  if (!data) return null

  const runningCount = activeOptimizeJobs.filter((j) => j.status === 'running').length
  const queuedCount = activeOptimizeJobs.filter((j) => j.status === 'queued').length

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>{folder?.label ?? folderId}</h1>
          <p className="card-sub">{folder?.path}</p>
          <p className="hint">
            Última análise: {formatDateTime(data.generated_at)} · {data.rows.length} arquivo(s)
          </p>
        </div>
        <button onClick={handleAnalyze} disabled={analyzeBlocked}>
          {analyzeJob ? 'Analisando…' : 'Atualizar'}
        </button>
      </div>

      {analyzeJob && (
        <div className="job-banner">
          <JobStatusBadge status={analyzeJob.status} />
          <span>Reanalisando pasta…</span>
        </div>
      )}
      {activeOptimizeJobs.length > 0 && (
        <div className="job-banner">
          <span>
            Otimizando: {runningCount} rodando · {queuedCount} na fila
          </span>
        </div>
      )}
      {actionError && <p className="error">{actionError}</p>}

      {data.rows.length === 0 ? (
        <p className="hint">Ainda não foi analisada. Clique em Atualizar.</p>
      ) : (
        <SortableTable
          columns={columns}
          rows={data.rows}
          rowKey={(row) => row.path}
          renderActions={(row) => {
            if (optimizedPaths.has(row.path)) {
              return <span className="badge badge-optimized">Otimizado — clique Atualizar</span>
            }
            const rowJob = trackedJobs.find(
              (j) => j.type === 'optimize' && j.file_path === row.path && (j.status === 'running' || j.status === 'queued'),
            )
            if (rowJob) {
              return <JobStatusBadge status={rowJob.status} />
            }
            return (
              <button onClick={() => handleOptimize(row)} disabled={Boolean(analyzeJob)}>
                Otimizar
              </button>
            )
          }}
        />
      )}
    </div>
  )
}
