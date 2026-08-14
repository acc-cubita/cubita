import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../../electron.d'
import type { PurchaseInvoiceRecord } from '../../api'
import { usePurchaseInvoiceDraft, type PurchaseInvoiceDraft } from '../../lib/purchaseInvoiceDraft'
import { NumberInput } from '../NumberInput'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { ItemPicker } from '../ItemPicker'
import { QuickItemForm } from '../QuickItemForm'
import { TaskFlow, type WizardStep } from './TaskFlow'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

/** ویزاردِ «ثبت فاکتور خرید» — همان منطقِ فرمِ کلاسیک ([usePurchaseInvoiceDraft]) در چهار
 *  مرحله + پیش‌نمایشِ زنده. ساختِ سریعِ کالا (QuickItemForm) هم پشتیبانی می‌شود. */
export function PurchaseInvoiceWizard({
  token,
  warehouses,
  items,
  onQueued,
  prefill,
  onPrefillConsumed,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onQueued: () => void
  prefill?: PurchaseInvoiceRecord | null
  onPrefillConsumed?: () => void
}) {
  const d = usePurchaseInvoiceDraft({ token, warehouses, items, onQueued, prefill, onPrefillConsumed })
  const [resetTick, setResetTick] = useState(0)

  if (warehouses.length === 0) {
    return (
      <section className="taskflow">
        <h2 className="taskflow-title">ثبت فاکتور خرید</h2>
        <p className="hint">قبل از ثبت فاکتور، حداقل یک انبار لازم است؛ یک‌بار «هم‌گام‌سازی» کنید.</p>
      </section>
    )
  }

  const steps: WizardStep[] = [
    {
      key: 'header',
      title: 'سربرگ و تأمین‌کننده',
      subtitle: 'انبار، تاریخ و تأمین‌کننده‌ی فاکتور را مشخص کنید.',
      canAdvance: !!d.effectiveWarehouseId,
      blockHint: 'ابتدا هم‌گام‌سازی کنید تا انبار در دسترس باشد.',
      body: <HeaderStep d={d} warehouses={warehouses} />,
    },
    {
      key: 'lines',
      title: 'اقلام',
      subtitle: 'کالاها، تعداد و بهای واحد را وارد کنید.',
      canAdvance: d.linesValid,
      blockHint: 'حداقل یک ردیف با کالا و تعداد لازم است؛ و تخفیف نباید از مبلغِ ردیف بیشتر باشد.',
      body: <LinesStep d={d} />,
    },
    {
      key: 'adjust',
      title: 'مالیات و تخفیف',
      subtitle: 'نرخِ مالیات و تخفیفِ کلِ فاکتور.',
      body: <AdjustStep d={d} />,
    },
    {
      key: 'review',
      title: 'بازبینی و ثبت',
      subtitle: 'همه‌چیز را یک‌بار مرور کنید، بعد ثبت را بزنید.',
      body: <ReviewStep d={d} items={items} warehouses={warehouses} />,
    },
  ]

  return (
    <>
      <TaskFlow
        title="ثبت فاکتور خرید"
        steps={steps}
        submitLabel="ثبت فاکتور خرید"
        submitting={d.submitting}
        message={d.message}
        resetKey={resetTick}
        preview={<LivePreview d={d} warehouses={warehouses} />}
        onSubmit={() => {
          void d.submit().then((ok) => {
            if (ok) setResetTick((t) => t + 1)
          })
        }}
      />
      {d.quickAdd && (
        <QuickItemForm
          token={token}
          initialName={d.quickAdd.name}
          onCreated={(item) => d.acceptCreatedItem(item, d.quickAdd!.lineIndex)}
          onClose={() => d.setQuickAdd(null)}
        />
      )}
    </>
  )
}

