import { useEffect, useState, type FormEvent } from 'react'
import { useFolders } from '../hooks/useFolders'
import { api, ApiError } from '../api/client'
import type { Settings } from '../api/types'

export function SettingsPage() {
  const { folders, loading, error, refetch } = useFolders()
  const [newPath, setNewPath] = useState('')
  const [addError, setAddError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  const [settings, setSettings] = useState<Settings | null>(null)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [settingsSaved, setSettingsSaved] = useState(false)

  useEffect(() => {
    api.getSettings().then(setSettings)
  }, [])

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
              CRF (libx265)
              <input
                type="number"
                value={settings.crf}
                onChange={(e) => setSettings({ ...settings, crf: Number(e.target.value) })}
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
    </div>
  )
}
