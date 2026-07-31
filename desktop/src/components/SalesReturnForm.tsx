import { useEffect, useState } from 'react'
import { Undo2, Save, RefreshCw, Printer } from 'lucide-react'
import {
  createSalesReturn,
  fetchReturnable,
  fetchSalesInvoices,
  fetchSalesReturns,
  printSalesReturn,
  type ReturnableLine,
  type SalesInvoiceRecord,
  type SalesReturnRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

const fa = (n: number) => n.toLocaleString('fa-IR')

export function SalesReturnForm({ token }: { token: string }) {
  const [invoices, setInvoices] = useState<SalesInvoiceRecord[]>([])
  const [returns, setReturns] = useState<SalesReturnRecord[]>([])
  const [invoiceId, setInvoiceId] = useState('')
  const [returnable, setReturnable] = useState<ReturnableLine[]>([])
  const [returnDate, setReturnDate] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [qtyByItem, setQtyByItem] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const selectedInvoice = invoices.find((inv) => inv.id === invoiceId) ?? null
  // نگاشتِ شناسه‌ی فاکتور → شماره، برای ستونِ «فاکتور اصلی» در فهرستِ برگشت‌ها
  const invoiceNumberById = new Map(invoices.map((inv) => [inv.id, inv.number]))

  async function refresh() {
    try {
      const [invoiceList, returnList] = await Promise.all([fetchSalesInvoices(token), fetchSalesReturns(token)])
      setInvoices(invoiceList)
      setReturns(returnList)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  // با انتخابِ فاکتور، باقی‌ماندهٔ قابلِ برگشتِ هر کالا زنده خوانده می‌شود.
  useEffect(() => {
    setQtyByItem({})
    if (!invoiceId) {
      setReturnable([])
      return
    }
    let cancelled = false
    fetchReturnable(token, invoiceId)
      .then((rows) => !cancelled && setReturnable(rows))
      .catch(() => !cancelled && setReturnable([]))
    return () => {
      cancelled = true
    }
  }, [token, invoiceId])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)

    if (!selectedInvoice) {
      setMessage('یک فاکتور فروش انتخاب کنید.')
      return
    }
    const lines = Object.entries(qtyByItem)
      .filter(([, qty]) => Number(qty) > 0)
      .map(([itemId, qty]) => ({ item_id: itemId, qty: Number(qty) }))
    if (lines.length === 0) {
      setMessage('حداقل مقدار برگشتی یک ردیف را وارد کنید.')
      return
    }
    // بیش از باقی‌مانده را سمتِ کلاینت هم می‌گیریم تا کاربر پیش از رفت‌وبرگشت بفهمد.
    const over = lines.find((l) => {
      const r = returnable.find((x) => x.item_id === l.item_id)
      return r && l.qty > Number(r.remaining)
    })
    if (over) {
      setMessage('مقدار برگشتی نمی‌تواند از باقی‌ماندهٔ قابلِ برگشت بیشتر باشد.')
      return
    }

    setBusy(true)
    try {
      await createSalesReturn(token, {
        return_date: returnDate,
        sales_invoice_id: selectedInvoice.id,
        description,
        lines,
      })
      setQtyByItem({})
      setDescription('')
      setMessage('برگشت از فروش با موفقیت ثبت شد.')
      await refresh()
      // باقی‌مانده‌ها را هم تازه کن
      const rows = await fetchReturnable(token, selectedInvoice.id)
      setReturnable(rows)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  async function handlePrint(id: string) {
    setMessage(null)
    try {
      await printSalesReturn(token, id)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const anyReturnable = returnable.some((r) => Number(r.remaining) > 0)

  return (
    <SectionCard
      icon={Undo2}
      title="برگشت از فروش"
      description="بابت یک فاکتور فروش مشخص؛ موجودی برمی‌گردد و درآمد/بهای تمام‌شده معکوس می‌شود."
      actions={
        <button onClick={() => void refresh()}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      {invoices.length === 0 ? (
        <p className="hint">هنوز هیچ فاکتور فروشی ثبت نشده است.</p>
      ) : (
        <form className="invoice-form" onSubmit={handleSubmit}>
          <label>
            فاکتور فروش
            <select value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)}>
              <option value="">— انتخاب فاکتور —</option>
              {invoices.map((inv) => (
                <option key={inv.id} value={inv.id}>
                  شماره {inv.number ?? '—'} — {formatJalali(inv.invoice_date)} — {Number(inv.total_amount).toLocaleString('fa-IR')}
                </option>
              ))}
            </select>
          </label>
          <label>
            تاریخ برگشت
            <JalaliDatePicker value={returnDate} onChange={setReturnDate} />
          </label>
          <label>
            توضیحات
            <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>

          {selectedInvoice && Number(selectedInvoice.tax_amount) > 0 && (
            <div className="hint">
              این فاکتور {Number(selectedInvoice.tax_rate).toLocaleString('fa-IR')}٪ مالیات بر ارزش افزوده دارد؛ مالیاتِ متناسب با مقدارِ برگشتی هم خودکار برمی‌گردد.
            </div>
          )}
          {selectedInvoice && !anyReturnable && (
            <div className="hint">همه‌ی اقلامِ این فاکتور قبلاً به‌طور کامل برگشت خورده‌اند.</div>
          )}
          {selectedInvoice && returnable.length > 0 && (
            <div className="table-scroll">
            <table className="invoice-lines">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>فروخته‌شده</th>
                  <th>قبلاً برگشتی</th>
                  <th>باقی‌مانده</th>
                  <th>مقدار برگشتی</th>
                </tr>
              </thead>
              <tbody>
                {returnable.map((r) => {
                  const remaining = Number(r.remaining)
                  const entered = Number(qtyByItem[r.item_id] ?? 0)
                  const over = entered > remaining
                  return (
                    <tr key={r.item_id}>
                      <td className="entity-name">{r.item_name} {r.unit && <span className="unit-suffix">/ {r.unit}</span>}</td>
                      <td>{fa(Number(r.sold))}</td>
                      <td>{fa(Number(r.already_returned))}</td>
                      <td className={remaining > 0 ? 'stock-ok' : 'unit-suffix'}>{fa(remaining)}</td>
                      <td>
                        <div className="stock-cell">
                          <input
                            type="number"
                            min="0"
                            step="any"
                            max={remaining}
                            disabled={remaining <= 0}
                            value={qtyByItem[r.item_id] ?? ''}
                            onChange={(e) => setQtyByItem((prev) => ({ ...prev, [r.item_id]: e.target.value }))}
                          />
                          {remaining > 0 && (
                            <button type="button" className="link-like" onClick={() => setQtyByItem((prev) => ({ ...prev, [r.item_id]: String(remaining) }))}>همه</button>
                          )}
                          {over && <div className="stock-warn">بیش از باقی‌مانده</div>}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            </div>
          )}

          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !anyReturnable}>
              <Save size={14} /> ثبت برگشت
            </button>
          </div>
          {message && <div className="hint">{message}</div>}
        </form>
      )}

      {returns.length === 0 ? (
        <EmptyState icon={Undo2} text="برگشتی از فروش ثبت نشده." />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>شماره</th>
                <th>تاریخ</th>
                <th>فاکتور اصلی</th>
                <th>خالص</th>
                <th>مالیات</th>
                <th>جمع کل</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {returns.map((r) => (
                <tr key={r.id}>
                  <td>{r.number != null ? r.number.toLocaleString('fa-IR') : '—'}</td>
                  <td>{formatJalali(r.return_date)}</td>
                  <td>{(invoiceNumberById.get(r.sales_invoice_id) ?? '—')?.toLocaleString('fa-IR') ?? '—'}</td>
                  <td>{Number(r.total_amount).toLocaleString('fa-IR')}</td>
                  <td>{Number(r.tax_amount).toLocaleString('fa-IR')}</td>
                  <td>{(Number(r.total_amount) + Number(r.tax_amount)).toLocaleString('fa-IR')}</td>
                  <td>
                    <button type="button" onClick={() => void handlePrint(r.id)}>
                      <Printer size={13} /> چاپ
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}
