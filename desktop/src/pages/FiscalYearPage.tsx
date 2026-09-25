import { useEffect, useState } from 'react'
import { AlertTriangle, CalendarRange, CheckCircle2, Plus, RefreshCw, Sparkles } from 'lucide-react'
import {
  createFiscalYear,
  fetchFiscalYearSuggestion,
  fetchFiscalYears,
  type FiscalYearRecord,
  type FiscalYearSuggestion,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { formatJalali, isoToJalali, todayIso } from '../lib/jalali'

/**
 * سال مالی — نیمه‌ی «ساختن».
 *
 * وضعیتِ سالِ جاری + فرمِ ساختِ دوره‌ی تازه، با پیشنهادِ خودکارِ ۱ فروردین تا آخرِ اسفند
 * (با محاسبه‌ی کبیسه، نه فرضِ ۲۹ اسفند).
 *
 * کارِ روی دوره‌ی موجود — جاری‌کردن، افتتاحیه، بستن، حذف — در صفحه‌ی «سال‌های مالی»
 * است، چون هر کنش به یک ردیفِ مشخص گره خورده و بدونِ دیدنِ آن ردیف معنا ندارد.
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




  const active = years.find((y) => y.is_active) ?? null
  const days = spanDays(startDate, endDate)
  const startJy = isoToJalali(startDate).jy

  return (
    // پوسته‌ی کارتیِ صفحه — مثلِ بقیه‌ی صفحه‌های تنظیمات. بدونِ آن، محتوا مستقیم روی
    // پس‌زمینه‌ی برنامه شناور می‌ماند و هیچ سطحِ سفیدی زیرش نیست.
    <div className="page panels">
      <PageHeader
        icon={CalendarRange}
        title="سال مالی"
        description="تعریفِ دوره‌ی رسمیِ حسابداری و سالِ جاری. بستنِ سود و زیان، اختتامیه و افتتاحیه در «حسابداری ← پایان دوره» است."
      />

      {/* بنرها یک پنلِ مشترک می‌گیرند و *نوه‌ی* پوسته می‌مانند، نه فرزندِ مستقیم:
          قانونِ `.page.panels > *` پس‌زمینه‌ی هر فرزند را به سطحِ خنثی می‌برد و
          تخصصش از `.fy-note--ok/warn/err` بیشتر است، پس رنگِ وضعیت را می‌خورد. */}
      <section className="fy-status">
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
      </section>

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
    </div>
  )
}
