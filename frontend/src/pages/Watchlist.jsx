import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Star, Trash2, TrendingUp, TrendingDown,
  RefreshCw, ShoppingCart, Plus, X,
} from 'lucide-react'
import Header from '../components/Header'
import OrderForm from '../components/OrderForm'
import { SkeletonTable } from '../components/LoadingSkeleton'
import TickerInput from '../components/TickerInput'
import { watchlistAPI, stocksAPI } from '../services/api'
import { useRegion, tickerCurrency } from '../context/RegionContext'

export default function Watchlist() {
  const navigate = useNavigate()

  const [items, setItems]             = useState([])
  const [folders, setFolders]         = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)
  const [removing, setRemoving]       = useState(null)
  const [orderTarget, setOrderTarget] = useState(null)
  const [addTicker, setAddTicker]     = useState('')
  const [addError, setAddError]       = useState(null)
  const [adding, setAdding]           = useState(false)
  const [toast, setToast]             = useState(null)

  // Tab state — null = "Watchlist" (uncategorised)
  const [activeTab, setActiveTab]         = useState(null)
  const [renamingTab, setRenamingTab]     = useState(null)
  const [renameVal, setRenameVal]         = useState('')
  const [showNewTab, setShowNewTab]       = useState(false)
  const [newTabName, setNewTabName]       = useState('')
  const [creatingFolder, setCreatingFolder] = useState(false)
  const newTabInputRef = useRef(null)

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 2500) }

  const fetchWatchlist = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await watchlistAPI.get()
      setItems(data.watchlist || [])
      const newFolders = data.folders || []
      setFolders(newFolders)
      // If active tab was deleted, fall back to uncategorised
      setActiveTab((prev) => {
        if (prev === null) return null
        return newFolders.find((f) => f.folder_id === prev) ? prev : null
      })
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to load watchlist')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchWatchlist() }, [fetchWatchlist])

  useEffect(() => {
    if (showNewTab && newTabInputRef.current) newTabInputRef.current.focus()
  }, [showNewTab])

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
      if (activeTab !== null) {
        // Move the newly added item into the active folder
        const { data } = await watchlistAPI.get()
        const newItem = (data.watchlist || []).find(
          (i) => i.ticker === t && i.folder_id == null,
        )
        if (newItem) await watchlistAPI.moveItem(newItem.watchlist_id, activeTab)
        await fetchWatchlist()
      } else {
        await fetchWatchlist()
      }
    } catch (err) {
      setAddError(err.response?.data?.error || `Failed to add ${t}`)
    } finally {
      setAdding(false)
    }
  }

  const handleOrderSuccess = () => { setOrderTarget(null); fetchWatchlist() }

  const openOrder = async (ticker) => {
    try {
      const { data } = await stocksAPI.quote(ticker)
      setOrderTarget({ ticker, price: data.price })
    } catch (_) {
      setOrderTarget({ ticker, price: null })
    }
  }

  // ── Folder CRUD ───────────────────────────────────────────────────────────

  const handleCreateFolder = async () => {
    const name = newTabName.trim()
    setShowNewTab(false)
    setNewTabName('')
    if (!name || creatingFolder) return
    setCreatingFolder(true)
    try {
      const { data } = await watchlistAPI.createFolder(name)
      await fetchWatchlist()
      setActiveTab(data.folder_id)   // jump to the new tab
      showToast(`List "${name}" created`)
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to create list')
    } finally {
      setCreatingFolder(false)
    }
  }

  const handleRenameTab = async (folder_id) => {
    const name = renameVal.trim()
    setRenamingTab(null)
    if (!name) return
    try {
      await watchlistAPI.renameFolder(folder_id, name)
      await fetchWatchlist()
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to rename')
    }
  }

  const handleDeleteTab = async (folder_id, name, e) => {
    e.stopPropagation()
    if (!window.confirm(`Delete list "${name}"? Items will become Uncategorised.`)) return
    try {
      await watchlistAPI.deleteFolder(folder_id)
      if (activeTab === folder_id) setActiveTab(null)
      showToast('List deleted')
      await fetchWatchlist()
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to delete list')
    }
  }

  const handleMoveItem = async (watchlist_id, folder_id) => {
    try {
      await watchlistAPI.moveItem(watchlist_id, folder_id || null)
      await fetchWatchlist()
    } catch (_) {}
  }

  const { formatPrice } = useRegion()
  const fmtPrice = (n, ticker) => formatPrice(n, { from: tickerCurrency(ticker) })

  const tabs = [{ folder_id: null, name: 'Watchlist' }, ...folders]

  const activeItems = items.filter((i) =>
    activeTab === null ? i.folder_id == null : i.folder_id === activeTab,
  )

  const folderOptions = [
    { folder_id: null, name: 'Watchlist' },
    ...folders,
  ]

  return (
    <div className="page-layout">
      <Header title="Watchlist" />

      <main className="page-content">
        {/* Add ticker */}
        <section className="card">
          <h2 className="card-title">Add to Watchlist</h2>
          <form className="add-ticker-form" onSubmit={handleAdd}>
            <TickerInput
              value={addTicker}
              onChange={setAddTicker}
              onSelect={(t) => setAddTicker(t)}
              placeholder="Search ticker (e.g. RELIANCE.NS)"
              disabled={adding}
            />
            <button type="submit" className="btn btn-primary" disabled={adding}>
              <Plus size={15} /> Add
            </button>
          </form>
          {addError && <p className="form-error" style={{ marginTop: '0.5rem' }}>{addError}</p>}
        </section>

        {/* Watchlist with Kite-style tabs */}
        <section className="card wl-card">
          {/* Tab bar */}
          <div className="wl-tabs">
            {tabs.map((tab) => (
              <button
                key={tab.folder_id ?? 'none'}
                className={`wl-tab ${activeTab === tab.folder_id ? 'active' : ''}`}
                onClick={() => { if (renamingTab !== tab.folder_id) setActiveTab(tab.folder_id) }}
                onDoubleClick={() => {
                  if (tab.folder_id === null) return
                  setRenamingTab(tab.folder_id)
                  setRenameVal(tab.name)
                }}
              >
                {renamingTab === tab.folder_id ? (
                  <input
                    className="wl-tab-rename"
                    value={renameVal}
                    autoFocus
                    style={{ width: Math.max(60, renameVal.length * 8) + 'px' }}
                    onChange={(e) => setRenameVal(e.target.value)}
                    onBlur={() => handleRenameTab(tab.folder_id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleRenameTab(tab.folder_id)
                      if (e.key === 'Escape') setRenamingTab(null)
                      e.stopPropagation()
                    }}
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <>
                    <span className="wl-tab-name">{tab.name}</span>
                    <span className="wl-tab-count">
                      {items.filter((i) =>
                        tab.folder_id === null
                          ? i.folder_id == null
                          : i.folder_id === tab.folder_id,
                      ).length}
                    </span>
                    {tab.folder_id !== null && (
                      <span
                        className="wl-tab-x"
                        title="Delete list"
                        onClick={(e) => handleDeleteTab(tab.folder_id, tab.name, e)}
                      >
                        <X size={10} />
                      </span>
                    )}
                  </>
                )}
              </button>
            ))}

            {/* Inline new-tab input */}
            {showNewTab && (
              <div className="wl-tab wl-tab-creating">
                <input
                  ref={newTabInputRef}
                  className="wl-tab-rename"
                  placeholder="List name…"
                  value={newTabName}
                  onChange={(e) => setNewTabName(e.target.value)}
                  onBlur={handleCreateFolder}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCreateFolder()
                    if (e.key === 'Escape') { setShowNewTab(false); setNewTabName('') }
                  }}
                  disabled={creatingFolder}
                  style={{ width: '96px' }}
                />
              </div>
            )}

            {/* + button */}
            {!showNewTab && (
              <button
                className="wl-tab-add"
                onClick={() => setShowNewTab(true)}
                title="New list"
              >
                <Plus size={14} />
              </button>
            )}

            <div className="wl-tabs-spacer" />
            <button className="icon-btn wl-refresh" onClick={fetchWatchlist} title="Refresh">
              <RefreshCw size={13} />
            </button>
          </div>

          {/* Tab content */}
          <div className="wl-content">
            {error && <div className="error-banner">{error}</div>}

            {loading ? (
              <div style={{ padding: '16px' }}><SkeletonTable rows={6} cols={5} /></div>
            ) : activeItems.length === 0 ? (
              <div className="empty-state">
                <Star size={36} opacity={0.25} />
                <p>This list is empty. Add tickers above.</p>
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
                      <th>Move to</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeItems.map((item) => (
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
                        <td className="fw-medium">{fmtPrice(item.price, item.ticker)}</td>
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
                          <select
                            className="folder-select"
                            value={item.folder_id ?? ''}
                            onChange={(e) => {
                              const val = e.target.value === '' ? null : parseInt(e.target.value)
                              handleMoveItem(item.watchlist_id, val)
                            }}
                          >
                            {folderOptions.map((fo) => (
                              <option key={fo.folder_id ?? 'none'} value={fo.folder_id ?? ''}>
                                {fo.name}
                              </option>
                            ))}
                          </select>
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
          </div>
        </section>

        {orderTarget && (
          <OrderForm
            ticker={orderTarget.ticker}
            price={orderTarget.price}
            onClose={() => setOrderTarget(null)}
            onSuccess={handleOrderSuccess}
          />
        )}
      </main>

      {toast && <div className="toast success">{toast}</div>}
    </div>
  )
}
