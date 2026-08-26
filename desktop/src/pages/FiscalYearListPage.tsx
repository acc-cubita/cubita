import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowDownToLine,
  CalendarRange,
  CheckCircle2,
  Lock,
  RefreshCw,
  Star,
  Trash2,
} from 'lucide-react'
import {
  activateFiscalYear,
  carryForwardFiscalYear,
  closeFiscalYear,
  deleteFiscalYear,
  fetchFiscalYears,
  type FiscalYearRecord,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { formatJalali } from '../lib/jalali'

/**
 * فهرستِ سال‌های مالی — نیمه‌ی «دیدن و مدیریت‌کردن».
 *
 * صفحه‌ی «سال مالی» فقط دوره می‌سازد؛ کارِ روی دوره‌ی موجود (جاری‌کردن، افتتاحیه،
 * بستن، حذف) این‌جاست، چون هر کنش به یک ردیفِ مشخص گره خورده.
 *
 * ترتیبِ اجباریِ افتتاحیه/اختتامیه را بک‌اند تضمین می‌کند؛ این‌جا فقط دکمه‌ای که
 * معنا ندارد اصلاً نشان داده نمی‌شود.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')

/** طولِ دوره به روز — شاملِ هر دو سرِ بازه. */
const spanDays = (start: string, end: string) =>
  Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000) + 1

export function FiscalYearListPage({ token }: { token: string }) {
  const [years, setYears] = useState<FiscalYearRecord[] | null>(null)
  const [message, setMessage] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    try {
      setYears(await fetchFiscalYears(token))
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function run(action: () => Promise<string>) {
    setBusy(true)
    setMessage(null)
    try {
      setMessage({ text: await action(), kind: 'ok' })
      await refresh()
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  function handleClose(year: FiscalYearRecord) {
    const ok = window.confirm(
      `با بستن «${year.title}»، حساب‌های درآمد و هزینه‌ی این دوره صفر و سود/زیان به سود انباشته منتقل می‌شود. ` +
        'پس از آن هیچ سندی با تاریخِ داخلِ این دوره قابل ثبت نیست. ادامه می‌دهید؟',
    )
    if (!ok) return
    void run(async () => {
      const closed = await closeFiscalYear(token, year.id)
      return closed.closing_entry_id
        ? `«${closed.title}» بسته شد و سند اختتامیه ثبت شد.`
        : `«${closed.title}» بسته شد. این دوره فعالیت درآمد/هزینه‌ای نداشت، پس سند اختتامیه لازم نشد.`
    })
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={CalendarRange}
        title="سال‌های مالی"
        description="دوره‌های تعریف‌شده و کارهایی که روی هرکدام می‌شود انجام داد: جاری‌کردن، افتتاحیه، بستن و حذف."
      />

      {message && (
        <div className={`fy-note ${message.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {message.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{message.text}</div>
        </div>
      )}

      <SectionCard
        icon={CalendarRange}
        title="دوره‌های تعریف‌شده"
        description="افتتاحیه فقط وقتی ممکن است که سالِ قبل بسته شده باشد؛ بستنِ هر سال هم به بسته‌بودنِ سال‌های قدیمی‌تر نیاز دارد."
        actions={
          <button type="button" onClick={() => void refresh()} disabled={busy}>
            <RefreshCw size={13} /> به‌روزرسانی
          </button>
        }
      >
        {years == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : years.length === 0 ? (
          <EmptyState icon={CalendarRange} text="هنوز سال مالی‌ای ساخته نشده. از «تنظیمات ← سال مالی» بسازید." />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>بازه</th>
                  <th>طول</th>
                  <th>وضعیت</th>
                  <th>اسناد</th>
                  <th>افتتاحیه</th>
                  <th>اختتامیه</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {years.map((y) => {
                  const closed = y.status === 'closed'
                  return (
                    <tr key={y.id}>
                      <td className="card-title" data-label="نام">
                        {y.title}
                        {y.is_active && <span className="fy-badge fy-badge--active">جاری</span>}
                      </td>
                      <td data-label="بازه">
                        {formatJalali(y.start_date)} تا {formatJalali(y.end_date)}
                      </td>
                      <td data-label="طول">{fa(spanDays(y.start_date, y.end_date))} روز</td>
                      <td data-label="وضعیت">
                        <span className={`fy-badge ${closed ? 'fy-badge--closed' : 'fy-badge--open'}`}>
                          {closed ? 'بسته' : 'باز'}
                        </span>
                      </td>
                      <td data-label="اسناد">{fa(y.entry_count)}</td>
                      <td data-label="افتتاحیه">{y.opening_entry_id ? 'ثبت شده' : '—'}</td>
                      <td data-label="اختتامیه">{y.closing_entry_id ? 'ثبت شده' : '—'}</td>
                      <td data-label="عملیات">
                        <div className="fy-actions">
                          {!closed && !y.is_active && (
                            <button
                              type="button"
                              disabled={busy}
                              title="این سال، سال جاری شود"
                              onClick={() =>
                                void run(async () => {
                                  const r = await activateFiscalYear(token, y.id)
                                  return `«${r.title}» سال جاری شد.`
                                })
                              }
                            >
                              <Star size={13} /> جاری
                            </button>
                          )}
                          {!closed && !y.opening_entry_id && (
                            <button
                              type="button"
                              disabled={busy}
                              title="انتقال مانده‌ی حساب‌های دائمی از سال قبل"
                              onClick={() =>
                                void run(async () => {
                                  const res = await carryForwardFiscalYear(token, y.id)
                                  return `سند افتتاحیه‌ی «${y.title}» با ${fa(res.line_count)} ردیف ثبت شد.`
                                })
                              }
                            >
                              <ArrowDownToLine size={13} /> افتتاحیه
                            </button>
                          )}
                          {!closed && (
                            <button type="button" onClick={() => handleClose(y)} disabled={busy}>
                              <Lock size={13} /> بستن
                            </button>
                          )}
                          {!closed && y.entry_count === 0 && (
                            <button
                              type="button"
                              className="btn-danger"
                              disabled={busy}
                              onClick={() => {
                                if (!window.confirm(`«${y.title}» حذف شود؟`)) return
                                void run(async () => {
                                  await deleteFiscalYear(token, y.id)
                                  return `«${y.title}» حذف شد.`
                                })
                              }}
                            >
                              <Trash2 size={13} /> حذف
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
