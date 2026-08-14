import type { ReactNode } from 'react'

export function StatCard({
  icon,
  label,
  value,
  tone = 'default',
  hint,
}: {
  icon: ReactNode
  label: string
  value: string
  tone?: 'default' | 'success' | 'danger' | 'warning'
  hint?: string
}) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <div className="stat-card-top">
        <div className="stat-card-label">{label}</div>
        <div className="stat-card-icon">{icon}</div>
      </div>
      <div className="stat-card-value">{value}</div>
      {hint && <div className="stat-card-hint">{hint}</div>}
    </div>
  )
}
