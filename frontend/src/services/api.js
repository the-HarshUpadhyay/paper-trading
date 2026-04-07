/**
 * api.js — Axios instance with JWT interceptor and all API calls.
 */
import axios from 'axios'

const BASE_URL = '/api'

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor: attach JWT ──────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: handle 401 globally ───────────────────────────────
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth ─────────────────────────────────────────────────────────────────────
export const authAPI = {
  register: (username, email, password) =>
    api.post('/register', { username, email, password }),
  login: (username, password) =>
    api.post('/login', { username, password }),
  me: () => api.get('/me'),
  logout: () => api.post('/logout'),
}

// ── Stocks ───────────────────────────────────────────────────────────────────
export const stocksAPI = {
  search: (q) => api.get('/stocks/search', { params: { q } }),
  quote: (ticker) => api.get(`/stocks/${ticker}`),
  history: (ticker, period = '1mo', interval = '1d') =>
    api.get(`/stocks/${ticker}/history`, { params: { period, interval } }),
}

// ── Trading ──────────────────────────────────────────────────────────────────
export const tradingAPI = {
  buy: (ticker, quantity, price) =>
    api.post('/buy', { ticker, quantity, price }),
  sell: (ticker, quantity, price) =>
    api.post('/sell', { ticker, quantity, price }),
  orders: (page = 1, per_page = 20) =>
    api.get('/orders', { params: { page, per_page } }),
}

// ── Portfolio ────────────────────────────────────────────────────────────────
export const portfolioAPI = {
  get: () => api.get('/portfolio'),
  snapshots: (days = 30) =>
    api.get('/portfolio/snapshots', { params: { days } }),
}

// ── Watchlist ────────────────────────────────────────────────────────────────
export const watchlistAPI = {
  get: () => api.get('/watchlist'),
  add: (ticker) => api.post('/watchlist', { ticker }),
  remove: (ticker) => api.delete(`/watchlist/${ticker}`),
}

export default api
