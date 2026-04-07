import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Star, Trash2, TrendingUp, TrendingDown,
  RefreshCw, ShoppingCart, Plus,
} from 'lucide-react'
import Header from '../components/Header'
import OrderForm from '../components/OrderForm'
import { SkeletonTable } from '../components/LoadingSkeleton'
import { watchlistAPI, stocksAPI } from '../services/api'

export default function Watchlist() {
  const navigate = useNavigate()

  const [items, setItems]         = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [removing, setRemoving]   = useState(null)
  const [orderTarget, setOrderTarget] = useState(null)  // { ticker, price }
  const [addTicker, setAddTicker] = useState('')
  const [addError, setAddError]   = useState(null)
  const [adding, setAdding]       = useState(false)

  const fetchWatchlist = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await watchlistAPI.get()
      setItems(data.watchlist || [])
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to load watchlist')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchWatchlist() }, [fetchWatchlist])

  const handleRemove = async (ticker) => {
    setRemoving(ticker)
    try {
      await watchlistAPI.remove(ticker)
      setItems((prev) => prev.filter((i) => i.ticker !== ticker))
    } catch (_) {}
    finally { setRemoving(null) }
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    const t = addTicker.trim().toUpperCase()
    if (!t) return
    setAdding(true)
    setAddError(null)
    try {
      await watchlistAPI.add(t)
      setAddTicker('')
      await fetchWatchlist()
    } catch (err) {
      setAddError(err.response?.data?.error || `Failed to add ${t}`)
    } finally {
      setAdding(false)
    }
  }

  const handleOrderSuccess = () => {
    setOrderTarget(null)
    fetchWatchlist()
  }

  const openOrder = async (ticker) => {
    try {
      const { data } = await stocksAPI.quote(ticker)
      setOrderTarget({ ticker, price: data.price })
    } catch (_) {
      setOrderTarget({ ticker, price: null })
    }
  }

  const fmt = (n) =>
    n != null
      ? `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
      : '—'

  return (
    <div className="page-layout">
      <Header title="Watchlist" />

      <main className="page-content">
        {/* Add ticker */}
        <section className="card">
          <h2 className="card-title">Add to Watchlist</h2>
          <form className="add-ticker-form" onSubmit={handleAdd}>
            <input
              type="text"
              className="form-input"
              placeholder="Enter ticker (e.g. AAPL)"
              value={addTicker}
              onChange={(e) => setAddTicker(e.target.value)}
              maxLength={10}
            />
            <button type="submit" className="btn btn-primary" disabled={adding}>
              <Plus size={15} /> Add
            </button>
          </form>
          {addError && <p className="form-error" style={{ marginTop: '0.5rem' }}>{addError}</p>}
        </section>

        {/* Watchlist table */}
        <section className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">
                <Star size={16} style={{ marginRight: 6 }} />
                My Watchlist
              </h2>
              <p className="card-sub">{items.length} stocks</p>
            </div>
            <button className="icon-btn" onClick={fetchWatchlist} title="Refresh">
              <RefreshCw size={15} />
            </button>
          </div>

          {error && <div className="error-banner">{error}</div>}

          {loading ? (
            <SkeletonTable rows={6} cols={5} />
          ) : !items.length ? (
            <div className="empty-state">
              <Star size={40} opacity={0.3} />
              <p>Your watchlist is empty. Add tickers above to track stocks.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Stock</th>
                    <th>Sector</th>
                    <th>Price</th>
                    <th>Change</th>
                    <th>Added</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.ticker}>
                      <td>
                        <div
                          className="stock-cell clickable"
                          onClick={() => navigate(`/stocks/${item.ticker}`)}
                        >
                          <span className="ticker-badge">{item.ticker}</span>
                          <span className="company-name">{item.company_name}</span>
                        </div>
                      </td>
                      <td className="text-muted">{item.sector || '—'}</td>
                      <td className="fw-medium">{fmt(item.price)}</td>
                      <td>
                        {item.change_pct != null ? (
                          <span className={`change-badge ${item.change_pct >= 0 ? 'pos' : 'neg'}`}>
                            {item.change_pct >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                            {item.change_pct >= 0 ? '+' : ''}{item.change_pct.toFixed(2)}%
                          </span>
                        ) : '—'}
                      </td>
                      <td className="text-muted">
                        {item.added_at ? new Date(item.added_at).toLocaleDateString() : '—'}
                      </td>
                      <td>
                        <div className="action-btns">
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={() => openOrder(item.ticker)}
                            title="Trade"
                          >
                            <ShoppingCart size={13} />
                          </button>
                          <button
                            className="btn btn-sm btn-ghost btn-danger"
                            onClick={() => handleRemove(item.ticker)}
                            disabled={removing === item.ticker}
                            title="Remove from watchlist"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Order modal */}
        {orderTarget && (
          <OrderForm
            ticker={orderTarget.ticker}
            price={orderTarget.price}
            onClose={() => setOrderTarget(null)}
            onSuccess={handleOrderSuccess}
          />
        )}
      </main>
    </div>
  )
}
