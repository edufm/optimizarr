export interface CsvInfo {
  exists: boolean
  generated_at: string | null
  row_count: number | null
}

export interface Folder {
  id: string
  path: string
  label: string
  csv: CsvInfo
}

export type Encoder = 'cpu' | 'nvenc'

export interface Settings {
  resolution: number
  fps: number
  encoder: Encoder
  quality: number
}

export interface Calibration {
  target_bpp: number
  speed_factor: number
  measured_at: string
  encoder: Encoder
  quality: number
  resolution: number
  fps: number
  sample_input: string
  sample_output: string
}

export interface DiskUsage {
  mount: string
  total_bytes: number
  used_bytes: number
  free_bytes: number
  folder_ids: string[]
}

export interface FolderSummary {
  id: string
  path: string
  label: string
  has_csv: boolean
  generated_at: string | null
  file_count: number | null
  current_size_bytes: number | null
  estimated_size_bytes: number | null
  savings_pct: number | null
}

export interface Dashboard {
  disks: DiskUsage[]
  folders: FolderSummary[]
}

export interface FileRow {
  path: string
  filename: string
  codec: string
  width: number
  height: number
  fps: number
  duration: number
  size: number
  bpp: number
  est_size: number
  savings: number
  savings_gb: number
  gb_per_hour: number
  profile: string
  pix_fmt: string
  color_space: string
  color_transfer: string
  color_primaries: string
  field_order: string
}

export interface FolderFiles {
  folder_id: string
  generated_at: string | null
  rows: FileRow[]
}

export type JobType = 'analyze' | 'optimize' | 'sample'
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface Job {
  id: string
  type: JobType
  folder_id: string
  file_path: string | null
  status: JobStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  returncode: number | null
  progress_pct: number | null
  log_tail: string[]
}

export interface JobCreated {
  job_id: string
  status: JobStatus
}
