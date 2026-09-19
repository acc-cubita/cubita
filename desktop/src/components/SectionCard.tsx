import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { InfoTip } from './form/FormKit'

export function SectionCard({
  icon: Icon,
  title,
  description,
  tip,
  actions,
  children,
}: {
  icon: LucideIcon
  title: string
  description?: string
  /** راهنمای بلند — آیکونِ «؟» کنارِ عنوان، به‌جای پاراگرافِ ثابت زیرِ آن. */
  tip?: string
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
            {tip ? (
              <div className="ef-title-row">
                <h2>{title}</h2>
                <InfoTip text={tip} />
              </div>
            ) : (
              <h2>{title}</h2>
            )}
            {description && <p className="section-card-desc">{description}</p>}
          </div>
        </div>
        {actions && <div className="header-actions">{actions}</div>}
      </div>
      {children}
    </section>
  )
}
