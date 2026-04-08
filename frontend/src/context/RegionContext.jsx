/**
 * RegionContext — global region + currency handling.
 *
 * Exchange rates are fetched once per session from /api/currency/rates
 * (which yfinance refreshes daily from Forex tickers).
 *
 * All values in the backend are stored in the stock's native currency
 * (INR for .NS stocks, USD for US stocks). The region sets:
 *   1. Which stocks are visible (search + watchlist filter)
 *   2. The display currency for prices and portfolio values
 *
 * formatCurrency(value, { fromCurrency }) converts from the source
 * currency to the region's currency using today's FX rates.
 */
import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { currencyAPI } from '../services/api'

/**
 * Derive the actual price currency for a ticker from its suffix.
 * This is static — determined by the exchange, not the selected region.
 * Used so formatPrice always converts from the REAL source currency,
 * not from whatever region is currently selected.
 */
export function tickerCurrency(ticker) {
  if (!ticker) return 'USD'
  const t = ticker.toUpperCase()
  if (t.endsWith('.NS') || t.endsWith('.BO')) return 'INR'
  if (t.endsWith('.L'))                        return 'GBP'
  if (t.endsWith('.DE') || t.endsWith('.PA') || t.endsWith('.F')) return 'EUR'
  if (t.endsWith('.T'))                        return 'JPY'
  if (t.endsWith('.HK'))                       return 'HKD'
  return 'USD'
}

export const REGIONS = [
  {
    id:           'US',
    label:        'United States',
    flag:         '🇺🇸',
    currency:     'USD',
    symbol:       '$',
    index:        '^GSPC',
    indexName:    'S&P 500',
    tickerSuffix: [],          // no suffix = US
    stockCurrency: 'USD',     // native price currency for region stocks
  },
  {
    id:           'IN',
    label:        'India',
    flag:         '🇮🇳',
    currency:     'INR',
    symbol:       '₹',
    index:        '^NSEI',
    indexName:    'NIFTY 50',
    tickerSuffix: ['.NS', '.BO'],
    stockCurrency: 'INR',
  },
  {
    id:           'UK',
    label:        'United Kingdom',
    flag:         '🇬🇧',
    currency:     'GBP',
    symbol:       '£',
    index:        '^FTSE',
    indexName:    'FTSE 100',
    tickerSuffix: ['.L'],
    stockCurrency: 'GBP',
  },
  {
    id:           'EU',
    label:        'Europe',
    flag:         '🇪🇺',
    currency:     'EUR',
    symbol:       '€',
    index:        '^GDAXI',
    indexName:    'DAX',
    tickerSuffix: ['.DE', '.PA', '.F'],
    stockCurrency: 'EUR',
  },
  {
    id:           'JP',
    label:        'Japan',
    flag:         '🇯🇵',
    currency:     'JPY',
    symbol:       '¥',
    index:        '^N225',
    indexName:    'Nikkei 225',
    tickerSuffix: ['.T'],
    stockCurrency: 'JPY',
  },
  {
    id:           'HK',
    label:        'Hong Kong',
    flag:         '🇭🇰',
    currency:     'HKD',
    symbol:       'HK$',
    index:        '^HSI',
    indexName:    'Hang Seng',
    tickerSuffix: ['.HK'],
    stockCurrency: 'HKD',
  },
]

// Fallback rates (used before the API responds)
const FALLBACK_RATES = {
  USD: 1.0,
  INR: 84.0,
  GBP: 0.79,
  EUR: 0.91,
  JPY: 149.5,
  HKD: 7.78,
}

const RegionContext = createContext(null)

