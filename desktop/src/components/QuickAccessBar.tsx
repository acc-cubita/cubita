import { useState } from 'react'
import { Settings2 } from 'lucide-react'

import { LauncherPicker } from './LauncherPicker'
import { LaunchIcon } from './LaunchIcon'
import { cardHint } from '../lib/launchers'
import { useDashboardCards } from '../lib/useDashboardCards'
import type { MeResponse } from '../api'
import type { PageKey } from '../lib/navModel'

/**
 * نوارِ افقیِ میان‌بر، درست زیرِ TopNav — همان کارت‌هایی که کاربر در داشبورد
 * («شروعِ کارِ تازه») انتخاب کرده، ولی این‌جا از **هر صفحه‌ای** یک کلیک دورند، نه
 * فقط از داشبورد. منبعِ داده یکی است (`useDashboardCards`، `memberships.dashboard_cards`
 * روی سرور)، پس انتخابِ کاربر همه‌جا هم‌گام می‌ماند.
 *
 * وقتی کاربر هنوز کارتی انتخاب نکرده چیزی رندر نمی‌شود — نوارِ خالی زیرِ TopNav
 * در هر صفحه فقط ارتفاع تلف می‌کرد؛ ورودِ اول از EmptyStateِ خودِ داشبورد است.
 */
export function QuickAccessBar({
  token,
  me,
  onMeUpdated,
  onNavigate,
  activePage,
  activeSection,
}: {
  token: string
  me: MeResponse
  onMeUpdated: (me: MeResponse) => void
  onNavigate: (page: PageKey, section?: string) => void
  activePage: PageKey
  activeSection: string | null
}) {
  const [picking, setPicking] = useState(false)
  const { groups, cards, busy, error, setError, confirm, reset } = useDashboardCards(token, me, onMeUpdated)
  const selected = cards.map((t) => t.id)

  if (cards.length === 0) return null

  return (
    <>
      <div className="quick-bar">
        <div className="quick-bar-scroll">
          {cards.map((t) => {
            const active = t.page === activePage && (t.section ?? null) === activeSection
            return (
              <button
                key={t.id}
                type="button"
                className={`quick-bar-chip${active ? ' active' : ''}`}
                title={cardHint(t)}
                onClick={() => onNavigate(t.page, t.section)}
              >
                <LaunchIcon icon={t.icon} size={15} />
                <span>{t.label}</span>
              </button>
            )
          })}
        </div>
        <button
          type="button"
          className="quick-bar-manage"
          onClick={() => setPicking(true)}
          title="مدیریتِ کارت‌های میان‌بر"
          aria-label="مدیریتِ کارت‌های میان‌بر"
        >
          <Settings2 size={15} />
        </button>
      </div>

      {picking && (
        <LauncherPicker
          groups={groups}
          selected={selected}
          busy={busy}
          error={error}
          onCancel={() => {
            setPicking(false)
            setError(null)
          }}
          onConfirm={(ids) => void confirm(ids).then((ok) => { if (ok) setPicking(false) })}
          onReset={() => void reset().then((ok) => { if (ok) setPicking(false) })}
        />
      )}
    </>
  )
}
