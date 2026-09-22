import { useState } from 'react'
import { LayoutGrid, Rocket } from 'lucide-react'

import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { CountBadge } from './form/FormKit'
import { LauncherPicker } from './LauncherPicker'
import { LaunchIcon } from './LaunchIcon'
import { cardHint } from '../lib/launchers'
import { useDashboardCards } from '../lib/useDashboardCards'
import type { MeResponse } from '../api'
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
  const { groups, cards, busy, error, setError, confirm, reset } = useDashboardCards(token, me, onMeUpdated)

  //: فهرستِ تیک‌خورده‌ی انتخاب‌گر باید همان چیزی باشد که *روی صفحه* است — نه فهرستِ
  //: خامِ ذخیره‌شده. کاربری که هنوز انتخابی نکرده، پیش‌فرض‌ها را تیک‌خورده می‌بیند و
  //: می‌تواند از همان‌جا کم و زیادشان کند.
  const selected = cards.map((t) => t.id)

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
          onConfirm={(ids) => void confirm(ids).then((ok) => { if (ok) setPicking(false) })}
          onReset={() => void reset().then((ok) => { if (ok) setPicking(false) })}
        />
      )}
    </>
  )
}
