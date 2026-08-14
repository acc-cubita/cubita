import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { useSalesReturnDraft, type SalesReturnDraft } from '../../lib/salesReturnDraft'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { formatJalali } from '../../lib/jalali'
import { ReturnableTable, SalesReturnsList } from '../SalesReturnForm'
import { TaskFlow, type WizardStep } from './TaskFlow'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** ویزاردِ «برگشت از فروش» برای نسخه‌ی جدید. همان منطقِ فرمِ کلاسیک ([useSalesReturnDraft])
 *  در سه مرحله + پیش‌نمایشِ زنده؛ فهرستِ برگشت‌های گذشته زیرِ ویزارد. */
export function SalesReturnWizard({ token }: { token: string }) {
  const r = useSalesReturnDraft({ token })
  const [resetTick, setResetTick] = useState(0)

  if (r.invoices.length === 0) {
    return (
      <section className="taskflow">
        <h2 className="taskflow-title">برگشت از فروش</h2>
        <p className="hint">هنوز هیچ فاکتور فروشی ثبت نشده است.</p>
      </section>
    )
  }

  const step1Block = !r.invoiceId
    ? 'یک فاکتور فروش انتخاب کنید.'
    : !r.anyReturnable
      ? 'همه‌ی اقلامِ این فاکتور قبلاً به‌طور کامل برگشت خورده‌اند.'
      : undefined

  const steps: WizardStep[] = [
    {
      key: 'invoice',
      title: 'انتخاب فاکتور',
      subtitle: 'فاکتورِ فروشی که می‌خواهید بابتش برگشت بزنید را انتخاب کنید.',
      canAdvance: !!r.invoiceId && r.anyReturnable,
      blockHint: step1Block,
      body: <InvoiceStep r={r} />,
    },
    {
      key: 'lines',
      title: 'اقلام برگشتی',
      subtitle: 'برای هر کالا، مقدارِ برگشتی را (تا سقفِ باقی‌مانده) وارد کنید.',
      canAdvance: r.returnLinesValid,
      blockHint: 'حداقل مقدارِ یک ردیف را وارد کنید و از باقی‌مانده بیشتر نباشد.',
      body: r.returnable.length > 0 ? <ReturnableTable r={r} /> : <p className="hint">برای این فاکتور اقلامِ قابلِ برگشتی نیست.</p>,
    },
    {
      key: 'review',
      title: 'بازبینی و ثبت',
      subtitle: 'مقادیرِ برگشتی را یک‌بار مرور کنید، بعد ثبت را بزنید.',
      body: <ReviewStep r={r} />,
    },
  ]

  return (
    <>
      <TaskFlow
        title="برگشت از فروش"
        steps={steps}
        submitLabel="ثبت برگشت"
        submitting={r.busy}
        message={r.message}
        resetKey={resetTick}
        preview={<LivePreview r={r} />}
        onSubmit={() => {
          void r.submit().then((ok) => {
            if (ok) setResetTick((t) => t + 1)
          })
        }}
      />
      <section>
        <div className="section-card-header">
          <div className="section-card-heading">
            <div>
              <h2>برگشت‌های ثبت‌شده</h2>
            </div>
          </div>
          <div className="header-actions">
            <button onClick={() => void r.refresh()}>
              <RefreshCw size={13} /> به‌روزرسانی
            </button>
          </div>
        </div>
        <SalesReturnsList r={r} />
      </section>
    </>
  )
}

function InvoiceStep({ r }: { r: SalesReturnDraft }) {
  return (
    <div className="invoice-form">
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
        <div className="hint" style={{ gridColumn: '1 / -1' }}>
          این فاکتور {Number(r.selectedInvoice.tax_rate).toLocaleString('fa-IR')}٪ مالیات دارد؛ مالیاتِ متناسب با مقدارِ برگشتی هم خودکار برمی‌گردد.
        </div>
      )}
    </div>
  )
}

function ReviewStep({ r }: { r: SalesReturnDraft }) {
  const nameOf = (id: string) => r.returnable.find((x) => x.item_id === id)?.item_name ?? '—'
  const unitOf = (id: string) => r.returnable.find((x) => x.item_id === id)?.unit ?? ''
  return (
    <div className="review-step">
      <div className="review-facts">
        <div className="live-preview-row"><span>فاکتور اصلی</span><strong>شماره {r.selectedInvoice?.number ?? '—'}</strong></div>
        <div className="live-preview-row"><span>تاریخ برگشت</span><strong>{r.returnDate}</strong></div>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>کالا</th><th>مقدار برگشتی</th></tr>
          </thead>
          <tbody>
            {r.enteredLines.map((l) => (
              <tr key={l.item_id}>
                <td>{nameOf(l.item_id)}</td>
                <td>{fa(l.qty)} {unitOf(l.item_id)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function LivePreview({ r }: { r: SalesReturnDraft }) {
  const totalQty = r.enteredLines.reduce((s, l) => s + l.qty, 0)
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ برگشت</p>
      <div className="live-preview-row"><span>فاکتور اصلی</span><strong>شماره {r.selectedInvoice?.number ?? '—'}</strong></div>
      <div className="live-preview-row"><span>تاریخ برگشت</span><strong>{r.returnDate}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row"><span>تعداد ردیف</span><strong>{r.enteredLines.length.toLocaleString('fa-IR')}</strong></div>
      <div className="live-preview-row live-preview-total"><span>مجموع مقدار</span><strong>{fa(totalQty)}</strong></div>
    </div>
  )
}