export function RegionProvider({ children }) {
  const [regionId, setRegionId] = useState(
    () => localStorage.getItem('region') || 'IN'
  )
  const [rates, setRates]     = useState(FALLBACK_RATES)
  const [ratesLoaded, setRatesLoaded] = useState(false)

  const region = REGIONS.find((r) => r.id === regionId) || REGIONS[0]

  // Persist region selection
  useEffect(() => {
    localStorage.setItem('region', regionId)
  }, [regionId])

  // Fetch exchange rates once per session (backend caches per day)
  useEffect(() => {
    currencyAPI.rates()
      .then(({ data }) => {
        if (data && typeof data === 'object') {
          setRates({ ...FALLBACK_RATES, ...data })
          setRatesLoaded(true)
        }
      })
      .catch(() => {
        // Keep fallback rates — app still works
        setRatesLoaded(true)
      })
  }, [])

  /**
   * Core conversion: convert `value` from `fromCurr` to the region's display currency.
   * Routes through USD as the universal bridge.
   *
   *   inUSD      = value / rates[fromCurr]   (or value itself if fromCurr is USD)
   *   converted  = inUSD * rates[region.currency]
   */
  const _convert = useCallback((value, fromCurr) => {
    const num   = Number(value)
    const inUSD = fromCurr === 'USD' ? num : num / (rates[fromCurr] || 1)
    return inUSD * (rates[region.currency] || 1)
  }, [region, rates])

  /**
   * Format a monetary VALUE that lives in the app's BASE CURRENCY (INR).
   * Use this for: balance, portfolio totals, P&L, cost basis, order totals.
   *
   * Examples:
   *   Region = IN  →  formatCurrency(10_000_000) = "₹1,00,00,000"
   *   Region = US  →  formatCurrency(10_000_000) = "$119,047.62"  (₹1Cr → USD)
   */
  const formatCurrency = useCallback((value, opts = {}) => {
    if (value == null || isNaN(value)) return `${region.symbol}—`

    const decimals = opts.decimals ?? 2
    const compact  = opts.compact  ?? false
    const converted = _convert(value, 'INR')   // base currency is always INR

    if (compact) {
      const abs = Math.abs(converted)
      if (abs >= 1_000_000_000) return `${region.symbol}${(converted / 1_000_000_000).toFixed(1)}B`
      if (abs >= 10_000_000)    return `${region.symbol}${(converted / 10_000_000).toFixed(2)}Cr`
      if (abs >= 100_000)       return `${region.symbol}${(converted / 100_000).toFixed(1)}L`
      if (abs >= 1_000_000)     return `${region.symbol}${(converted / 1_000_000).toFixed(1)}M`
    }

    return `${region.symbol}${converted.toLocaleString('en-IN', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}`
  }, [region, _convert])

  /**
   * Format a MARKET PRICE that comes from yfinance in the region's native currency.
   * Use this for: stock quote price, watchlist price, order price, limit/stop price,
   *               alert target price, avg buy price, market value per share.
   *
   * Examples (region = US, rate 84):
   *   formatPrice(200)   →  "$200.00"          (USD→USD, no change)
   * Examples (region = IN):
   *   formatPrice(2800)  →  "₹2,800.00"        (INR→INR, no change)
   * Cross-region (user in US viewing an INR price):
   *   formatPrice(2800, 'INR')  →  "$33.33"
   */
  const formatPrice = useCallback((value, optsOrCurr) => {
    if (value == null || isNaN(value)) return `${region.symbol}—`
    // Accept either a currency string or an opts object { from, compact, decimals }
    const opts      = typeof optsOrCurr === 'string' ? { from: optsOrCurr } : (optsOrCurr || {})
    const src       = opts.from     || region.stockCurrency
    const compact   = opts.compact  ?? false
    const decimals  = opts.decimals ?? 2
    const converted = _convert(value, src)

    if (compact) {
      const abs = Math.abs(converted)
      if (abs >= 1_000_000_000) return `${region.symbol}${(converted / 1_000_000_000).toFixed(1)}B`
      if (abs >= 10_000_000)    return `${region.symbol}${(converted / 10_000_000).toFixed(2)}Cr`
      if (abs >= 100_000)       return `${region.symbol}${(converted / 100_000).toFixed(1)}L`
      if (abs >= 1_000_000)     return `${region.symbol}${(converted / 1_000_000).toFixed(1)}M`
    }

    return `${region.symbol}${converted.toLocaleString('en-IN', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}`
  }, [region, _convert])

  /**
   * Convert a raw price to USD (for internal calculations).
   */
  const toUSD = useCallback((value, fromCurrency) => {
    if (!value) return 0
    const curr = fromCurrency || region.stockCurrency
    return curr === 'USD' ? value : value / (rates[curr] || 1)
  }, [region, rates])

  return (
    <RegionContext.Provider value={{
      region,
      regionId,
      setRegionId,
      rates,
      ratesLoaded,
      formatCurrency,
      formatPrice,
      toUSD,
    }}>
      {children}
    </RegionContext.Provider>
  )
}

export function useRegion() {
  const ctx = useContext(RegionContext)
  if (!ctx) throw new Error('useRegion must be used inside RegionProvider')
  return ctx
}
