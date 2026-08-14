import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

export function SectionCard({
  icon: Icon,
  title,
  description,
  actions,
  children,
}: {
  icon: LucideIcon
  title: string
  description?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section>
      <div className="section-card-header">
        <div className="section-card-heading">
          <span className="section-card-icon">
            <Icon size={16} />
          </span>
          <div>
            <h2>{title}</h2>
            {description && <p className="section-card-desc">{description}</p>}
          </div>
        </div>
        {actions && <div className="header-actions">{actions}</div>}
      </div>
      {children}
    </section>
  )
}
