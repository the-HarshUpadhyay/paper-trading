import { useState } from 'react'
import { X, TrendingUp, TrendingDown, Loader2 } from 'lucide-react'
import { tradingAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'

/**
 * OrderForm — modal for buying/selling a stock.
 * Props:
 *   ticker       string
 *   price        number  (current market price)
 *   onClose      fn()
 *   onSuccess    fn(result)
 */
export default function OrderForm({ ticker, price, onClose, onSuccess }) {
  const { refreshUser } = useAuth()
  const [tab, setTab]         = useState('buy')   // 'buy' | 'sell'
  const [quantity, setQty]    = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  const qty   = parseFloat(quantity) || 0
  const total = qty * (price || 0)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (qty <= 0) { setError('Quantity must be positive'); return }
    if (!price)   { setError('Price unavailable — try again'); return }

    setLoading(true)
    setError(null)
    try {
      const fn   = tab === 'buy' ? tradingAPI.buy : tradingAPI.sell
      const { data } = await fn(ticker, qty, price)
      await refreshUser()
      onSuccess?.(data)
      onClose?.()
    } catch (err) {
      setError(err.response?.data?.error || 'Order failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className="modal-card order-form">
        {/* Header */}
        <div className="modal-header">
          <span className="modal-ticker">{ticker}</span>
          <span className="modal-price">${price?.toFixed(2) ?? '—'}</span>
          <button className="modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="order-tabs">
          <button
            className={`order-tab buy${tab === 'buy' ? ' active' : ''}`}
            onClick={() => { setTab('buy'); setError(null) }}
          >
            <TrendingUp size={15} /> Buy
          </button>
          <button
            className={`order-tab sell${tab === 'sell' ? ' active' : ''}`}
            onClick={() => { setTab('sell'); setError(null) }}
          >
            <TrendingDown size={15} /> Sell
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="order-body">
          <label className="form-label">
            Quantity
            <input
              type="number"
              className="form-input"
              min="0.0001"
              step="0.0001"
              value={quantity}
              onChange={(e) => setQty(e.target.value)}
              placeholder="0"
              autoFocus
            />
          </label>

          <div className="order-summary">
            <span className="summary-label">Price per share</span>
            <span className="summary-value">${price?.toFixed(2) ?? '—'}</span>
          </div>
          <div className="order-summary total">
            <span className="summary-label">Estimated total</span>
            <span className="summary-value">
              {qty > 0 ? `$${total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
            </span>
          </div>

          {error && <p className="form-error">{error}</p>}

          <button
            type="submit"
            className={`order-submit ${tab}`}
            disabled={loading || qty <= 0}
          >
            {loading
              ? <Loader2 size={16} className="spin" />
              : `${tab === 'buy' ? 'Buy' : 'Sell'} ${ticker}`
            }
          </button>
        </form>
      </div>
    </div>
  )
}
