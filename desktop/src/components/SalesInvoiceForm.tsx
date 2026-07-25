import { useEffect, useRef, useState } from 'react'
import { ShoppingCart, Plus, Trash2, Save, AlertTriangle } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import {
  createSalesInvoiceDirect,
  fetchContacts,
  fetchCostCenters,
  fetchCreditStatus,
  fetchCurrencies,
  fetchLatestRate,
  newIdempotencyKey,
  type ContactRecord,
  type CostCenterRecord,
  type CreditStatus,
  type Currency,
} from '../api'
import { isElectron } from '../platform'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { todayIso } from '../lib/jalali'

interface DraftLine {
  itemId: string
  qty: string
  unitPrice: string
  discount: string
}

export function SalesInvoiceForm({
  token,
  warehouses,
  items,
  onQueued,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onQueued: () => void
}) {
  const [warehouseId, setWarehouseId] = useState('')
  const [invoiceDate, setInvoiceDate] = useState(todayIso())
  const [taxRate, setTaxRate] = useState('10')
  const [lines, setLines] = useState<DraftLine[]>([{ itemId: '', qty: '1', unitPrice: '', discount: '' }])
  const [message, setMessage] = useState<string | null>(null)
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [costCenterId, setCostCenterId] = useState('')
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [contactId, setContactId] = useState('')
  const [credit, setCredit] = useState<CreditStatus | null>(null)
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [currencyCode, setCurrencyCode] = useState('')
  const [exchangeRate, setExchangeRate] = useState('1')

  // مراکز هزینه زنده خوانده می‌شوند؛ آفلاین که نشد، انتخاب‌گر پنهان و فاکتور بدون مرکز است.
  useEffect(() => {
    fetchCostCenters(token)
      .then((rows) => setCostCenters(rows.filter((c) => c.is_active)))
      .catch(() => setCostCenters([]))
  }, [token])

  // مشتری‌ها هم زنده خوانده می‌شوند (همان الگوی مراکز هزینه). آفلاین که نشد، انتخاب‌گر
  // پنهان و فاکتور بدون مشتری است — دقیقاً رفتار فعلی. تأمین‌کننده‌ها کنار گذاشته می‌شوند.
  useEffect(() => {
    fetchContacts(token)
      .then((rows) => setContacts(rows.filter((c) => c.type !== 'supplier')))
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

  // وضعیت اعتبارِ مشتریِ انتخاب‌شده را زنده می‌گیریم تا مانده و سقف را نشان دهیم.
  useEffect(() => {
    if (!contactId) {
      setCredit(null)
      return
    }
    let cancelled = false
    fetchCreditStatus(token, contactId)
      .then((s) => !cancelled && setCredit(s))
      .catch(() => !cancelled && setCredit(null))
    return () => {
      cancelled = true
    }
  }, [token, contactId])
  // کلید یکتاسازی به *این فاکتور* گره می‌خورد، نه به هر تلاش شبکه‌ای.
  //
  // اگر ثبت با خطا برگردد و کاربر دوباره دکمه را بزند، همان کلید می‌رود — چون
  // ممکن است سرور نوبت اول کارش را کرده باشد و فقط پاسخ گم شده باشد. کلید تازه
  // در آن حالت یعنی فاکتور دوم. کلید فقط بعد از موفقیت قطعی نو می‌شود.
  const idempotencyKey = useRef(newIdempotencyKey())

  const effectiveWarehouseId = warehouseId || warehouses[0]?.id || ''

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  function addLine() {
    setLines((prev) => [...prev, { itemId: '', qty: '1', unitPrice: '', discount: '' }])
  }

  function removeLine(index: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev))
  }

  const gross = lines.reduce((sum, line) => sum + (Number(line.qty) || 0) * (Number(line.unitPrice) || 0), 0)
  const discountTotal = lines.reduce((sum, line) => sum + (Number(line.discount) || 0), 0)
  // پایه‌ی مالیات، خالصِ پس از تخفیف است — همان چیزی که سرور هم حساب می‌کند.
  const total = gross - discountTotal
  const taxRateNum = Math.min(Math.max(Number(taxRate) || 0, 0), 100)
  const taxAmount = Math.round((total * taxRateNum) / 100)
  const grandTotal = total + taxAmount
  // ارز پایه = ریال با نرخ ۱. مبالغِ بالا به ارزِ انتخابی وارد شده‌اند؛ برای ارسال و
  // نمایشِ معادلِ ریالی در نرخ ضرب می‌شوند. دفتر همیشه ریالی است.
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
      (l) => (Number(l.discount) || 0) > (Number(l.qty) || 0) * (Number(l.unitPrice) || 0),
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
      lines: validLines.map((l) => ({
        item_id: l.itemId,
        qty: Number(l.qty),
        // مبالغ به پایه (ریال) تبدیل می‌شوند؛ ردیف‌ها همیشه پایه ذخیره می‌شوند.
        unit_price: Math.round((Number(l.unitPrice) || 0) * rate),
        discount: Math.round((Number(l.discount) || 0) * rate),
      })),
    }

    try {
      if (isElectron) {
        await window.cubita.queueSalesInvoice(payload)
        setMessage('فاکتور در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور ارسال می‌شود.')
      } else {
        await createSalesInvoiceDirect(token, payload, idempotencyKey.current)
        setMessage('فاکتور با موفقیت ثبت شد.')
      }
      idempotencyKey.current = newIdempotencyKey() // فاکتور بعدی، کلید تازه
      setLines([{ itemId: '', qty: '1', unitPrice: '', discount: '' }])
      setCostCenterId('')
      setContactId('')
      setCurrencyCode('')
      onQueued()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard icon={ShoppingCart} title="ثبت فاکتور فروش">
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
            <input
              type="number"
              min="0"
              max="100"
              step="any"
              value={taxRate}
              onChange={(e) => setTaxRate(e.target.value)}
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
              مشتری (اختیاری)
              <select value={contactId} onChange={(e) => setContactId(e.target.value)}>
                <option value="">— بدون مشتری —</option>
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
                  <input type="number" min="0" value={exchangeRate} onChange={(e) => setExchangeRate(e.target.value)} />
                </label>
              )}
            </div>
          )}

          {credit && Number(credit.credit_limit) > 0 && (
            <CreditBanner credit={credit} invoiceTotal={baseGrandTotal} />
          )}

          <table className="invoice-lines">
            <thead>
              <tr>
                <th>کالا</th>
                <th>تعداد</th>
                <th>قیمت واحد</th>
                <th>تخفیف</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, i) => (
                <tr key={i}>
                  <td>
                    <select value={line.itemId} onChange={(e) => updateLine(i, { itemId: e.target.value })}>
                      <option value="">— انتخاب کالا —</option>
                      {items.map((it) => (
                        <option key={it.id} value={it.id}>
                          {it.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={line.qty}
                      onChange={(e) => updateLine(i, { qty: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      value={line.unitPrice}
                      onChange={(e) => updateLine(i, { unitPrice: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      value={line.discount}
                      onChange={(e) => updateLine(i, { discount: e.target.value })}
                      placeholder="۰"
                    />
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

          <div className="invoice-form-footer">
            <button type="button" onClick={addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <div className="invoice-totals">
              {discountTotal > 0 && <span>جمع ناخالص: {gross.toLocaleString('fa-IR')}</span>}
              {discountTotal > 0 && <span>تخفیف: {discountTotal.toLocaleString('fa-IR')}</span>}
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
            <button type="submit" className="btn-primary"><Save size={14} /> ثبت فاکتور</button>
          </div>

          {message && <div className="hint">{message}</div>}
        </form>
      )}
    </SectionCard>
  )
}

// بنر اعتبار — مانده و سقفِ مشتری را نشان می‌دهد و اگر این فاکتور مانده را از سقف
// عبور دهد، هشدار می‌دهد. عمداً بلاک‌کننده نیست: تصمیمِ فروش با کاربر است و فاکتورهای
// آفلاین هم نباید سمت سرور رد شوند — این فقط یک هشدارِ آگاه‌کننده است.
function CreditBanner({ credit, invoiceTotal }: { credit: CreditStatus; invoiceTotal: number }) {
  const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')
  const limit = Number(credit.credit_limit)
  const outstanding = Number(credit.outstanding)
  const available = limit - outstanding
  const projected = outstanding + invoiceTotal
  const willExceed = projected > limit

  return (
    <div className={`credit-banner ${willExceed ? 'credit-banner--warn' : 'credit-banner--ok'}`}>
      {willExceed && <AlertTriangle size={15} />}
      <span>
        مانده فعلی: <strong>{fa(outstanding)}</strong> از سقف <strong>{fa(limit)}</strong> تومان
        {' — '}
        قابل استفاده: <strong>{fa(available)}</strong>
      </span>
      {willExceed && (
        <span className="credit-banner-alert">
          این فاکتور مانده را به {fa(projected)} می‌رساند و از سقف اعتبار عبور می‌کند.
        </span>
      )}
    </div>
  )
}
