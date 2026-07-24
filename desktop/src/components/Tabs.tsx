import { useState, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

export interface TabDef {
  key: string
  label: string
  icon?: LucideIcon
  /** محتوای این تب فقط وقتی رندر می‌شود که تب فعال باشد (mount تنبل). */
  content: ReactNode
}

/** نوار تبِ افقی برای صفحه‌های ماژول — به‌جای چیدنِ همه‌ی بخش‌ها زیر هم.
 *
 * فقط تبِ فعال رندر می‌شود؛ لیست‌هایی که موقع mount داده می‌گیرند تنبل و هنگام
 * باز شدنِ تب بارگذاری می‌شوند. حالتِ صفحه (state) در خودِ صفحه می‌ماند، پس
 * جابه‌جایی بین تب‌ها داده‌ی مشترک را از دست نمی‌دهد. */
export function Tabs({ tabs, initialKey }: { tabs: TabDef[]; initialKey?: string }) {
  const [active, setActive] = useState(initialKey ?? tabs[0]?.key)
  const activeTab = tabs.find((t) => t.key === active) ?? tabs[0]

  return (
    <div className="tabs">
      <div className="tab-list" role="tablist">
        {tabs.map((t) => {
          const Icon = t.icon
          const isActive = t.key === activeTab.key
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`tab${isActive ? ' active' : ''}`}
              onClick={() => setActive(t.key)}
            >
              {Icon && <Icon size={16} />}
              <span>{t.label}</span>
            </button>
          )
        })}
      </div>
      <div className="tab-panel" role="tabpanel">
        {activeTab.content}
      </div>
    </div>
  )
}
