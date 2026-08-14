import { useEffect, useState } from 'react'
import {
  BellRing,
  CheckCircle2,
  Banknote,
  Clock,
  CreditCard,
  Repeat,
  CalendarClock,
  PackageX,
  Coins,
} from 'lucide-react'
import { fetchAlerts, type AlertCategory, type AlertItem, type Alerts } from '../api'
import { formatJalali, toFaDigits } from '../lib/jalali'
import { Pager, usePagination } from './Pager'

const CAT_ICON: Record<AlertCategory, typeof Banknote> = {
  check: Banknote,
  receivable: Clock,
  credit: CreditCard,
  recurring: Repeat,
  calendar: CalendarClock,
  stock: PackageX,
  installment: Coins,
}

// danger اول، بعد warning، بعد info — مهم‌ترین‌ها بالای فهرست.
const SEVERITY_ORDER: Record<string, number> = { danger: 0, warning: 1, info: 2 }
const fa = (v: string) => Math.round(Number(v)).toLocaleString('fa-IR')

export function AlertsPanel({ token }: { token: string }) {
  const [data, setData] = useState<Alerts | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchAlerts(token)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [token])

  // هوکِ صفحه‌بندی باید بی‌قید و پیش از هر return زودهنگام صدا زده شود (قاعده‌ی هوک‌ها).
  const sorted = data
    ? [...data.items].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
    : []
  const { pageItems, page, setPage, pageCount } = usePagination(sorted, 4)

  // آفلاین یا خطا: بی‌صدا چیزی نشان نده تا نمای کلی نشکند.
  if (failed || !data) return null

  if (data.total === 0) {
    return (
      <div className="alerts-card alerts-ok">
        <CheckCircle2 size={16} />
        <span>هیچ مورد نیازمند رسیدگی‌ای نیست — همه‌چیز مرتب است.</span>
      </div>
    )
  }

  return (
    <div className="alerts-card">
      <div className="alerts-head">
        <BellRing size={16} />
        <strong>نیازمند رسیدگی</strong>
        <span className="alerts-count">{toFaDigits(data.total)}</span>
      </div>
      <ul className="alerts-list">
        {pageItems.map((it: AlertItem, i) => {
          const Icon = CAT_ICON[it.category]
          return (
            <li key={i} className={`alert-row sev-${it.severity}`}>
              <span className="alert-dot" />
              <Icon size={15} className="alert-cat-icon" />
              <div className="alert-body">
                <div className="alert-title">{it.title}</div>
                <div className="alert-detail">
                  {it.detail}
                  {it.alert_date && <span className="alert-date"> · {formatJalali(it.alert_date)}</span>}
                </div>
              </div>
              {it.amount && <div className="alert-amount">{fa(it.amount)}</div>}
            </li>
          )
        })}
      </ul>
      <Pager page={page} pageCount={pageCount} onChange={setPage} />
    </div>
  )
}
