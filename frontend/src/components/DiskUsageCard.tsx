import type { DiskUsage } from '../api/types'
import { formatBytes } from '../utils/format'

export function DiskUsageCard({ disk }: { disk: DiskUsage }) {
  const usedPct = disk.total_bytes > 0 ? (disk.used_bytes / disk.total_bytes) * 100 : 0

  return (
    <div className="card">
      <div className="card-title">{disk.mount}</div>
      <div className="meter">
        <div className="meter-fill" style={{ width: `${usedPct.toFixed(1)}%` }} />
      </div>
      <div className="card-sub">
        {formatBytes(disk.used_bytes)} usados de {formatBytes(disk.total_bytes)} ({formatBytes(disk.free_bytes)}{' '}
        livres)
      </div>
    </div>
  )
}