function HeaderStep({ d, warehouses }: { d: PurchaseInvoiceDraft; warehouses: WarehouseCache[] }) {
  return (
    <div className="invoice-form">
      <label>
        انبار
        <select value={d.effectiveWarehouseId} onChange={(e) => d.setWarehouseId(e.target.value)}>
          {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
        </select>
      </label>
      <label>
        تاریخ فاکتور
        <JalaliDatePicker value={d.invoiceDate} onChange={d.setInvoiceDate} />
      </label>
      {d.costCenters.length > 0 && (
        <label>
          مرکز هزینه/پروژه (اختیاری)
          <select value={d.costCenterId} onChange={(e) => d.setCostCenterId(e.target.value)}>
            <option value="">— بدون مرکز —</option>
            {d.costCenters.map((c) => (<option key={c.id} value={c.id}>{c.code ? `${c.code} — ${c.name}` : c.name}</option>))}
          </select>
        </label>
      )}
      {d.contacts.length > 0 && (
        <label>
          تأمین‌کننده (اختیاری)
          <select value={d.contactId} onChange={(e) => d.setContactId(e.target.value)}>
            <option value="">— بدون تأمین‌کننده —</option>
            {d.contacts.map((c) => (<option key={c.id} value={c.id}>{c.name}</option>))}
          </select>
        </label>
      )}
      {d.currencies.length > 0 && (
        <div className="field-row">
          <label>
            ارز فاکتور
            <select value={d.currencyCode} onChange={(e) => d.setCurrencyCode(e.target.value)}>
              <option value="">ریال (پایه)</option>
              {d.currencies.map((c) => (<option key={c.id} value={c.code}>{c.code} — {c.name}</option>))}
            </select>
          </label>
          {d.currencyCode && (
            <label>
              نرخ برابری (۱ {d.currencyCode} = ؟ ریال)
              <NumberInput allowDecimal value={d.exchangeRate} onChange={d.setExchangeRate} />
            </label>
          )}
        </div>
      )}
    </div>
  )
}

function LinesStep({ d }: { d: PurchaseInvoiceDraft }) {
  return (
    <>
      <div className="table-scroll">
        <table className="invoice-lines">
          <thead>
            <tr><th>کالا</th><th>تعداد</th><th>بهای واحد</th><th>تخفیف</th><th>مبلغ</th><th></th></tr>
          </thead>
          <tbody>
            {d.lines.map((line, i) => (
              <tr key={i}>
                <td data-label="کالا">
                  <ItemPicker
                    items={d.pickItems}
                    value={line.itemId}
                    onChange={(id) => d.updateLine(i, { itemId: id })}
                    onCreateNew={(name) => d.setQuickAdd({ lineIndex: i, name })}
                  />
                </td>
                <td data-label="تعداد">
                  <div className="qty-with-unit">
                    <NumberInput allowDecimal value={line.qty} onChange={(v) => d.updateLine(i, { qty: v })} />
                    {(() => { const u = d.unitOf(line.itemId); return u ? <span className="unit-suffix">{u}</span> : null })()}
                  </div>
                </td>
                <td data-label="بهای واحد">
                  <NumberInput
                    value={line.unitCost}
                    onChange={(v) => d.updateLine(i, { unitCost: v })}
                    title={(() => { const u = d.unitOf(line.itemId); return u ? `بهای هر ${u}` : 'بهای واحد' })()}
                  />
                </td>
                <td data-label="تخفیف">
                  <NumberInput value={line.discount} onChange={(v) => d.updateLine(i, { discount: v })} placeholder="۰" />
                </td>
                <td data-label="مبلغ">
                  <span className={`line-amount${line.itemId ? '' : ' muted'}`}>
                    {line.itemId
                      ? Math.max((Number(line.qty) || 0) * (Number(line.unitCost) || 0) - (Number(line.discount) || 0), 0).toLocaleString('fa-IR')
                      : '—'}
                  </span>
                </td>
                <td>
                  <button type="button" className="icon-btn-danger" onClick={() => d.removeLine(i)} disabled={d.lines.length === 1} aria-label="حذف ردیف">
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        <button type="button" onClick={d.addLine}>
          <Plus size={14} /> افزودن ردیف
        </button>
      </div>
    </>
  )
}

function AdjustStep({ d }: { d: PurchaseInvoiceDraft }) {
  return (
    <div className="invoice-form">
      <label>
        نرخ مالیات بر ارزش افزوده (٪)
        <NumberInput allowDecimal value={d.taxRate} onChange={d.setTaxRate} />
      </label>
      <div className="invoice-adjustments">
        <label className="adj-field">
          تخفیف کل فاکتور
          <div className="qty-with-unit">
            <NumberInput value={d.invoiceDiscount} onChange={d.setInvoiceDiscount} placeholder="۰" />
            <div className="seg-toggle">
              <button type="button" className={d.invoiceDiscountMode === 'amount' ? 'active' : ''} onClick={() => d.setInvoiceDiscountMode('amount')}>مبلغ</button>
              <button type="button" className={d.invoiceDiscountMode === 'percent' ? 'active' : ''} onClick={() => d.setInvoiceDiscountMode('percent')}>٪</button>
            </div>
          </div>
          {d.invoiceDiscountMode === 'percent' && d.invoiceDiscountAmount > 0 && (
            <span className="hint">معادل {d.invoiceDiscountAmount.toLocaleString('fa-IR')}</span>
          )}
        </label>
      </div>
    </div>
  )
}

function ReviewStep({ d, items, warehouses }: { d: PurchaseInvoiceDraft; items: ItemCache[]; warehouses: WarehouseCache[] }) {
  const supplier = d.contacts.find((c) => c.id === d.contactId)
  const warehouse = warehouses.find((w) => w.id === d.effectiveWarehouseId)
  const validLines = d.lines.filter((l) => l.itemId && Number(l.qty) > 0)
  const nameOf = (id: string) => d.pickItems.find((x) => x.id === id)?.name ?? items.find((x) => x.id === id)?.name ?? '—'
  return (
    <div className="review-step">
      <div className="review-facts">
        <div className="live-preview-row"><span>تأمین‌کننده</span><strong>{supplier?.name ?? 'بدون تأمین‌کننده'}</strong></div>
        <div className="live-preview-row"><span>انبار</span><strong>{warehouse?.name ?? '—'}</strong></div>
        <div className="live-preview-row"><span>تاریخ</span><strong>{d.invoiceDate}</strong></div>
        {d.currencyCode && <div className="live-preview-row"><span>ارز</span><strong>{d.currencyCode}</strong></div>}
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>کالا</th><th>تعداد</th><th>بهای واحد</th><th>تخفیف</th><th>مبلغ</th></tr>
          </thead>
          <tbody>
            {validLines.map((line, i) => {
              const amount = Math.max((Number(line.qty) || 0) * (Number(line.unitCost) || 0) - (Number(line.discount) || 0), 0)
              return (
                <tr key={i}>
                  <td>{nameOf(line.itemId)}</td>
                  <td>{Number(line.qty).toLocaleString('fa-IR')} {d.unitOf(line.itemId)}</td>
                  <td>{Number(line.unitCost || 0).toLocaleString('fa-IR')}</td>
                  <td>{Number(line.discount || 0).toLocaleString('fa-IR')}</td>
                  <td>{amount.toLocaleString('fa-IR')}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function LivePreview({ d, warehouses }: { d: PurchaseInvoiceDraft; warehouses: WarehouseCache[] }) {
  const supplier = d.contacts.find((c) => c.id === d.contactId)
  const warehouse = warehouses.find((w) => w.id === d.effectiveWarehouseId)
  const lineCount = d.lines.filter((l) => l.itemId && Number(l.qty) > 0).length
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ فاکتورِ خرید</p>
      <div className="live-preview-row"><span>تأمین‌کننده</span><strong>{supplier?.name ?? 'بدون تأمین‌کننده'}</strong></div>
      <div className="live-preview-row"><span>انبار</span><strong>{warehouse?.name ?? '—'}</strong></div>
      <div className="live-preview-row"><span>تاریخ</span><strong>{d.invoiceDate}</strong></div>
      <div className="live-preview-row"><span>تعداد اقلام</span><strong>{lineCount.toLocaleString('fa-IR')}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row"><span>جمع خالص</span><strong>{fa(d.total)}</strong></div>
      <div className="live-preview-row"><span>مالیات ({d.taxRateNum.toLocaleString('fa-IR')}٪)</span><strong>{fa(d.taxAmount)}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total">
        <span>قابل پرداخت</span>
        <strong>{fa(d.grandTotal)}{d.currencyCode ? ` ${d.currencyCode}` : ''}</strong>
      </div>
      {d.currencyCode && <div className="live-preview-row"><span>معادل ریالی</span><strong>{fa(d.baseGrandTotal)}</strong></div>}
    </div>
  )
}
