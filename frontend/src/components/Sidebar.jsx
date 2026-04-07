import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, Star, ClipboardList,
  LogOut, Activity,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const NAV = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard'  },
  { to: '/watchlist',  icon: Star,             label: 'Watchlist'  },
  { to: '/orders',     icon: ClipboardList,    label: 'Orders'     },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <Activity size={22} strokeWidth={2.5} className="brand-icon" />
        <span className="brand-name">PaperTrade</span>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `sidebar-link${isActive ? ' active' : ''}`
            }
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        {user && (
          <div className="sidebar-user">
            <div className="user-avatar">
              {user.username?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="user-info">
              <span className="user-name">{user.username}</span>
              <span className="user-balance">
                ${user.balance?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        )}
        <button className="sidebar-logout" onClick={handleLogout} title="Logout">
          <LogOut size={17} />
        </button>
      </div>
    </aside>
  )
}
