import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import Sidebar from './components/Sidebar'

// Pages
import Login     from './pages/Login'
import Register  from './pages/Register'
import Dashboard from './pages/Dashboard'
import StockDetail from './pages/StockDetail'
import Orders    from './pages/Orders'
import Watchlist from './pages/Watchlist'

/** Wraps authenticated routes — redirects to /login if not logged in */
function ProtectedLayout() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="splash">
        <div className="splash-spinner" />
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-area">
        <Outlet />
      </div>
    </div>
  )
}

/** Wraps public routes — redirects to /dashboard if already logged in */
function PublicLayout() {
  const { user, loading } = useAuth()
  if (loading) return null
  if (user) return <Navigate to="/dashboard" replace />
  return <Outlet />
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route element={<PublicLayout />}>
              <Route path="/login"    element={<Login />} />
              <Route path="/register" element={<Register />} />
            </Route>

            {/* Protected */}
            <Route element={<ProtectedLayout />}>
              <Route path="/dashboard"      element={<Dashboard />} />
              <Route path="/stocks/:ticker" element={<StockDetail />} />
              <Route path="/orders"         element={<Orders />} />
              <Route path="/watchlist"      element={<Watchlist />} />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
