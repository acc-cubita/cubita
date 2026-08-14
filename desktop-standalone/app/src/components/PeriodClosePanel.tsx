import { useEffect, useState } from 'react'
import { Lock, RefreshCw } from 'lucide-react'
import { createPeriodClose, fetchPeriodCloses, type FiscalPeriodCloseRecord } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

export function PeriodClosePanel({ token }: { token: string }) {
  const [closingDate, setClosingDate] = useState(todayIso())
  const [notes, setNotes] = useState('')
  const [closes, setCloses] = useState<FiscalPeriodCloseRecord[]>([])
  const [message, setMessage] = useState<string | null>(null)

  async function refresh() {
    try {
      setCloses(await fetchPeriodCloses(token))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const latestClose = closes[0]

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)

    const confirmed = window.confirm(
      `با بستن دوره تا تاریخ ${formatJalali(closingDate)}، دیگر هیچ سند حسابداری‌ای با تاریخ برابر یا قبل از آن قابل ثبت نخواهد بود. ادامه می‌دهید؟`,
    )
    if (!confirmed) return

    try {
      const result = await createPeriodClose(token, { closing_date: closingDate, notes })
      setNotes('')
      setMessage(
        `دوره تا تاریخ ${formatJalali(result.closing_date)} بسته شد؛ سود/زیان خالص ${Number(result.net_profit).toLocaleString('fa-IR')} به سود انباشته منتقل شد.`,
      )
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard
      icon={Lock}
      title="بستن رسمی دوره مالی"
      description="حساب‌های درآمد و هزینه تا این تاریخ صفر و سود/زیان خالص به سود انباشته منتقل می‌شود؛ پس از آن ثبت سند در این بازه قفل می‌شود."
      actions={
        <button onClick={() => void refresh()}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      {latestClose && (
        <p className="hint">
          آخرین دوره‌ی بسته‌شده تا تاریخ {formatJalali(latestClose.closing_date)} است؛ تاریخ بستن جدید باید بعد از آن باشد.
        </p>
      )}
      <form className="invoice-form" onSubmit={handleSubmit}>
        <label>
          بستن تا تاریخ
          <JalaliDatePicker value={closingDate} onChange={setClosingDate} />
        </label>
        <label>
          یادداشت
          <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary">
            <Lock size={14} /> بستن دوره
          </button>
        </div>
        {message && <div className="hint">{message}</div>}
      </form>

      {closes.length === 0 ? (
        <EmptyState icon={Lock} text="هنوز هیچ دوره‌ای بسته نشده." />
      ) : (
        <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>تاریخ بستن</th>
              <th>سود/زیان خالص</th>
              <th>یادداشت</th>
            </tr>
          </thead>
          <tbody>
            {closes.map((c) => (
              <tr key={c.id}>
                <td>{formatJalali(c.closing_date)}</td>
                <td>{Number(c.net_profit).toLocaleString('fa-IR')}</td>
                <td>{c.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
    </SectionCard>
  )
}
