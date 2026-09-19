import type { Dispatch, SetStateAction } from 'react'
import { Undo2, Save, RefreshCw, Printer, Ban } from 'lucide-react'
import type { ReturnableLine, SalesReturnReasonRecord } from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali } from '../lib/jalali'
import { returnableKey, useSalesReturnDraft, type SalesReturnDraft } from '../lib/salesReturnDraft'
import { SearchSelect } from '../components/SearchSelect'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** وضعیتِ مالیِ سندِ برگشت — «باطل» عمداً از «تسویه‌نشده» جداست، وگرنه کاربر
 *  دنبالِ پولی می‌گردد که اصلاً قرار نیست جابه‌جا شود. */
const RETURN_STATUS_LABELS: Record<string, string> = {
  unsettled: 'تسویه‌نشده',
  partially_settled: 'تسویهٔ جزئی',
  fully_settled: 'تسویه‌شده',
  voided: 'باطل‌شده',
}

/** فرمِ کلاسیکِ «برگشت از فروش» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ
 *  [useSalesReturnDraft] است تا با ویزاردِ نسخه‌ی جدید یک‌دست بماند. */
export function SalesReturnForm({ token }: { token: string }) {
  const r = useSalesReturnDraft({ token })

  return (
    <SectionCard
      icon={Undo2}
      title="برگشت از فروش"
      description="بابت یک فاکتور فروش مشخص؛ درآمد، مالیات و طلبِ مشتری معکوس می‌شود. کالا با «برگشت خروج انبار» برمی‌گردد — در حالتِ خودکار همان لحظه."
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
            <SearchSelect value={r.invoiceId} onChange={(e) => r.setInvoiceId(e.target.value)}>
              <option value="">— انتخاب فاکتور —</option>
              {r.invoices.map((inv) => (
                <option key={inv.id} value={inv.id}>
                  شماره {inv.number ?? '—'} — {formatJalali(inv.invoice_date)} — {Number(inv.total_amount).toLocaleString('fa-IR')}
                </option>
              ))}
            </SearchSelect>
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
    qtyByLine: Record<string, string>
    setQtyByLine: Dispatch<SetStateAction<Record<string, string>>>
    /** فقط سمتِ فروش علتِ برگشت دارد؛ برای خرید تعریف نمی‌شود و ستون نمی‌آید. */
    reasons?: SalesReturnReasonRecord[]
    reasonByLine?: Record<string, string>
    setReasonByLine?: Dispatch<SetStateAction<Record<string, string>>>
  }
}) {
  const withReasons = r.reasons !== undefined && r.setReasonByLine !== undefined
  const activeReasons = (r.reasons ?? []).filter((x) => x.is_active)
  return (
    <div className="table-scroll">
      <table className="invoice-lines cards-on-mobile">
        <thead>
          <tr>
            <th>کالا</th>
            <th>قیمت واحد</th>
            <th>فروخته‌شده</th>
            <th>قبلاً برگشتی</th>
            <th>باقی‌مانده</th>
            <th>مقدار برگشتی</th>
            {withReasons && <th>علت برگشت</th>}
          </tr>
        </thead>
        <tbody>
          {r.returnable.map((row) => {
            // کلیدْ ردیفِ فاکتور است نه کالا: یک کالا می‌تواند در یک فاکتور دو
            // ردیف با دو قیمت داشته باشد و هر کدام ماندهٔ خودش را دارد.
            const key = returnableKey(row)
            const remaining = Number(row.remaining)
            const entered = Number(r.qtyByLine[key] ?? 0)
            const over = entered > remaining
            return (
              <tr key={key}>
                <td className="entity-name" data-label="کالا">{row.item_name} {row.unit && <span className="unit-suffix">/ {row.unit}</span>}</td>
                <td className="num" data-label="قیمت واحد">{fa(Number(row.unit_price))}</td>
                <td data-label="فروخته‌شده">{fa(Number(row.sold))}</td>
                <td data-label="قبلاً برگشتی">{fa(Number(row.already_returned))}</td>
                <td data-label="باقی‌مانده" className={remaining > 0 ? 'stock-ok' : 'unit-suffix'}>{fa(remaining)}</td>
                <td data-label="مقدار برگشتی">
                  <div className="stock-cell">
                    <NumberInput
                      allowDecimal
                      disabled={remaining <= 0}
                      value={r.qtyByLine[key] ?? ''}
                      onChange={(v) => r.setQtyByLine((prev) => ({ ...prev, [key]: v }))}
                    />
                    {remaining > 0 && (
                      <button type="button" className="link-like" onClick={() => r.setQtyByLine((prev) => ({ ...prev, [key]: String(remaining) }))}>همه</button>
                    )}
                    {over && <div className="stock-warn">بیش از باقی‌مانده</div>}
                  </div>
                </td>
                {withReasons && (
                  <td data-label="علت برگشت">
                    <SearchSelect
                      value={r.reasonByLine?.[key] ?? ''}
                      disabled={remaining <= 0}
                      onChange={(e) => r.setReasonByLine?.((prev) => ({ ...prev, [key]: e.target.value }))}
                    >
                      {/* اختیاری است — نمونه‌ی مرجع هم اجباری‌اش نمی‌کند. */}
                      <option value="">—</option>
                      {activeReasons.map((reason) => (
                        <option key={reason.id} value={reason.id}>{reason.title}</option>
                      ))}
                    </SearchSelect>
                  </td>
                )}
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
      <table className="cards-on-mobile">
        <thead>
          <tr>
            <th>شماره</th>
            <th>تاریخ</th>
            <th>فاکتور اصلی</th>
            <th>جمع کل</th>
            {/* سه حقیقتِ جدا: مبلغِ برگشت، آنچه واقعاً پرداخت شده، و ماندهٔ باز.
                هیچ‌کدام ذخیره نمی‌شوند؛ سرور هر بار از منبع می‌خواندشان. */}
            <th>پرداخت‌شده</th>
            <th>ماندهٔ برگشت</th>
            <th>وضعیت</th>
            <th>عملیات</th>
          </tr>
        </thead>
        <tbody>
          {r.returns.map((row) => {
            const voided = row.voided_at != null
            return (
              <tr key={row.id} className={voided ? 'acc-row--void' : ''}>
                <td className="card-title" data-label="شماره">برگشت {row.number != null ? '#' + row.number.toLocaleString('fa-IR') : '—'}</td>
                <td data-label="تاریخ">{formatJalali(row.return_date)}</td>
                <td data-label="فاکتور اصلی">{(r.invoiceNumberById.get(row.sales_invoice_id) ?? '—')?.toLocaleString('fa-IR') ?? '—'}</td>
                <td className="num" data-label="جمع کل">{Number(row.final_amount).toLocaleString('fa-IR')}</td>
                <td className="num" data-label="پرداخت‌شده">{Number(row.settled_amount).toLocaleString('fa-IR')}</td>
                <td className="num" data-label="ماندهٔ برگشت">{Number(row.remaining_amount).toLocaleString('fa-IR')}</td>
                <td data-label="وضعیت">{RETURN_STATUS_LABELS[row.financial_status] ?? row.financial_status}</td>
                <td className="card-actions" data-label="عملیات">
                  <button type="button" onClick={() => void r.handlePrint(row.id)}>
                    <Printer size={13} /> چاپ
                  </button>
                  {!voided && (
                    <button
                      type="button"
                      className="danger"
                      disabled={r.busy}
                      onClick={() => {
                        const reason = window.prompt('دلیلِ ابطالِ این برگشت؟')
                        if (reason !== null) void r.voidReturn(row.id, reason)
                      }}
                    >
                      <Ban size={13} /> ابطال
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
