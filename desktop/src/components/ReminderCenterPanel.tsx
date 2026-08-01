import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  BellRing, RefreshCw, CheckCircle2, Banknote, Clock, CreditCard, Repeat, CalendarClock, PackageX, Coins,
} from 'lucide-react'
import { fetchAlerts, type AlertCategory, type AlertItem, type Alerts } from '../api'
import { SectionCard } from './SectionCard'
import { formatJalali, toFaDigits } from '../lib/jalali'

const CAT_META: Record<AlertCategory, { icon: typeof Banknote; label: string }> = {
  check: { icon: Banknote, label: 'چک' },
  receivable: { icon: Clock, label: 'مطالبات' },
  credit: { icon: CreditCard, label: 'سقف اعتبار' },
  recurring: { icon: Repeat, label: 'سند تکرارشونده' },
  calendar: { icon: CalendarClock, label: 'یادآوری تقویم' },
  stock: { icon: PackageX, label: 'موجودی' },
  installment: { icon: Coins, label: 'اقساط' },
}
const SEV_ORDER: Record<string, number> = { danger: 0, warning: 1, info: 2 }
const fa = (v: string) => Math.round(Number(v)).toLocaleString('fa-IR')

/**
 * مرکزِ یادآوری‌ها و «کارهای امروز» — نمای کاملِ `/api/alerts`: چک‌های سررسید، مطالباتِ
 * معوق، عبور از سقفِ اعتبار، اسنادِ تکرارشونده‌ی سررسیدشده، یادآوری‌های تقویم، موجودیِ
 * منفی و اقساطِ معوق، یک‌جا و گروه‌بندی‌شده بر پایه‌ی شدت. فقط‌خواندنی است و داده‌ی
 * تازه‌ای نمی‌سازد؛ صرفاً از ماژول‌های موجود آیتم‌های قابلِ‌اقدام را زنده جمع می‌کند.
 */
export function ReminderCenterPanel({ token }: { token: string }) {
  const [data, setData] = useState<Alerts | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [cat, setCat] = useState<'all' | AlertCategory>('all')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await fetchAlerts(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])

  const sevCounts = useMemo(() => {
    const c = { danger: 0, warning: 0, info: 0 }
    for (const it of data?.items ?? []) c[it.severity] += 1
    return c
  }, [data])

  const shown = useMemo(() => {
    const items = (data?.items ?? []).filter((it) => cat === 'all' || it.category === cat)
    return [...items].sort((a, b) => {
      if (SEV_ORDER[a.severity] !== SEV_ORDER[b.severity]) return SEV_ORDER[a.severity] - SEV_ORDER[b.severity]
      const ad = a.alert_date ?? '9999'
      const bd = b.alert_date ?? '9999'
      return ad < bd ? -1 : 1
    })
  }, [data, cat])

  // دسته‌هایی که واقعاً آیتم دارند (از counts سرور) برای چیپ‌های فیلتر
  const activeCats = useMemo(
    () => (Object.keys(data?.counts ?? {}) as AlertCategory[]).filter((k) => (data?.counts[k] ?? 0) > 0),
    [data],
  )

  return (
    <SectionCard
      icon={BellRing}
      title="کارهای امروز — مرکز یادآوری"
      description="چک‌های سررسید، اقساط و مطالباتِ معوق، اسنادِ تکرارشونده و یادآوری‌های تقویم؛ همه یک‌جا و بر پایه‌ی فوریت."
      actions={
        <button type="button" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={13} /> بازخوانی
        </button>
      }
    >
      {error && <div className="error">{error}</div>}
      {!data && !error && <p className="hint">در حال بارگذاری…</p>}

      {data && data.total === 0 && (
        <div className="reminder-ok">
          <CheckCircle2 size={18} />
          <span>هیچ مورد نیازمند رسیدگی‌ای نیست — همه‌چیز مرتب است.</span>
        </div>
      )}

      {data && data.total > 0 && (
        <>
          <div className="reminder-kpis">
            <div className="reminder-kpi sev-danger"><span>فوری</span><strong>{toFaDigits(sevCounts.danger)}</strong></div>
            <div className="reminder-kpi sev-warning"><span>هشدار</span><strong>{toFaDigits(sevCounts.warning)}</strong></div>
            <div className="reminder-kpi sev-info"><span>اطلاع</span><strong>{toFaDigits(sevCounts.info)}</strong></div>
            <div className="reminder-kpi"><span>جمعِ کل</span><strong>{toFaDigits(data.total)}</strong></div>
          </div>

          <div className="reminder-filters">
            <button type="button" className={cat === 'all' ? 'chip-active' : ''} onClick={() => setCat('all')}>
              همه ({toFaDigits(data.total)})
            </button>
            {activeCats.map((c) => (
              <button key={c} type="button" className={cat === c ? 'chip-active' : ''} onClick={() => setCat(c)}>
                {CAT_META[c]?.label ?? c} ({toFaDigits(data.counts[c])})
              </button>
            ))}
          </div>

          <ul className="reminder-list">
            {shown.map((it: AlertItem, i) => {
              const Icon = CAT_META[it.category]?.icon ?? BellRing
              return (
                <li key={i} className={`reminder-row sev-${it.severity}`}>
                  <span className="reminder-dot" />
                  <Icon size={16} className="reminder-cat-icon" />
                  <div className="reminder-body">
                    <div className="reminder-title">{it.title}</div>
                    <div className="reminder-detail">
                      <span className="reminder-cat-label">{CAT_META[it.category]?.label ?? it.category}</span>
                      {it.detail && <> · {it.detail}</>}
                      {it.alert_date && <span className="reminder-date"> · {formatJalali(it.alert_date)}</span>}
                    </div>
                  </div>
                  {it.amount && <div className="reminder-amount">{fa(it.amount)}</div>}
                </li>
              )
            })}
          </ul>
          {shown.length === 0 && <p className="hint">در این دسته موردی نیست.</p>}
        </>
      )}
    </SectionCard>
  )
}
