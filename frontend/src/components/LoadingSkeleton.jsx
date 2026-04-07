/**
 * LoadingSkeleton — animated placeholder blocks for loading states.
 */
export function Skeleton({ width = '100%', height = '1rem', borderRadius = '4px', className = '' }) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{ width, height, borderRadius }}
    />
  )
}

export function SkeletonCard({ rows = 3 }) {
  return (
    <div className="skeleton-card">
      <Skeleton height="1.2rem" width="40%" />
      <div style={{ marginTop: '1rem' }}>
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} height="0.9rem" width={`${70 + Math.random() * 25}%`}
            style={{ marginBottom: '0.5rem' }} />
        ))}
      </div>
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4 }) {
  return (
    <div className="skeleton-table">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton-row" style={{ display: 'flex', gap: '1rem', marginBottom: '0.75rem' }}>
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} height="0.9rem" width={`${60 + Math.random() * 35}%`} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonChart() {
  return (
    <div className="skeleton-chart">
      <Skeleton height="280px" borderRadius="8px" />
    </div>
  )
}
