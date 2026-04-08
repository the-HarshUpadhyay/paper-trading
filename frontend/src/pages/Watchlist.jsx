import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Star, Trash2, TrendingUp, TrendingDown,
  RefreshCw, ShoppingCart, Plus, FolderOpen,
  Pencil, ChevronDown,
} from 'lucide-react'
import Header from '../components/Header'
import OrderForm from '../components/OrderForm'
import { SkeletonTable } from '../components/LoadingSkeleton'
import { watchlistAPI, stocksAPI } from '../services/api'
import { useRegion, tickerCurrency } from '../context/RegionContext'

export default function Watchlist() {
  const navigate = useNavigate()

  const [items, setItems]             = useState([])
  const [folders, setFolders]         = useState([])   // derived from items
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)
  const [removing, setRemoving]       = useState(null)
  const [orderTarget, setOrderTarget] = useState(null)
  const [addTicker, setAddTicker]     = useState('')
  const [addError, setAddError]       = useState(null)
  const [adding, setAdding]           = useState(false)
  const [toast, setToast]             = useState(null)

  // Folder management
  const [showFolderMgr, setShowFolderMgr]   = useState(false)
  const [newFolderName, setNewFolderName]   = useState('')
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [folderError, setFolderError]       = useState(null)
  const [renamingId, setRenamingId]         = useState(null)
  const [renameVal, setRenameVal]           = useState('')

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 2500) }

  const fetchWatchlist = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await watchlistAPI.get()
      setItems(data.watchlist || [])
      setFolders(data.folders || [])
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

  // ── Folder CRUD ──────────────────────────────────────────────────────────

  const handleCreateFolder = async (e) => {
    e.preventDefault()
    const name = newFolderName.trim()
    if (!name) return
    setCreatingFolder(true)
    setFolderError(null)
    try {
      await watchlistAPI.createFolder(name)
      setNewFolderName('')
      showToast(`Folder "${name}" created`)
      await fetchWatchlist()
    } catch (err) {
      setFolderError(err.response?.data?.error || 'Failed to create folder')
    } finally {
      setCreatingFolder(false)
    }
  }

  const handleRenameFolder = async (folder_id) => {
    const name = renameVal.trim()
    if (!name) { setRenamingId(null); return }
    try {
      await watchlistAPI.renameFolder(folder_id, name)
      showToast('Folder renamed')
      await fetchWatchlist()
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to rename')
    } finally {
      setRenamingId(null)
    }
  }

  const handleDeleteFolder = async (folder_id, name) => {
    if (!window.confirm(`Delete folder "${name}"? Items will become Uncategorised.`)) return
    try {
      await watchlistAPI.deleteFolder(folder_id)
      showToast('Folder deleted')
      await fetchWatchlist()
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to delete folder')
    }
  }

  const handleMoveItem = async (watchlist_id, folder_id) => {
    try {
      await watchlistAPI.moveItem(watchlist_id, folder_id || null)
      await fetchWatchlist()
    } catch (_) {}
  }

  const { formatPrice } = useRegion()
  // Per-item price formatter — uses the ticker's actual currency as source
  const fmtPrice = (n, ticker) => formatPrice(n, { from: tickerCurrency(ticker) })

  // Group items by folder; always include Uncategorised for items with no folder
  const uncategorisedItems = items.filter((i) => i.folder_id == null)
  const groupedItems = [
    ...folders.map((f) => ({
      ...f,
      items: items.filter((i) => i.folder_id === f.folder_id),
    })),
    { folder_id: null, name: 'Uncategorised', items: uncategorisedItems },
  ]

  // Collect folder options for the move dropdown
  const folderOptions = [
    { folder_id: null, name: 'Uncategorised' },
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

        {/* Folder management */}
        <section className="card">
          <button
            className="folder-mgr-toggle"
            onClick={() => setShowFolderMgr((v) => !v)}
          >
            <FolderOpen size={15} />
            Manage Folders
            <ChevronDown
              size={14}
              style={{ marginLeft: 'auto', transform: showFolderMgr ? 'rotate(180deg)' : 'none', transition: '0.2s' }}
            />
          </button>

          {showFolderMgr && (
            <div className="folder-mgr-body">
              <form className="add-ticker-form" onSubmit={handleCreateFolder} style={{ marginBottom: 12 }}>
                <input
                  className="form-input"
                  placeholder="New folder name"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  maxLength={100}
                />
                <button type="submit" className="btn btn-primary btn-sm" disabled={creatingFolder}>
                  <Plus size={13} /> Create
                </button>
              </form>
              {folderError && <p className="form-error">{folderError}</p>}

              {folders.length === 0 ? (
                <p className="text-muted" style={{ fontSize: '0.82rem' }}>No folders yet.</p>
              ) : (
                <ul className="folder-list">
                  {folders.map((f) => (
                    <li key={f.folder_id} className="folder-list-item">
                      {renamingId === f.folder_id ? (
                        <input
                          className="form-input"
                          style={{ flex: 1, padding: '4px 8px', fontSize: '0.85rem' }}
                          value={renameVal}
                          autoFocus
                          onChange={(e) => setRenameVal(e.target.value)}
                          onBlur={() => handleRenameFolder(f.folder_id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleRenameFolder(f.folder_id)
                            if (e.key === 'Escape') setRenamingId(null)
                          }}
                        />
                      ) : (
                        <span className="folder-name">
                          <FolderOpen size={13} /> {f.name}
                        </span>
                      )}
                      <div className="action-btns">
                        <button
                          className="btn btn-sm btn-ghost"
                          title="Rename"
                          onClick={() => { setRenamingId(f.folder_id); setRenameVal(f.name) }}
                        >
                          <Pencil size={12} />
                        </button>
                        <button
                          className="btn btn-sm btn-ghost btn-danger"
                          title="Delete"
                          onClick={() => handleDeleteFolder(f.folder_id, f.name)}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>

        {/* Watchlist grouped by folder */}
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
            <SkeletonTable rows={6} cols={6} />
          ) : !items.length ? (
            <div className="empty-state">
              <Star size={40} opacity={0.3} />
              <p>Your watchlist is empty. Add tickers above.</p>
            </div>
          ) : (
            groupedItems.map((group) =>
              group.items.length === 0 ? null : (
                <div key={group.folder_id ?? 'none'} className="folder-group">
                  <div className="folder-group-header">
                    <FolderOpen size={13} />
                    {group.name}
                    <span className="text-muted" style={{ fontSize: '0.75rem', marginLeft: 6 }}>
                      ({group.items.length})
                    </span>
                  </div>
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
                        {group.items.map((item) => (
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
                </div>
              )
            )
          )}
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
