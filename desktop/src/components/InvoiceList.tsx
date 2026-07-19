import { useEffect, useState } from 'react'
import { Ban, FileText, Printer } from 'lucide-react'
import {
  can,
  fetchPurchaseInvoices,
  fetchSalesInvoices,
  printPurchaseInvoice,
  printSalesInvoice,
  voidPurchaseInvoice,
  voidSalesInvoice,
  type MeResponse,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { formatJalali } from '../lib/jalali'

type Row = {
  id: string
  number: number | null
  invoice_date: string
  description: string
  total_amount: string
  voided_at: string | null
  void_reason: string
}

/** فهرست فاکتورها با امکان چاپ و ابطال.
 *
 * تا امروز فاکتور ثبت‌شده هیچ‌جا فهرست نمی‌شد و هیچ کاری نمی‌شد رویش کرد — نه
 * چاپ، نه تصحیح. یعنی اشتباهِ ثبت‌شده دائمی بود.
 */
export function InvoiceList({ token, me, kind }: { token: string; me: MeResponse; kind: 'sales' | 'purchase' }) {
  const isSales = kind === 'sales'
  const [rows, setRows] = useState<Row[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const canVoid = can(me, 'invoices', 'delete')

  async function refresh() {
    try {
      const data = isSales ? await fetchSalesInvoices(token) : await fetchPurchaseInvoices(token)
      setRows(data as unknown as Row[])
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [token, kind])

  async function handlePrint(id: string) {
    setMessage(null)
    try {
      await (isSales ? printSalesInvoice(token, id) : printPurchaseInvoice(token, id))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleVoid(row: Row) {
    // دلیل اجباری است و سرور هم آن را الزام می‌کند؛ اینجا فقط زودتر پرسیده می‌شود
    // تا کاربر بعد از یک رفت‌وبرگشت شبکه پیام خطا نگیرد.
    const reason = window.prompt(
      `ابطال ${isSales ? 'فاکتور فروش' : 'فاکتور خرید'} شماره ${row.number}؟\n\n` +
        'فاکتور پاک نمی‌شود؛ یک سند معکوس ثبت می‌شود و اثر مالی و انباری‌اش برمی‌گردد.\n' +
        'دلیل ابطال:',
    )
    if (reason === null) return
    if (reason.trim().length < 3) {
      setMessage('دلیل ابطال باید نوشته شود.')
      return
    }

    setBusy(true)
    setMessage(null)
    try {
      const res = await (isSales
        ? voidSalesInvoice(token, row.id, reason)
        : voidPurchaseInvoice(token, row.id, reason))
      setMessage(`فاکتور باطل شد. سند معکوس شماره ${res.reversal_entry_number} ثبت شد.`)
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'ابطال ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={FileText}
      title={isSales ? 'فاکتورهای فروش' : 'فاکتورهای خرید'}
      description="برای اصلاح اشتباه، فاکتور را باطل کنید — حذف نمی‌شود و سند معکوسش ثبت می‌گردد."
    >
      {message && <div className="hint">{message}</div>}

      {rows == null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <EmptyState icon={FileText} text="هنوز فاکتوری ثبت نشده." />
      ) : (
        <table>
          <thead>
            <tr>
              <th>شماره</th>
              <th>تاریخ</th>
              <th>شرح</th>
              <th>مبلغ</th>
              <th>وضعیت</th>
              <th>عملیات</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} style={row.voided_at ? { opacity: 0.55 } : undefined}>
                <td>{row.number ?? '—'}</td>
                <td>{formatJalali(row.invoice_date)}</td>
                <td>{row.description || '—'}</td>
                <td>{Number(row.total_amount).toLocaleString('fa-IR')}</td>
                <td>
                  {row.voided_at ? (
                    <span title={row.void_reason}>باطل شده</span>
                  ) : (
                    'معتبر'
                  )}
                </td>
                <td>
                  <div className="check-actions">
                    <button type="button" onClick={() => void handlePrint(row.id)}>
                      <Printer size={13} /> چاپ
                    </button>
                    {canVoid && !row.voided_at && (
                      <button
                        type="button"
                        className="icon-btn-danger"
                        disabled={busy}
                        onClick={() => void handleVoid(row)}
                      >
                        <Ban size={13} /> ابطال
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionCard>
  )
}
