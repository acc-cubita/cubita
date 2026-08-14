import { useEffect, useRef, useState } from 'react'
import { PackagePlus, Plus, Trash2, Save } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import {
  createPurchaseInvoiceDirect,
  fetchContacts,
  fetchCostCenters,
  fetchCurrencies,
  fetchLatestRate,
  newIdempotencyKey,
  type ContactRecord,
  type CostCenterRecord,
  type Currency,
  type PurchaseInvoiceRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { ItemPicker } from './ItemPicker'
import { todayIso } from '../lib/jalali'

interface DraftLine {
  itemId: string
  qty: string
  unitCost: string
  discount: string
}

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
  /** رونوشتِ فاکتور خرید: فرم را با اقلامِ یک فاکتورِ موجود پیش‌پر می‌کند. */
  prefill?: PurchaseInvoiceRecord | null
  onPrefillConsumed?: () => void
}) {
  const [warehouseId, setWarehouseId] = useState('')
  const [invoiceDate, setInvoiceDate] = useState(todayIso())
  const [taxRate, setTaxRate] = useState('10')
  const [invoiceDiscount, setInvoiceDiscount] = useState('')
  const [invoiceDiscountMode, setInvoiceDiscountMode] = useState<'amount' | 'percent'>('amount')
  const [lines, setLines] = useState<DraftLine[]>([{ itemId: '', qty: '1', unitCost: '', discount: '' }])
  const [message, setMessage] = useState<string | null>(null)
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [costCenterId, setCostCenterId] = useState('')
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [contactId, setContactId] = useState('')
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [currencyCode, setCurrencyCode] = useState('')
  const [exchangeRate, setExchangeRate] = useState('1')

  // مراکز هزینه زنده خوانده می‌شوند؛ آفلاین که نشد, انتخاب‌گر پنهان و فاکتور بدون مرکز است.
  useEffect(() => {
    fetchCostCenters(token)
      .then((rows) => setCostCenters(rows.filter((c) => c.is_active)))
      .catch(() => setCostCenters([]))
  }, [token])

  // تأمین‌کننده‌ها هم زنده خوانده می‌شوند (همان الگوی مراکز هزینه). آفلاین که نشد،
  // انتخاب‌گر پنهان و فاکتور بدون تأمین‌کننده است. مشتری‌ها کنار گذاشته می‌شوند.
  useEffect(() => {
    fetchContacts(token)
      .then((rows) => setContacts(rows.filter((c) => c.type !== 'customer')))
      .catch(() => setContacts([]))
  }, [token])

  // ارزها زنده خوانده می‌شوند؛ آفلاین که نشد، انتخاب‌گر پنهان و فاکتور به ریال است.
  useEffect(() => {
    fetchCurrencies(token)
      .then(setCurrencies)
      .catch(() => setCurrencies([]))
  }, [token])

  // با انتخابِ ارز، آخرین نرخِ ثبت‌شده پیشنهاد می‌شود (کاربر می‌تواند دستی تغییر دهد).
  useEffect(() => {
    if (!currencyCode) {
      setExchangeRate('1')
      return
    }
    let cancelled = false
    fetchLatestRate(token, currencyCode)
      .then((r) => !cancelled && r.rate && setExchangeRate(String(Number(r.rate))))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [token, currencyCode])
  // کلید یکتاسازی به *این فاکتور* گره می‌خورد، نه به هر تلاش شبکه‌ای.
  //
  // اگر ثبت با خطا برگردد و کاربر دوباره دکمه را بزند، همان کلید می‌رود — چون
  // ممکن است سرور نوبت اول کارش را کرده باشد و فقط پاسخ گم شده باشد. کلید تازه
  // در آن حالت یعنی فاکتور دوم. کلید فقط بعد از موفقیت قطعی نو می‌شود.
  const idempotencyKey = useRef(newIdempotencyKey())

  // رونوشتِ فاکتور خرید: با تغییرِ prefill، فرم با اقلامِ همان فاکتور به‌عنوان پیش‌نویسِ
  // تازه پر می‌شود (تاریخ و کلیدِ یکتاسازی نو).
  useEffect(() => {
    if (!prefill) return
    setWarehouseId(prefill.warehouse_id)
    setContactId(prefill.contact_id ?? '')
    setTaxRate(String(Number(prefill.tax_rate)))
    setCurrencyCode('')
    setInvoiceDate(todayIso())
    setLines(
      prefill.lines.map((l) => ({
        itemId: l.item_id,
        qty: String(Number(l.qty)),
        unitCost: String(Number(l.unit_cost)),
        discount: Number(l.discount) ? String(Number(l.discount)) : '',
      })),
    )
    idempotencyKey.current = newIdempotencyKey()
    setMessage(`رونوشت از فاکتور خرید شماره ${prefill.number ?? ''} بارگذاری شد؛ ویرایش و ثبت کنید.`)
    onPrefillConsumed?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill])

  const effectiveWarehouseId = warehouseId || warehouses[0]?.id || ''

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  function addLine() {
    setLines((prev) => [...prev, { itemId: '', qty: '1', unitCost: '', discount: '' }])
  }

  function removeLine(index: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev))
  }

  const gross = lines.reduce((sum, line) => sum + (Number(line.qty) || 0) * (Number(line.unitCost) || 0), 0)
  const discountTotal = lines.reduce((sum, line) => sum + (Number(line.discount) || 0), 0)
  const netAfterLine = gross - discountTotal
  // تخفیفِ کلِ فاکتور: مبلغی یا درصدی (روی خالصِ پس از تخفیفِ سطری). سقفش همان خالص است.
  const invoiceDiscountInput = Number(invoiceDiscount) || 0
  const invoiceDiscountAmount = Math.min(
    invoiceDiscountMode === 'percent' ? Math.round((netAfterLine * invoiceDiscountInput) / 100) : invoiceDiscountInput,
    netAfterLine,
  )
  // بهای موجودی هم پس از همه‌ی تخفیف‌ها ثبت می‌شود، پس پایه همین خالص است.
  const total = netAfterLine - invoiceDiscountAmount
  const taxRateNum = Math.min(Math.max(Number(taxRate) || 0, 0), 100)
  const taxAmount = Math.round((total * taxRateNum) / 100)
  const grandTotal = total + taxAmount
  // ارز پایه = ریال با نرخ ۱. مبالغِ بالا به ارزِ انتخابی وارد شده‌اند؛ برای ارسال
  // در نرخ ضرب می‌شوند. دفتر همیشه ریالی است.
  const rate = currencyCode ? Number(exchangeRate) || 1 : 1
  const baseGrandTotal = Math.round(grandTotal * rate)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)

    if (!effectiveWarehouseId) {
      setMessage('ابتدا هم‌گام‌سازی کنید تا انبار در دسترس باشد.')
      return
    }
    const validLines = lines.filter((l) => l.itemId && Number(l.qty) > 0)
    if (validLines.length === 0) {
      setMessage('حداقل یک ردیف معتبر (کالا + تعداد) لازم است.')
      return
    }
    const overDiscounted = validLines.find(
      (l) => (Number(l.discount) || 0) > (Number(l.qty) || 0) * (Number(l.unitCost) || 0),
    )
    if (overDiscounted) {
      setMessage('تخفیف نمی‌تواند از مبلغ ردیف بیشتر باشد.')
      return
    }

    const payload = {
      invoice_date: invoiceDate,
      warehouse_id: effectiveWarehouseId,
      tax_rate: taxRateNum,
      cost_center_id: costCenterId || null,
      contact_id: contactId || null,
      currency_code: currencyCode || null,
      exchange_rate: rate,
      invoice_discount: Math.round(invoiceDiscountAmount * rate),
      lines: validLines.map((l) => ({
        item_id: l.itemId,
        qty: Number(l.qty),
        // مبالغ به پایه (ریال) تبدیل می‌شوند؛ ردیف‌ها همیشه پایه ذخیره می‌شوند.
        unit_cost: Math.round((Number(l.unitCost) || 0) * rate),
        discount: Math.round((Number(l.discount) || 0) * rate),
      })),
    }

    try {
      await createPurchaseInvoiceDirect(token, payload, idempotencyKey.current)
      setMessage('فاکتور خرید با موفقیت ثبت شد.')
      idempotencyKey.current = newIdempotencyKey() // فاکتور بعدی، کلید تازه
      setLines([{ itemId: '', qty: '1', unitCost: '', discount: '' }])
      setCostCenterId('')
      setContactId('')
      setCurrencyCode('')
      setInvoiceDiscount('')
      onQueued()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard icon={PackagePlus} title="ثبت فاکتور خرید">
      {warehouses.length === 0 || items.length === 0 ? (
        <p className="hint">قبل از ثبت فاکتور، یک‌بار «هم‌گام‌سازی» کنید تا انبار و کالاها در دسترس باشند.</p>
      ) : (
        <form className="invoice-form" onSubmit={handleSubmit}>
          <label>
            انبار
            <select value={effectiveWarehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            تاریخ فاکتور
            <JalaliDatePicker value={invoiceDate} onChange={setInvoiceDate} />
          </label>
          <label>
            نرخ مالیات بر ارزش افزوده (٪)
            <NumberInput
              allowDecimal
              value={taxRate}
              onChange={setTaxRate}
            />
          </label>
          {costCenters.length > 0 && (
            <label>
              مرکز هزینه/پروژه (اختیاری)
              <select value={costCenterId} onChange={(e) => setCostCenterId(e.target.value)}>
                <option value="">— بدون مرکز —</option>
                {costCenters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code ? `${c.code} — ${c.name}` : c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {contacts.length > 0 && (
            <label>
              تأمین‌کننده (اختیاری)
              <select value={contactId} onChange={(e) => setContactId(e.target.value)}>
                <option value="">— بدون تأمین‌کننده —</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {currencies.length > 0 && (
            <div className="field-row">
              <label>
                ارز فاکتور
                <select value={currencyCode} onChange={(e) => setCurrencyCode(e.target.value)}>
                  <option value="">ریال (پایه)</option>
                  {currencies.map((c) => (
                    <option key={c.id} value={c.code}>
                      {c.code} — {c.name}
                    </option>
                  ))}
                </select>
              </label>
              {currencyCode && (
                <label>
                  نرخ برابری (۱ {currencyCode} = ؟ ریال)
                  <NumberInput allowDecimal value={exchangeRate} onChange={setExchangeRate} />
                </label>
              )}
            </div>
          )}

          <div className="table-scroll">
          <table className="invoice-lines">
            <thead>
              <tr>
                <th>کالا</th>
                <th>تعداد</th>
                <th>بهای واحد</th>
                <th>تخفیف</th>
                <th>مبلغ</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, i) => (
                <tr key={i}>
                  <td data-label="کالا">
                    <ItemPicker items={items} value={line.itemId} onChange={(id) => updateLine(i, { itemId: id })} />
                  </td>
                  <td data-label="تعداد">
                    <div className="qty-with-unit">
                      <NumberInput
                        allowDecimal
                        value={line.qty}
                        onChange={(v) => updateLine(i, { qty: v })}
                      />
                      {(() => { const u = items.find((it) => it.id === line.itemId)?.unit; return u ? <span className="unit-suffix">{u}</span> : null })()}
                    </div>
                  </td>
                  <td data-label="بهای واحد">
                    <NumberInput
                      value={line.unitCost}
                      onChange={(v) => updateLine(i, { unitCost: v })}
                      title={(() => { const u = items.find((it) => it.id === line.itemId)?.unit; return u ? `بهای هر ${u}` : 'بهای واحد' })()}
                    />
                  </td>
                  <td data-label="تخفیف">
                    <NumberInput
                      value={line.discount}
                      onChange={(v) => updateLine(i, { discount: v })}
                      placeholder="۰"
                    />
                  </td>
                  <td data-label="مبلغ">
                    <span className={`line-amount${line.itemId ? '' : ' muted'}`}>
                      {line.itemId
                        ? Math.max(
                            (Number(line.qty) || 0) * (Number(line.unitCost) || 0) - (Number(line.discount) || 0),
                            0,
                          ).toLocaleString('fa-IR')
                        : '—'}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="icon-btn-danger"
                      onClick={() => removeLine(i)}
                      disabled={lines.length === 1}
                      aria-label="حذف ردیف"
                    >
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
                <NumberInput
                  value={invoiceDiscount}
                  onChange={setInvoiceDiscount}
                  placeholder="۰"
                />
                <div className="seg-toggle">
                  <button type="button" className={invoiceDiscountMode === 'amount' ? 'active' : ''} onClick={() => setInvoiceDiscountMode('amount')}>مبلغ</button>
                  <button type="button" className={invoiceDiscountMode === 'percent' ? 'active' : ''} onClick={() => setInvoiceDiscountMode('percent')}>٪</button>
                </div>
              </div>
              {invoiceDiscountMode === 'percent' && invoiceDiscountAmount > 0 && (
                <span className="hint">معادل {invoiceDiscountAmount.toLocaleString('fa-IR')}</span>
              )}
            </label>
          </div>

          <div className="invoice-form-footer">
            <button type="button" onClick={addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <div className="invoice-totals">
              {discountTotal > 0 && <span>تخفیف سطری: {discountTotal.toLocaleString('fa-IR')}</span>}
              {invoiceDiscountAmount > 0 && <span>تخفیف کل: {invoiceDiscountAmount.toLocaleString('fa-IR')}</span>}
              <span>جمع خالص: {total.toLocaleString('fa-IR')}</span>
              <span>مالیات ({taxRateNum.toLocaleString('fa-IR')}٪): {taxAmount.toLocaleString('fa-IR')}</span>
              <span className="invoice-total">
                قابل پرداخت: {grandTotal.toLocaleString('fa-IR')}
                {currencyCode ? ` ${currencyCode}` : ''}
              </span>
              {currencyCode && (
                <span className="hint">معادل ریالی: {baseGrandTotal.toLocaleString('fa-IR')}</span>
              )}
            </div>
            <button type="submit" className="btn-primary"><Save size={14} /> ثبت فاکتور خرید</button>
          </div>

          {message && <div className="hint">{message}</div>}
        </form>
      )}
    </SectionCard>
  )
}
