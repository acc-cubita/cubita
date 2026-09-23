import { useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { LayoutList } from 'lucide-react'

import { SectionCard } from './SectionCard'
import { LaunchIcon } from './LaunchIcon'
import { useNavSection } from './navContext'
import { buildLaunchers } from '../lib/launchers'
import { useExperienceMode } from '../lib/experienceMode'
import { buildReportCatalog, filterReportCatalog, isReportKind, type ReportEntry } from '../lib/reportCatalog'
import type { PageKey } from '../lib/navModel'
import type { MeResponse } from '../api'

/**
 * «همه‌ی گزارش‌ها» — سرِ صفحه‌ی «گزارش‌ها». داده و ترتیب از `lib/reportCatalog.ts`.
 *
 * **صفحه‌کلید:** تایپ صافی می‌کند؛ Enter در کادر اولین نتیجه را باز می‌کند؛ پیکانِ
 * پایین به فهرست می‌رود و پیکان‌ها بینِ ردیف‌ها حرکت می‌کنند؛ Escape به کادر برمی‌گردد.
 * موس هم مثلِ قبل کار می‌کند (§۴۵).
 */
export function ReportCatalog({
  me,
  onNavigate,
}: {
  me: MeResponse
  onNavigate: (page: PageKey, section?: string) => void
}) {
  const { mode } = useExperienceMode()
  const nav = useNavSection()
  const launchers = useMemo(() => buildLaunchers(me), [me])
  const catalog = useMemo(() => buildReportCatalog(launchers, mode), [launchers, mode])
  const [query, setQuery] = useState('')
  const shown = filterReportCatalog(catalog, query)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  //: گزارشِ بازِ صفحه‌ی «گزارش‌ها» — بی‌بخش یعنی تبِ پیش‌فرض، سود و زیان.
  const current =
    nav?.activePage === 'reports' ? `reports/${isReportKind(nav.section) ? nav.section : 'income-statement'}` : null

  const items = () => [...(listRef.current?.querySelectorAll<HTMLButtonElement>('.rc-item') ?? [])]

  function open(e: ReportEntry) {
    onNavigate(e.page, e.section)
    //: تبِ همین صفحه زیرِ فهرست باز می‌شود؛ بی‌این، کلیک هیچ تغییرِ دیدنی‌ای نداشت.
    if (e.page === 'reports' && nav?.activePage === 'reports') {
      requestAnimationFrame(() =>
        document.getElementById('report-view')?.scrollIntoView({ block: 'start', behavior: 'smooth' }),
      )
    }
  }

  function onFilterKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      items()[0]?.focus()
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const first = shown[0]?.entries[0]
      if (first) open(first)
    } else if (e.key === 'Escape' && query) {
      e.preventDefault()
      setQuery('')
    }
  }

  function onListKey(e: KeyboardEvent<HTMLDivElement>) {
    const all = items()
    const i = all.indexOf(e.target as HTMLButtonElement)
    if (i === -1) return
    const to = (n: number) => {
      e.preventDefault()
      all[Math.max(0, Math.min(all.length - 1, n))]?.focus()
    }
    if (e.key === 'ArrowDown') to(i + 1)
    else if (e.key === 'ArrowUp') {
      if (i === 0) {
        e.preventDefault()
        inputRef.current?.focus()
      } else to(i - 1)
    } else if (e.key === 'Home') to(0)
    else if (e.key === 'End') to(all.length - 1)
    else if (e.key === 'Escape') {
      e.preventDefault()
      inputRef.current?.focus()
    }
  }

  return (
    <SectionCard
      icon={LayoutList}
      title="همه‌ی گزارش‌ها"
      description="هر گزارشی که در کوبیتا هست، یک‌جا — از هر ماژولی که باشد."
    >
      <input
        ref={inputRef}
        type="search"
        className="rc-filter"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onFilterKey}
        placeholder="جست‌وجوی گزارش…"
        aria-label="جست‌وجوی گزارش"
      />
      <div className="rc-groups" ref={listRef} onKeyDown={onListKey}>
        {shown.map((g) => (
          //: `div` و نه `section`: پوسته‌ی «مرحله‌ای» هر `section`ِ داخلِ `.page` را کارتِ
          //: شناور می‌کند (`.page section`)، و هفت کارتِ تودرتو فهرست را سه برابر بلند می‌کرد.
          <div className="rc-group" role="group" key={g.key} aria-labelledby={`rc-${g.key}`}>
            <h3 className="rc-heading" id={`rc-${g.key}`}>{g.heading}</h3>
            <ul className="rc-list">
              {g.entries.map((e) => {
                const on = e.id === current
                return (
                  <li key={e.id}>
                    <button
                      type="button"
                      className={`rc-item${on ? ' active' : ''}`}
                      aria-current={on ? 'page' : undefined}
                      onClick={() => open(e)}
                    >
                      <LaunchIcon icon={e.icon} size={15} />
                      <span>{e.label}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
        {shown.length === 0 && (
          <p className="muted rc-empty">گزارشی با «{query.trim()}» پیدا نشد. واژه‌ی کوتاه‌تری امتحان کنید.</p>
        )}
      </div>
    </SectionCard>
  )
}
