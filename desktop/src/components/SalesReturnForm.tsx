import type { Dispatch, SetStateAction } from 'react'
import { Undo2, Save, RefreshCw, Printer } from 'lucide-react'
import type { ReturnableLine } from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali } from '../lib/jalali'
import { useSalesReturnDraft, type SalesReturnDraft } from '../lib/salesReturnDraft'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** فرمِ کلاسیکِ «برگشت از فروش» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ
 *  [useSalesReturnDraft] است تا با ویزاردِ نسخه‌ی جدید یک‌دست بماند. */
export function SalesReturnForm({ token }: { token: string }) {
  const r = useSalesReturnDraft({ token })

  return (
    <SectionCard
      icon={Undo2}
      title="برگشت از فروش"
      description="بابت یک فاکتور فروش مشخص؛ موجودی برمی‌گردد و درآمد/بهای تمام‌شده معکوس می‌شود."
      actions={
        <button onClick={() => void r.refresh()}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      {r.invoices.length === 0 ? (
        <p className="hint">هنوز هیچ فاکتور فروشی ثبت نشده است.</p>
      ) : (
        <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void r.submit()
          }}
        >
          <label>
            فاکتور فروش
            <select value={r.invoiceId} onChange={(e) => r.setInvoiceId(e.target.value)}>
              <option value="">— انتخاب فاکتور —</option>
              {r.invoices.map((inv) => (
                <option key={inv.id} value={inv.id}>
                  شماره {inv.number ?? '—'} — {formatJalali(inv.invoice_date)} — {Number(inv.total_amount).toLocaleString('fa-IR')}
                </option>
              ))}
            </select>
          </label>
          <label>
            تاریخ برگشت
            <JalaliDatePicker value={r.returnDate} onChange={r.setReturnDate} />
          </label>
          <label>
            توضیحات
            <input type="text" value={r.description} onChange={(e) => r.setDescription(e.target.value)} />
          </label>

          {r.selectedInvoice && Number(r.selectedInvoice.tax_amount) > 0 && (
            <div className="hint">
              این فاکتور {Number(r.selectedInvoice.tax_rate).toLocaleString('fa-IR')}٪ مالیات بر ارزش افزوده دارد؛ مالیاتِ متناسب با مقدارِ برگشتی هم خودکار برمی‌گردد.
            </div>
          )}
          {r.selectedInvoice && !r.anyReturnable && (
            <div className="hint">همه‌ی اقلامِ این فاکتور قبلاً به‌طور کامل برگشت خورده‌اند.</div>
          )}
          {r.selectedInvoice && r.returnable.length > 0 && <ReturnableTable r={r} />}

          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={r.busy || !r.anyReturnable}>
              <Save size={14} /> ثبت برگشت
            </button>
          </div>
          {r.message && <div className="hint">{r.message}</div>}
        </form>
      )}

      <SalesReturnsList r={r} />
    </SectionCard>
  )
}

/** جدولِ اقلامِ قابلِ برگشت با ورودِ مقدار — مشترکِ فرم و ویزاردِ فروش و خرید (شکلِ
 *  حداقلی تا هر دو draft ساختاراً جور شوند). */
export function ReturnableTable({
  r,
}: {
  r: {
    returnable: ReturnableLine[]
    qtyByItem: Record<string, string>
    setQtyByItem: Dispatch<SetStateAction<Record<string, string>>>
  }
}) {
  return (
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
          {r.returnable.map((row) => {
            const remaining = Number(row.remaining)
            const entered = Number(r.qtyByItem[row.item_id] ?? 0)
            const over = entered > remaining
            return (
              <tr key={row.item_id}>
                <td className="entity-name" data-label="کالا">{row.item_name} {row.unit && <span className="unit-suffix">/ {row.unit}</span>}</td>
                <td data-label="فروخته‌شده">{fa(Number(row.sold))}</td>
                <td data-label="قبلاً برگشتی">{fa(Number(row.already_returned))}</td>
                <td data-label="باقی‌مانده" className={remaining > 0 ? 'stock-ok' : 'unit-suffix'}>{fa(remaining)}</td>
                <td data-label="مقدار برگشتی">
                  <div className="stock-cell">
                    <NumberInput
                      allowDecimal
                      disabled={remaining <= 0}
                      value={r.qtyByItem[row.item_id] ?? ''}
                      onChange={(v) => r.setQtyByItem((prev) => ({ ...prev, [row.item_id]: v }))}
                    />
                    {remaining > 0 && (
                      <button type="button" className="link-like" onClick={() => r.setQtyByItem((prev) => ({ ...prev, [row.item_id]: String(remaining) }))}>همه</button>
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
  )
}

/** فهرستِ برگشت‌های گذشته — مشترکِ فرم و ویزارد. */
export function SalesReturnsList({ r }: { r: SalesReturnDraft }) {
  if (r.returns.length === 0) {
    return <EmptyState icon={Undo2} text="برگشتی از فروش ثبت نشده." />
  }
  return (
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
          {r.returns.map((row) => (
            <tr key={row.id}>
              <td>{row.number != null ? row.number.toLocaleString('fa-IR') : '—'}</td>
              <td>{formatJalali(row.return_date)}</td>
              <td>{(r.invoiceNumberById.get(row.sales_invoice_id) ?? '—')?.toLocaleString('fa-IR') ?? '—'}</td>
              <td>{Number(row.total_amount).toLocaleString('fa-IR')}</td>
              <td>{Number(row.tax_amount).toLocaleString('fa-IR')}</td>
              <td>{(Number(row.total_amount) + Number(row.tax_amount)).toLocaleString('fa-IR')}</td>
              <td>
                <button type="button" onClick={() => void r.handlePrint(row.id)}>
                  <Printer size={13} /> چاپ
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
