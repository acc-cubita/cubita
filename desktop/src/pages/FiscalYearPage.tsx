import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  CalendarRange,
  CheckCircle2,
  Lock,
  Plus,
  RefreshCw,
  Sparkles,
  Star,
  Trash2,
  ArrowDownToLine,
} from 'lucide-react'
import {
  activateFiscalYear,
  carryForwardFiscalYear,
  closeFiscalYear,
  createFiscalYear,
  deleteFiscalYear,
  fetchFiscalYearSuggestion,
  fetchFiscalYears,
  type FiscalYearRecord,
  type FiscalYearSuggestion,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { formatJalali, isoToJalali, todayIso } from '../lib/jalali'

/**
 * سال مالی — تعریفِ دوره‌ی رسمیِ حسابداری.
 *
 * این صفحه سه کارِ متفاوت را که به‌هم زنجیر شده‌اند در یک جا جمع می‌کند:
 *  ۱. **ساختنِ دوره** با بازه‌ی دقیق (پیشنهادِ خودکارِ ۱ فروردین تا آخرِ اسفند، با
 *     محاسبه‌ی کبیسه — نه فرضِ ۲۹ اسفند).
 *  ۲. **افتتاحیه**: آوردنِ مانده‌ی حساب‌های دائمیِ سالِ قبل به این سال.
 *  ۳. **اختتامیه**: صفرکردنِ حساب‌های موقت و قفلِ دوره.
 *
 * ترتیب اجباری است و بک‌اند آن را تضمین می‌کند؛ این‌جا فقط همان ترتیب *دیده* می‌شود تا
 * کاربر پیش از کلیک بداند چرا دکمه‌ای غیرفعال است.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')

/** طولِ دوره به روز — شاملِ هر دو سرِ بازه. */
const spanDays = (start: string, end: string) =>
  Math.round((Date.parse(end) - Date.parse(start)) / 86_400_000) + 1

export function FiscalYearPage({ token }: { token: string }) {
  const [years, setYears] = useState<FiscalYearRecord[]>([])
  const [suggestion, setSuggestion] = useState<FiscalYearSuggestion | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [title, setTitle] = useState('')
  const [startDate, setStartDate] = useState(todayIso())
  const [endDate, setEndDate] = useState(todayIso())
  const [notes, setNotes] = useState('')
  const [activate, setActivate] = useState(true)

  async function refresh() {
    try {
      const [list, next] = await Promise.all([
        fetchFiscalYears(token),
        fetchFiscalYearSuggestion(token),
      ])
      setYears(list)
      setSuggestion(next)
      // فرمِ خالی با پیشنهاد پر می‌شود تا حالتِ عادی یک کلیک باشد، نه تایپِ سه فیلد.
      setTitle((t) => t || next.title)
      setStartDate((d) => (d === todayIso() ? next.start_date : d))
      setEndDate((d) => (d === todayIso() ? next.end_date : d))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
    // فقط بارِ اول؛ بقیه‌ی به‌روزرسانی‌ها پس از هر عملیات دستی انجام می‌شود.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  /** هر عملیاتِ سرور را با پیام/خطای یکسان و قفلِ دکمه اجرا می‌کند. */
  async function run(action: () => Promise<string>) {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      setMessage(await action())
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  function applySuggestion() {
    if (!suggestion) return
    setTitle(suggestion.title)
    setStartDate(suggestion.start_date)
    setEndDate(suggestion.end_date)
  }

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    void run(async () => {
      const created = await createFiscalYear(token, {
        title: title.trim(),
        start_date: startDate,
        end_date: endDate,
        notes,
        activate,
      })
      setNotes('')
      return `«${created.title}» ساخته شد — از ${formatJalali(created.start_date)} تا ${formatJalali(created.end_date)}.`
    })
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

  function handleCarryForward(year: FiscalYearRecord) {
    void run(async () => {
      const res = await carryForwardFiscalYear(token, year.id)
      return `سند افتتاحیه‌ی «${year.title}» با ${fa(res.line_count)} ردیف ثبت شد.`
    })
  }

  function handleDelete(year: FiscalYearRecord) {
    if (!window.confirm(`«${year.title}» حذف شود؟`)) return
    void run(async () => {
      await deleteFiscalYear(token, year.id)
      return `«${year.title}» حذف شد.`
    })
  }

  const active = years.find((y) => y.is_active) ?? null
  const days = spanDays(startDate, endDate)
  const startJy = isoToJalali(startDate).jy

  return (
    <>
      <PageHeader
        icon={CalendarRange}
        title="سال مالی"
        description="تعریفِ دوره‌ی رسمیِ حسابداری، انتقالِ مانده‌ی سال قبل (افتتاحیه) و بستنِ سال (اختتامیه)."
      />

      {years.length === 0 ? (
        <div className="fy-note fy-note--warn">
          <AlertTriangle size={16} />
          <div>
            <strong>هنوز هیچ سال مالی‌ای تعریف نشده.</strong>
            <p>
              تا وقتی سال مالی تعریف نکنید، ثبتِ سند با هر تاریخی آزاد است. با ساختنِ اولین سال مالی،
              از آن پس هر سندی باید تاریخش داخلِ یکی از سال‌های مالیِ بازِ تعریف‌شده باشد.
            </p>
          </div>
        </div>
      ) : (
        <div className="fy-note">
          <CheckCircle2 size={16} />
          <div>
            {active ? (
              <>
                <strong>سال مالی جاری: {active.title}</strong>
                <p>
                  از {formatJalali(active.start_date)} تا {formatJalali(active.end_date)} —{' '}
                  {fa(spanDays(active.start_date, active.end_date))} روز، {fa(active.entry_count)} سند ثبت‌شده.
                </p>
              </>
            ) : (
              <>
                <strong>هیچ سالی جاری نیست.</strong>
                <p>یکی از سال‌های باز را «جاری» کنید تا مرجعِ دوره‌ی کاری مشخص شود.</p>
              </>
            )}
          </div>
        </div>
      )}

      {message && <div className="fy-note fy-note--ok"><CheckCircle2 size={16} /><div>{message}</div></div>}
      {error && <div className="fy-note fy-note--err"><AlertTriangle size={16} /><div>{error}</div></div>}

      <SectionCard
        icon={Plus}
        title="سال مالی جدید"
        description="بازه را دقیق وارد کنید؛ سال‌های مالی نباید با هم هم‌پوشانی داشته باشند."
        actions={
          <button onClick={() => void refresh()} disabled={busy}>
            <RefreshCw size={13} /> به‌روزرسانی
          </button>
        }
      >
        {suggestion && (
          <button type="button" className="fy-suggest" onClick={applySuggestion}>
            <Sparkles size={14} />
            <span>
              پیشنهاد: <strong>{suggestion.title}</strong> — از {formatJalali(suggestion.start_date)} تا{' '}
              {formatJalali(suggestion.end_date)} ({fa(suggestion.days)} روز
              {suggestion.is_leap ? '، سال کبیسه' : ''})
            </span>
          </button>
        )}

        <form className="invoice-form" onSubmit={handleCreate}>
          <label>
            نام سال مالی
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={`سال مالی ${startJy}`}
              required
            />
          </label>
          <label>
            شروع دوره
            <JalaliDatePicker value={startDate} onChange={setStartDate} />
          </label>
          <label>
            پایان دوره
            <JalaliDatePicker value={endDate} onChange={setEndDate} />
          </label>
          <label>
            یادداشت
            <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>

          <div className="fy-form-meta">
            {days > 0 ? (
              <span>
                طول دوره: <strong>{fa(days)}</strong> روز
                {days > 550 && ' — بیشتر از سقفِ مجاز (۵۵۰ روز)'}
              </span>
            ) : (
              <span>تاریخ پایان باید بعد از تاریخ شروع باشد.</span>
            )}
            <label className="fy-check">
              <input type="checkbox" checked={activate} onChange={(e) => setActivate(e.target.checked)} />
              این سال، سال مالی جاری شود
            </label>
          </div>

          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || days <= 0}>
              <Plus size={14} /> ساختِ سال مالی
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard
        icon={CalendarRange}
        title="سال‌های مالی"
        description="افتتاحیه فقط وقتی ممکن است که سالِ قبل بسته شده باشد؛ بستنِ هر سال هم به بسته‌بودنِ سال‌های قدیمی‌تر نیاز دارد."
      >
        {years.length === 0 ? (
          <EmptyState icon={CalendarRange} text="هنوز سال مالی‌ای ساخته نشده." />
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
                              onClick={() => void run(async () => {
                                const r = await activateFiscalYear(token, y.id)
                                return `«${r.title}» سال جاری شد.`
                              })}
                              disabled={busy}
                              title="این سال، سال جاری شود"
                            >
                              <Star size={13} /> جاری
                            </button>
                          )}
                          {!closed && !y.opening_entry_id && (
                            <button
                              type="button"
                              onClick={() => handleCarryForward(y)}
                              disabled={busy}
                              title="انتقال مانده‌ی حساب‌های دائمی از سال قبل"
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
                              onClick={() => handleDelete(y)}
                              disabled={busy}
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
    </>
  )
}
