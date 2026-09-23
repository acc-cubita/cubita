import { useMemo, useState } from 'react'
import { useExperienceMode } from './experienceMode'
import { buildLaunchers, resolveCards } from './launchers'
import { resetDashboardCards, saveDashboardCards, type MeResponse } from '../api'

/**
 * منطقِ مشترکِ «کارت‌های داشبورد» — هم `LauncherBoard` (کارتِ درونِ داشبورد) و هم
 * `QuickAccessBar` (نوارِ افقیِ زیرِ TopNav) همین یک منبع را می‌خوانند و ذخیره
 * می‌کنند، تا انتخابِ کاربر همه‌جا یکی بماند.
 *
 * حالتِ تجربه فقط *پیش‌فرض* را عوض می‌کند (`MODE_DEFAULT_CARDS`)، پس کاربری که
 * هنوز کارت نچیده با عوض‌کردنِ حالت همان لحظه کارت‌های حالتِ تازه را می‌بیند —
 * بی درخواستِ شبکه، چون چیزی ذخیره نمی‌شود. «بازگرداندن به پیش‌فرض» هم به
 * پیش‌فرضِ حالتِ جاری برمی‌گرداند.
 */
export function useDashboardCards(
  token: string,
  me: MeResponse,
  onMeUpdated: (me: MeResponse) => void,
) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { mode } = useExperienceMode()
  const groups = useMemo(() => buildLaunchers(me), [me])
  const cards = useMemo(
    () => resolveCards(groups, me.dashboard_cards, mode),
    [groups, me.dashboard_cards, mode],
  )

  async function confirm(ids: string[]): Promise<boolean> {
    setBusy(true)
    setError(null)
    try {
      const res = await saveDashboardCards(token, ids)
      onMeUpdated({ ...me, dashboard_cards: res.cards })
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ذخیره‌ی کارت‌ها ناموفق بود')
      return false
    } finally {
      setBusy(false)
    }
  }

  async function reset(): Promise<boolean> {
    setBusy(true)
    setError(null)
    try {
      const res = await resetDashboardCards(token)
      onMeUpdated({ ...me, dashboard_cards: res.cards })
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'بازگرداندن به پیش‌فرض ناموفق بود')
      return false
    } finally {
      setBusy(false)
    }
  }

  return { groups, cards, busy, error, setError, confirm, reset }
}
