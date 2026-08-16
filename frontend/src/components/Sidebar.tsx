import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useFolders } from '../hooks/useFolders'

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? 'sidebar-link active' : 'sidebar-link'
}

export function Sidebar() {
  const { folders } = useFolders()
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)

  return (
    <>
      <button
        type="button"
        className="sidebar-toggle"
        aria-label={open ? 'Fechar menu' : 'Abrir menu'}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="sidebar-toggle-bar" />
        <span className="sidebar-toggle-bar" />
        <span className="sidebar-toggle-bar" />
      </button>

      {open && <div className="sidebar-overlay" onClick={close} />}

      <nav className={open ? 'sidebar open' : 'sidebar'}>
        <div className="sidebar-brand">optimizarr</div>
        <NavLink to="/" end className={navClass} onClick={close}>
          Dashboard
        </NavLink>
        <NavLink to="/settings" className={navClass} onClick={close}>
          Configurações
        </NavLink>
        {folders.length > 0 && (
          <div className="sidebar-section">
            <span className="sidebar-section-label">Pastas</span>
            {folders.map((f) => (
              <NavLink key={f.id} to={`/folders/${f.id}`} className={navClass} onClick={close}>
                {f.label}
              </NavLink>
            ))}
          </div>
        )}
      </nav>
    </>
  )
}
