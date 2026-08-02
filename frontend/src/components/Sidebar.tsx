import { NavLink } from 'react-router-dom'
import { useFolders } from '../hooks/useFolders'

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? 'sidebar-link active' : 'sidebar-link'
}

export function Sidebar() {
  const { folders } = useFolders()

  return (
    <nav className="sidebar">
      <div className="sidebar-brand">optimizarr</div>
      <NavLink to="/" end className={navClass}>
        Dashboard
      </NavLink>
      <NavLink to="/settings" className={navClass}>
        Configurações
      </NavLink>
      {folders.length > 0 && (
        <div className="sidebar-section">
          <span className="sidebar-section-label">Pastas</span>
          {folders.map((f) => (
            <NavLink key={f.id} to={`/folders/${f.id}`} className={navClass}>
              {f.label}
            </NavLink>
          ))}
        </div>
      )}
    </nav>
  )
}
