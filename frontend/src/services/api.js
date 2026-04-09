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
  indexQuote: (ticker) => api.get(`/stocks/index/${ticker}`),
}

export const currencyAPI = {
  rates: () => api.get('/currency/rates'),
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
  add: (ticker, folder_id = null) => api.post('/watchlist', { ticker, folder_id }),
  remove: (ticker) => api.delete(`/watchlist/${ticker}`),       // full unwatch (all lists)
  removeItem: (watchlist_id) => api.delete(`/watchlist/item/${watchlist_id}`),  // single-list
  createFolder: (name) => api.post('/watchlist/folders', { name }),
  renameFolder: (id, name) => api.patch(`/watchlist/folders/${id}`, { name }),
  deleteFolder: (id) => api.delete(`/watchlist/folders/${id}`),
  moveItem: (watchlist_id, folder_id) =>
    api.patch(`/watchlist/${watchlist_id}/folder`, { folder_id }),
}

// ── Notes ────────────────────────────────────────────────────────────────────
export const notesAPI = {
  list: (ticker) => api.get('/notes', { params: ticker ? { ticker } : {} }),
  get: (id) => api.get(`/notes/${id}`),
  create: (title, body, ticker) => api.post('/notes', { title, body, ticker }),
  update: (id, title, body) => api.put(`/notes/${id}`, { title, body }),
  delete: (id) => api.delete(`/notes/${id}`),
}

// ── Pending Orders ───────────────────────────────────────────────────────────
export const pendingOrdersAPI = {
  list: (status = 'OPEN') => api.get('/orders/pending', { params: { status } }),
  place: (data) => api.post('/orders/pending', data),
  cancel: (id) => api.delete(`/orders/pending/${id}`),
}

// ── Alerts & Notifications ───────────────────────────────────────────────────
export const alertsAPI = {
  list: () => api.get('/alerts'),
  create: (ticker, condition, target_price) =>
    api.post('/alerts', { ticker, condition, target_price }),
  delete: (id) => api.delete(`/alerts/${id}`),
  notifications: (unread_only = true) =>
    api.get('/notifications', { params: { unread_only } }),
  markRead: (ids) => api.post('/notifications/read', { ids }),
}

export default api
