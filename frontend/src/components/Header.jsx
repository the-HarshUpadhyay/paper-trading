import { Sun, Moon } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import StockSearch from './StockSearch'

export default function Header({ title }) {
  const { theme, toggleTheme } = useTheme()

  return (
    <header className="topbar">
      <div className="topbar-left">
        {title && <h1 className="page-title">{title}</h1>}
      </div>

      <div className="topbar-center">
        <StockSearch />
      </div>

      <div className="topbar-right">
        <button
          className="icon-btn"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </div>
    </header>
  )
}
