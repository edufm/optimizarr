import { useEffect, useState, type FormEvent } from 'react'
import { useFolders } from '../hooks/useFolders'
import { useJobsPolling } from '../hooks/useJobsPolling'
import { api, ApiError } from '../api/client'
import { JobStatusBadge } from '../components/JobStatusBadge'
import { formatDateTime } from '../utils/format'
import type { Calibration, Settings } from '../api/types'

export function SettingsPage() {
  const { folders, loading, error, refetch } = useFolders()
  const [newPath, setNewPath] = useState('')
  const [addError, setAddError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  const [settings, setSettings] = useState<Settings | null>(null)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [settingsSaved, setSettingsSaved] = useState(false)

  const [calibration, setCalibration] = useState<Calibration | null>(null)
  const [inputPath, setInputPath] = useState('')
  const [outputDir, setOutputDir] = useState('')
  const [sampleError, setSampleError] = useState<string | null>(null)
  const [sampleJobId, setSampleJobId] = useState<string | null>(null)
  const jobs = useJobsPolling(sampleJobId ? [sampleJobId] : [])
  const sampleJob = sampleJobId ? jobs[sampleJobId] : undefined

  useEffect(() => {
    api.getSettings().then(setSettings)
    api.getCalibration().then(setCalibration)
  }, [])

  useEffect(() => {
    if (sampleJob?.status === 'succeeded') {
      api.getCalibration().then(setCalibration)
      setSampleJobId(null)
    } else if (sampleJob?.status === 'failed') {
      setSampleError('Teste falhou — veja o log do job pra detalhes.')
      setSampleJobId(null)
    }
  }, [sampleJob])

  async function handleAddFolder(e: FormEvent) {
    e.preventDefault()
    setAddError(null)
    setAdding(true)
    try {
      await api.addFolder(newPath)
      setNewPath('')
      await refetch()
    } catch (err) {
      setAddError(err instanceof ApiError ? err.message : 'erro ao adicionar pasta')
    } finally {
      setAdding(false)
    }
  }

  async function handleRemove(id: string) {
    if (!confirm('Remover esta pasta? O CSV analisado dela também será apagado.')) return
    await api.removeFolder(id)
    await refetch()
  }

  async function handleSaveSettings(e: FormEvent) {
    e.preventDefault()
    if (!settings) return
    setSettingsSaving(true)
    setSettingsSaved(false)
    try {
      setSettings(await api.updateSettings(settings))
      setSettingsSaved(true)
    } finally {
      setSettingsSaving(false)
    }
  }

  async function handleRunSample(e: FormEvent) {
    e.preventDefault()
    setSampleError(null)
    try {
      const { job_id } = await api.runSampleTest(inputPath, outputDir)
      setSampleJobId(job_id)
    } catch (err) {
      setSampleError(err instanceof ApiError ? err.message : 'erro ao iniciar teste')
    }
  }

  const qualityLabel = settings?.encoder === 'nvenc' ? 'CQ (NVENC)' : 'CRF (libx265)'
  const testing = sampleJob ? sampleJob.status === 'running' || sampleJob.status === 'queued' : false
  const calibrationStale =
    calibration &&
    settings &&
    (calibration.encoder !== settings.encoder ||
      calibration.quality !== settings.quality ||
      calibration.resolution !== settings.resolution ||
      calibration.fps !== settings.fps)

  return (
    <div className="page">
      <h1>Configurações</h1>

      <section>
        <h2>Pastas monitoradas</h2>
        {loading && <p className="hint">Carregando…</p>}
        {error && <p className="error">Erro: {error}</p>}
        {folders.length > 0 && (
          <ul className="folder-list">
            {folders.map((f) => (
              <li key={f.id}>
                <span className="folder-path">{f.path}</span>
                <button onClick={() => handleRemove(f.id)}>Remover</button>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={handleAddFolder} className="inline-form">
          <input
            type="text"
            placeholder="/caminho/absoluto/da/pasta"
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
            required
          />
          <button type="submit" disabled={adding}>
            Adicionar
          </button>
        </form>
        {addError && <p className="error">{addError}</p>}
      </section>

      <section>
        <h2>Encode padrão</h2>
        <p className="hint">Usado quando um arquivo é otimizado a partir da tabela de uma pasta.</p>
        {settings && (
          <form onSubmit={handleSaveSettings} className="settings-form">
            <label>
              Encoder
              <select
                value={settings.encoder}
                onChange={(e) => setSettings({ ...settings, encoder: e.target.value as Settings['encoder'] })}
              >
                <option value="cpu">CPU (libx265)</option>
                <option value="nvenc">NVENC (GPU)</option>
              </select>
            </label>
            <label>
              Resolução (lado curto, px)
              <input
                type="number"
                value={settings.resolution}
                onChange={(e) => setSettings({ ...settings, resolution: Number(e.target.value) })}
                min={1}
              />
            </label>
            <label>
              FPS alvo
              <input
                type="number"
                value={settings.fps}
                onChange={(e) => setSettings({ ...settings, fps: Number(e.target.value) })}
                min={1}
              />
            </label>
            <label>
              {qualityLabel}
              <input
                type="number"
                value={settings.quality}
                onChange={(e) => setSettings({ ...settings, quality: Number(e.target.value) })}
                min={0}
                max={51}
              />
            </label>
            <button type="submit" disabled={settingsSaving}>
              Salvar
            </button>
            {settingsSaved && <span className="saved-hint">Salvo.</span>}
          </form>
        )}
      </section>

      <section>
        <h2>Teste de encoder</h2>
        <p className="hint">
          Extrai os primeiros 60s do vídeo escolhido e reencoda o trecho com as configs de "Encode
          padrão" acima. O resultado medido (tamanho e velocidade reais) passa a calibrar a estimativa
          de ganho mostrada nas pastas.
        </p>

        {calibration ? (
          <p className={calibrationStale ? 'hint' : 'saved-hint'}>
            Última calibração: bpp {calibration.target_bpp.toFixed(4)}, {calibration.speed_factor.toFixed(1)}x
            tempo real — medido com {calibration.encoder === 'nvenc' ? 'NVENC' : 'CPU'}{' '}
            {calibration.quality} {calibration.resolution}p {calibration.fps}fps em{' '}
            {formatDateTime(calibration.measured_at)}.
            {calibrationStale && ' As configs de encode padrão mudaram desde então — considere retestar.'}
          </p>
        ) : (
          <p className="hint">Ainda não calibrado — usando estimativa genérica (bpp 0.060).</p>
        )}

        <form onSubmit={handleRunSample} className="inline-form" style={{ flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="/caminho/do/video/de/entrada.mkv"
            value={inputPath}
            onChange={(e) => setInputPath(e.target.value)}
            required
          />
          <input
            type="text"
            placeholder="/caminho/da/pasta/de/saida"
            value={outputDir}
            onChange={(e) => setOutputDir(e.target.value)}
            required
          />
          <button type="submit" disabled={testing}>
            {testing ? 'Testando…' : 'Testar'}
          </button>
        </form>
        {sampleJob && (
          <div className="job-banner">
            <JobStatusBadge status={sampleJob.status} />
            <span>Rodando teste de encoder…</span>
          </div>
        )}
        {sampleError && <p className="error">{sampleError}</p>}
      </section>
    </div>
  )
}
