import { PackagePlus, Plus, Trash2, Save } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import type { PurchaseInvoiceDuplicateDraft } from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { ItemPicker } from './ItemPicker'
import { QuickItemForm } from './QuickItemForm'
import { usePurchaseInvoiceDraft } from '../lib/purchaseInvoiceDraft'
import { BlacklistBanner } from './BlacklistBanner'
import { SearchSelect } from '../components/SearchSelect'

/** فرمِ کلاسیکِ «ثبت فاکتور خرید» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ
 *  [usePurchaseInvoiceDraft] است تا با ویزاردِ نسخه‌ی جدید یک‌دست بماند. */
export function PurchaseInvoiceForm({
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
  prefill?: PurchaseInvoiceDuplicateDraft | null
  onPrefillConsumed?: () => void
}) {
  const d = usePurchaseInvoiceDraft({ token, warehouses, items, onQueued, prefill, onPrefillConsumed })

  return (
    <SectionCard icon={PackagePlus} title="ثبت فاکتور خرید">
      <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void d.submit()
          }}
        >
          <label>
            تاریخ فاکتور
            <JalaliDatePicker value={d.invoiceDate} onChange={d.setInvoiceDate} />
          </label>
          <label>
            نرخ مالیات بر ارزش افزوده (٪)
            <NumberInput allowDecimal value={d.taxRate} onChange={d.setTaxRate} />
          </label>
          {d.costCenters.length > 0 && (
            <label>
              مرکز هزینه/پروژه (اختیاری)
              <SearchSelect value={d.costCenterId} onChange={(e) => d.setCostCenterId(e.target.value)}>
                <option value="">— بدون مرکز —</option>
                {d.costCenters.map((c) => (
                  <option key={c.id} value={c.id}>{c.code ? `${c.code} — ${c.name}` : c.name}</option>
                ))}
              </SearchSelect>
            </label>
          )}
          {d.contacts.length > 0 && (
            <label>
              تأمین‌کننده
              <SearchSelect value={d.contactId} onChange={(e) => d.setContactId(e.target.value)}>
                <option value="">— انتخاب تأمین‌کننده —</option>
                {d.contacts.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </SearchSelect>
            </label>
          )}
          {d.blacklisted && <BlacklistBanner name={d.contacts.find((c) => c.id === d.contactId)?.name} />}
          <div className="field-row">
            <label>
              شماره فاکتور تأمین‌کننده
              <input value={d.supplierInvoiceNumber} onChange={(e) => d.setSupplierInvoiceNumber(e.target.value)} />
            </label>
            <label>
              شرح
              <input value={d.description} onChange={(e) => d.setDescription(e.target.value)} />
            </label>
          </div>
          {d.currencies.length > 0 && (
            <div className="field-row">
              <label>
                ارز فاکتور
                <SearchSelect value={d.currencyCode} onChange={(e) => d.setCurrencyCode(e.target.value)}>
                  <option value="">ریال (پایه)</option>
                  {d.currencies.map((c) => (
                    <option key={c.id} value={c.code}>{c.code} — {c.name}</option>
                  ))}
                </SearchSelect>
              </label>
              {d.currencyCode && (
                <label>
                  نرخ برابری (۱ {d.currencyCode} = ؟ ریال)
                  <NumberInput allowDecimal value={d.exchangeRate} onChange={d.setExchangeRate} />
                </label>
              )}
            </div>
          )}

          <div className="table-scroll">
            <table className="invoice-lines cards-on-mobile">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>تعداد</th>
                  <th>بهای واحد</th>
                  <th>تخفیف</th>
                  <th>اضافات</th>
                  <th>عوارض</th>
                  <th>شرح</th>
                  <th>مبلغ</th>
                  <th></th>
                </tr>
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
                      {line.itemId && d.priceHints[line.itemId]?.latest && (
                        <span className="hint">
                          آخرین خرید: {Number(d.priceHints[line.itemId].latest?.transaction_unit_cost).toLocaleString('fa-IR')}
                          {d.priceHints[line.itemId].supplier_latest && ` — از این تأمین‌کننده: ${Number(d.priceHints[line.itemId].supplier_latest?.transaction_unit_cost).toLocaleString('fa-IR')}`}
                        </span>
                      )}
                      {(() => {
                        const previous = Number(d.priceHints[line.itemId]?.supplier_latest?.transaction_unit_cost ?? 0)
                        const current = Number(line.unitCost || 0)
                        return previous > 0 && current > 0 && Math.abs(current - previous) / previous >= 0.1
                          ? <span className="stock-over">اختلاف قیمت با خرید قبلی این تأمین‌کننده بیش از ۱۰٪ است.</span>
                          : null
                      })()}
                    </td>
                    <td data-label="تخفیف">
                      <NumberInput value={line.discount} onChange={(v) => d.updateLine(i, { discount: v })} placeholder="۰" />
                    </td>
                    <td data-label="اضافات"><NumberInput value={line.addition ?? ''} onChange={(v) => d.updateLine(i, { addition: v })} placeholder="۰" /></td>
                    <td data-label="عوارض"><NumberInput value={line.dutyAmount ?? ''} onChange={(v) => d.updateLine(i, { dutyAmount: v })} placeholder="۰" /></td>
                    <td data-label="شرح"><input value={line.description ?? ''} onChange={(e) => d.updateLine(i, { description: e.target.value })} /></td>
                    <td data-label="مبلغ">
                      <span className={`line-amount${line.itemId ? '' : ' muted'}`}>
                        {line.itemId
                          ? Math.max((Number(line.qty) || 0) * (Number(line.unitCost) || 0) - (Number(line.discount) || 0) + (Number(line.addition) || 0) + (Number(line.dutyAmount) || 0), 0).toLocaleString('fa-IR')
                          : '—'}
                      </span>
                    </td>
                    <td className="card-actions">
                      <button type="button" className="icon-btn-danger" onClick={() => d.removeLine(i)} disabled={d.lines.length === 1} aria-label="حذف ردیف">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── تخفیفِ کلِ فاکتور ── */}
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
            <label className="adj-field">اضافات کل<NumberInput value={d.invoiceAddition} onChange={d.setInvoiceAddition} placeholder="۰" /></label>
            <label className="adj-field">عوارض کل<NumberInput value={d.dutyAmount} onChange={d.setDutyAmount} placeholder="۰" /></label>
          </div>

          <div className="invoice-form-footer">
            <button type="button" onClick={d.addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <div className="invoice-totals">
              {d.discountTotal > 0 && <span>تخفیف سطری: {d.discountTotal.toLocaleString('fa-IR')}</span>}
              {d.invoiceDiscountAmount > 0 && <span>تخفیف کل: {d.invoiceDiscountAmount.toLocaleString('fa-IR')}</span>}
              {d.additionTotal > 0 && <span>اضافات: {d.additionTotal.toLocaleString('fa-IR')}</span>}
              {d.dutiesTotal > 0 && <span>عوارض: {d.dutiesTotal.toLocaleString('fa-IR')}</span>}
              <span>جمع خالص: {d.total.toLocaleString('fa-IR')}</span>
              <span>مالیات ({d.taxRateNum.toLocaleString('fa-IR')}٪): {d.taxAmount.toLocaleString('fa-IR')}</span>
              <span className="invoice-total">
                قابل پرداخت: {d.grandTotal.toLocaleString('fa-IR')}
                {d.currencyCode ? ` ${d.currencyCode}` : ''}
              </span>
              {d.currencyCode && <span className="hint">معادل ریالی: {d.baseGrandTotal.toLocaleString('fa-IR')}</span>}
            </div>
            <button type="submit" className="btn-primary" disabled={d.submitting}><Save size={14} /> ثبت فاکتور خرید</button>
          </div>

          {d.message && <div className="hint">{d.message}</div>}
        </form>

      {d.quickAdd && (
        <QuickItemForm
          token={token}
          initialName={d.quickAdd.name}
          onCreated={(item) => d.acceptCreatedItem(item, d.quickAdd!.lineIndex)}
          onClose={() => d.setQuickAdd(null)}
        />
      )}
    </SectionCard>
  )
}
