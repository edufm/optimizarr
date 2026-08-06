import type {
  Calibration,
  Dashboard,
  Folder,
  FolderFiles,
  Job,
  JobCreated,
  Settings,
} from './types'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail ?? `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  listFolders: () => request<{ folders: Folder[] }>('/folders'),
  addFolder: (path: string) =>
    request<Folder>('/folders', { method: 'POST', body: JSON.stringify({ path }) }),
  removeFolder: (id: string) => request<void>(`/folders/${id}`, { method: 'DELETE' }),

  getSettings: () => request<Settings>('/settings'),
  updateSettings: (settings: Settings) =>
    request<Settings>('/settings', { method: 'PUT', body: JSON.stringify(settings) }),

  getDashboard: () => request<Dashboard>('/dashboard'),

  getFolderFiles: (id: string) => request<FolderFiles>(`/folders/${id}/files`),
  analyzeFolder: (id: string) =>
    request<JobCreated>(`/folders/${id}/analyze`, { method: 'POST' }),
  optimizeFile: (id: string, path: string) =>
    request<JobCreated>(`/folders/${id}/files/optimize`, {
      method: 'POST',
      body: JSON.stringify({ path }),
    }),

  getCalibration: () => request<Calibration | null>('/calibration'),
  runSampleTest: (inputPath: string, outputDir: string) =>
    request<JobCreated>('/sample/test', {
      method: 'POST',
      body: JSON.stringify({ input_path: inputPath, output_dir: outputDir }),
    }),

  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  listJobs: (params: { folderId?: string; active?: boolean } = {}) => {
    const qs = new URLSearchParams()
    if (params.folderId) qs.set('folder_id', params.folderId)
    if (params.active !== undefined) qs.set('active', String(params.active))
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<{ jobs: Job[] }>(`/jobs${suffix}`)
  },
}

export { ApiError }
