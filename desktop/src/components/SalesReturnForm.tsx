import { useEffect, useState } from 'react'
import { Undo2, Save, RefreshCw } from 'lucide-react'
import type { ItemCache } from '../electron.d'
import {
  createSalesReturn,
  fetchSalesInvoices,
  fetchSalesReturns,
  type SalesInvoiceRecord,
  type SalesReturnRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

export function SalesReturnForm({ token, items }: { token: string; items: ItemCache[] }) {
  const [invoices, setInvoices] = useState<SalesInvoiceRecord[]>([])
  const [returns, setReturns] = useState<SalesReturnRecord[]>([])
  const [invoiceId, setInvoiceId] = useState('')
  const [returnDate, setReturnDate] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [qtyByItem, setQtyByItem] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)

  const itemsById = new Map(items.map((i) => [i.id, i]))
  const selectedInvoice = invoices.find((inv) => inv.id === invoiceId) ?? null

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

  useEffect(() => {
    setQtyByItem({})
  }, [invoiceId])

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
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

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

          {selectedInvoice && (
            <table className="invoice-lines">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>تعداد فروخته‌شده</th>
                  <th>مقدار برگشتی</th>
                </tr>
              </thead>
              <tbody>
                {selectedInvoice.lines.map((line) => (
                  <tr key={line.id}>
                    <td>{itemsById.get(line.item_id)?.name ?? line.item_id}</td>
                    <td>{Number(line.qty).toLocaleString('fa-IR')}</td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={qtyByItem[line.item_id] ?? ''}
                        onChange={(e) => setQtyByItem((prev) => ({ ...prev, [line.item_id]: e.target.value }))}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary">
              <Save size={14} /> ثبت برگشت
            </button>
          </div>
          {message && <div className="hint">{message}</div>}
        </form>
      )}

      {returns.length === 0 ? (
        <EmptyState icon={Undo2} text="برگشتی از فروش ثبت نشده." />
      ) : (
        <table>
          <thead>
            <tr>
              <th>شماره</th>
              <th>تاریخ</th>
              <th>مبلغ</th>
            </tr>
          </thead>
          <tbody>
            {returns.map((r) => (
              <tr key={r.id}>
                <td>{r.number != null ? r.number.toLocaleString('fa-IR') : '—'}</td>
                <td>{formatJalali(r.return_date)}</td>
                <td>{Number(r.total_amount).toLocaleString('fa-IR')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionCard>
  )
}
