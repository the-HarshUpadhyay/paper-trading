import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authAPI } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(() => {
    try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
  })
  const [token, setToken]     = useState(() => localStorage.getItem('token'))
  const [loading, setLoading] = useState(true)

  // Verify token on mount
  useEffect(() => {
    if (token) {
      authAPI.me()
        .then(({ data }) => setUser(data))
        .catch(() => { logout() })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, []) // eslint-disable-line

  const login = useCallback(async (username, password) => {
    const { data } = await authAPI.login(username, password)
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify({
      user_id:  data.user_id,
      username: data.username,
      balance:  data.balance,
    }))
    setToken(data.token)
    setUser({ user_id: data.user_id, username: data.username, balance: data.balance })
    return data
  }, [])

  const register = useCallback(async (username, email, password) => {
    const { data } = await authAPI.register(username, email, password)
    return data
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setToken(null)
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    try {
      const { data } = await authAPI.me()
      setUser(data)
      localStorage.setItem('user', JSON.stringify(data))
    } catch (_) {}
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
