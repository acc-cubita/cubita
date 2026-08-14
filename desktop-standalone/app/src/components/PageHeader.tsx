import type { LucideIcon } from 'lucide-react'

export function PageHeader({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon
  title: string
  description: string
}) {
  return (
    <div className="page-header">
      <span className="page-header-icon">
        <Icon size={20} />
      </span>
      <div>
        <h1>{title}</h1>
        <p className="page-header-desc">{description}</p>
      </div>
    </div>
  )
}
