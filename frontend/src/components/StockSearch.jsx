import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Loader2 } from 'lucide-react'
import { stocksAPI } from '../services/api'
import { useDebounce } from '../hooks/useDebounce'

export default function StockSearch() {
  const [query, setQuery]       = useState('')
  const [results, setResults]   = useState([])
  const [loading, setLoading]   = useState(false)
  const [open, setOpen]         = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const navigate  = useNavigate()
  const wrapperRef = useRef(null)
  const inputRef   = useRef(null)
  const debouncedQ = useDebounce(query, 320)

  // Fetch suggestions
  useEffect(() => {
    if (!debouncedQ || debouncedQ.length < 1) {
      setResults([])
      setOpen(false)
      return
    }
    setLoading(true)
    stocksAPI.search(debouncedQ)
      .then(({ data }) => {
        setResults(data || [])
        setOpen(true)
        setActiveIdx(-1)
      })
      .catch(() => setResults([]))
      .finally(() => setLoading(false))
  }, [debouncedQ])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const goToStock = useCallback((ticker) => {
    setQuery('')
    setOpen(false)
    setResults([])
    navigate(`/stocks/${ticker}`)
  }, [navigate])

  const handleKeyDown = (e) => {
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, -1))
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      goToStock(results[activeIdx].ticker)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="search-wrapper" ref={wrapperRef}>
      <div className="search-input-wrap">
        {loading
          ? <Loader2 size={16} className="search-icon spin" />
          : <Search size={16} className="search-icon" />
        }
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          placeholder="Search stocks... (e.g. AAPL, Tesla)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setOpen(true)}
          autoComplete="off"
          spellCheck="false"
        />
      </div>

      {open && results.length > 0 && (
        <ul className="search-dropdown" role="listbox">
          {results.map((r, i) => (
            <li
              key={r.ticker}
              role="option"
              aria-selected={i === activeIdx}
              className={`search-item${i === activeIdx ? ' active' : ''}`}
              onMouseDown={() => goToStock(r.ticker)}
              onMouseEnter={() => setActiveIdx(i)}
            >
              <div className="search-item-left">
                <span className="search-ticker">{r.ticker}</span>
                <span className="search-name">{r.company_name}</span>
              </div>
              <div className="search-item-right">
                {r.price != null && (
                  <span className="search-price">${r.price?.toFixed(2)}</span>
                )}
                {r.change_pct != null && (
                  <span className={`search-change ${r.change_pct >= 0 ? 'pos' : 'neg'}`}>
                    {r.change_pct >= 0 ? '+' : ''}{r.change_pct?.toFixed(2)}%
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {open && !loading && results.length === 0 && query.length > 1 && (
        <div className="search-empty">No results for "{query}"</div>
      )}
    </div>
  )
}
