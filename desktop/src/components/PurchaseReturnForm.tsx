import { Undo2, Save, RefreshCw, Printer } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { ReturnableTable } from './SalesReturnForm'
import { formatJalali } from '../lib/jalali'
import { usePurchaseReturnDraft, type PurchaseReturnDraft } from '../lib/purchaseReturnDraft'

/** فرمِ کلاسیکِ «برگشت از خرید» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ
 *  [usePurchaseReturnDraft]؛ جدولِ اقلامِ قابلِ برگشت با فروش مشترک است ([ReturnableTable]). */
export function PurchaseReturnForm({ token }: { token: string }) {
  const r = usePurchaseReturnDraft({ token })

  return (
    <SectionCard
      icon={Undo2}
      title="برگشت از خرید"
      description="بابت یک فاکتور خرید مشخص؛ کالا از موجودی کسر و بدهی به تأمین‌کننده کاهش می‌یابد."
      actions={
        <button onClick={() => void r.refresh()}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      {r.invoices.length === 0 ? (
        <p className="hint">هنوز هیچ فاکتور خریدی ثبت نشده است.</p>
      ) : (
        <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void r.submit()
          }}
        >
          <label>
            فاکتور خرید
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
              این فاکتور {Number(r.selectedInvoice.tax_rate).toLocaleString('fa-IR')}٪ مالیات بر ارزش افزوده دارد؛ اعتبار مالیاتیِ متناسب با مقدارِ برگشتی هم خودکار برمی‌گردد.
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

      <PurchaseReturnsList r={r} />
    </SectionCard>
  )
}

/** فهرستِ برگشت‌های خرید — مشترکِ فرم و ویزارد. */
export function PurchaseReturnsList({ r }: { r: PurchaseReturnDraft }) {
  if (r.returns.length === 0) {
    return <EmptyState icon={Undo2} text="برگشتی از خرید ثبت نشده." />
  }
  return (
    <div className="table-scroll">
      <table className="cards-on-mobile">
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
              <td className="card-title" data-label="شماره">برگشت {row.number != null ? '#' + row.number.toLocaleString('fa-IR') : '—'}</td>
              <td data-label="تاریخ">{formatJalali(row.return_date)}</td>
              <td data-label="فاکتور اصلی">{(r.invoiceNumberById.get(row.purchase_invoice_id) ?? '—')?.toLocaleString('fa-IR') ?? '—'}</td>
              <td data-label="خالص">{Number(row.total_amount).toLocaleString('fa-IR')}</td>
              <td data-label="مالیات">{Number(row.tax_amount).toLocaleString('fa-IR')}</td>
              <td data-label="جمع کل">{(Number(row.total_amount) + Number(row.tax_amount)).toLocaleString('fa-IR')}</td>
              <td className="card-actions" data-label="عملیات">
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
