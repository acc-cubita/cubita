import { useMemo, useState } from 'react'
import { LayoutGrid, Rocket } from 'lucide-react'

import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { CountBadge } from './form/FormKit'
import { LauncherPicker } from './LauncherPicker'
import { LaunchIcon } from './LaunchIcon'
import { buildLaunchers, cardHint, resolveCards } from '../lib/launchers'
import { resetDashboardCards, saveDashboardCards, type MeResponse } from '../api'
import type { PageKey } from '../lib/navModel'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * باکسِ «شروعِ کارِ تازه» — کارت‌هایش را خودِ کاربر از میانِ ماژول‌ها و زیرمنوهایشان
 * می‌چیند.
 *
 * پیش‌تر این باکس شش کارتِ **ثابت** داشت (`TASK_LAUNCHERS`): همان شش‌تا برای
 * پیمانکاری که هر روز «صورت وضعیت» می‌زند و برای فروشگاهی که فقط فاکتور می‌بُرد.
 * حالا آن شش‌تا فقط *پیش‌فرض*اند و هرکس می‌تواند جایشان را با کارهای خودش عوض کند.
 *
 * انتخاب روی **حساب** ذخیره می‌شود (`memberships.dashboard_cards`) نه روی مرورگر،
 * پس نسخه‌ی ویندوز و مرورگر و هر دستگاهِ دیگری یک چیدمان می‌بینند. هر دو داشبورد —
 * «راهنما» و کلاسیک — همین یک کامپوننت را نشان می‌دهند.
 */
export function LauncherBoard({
  token,
  me,
  onMeUpdated,
  onNavigate,
}: {
  token: string
  me: MeResponse
  onMeUpdated: (me: MeResponse) => void
  onNavigate: (page: PageKey, section?: string) => void
}) {
  const [picking, setPicking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const groups = useMemo(() => buildLaunchers(me), [me])
  const cards = useMemo(() => resolveCards(groups, me.dashboard_cards), [groups, me.dashboard_cards])

  //: فهرستِ تیک‌خورده‌ی انتخاب‌گر باید همان چیزی باشد که *روی صفحه* است — نه فهرستِ
  //: خامِ ذخیره‌شده. کاربری که هنوز انتخابی نکرده، پیش‌فرض‌ها را تیک‌خورده می‌بیند و
  //: می‌تواند از همان‌جا کم و زیادشان کند.
  const selected = cards.map((t) => t.id)

  async function confirm(ids: string[]) {
    setBusy(true)
    setError(null)
    try {
      const res = await saveDashboardCards(token, ids)
      onMeUpdated({ ...me, dashboard_cards: res.cards })
      setPicking(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ذخیره‌ی کارت‌ها ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  async function reset() {
    setBusy(true)
    setError(null)
    try {
      const res = await resetDashboardCards(token)
      onMeUpdated({ ...me, dashboard_cards: res.cards })
      setPicking(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'بازگرداندن به پیش‌فرض ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <SectionCard
        icon={Rocket}
        title="شروعِ کارِ تازه"
        description="کارهایی که هر روز سراغشان می‌روید — یک کلیک تا خودِ فرم."
        badge={cards.length > 0 ? <CountBadge accent>{fa(cards.length)} کارت</CountBadge> : undefined}
        actions={
          <button type="button" className="ef-btn-secondary" onClick={() => setPicking(true)}>
            <LayoutGrid size={15} /> انتخابِ کارت‌ها
          </button>
        }
      >
        {cards.length === 0 ? (
          <EmptyState
            icon={LayoutGrid}
            text="هیچ کارتی انتخاب نشده است. با «انتخابِ کارت‌ها» ماژول‌ها را باز کنید و کارهای روزمره‌تان را تیک بزنید."
          />
        ) : (
          <div className="action-hub-grid">
            {cards.map((t) => (
              <button
                key={t.id}
                type="button"
                className="action-card"
                onClick={() => onNavigate(t.page, t.section)}
              >
                <span className="action-card-icon">
                  <LaunchIcon icon={t.icon} size={22} />
                </span>
                <span className="action-card-title">{t.label}</span>
                <span className="action-card-desc">{cardHint(t)}</span>
              </button>
            ))}
          </div>
        )}
      </SectionCard>

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
          onConfirm={(ids) => void confirm(ids)}
          onReset={() => void reset()}
        />
      )}
    </>
  )
}
