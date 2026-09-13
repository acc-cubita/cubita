import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Briefcase, Plus, Trash2, Save, Percent } from 'lucide-react'
import {
  PURCHASE_DEDUCTION_BASIS_LABELS,
  PURCHASE_DEDUCTION_NATURE_LABELS,
  createServicePurchaseInvoice,
  fetchAccountsLive,
  fetchContacts,
  fetchCostCenters,
  fetchCurrencies,
  fetchItemsLive,
  fetchLatestRate,
  fetchPurchaseDeductionTypes,
  fetchPurchaseInvoiceDuplicate,
  newIdempotencyKey,
  type ContactRecord,
  type CostCenterRecord,
  type Currency,
  type ItemRecord,
  type MeResponse,
  type PurchaseDeductionType,
  type PurchaseInvoiceRecord,
  type ServicePurchaseInvoiceInput,
} from '../api'
import type { ItemCache } from '../electron.d'
import { isElectron } from '../platform'
import { todayIso } from '../lib/jalali'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { ItemPicker, type PickableItem } from './ItemPicker'
import { InvoiceList, type AnyInvoice } from './InvoiceList'
import { BlacklistBanner } from './BlacklistBanner'

interface ServiceLine {
  itemId: string
  /** خالی = معینِ خودِ خدمت. */
  accountId: string
  qty: string
  unitCost: string
  discount: string
  addition: string
  dutyAmount: string
  description: string
}

interface DeductionRow {
  typeId: string
  rate: string
  amount: string
  /** کاربر مبلغ را خودش نوشته؛ دیگر از مبنا × نرخ حساب نمی‌شود. */
  manual: boolean
}

const EMPTY_LINE: ServiceLine = {
  itemId: '', accountId: '', qty: '1', unitCost: '', discount: '', addition: '', dutyAmount: '', description: '',
}

const num = (value: string) => Number(value) || 0
const fa = (value: number) => Math.round(value).toLocaleString('fa-IR')

/** «فاکتور خرید خدمات» — فرمِ ثبت و دفترِ همان فاکتورها.
 *
 *  با فاکتور خرید کالا یکی نیست: خدمت انبار ندارد، هزینه‌اش همان لحظه شناسایی
 *  می‌شود، و مالیات تکلیفی و بیمه از **بدهی به تأمین‌کننده** کم می‌شوند نه از هزینه.
 *  ولی موتور یکی است — همان `/api/purchase-invoices` با `kind: 'service'`. */
export function ServicePurchaseTab({
  token,
  me,
  items,
  onChanged,
  onCreatePayment,
}: {
  token: string
  me: MeResponse
  items: ItemCache[]
  onChanged: () => void
  onCreatePayment: (invoice: PurchaseInvoiceRecord) => void
}) {
  const [invoiceDate, setInvoiceDate] = useState(todayIso())
  const [contactId, setContactId] = useState('')
  const [supplierInvoiceNumber, setSupplierInvoiceNumber] = useState('')
  const [costCenterId, setCostCenterId] = useState('')
  const [description, setDescription] = useState('')
  const [description2, setDescription2] = useState('')
  const [taxRate, setTaxRate] = useState('10')
  const [currencyCode, setCurrencyCode] = useState('')
  const [exchangeRate, setExchangeRate] = useState('1')
  const [invoiceDiscount, setInvoiceDiscount] = useState('')
  const [invoiceAddition, setInvoiceAddition] = useState('')
  const [invoiceDuty, setInvoiceDuty] = useState('')
  const [lines, setLines] = useState<ServiceLine[]>([{ ...EMPTY_LINE }])
  const [deductions, setDeductions] = useState<DeductionRow[]>([])
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [expenseAccounts, setExpenseAccounts] = useState<{ id: string; code: string; name: string }[]>([])
  const [liveServices, setLiveServices] = useState<ItemRecord[] | null>(null)
  const [types, setTypes] = useState<PurchaseDeductionType[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const idempotencyKey = useRef(newIdempotencyKey())
  const formRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchContacts(token).then((rows) => setContacts(rows.filter((c) => c.type !== 'customer'))).catch(() => setContacts([]))
    fetchCostCenters(token).then((rows) => setCostCenters(rows.filter((c) => c.is_active))).catch(() => setCostCenters([]))
    fetchCurrencies(token).then(setCurrencies).catch(() => setCurrencies([]))
    fetchAccountsLive(token)
      .then((rows) => setExpenseAccounts(rows.filter((a) => !a.is_group && a.type === 'expense')))
      .catch(() => setExpenseAccounts([]))
    //: فهرستِ زنده معینِ پیش‌فرضِ هر خدمت را هم دارد؛ اگر نرسید، کشِ محلی کافی است.
    //: خدمتِ غیرفعال در فاکتورِ تازه انتخاب نمی‌شود — همان قاعده‌ی فهرستِ کالاها.
    fetchItemsLive(token)
      .then((rows) => setLiveServices(rows.filter((i) => i.is_service && i.is_active !== false)))
      .catch(() => setLiveServices(null))
  }, [token])

  useEffect(() => {
    fetchPurchaseDeductionTypes(token, false).then(setTypes).catch(() => setTypes([]))
  }, [token, reloadKey])

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

  const serviceOptions = useMemo<PickableItem[]>(
    () =>
      liveServices
        ? liveServices.map((i) => ({ id: i.id, name: i.name, sku: i.sku, unit: i.unit, barcode: i.barcode }))
        : items.filter((i) => Number(i.is_service) === 1).map((i) => ({ id: i.id, name: i.name, sku: i.sku, unit: i.unit })),
    [liveServices, items],
  )
  const serviceById = useMemo(() => new Map((liveServices ?? []).map((i) => [i.id, i])), [liveServices])
  const unitOf = (itemId: string) => serviceOptions.find((i) => i.id === itemId)?.unit ?? ''
  const typeById = useMemo(() => new Map(types.map((t) => [t.id, t])), [types])

  // ── جمع‌ها: همان ترتیبی که سرور می‌سازد (§۱۸–§۲۶) ──
  const gross = lines.reduce((sum, l) => sum + num(l.qty) * num(l.unitCost), 0)
  const lineDiscount = lines.reduce((sum, l) => sum + num(l.discount), 0)
  const lineAddition = lines.reduce((sum, l) => sum + num(l.addition), 0)
  const lineDuty = lines.reduce((sum, l) => sum + num(l.dutyAmount), 0)
  const netAfterLines = gross - lineDiscount + lineAddition + lineDuty
  const headerDiscount = Math.min(num(invoiceDiscount), Math.max(netAfterLines, 0))
  const total = netAfterLines - headerDiscount + num(invoiceAddition) + num(invoiceDuty)
  const dutiesTotal = lineDuty + num(invoiceDuty)
  const additionsTotal = lineAddition + num(invoiceAddition)
  const taxRateNum = Math.min(Math.max(num(taxRate), 0), 100)
  const taxAmount = Math.round((total * taxRateNum) / 100)
  const invoiceTotal = total + taxAmount
  //: مبنای «خالص پیش از مالیات و عوارض» — عوارض و ارزش افزوده پولِ دولت‌اند نه بهای خدمت.
  const netBeforeTax = total - dutiesTotal
  const computedDeductions = deductions.map((row) => {
    const type = typeById.get(row.typeId)
    const basis = type?.basis === 'gross' ? gross : netBeforeTax
    const amount = row.manual ? num(row.amount) : Math.round((basis * num(row.rate)) / 100)
    return { row, type, basis, amount }
  })
  const deductionTotal = computedDeductions.reduce((sum, d) => sum + d.amount, 0)
  const payable = invoiceTotal - deductionTotal
  const rate = currencyCode ? num(exchangeRate) || 1 : 1

  const blacklisted = contacts.some((c) => c.id === contactId && c.is_blacklisted)
  const validLines = lines.filter((l) => l.itemId && num(l.qty) > 0)
  const unusedTypes = types.filter((t) => !deductions.some((d) => d.typeId === t.id))

  function updateLine(index: number, patch: Partial<ServiceLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }
  function updateDeduction(index: number, patch: Partial<DeductionRow>) {
    setDeductions((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }
  function addDeduction() {
    const next = unusedTypes[0]
    if (!next) return
    setDeductions((prev) => [...prev, { typeId: next.id, rate: String(Number(next.rate)), amount: '', manual: false }])
  }

  function resetForm() {
    setLines([{ ...EMPTY_LINE }])
    setDeductions([])
    setContactId('')
    setSupplierInvoiceNumber('')
    setCostCenterId('')
    setDescription('')
    setDescription2('')
    setInvoiceDiscount('')
    setInvoiceAddition('')
    setInvoiceDuty('')
    setCurrencyCode('')
  }

  async function submit() {
    setMessage(null)
    if (!contactId) {
      setMessage('تأمین‌کننده را انتخاب کنید؛ فاکتور خرید خدمات بدونِ فروشنده ثبت نمی‌شود.')
      return
    }
    if (validLines.length === 0) {
      setMessage('حداقل یک ردیفِ خدمت با مقدار لازم است.')
      return
    }
    if (validLines.some((l) => num(l.discount) > num(l.qty) * num(l.unitCost))) {
      setMessage('تخفیفِ ردیف نمی‌تواند از مبلغِ همان ردیف بیشتر باشد.')
      return
    }
    if (payable < 0) {
      setMessage('جمعِ کسورات از جمعِ فاکتور بیشتر است؛ نرخ یا مبلغِ کسرها را اصلاح کنید.')
      return
    }
    const payload: ServicePurchaseInvoiceInput = {
      kind: 'service',
      invoice_date: invoiceDate,
      contact_id: contactId,
      supplier_invoice_number: supplierInvoiceNumber.trim(),
      cost_center_id: costCenterId || null,
      description: description.trim(),
      description2: description2.trim(),
      tax_rate: taxRateNum,
      currency_code: currencyCode || null,
      exchange_rate: rate,
      invoice_discount: Math.round(headerDiscount * rate),
      invoice_addition: Math.round(num(invoiceAddition) * rate),
      duty_amount: Math.round(num(invoiceDuty) * rate),
      lines: validLines.map((l) => ({
        item_id: l.itemId,
        expense_account_id: l.accountId || null,
        qty: num(l.qty),
        unit_cost: Math.round(num(l.unitCost) * rate),
        discount: Math.round(num(l.discount) * rate),
        addition: Math.round(num(l.addition) * rate),
        duty_amount: Math.round(num(l.dutyAmount) * rate),
        description: l.description.trim(),
      })),
      //: مبلغِ خودکار را سرور از مبنای ریالیِ خودش حساب می‌کند؛ فقط مبلغِ دستی فرستاده می‌شود.
      deductions: computedDeductions.map(({ row }) => ({
        deduction_type_id: row.typeId,
        rate: num(row.rate),
        amount: row.manual ? Math.round(num(row.amount) * rate) : null,
      })),
    }
    setSubmitting(true)
    try {
      if (isElectron) {
        await window.cubita.queuePurchaseInvoice(payload)
        setMessage('فاکتور خرید خدمات در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور می‌رسد.')
      } else {
        const created = await createServicePurchaseInvoice(token, payload, idempotencyKey.current)
        setMessage(
          `فاکتور خرید خدمات شماره ${(created.number ?? 0).toLocaleString('fa-IR')} ثبت شد — ` +
            `بدهی به تأمین‌کننده ${fa(Number(created.payable_amount))} ریال.`,
        )
      }
      idempotencyKey.current = newIdempotencyKey()
      resetForm()
      setReloadKey((k) => k + 1)
      onChanged()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'ثبتِ فاکتور ناموفق بود')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDuplicate = useCallback(
    async (invoice: AnyInvoice) => {
      try {
        const draft = await fetchPurchaseInvoiceDuplicate(token, invoice.id)
        setContactId(draft.contact_id ?? '')
        setSupplierInvoiceNumber('')
        setCostCenterId(draft.cost_center_id ?? '')
        setDescription(draft.description ?? '')
        setDescription2(draft.description2 ?? '')
        setTaxRate(String(Number(draft.tax_rate)))
        setCurrencyCode(draft.currency_code ?? '')
        setExchangeRate(String(Number(draft.exchange_rate || 1)))
        setInvoiceDiscount('')
        setInvoiceAddition('')
        setInvoiceDuty('')
        setInvoiceDate(todayIso())
        setLines(
          draft.lines.map((l) => ({
            itemId: l.item_id,
            accountId: l.expense_account_id ?? '',
            qty: String(Number(l.qty)),
            unitCost: String(Number(l.unit_cost)),
            discount: Number(l.discount) ? String(Number(l.discount)) : '',
            addition: Number(l.addition) ? String(Number(l.addition)) : '',
            dutyAmount: Number(l.duty_amount) ? String(Number(l.duty_amount)) : '',
            description: l.description ?? '',
          })),
        )
        //: نوعِ کسری که حالا غیرفعال است در رونوشت نمی‌آید — سرور هم ردش می‌کرد.
        setDeductions(
          (draft.deductions ?? [])
            .filter((d) => d.deduction_type_id && typeById.has(d.deduction_type_id))
            .map((d) => ({ typeId: d.deduction_type_id as string, rate: String(Number(d.rate)), amount: '', manual: false })),
        )
        idempotencyKey.current = newIdempotencyKey()
        setMessage(
          `رونوشت از فاکتور خرید خدمات شماره ${draft.source_invoice_number ?? ''} بارگذاری شد؛ ` +
            'تاریخ، شماره‌ی فاکتورِ فروشنده و مبلغِ کسرها از نو پر می‌شوند.',
        )
        formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      } catch (err) {
        setMessage(err instanceof Error ? err.message : 'پیش‌نویسِ رونوشت بارگذاری نشد.')
      }
    },
    [token, typeById],
  )

  return (
    <>
      <div ref={formRef}>
        <SectionCard
          icon={Briefcase}
          title="ثبت فاکتور خرید خدمات"
          description="خدمت وارد انبار نمی‌شود: هزینه همان لحظه ثبت می‌شود و مالیات تکلیفی و بیمه از بدهی به تأمین‌کننده کسر و به بدهیِ جدا منتقل می‌شوند."
        >
          <form
            className="invoice-form"
            onSubmit={(e) => {
              e.preventDefault()
              void submit()
            }}
          >
            <div className="field-row">
              <label>
                تأمین‌کننده
                <select value={contactId} onChange={(e) => setContactId(e.target.value)}>
                  <option value="">— انتخاب تأمین‌کننده —</option>
                  {contacts.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label>
                شماره فاکتور تأمین‌کننده
                <input value={supplierInvoiceNumber} onChange={(e) => setSupplierInvoiceNumber(e.target.value)} />
              </label>
              <label>
                تاریخ
                <JalaliDatePicker value={invoiceDate} onChange={setInvoiceDate} />
              </label>
            </div>
            {blacklisted && <BlacklistBanner name={contacts.find((c) => c.id === contactId)?.name} />}
            <div className="field-row">
              <label>
                مرکز هزینه
                <select value={costCenterId} onChange={(e) => setCostCenterId(e.target.value)}>
                  <option value="">— بدون مرکز —</option>
                  {costCenters.map((c) => (
                    <option key={c.id} value={c.id}>{c.code ? `${c.code} — ${c.name}` : c.name}</option>
                  ))}
                </select>
              </label>
              <label>
                نرخ مالیات بر ارزش افزوده (٪)
                <NumberInput allowDecimal value={taxRate} onChange={setTaxRate} />
              </label>
              {currencies.length > 0 && (
                <label>
                  ارز فاکتور
                  <select value={currencyCode} onChange={(e) => setCurrencyCode(e.target.value)}>
                    <option value="">ریال (پایه)</option>
                    {currencies.map((c) => (
                      <option key={c.id} value={c.code}>{c.code} — {c.name}</option>
                    ))}
                  </select>
                </label>
              )}
              {currencyCode && (
                <label>
                  نرخ برابری (۱ {currencyCode} = ؟ ریال)
                  <NumberInput allowDecimal value={exchangeRate} onChange={setExchangeRate} />
                </label>
              )}
            </div>
            <div className="field-row">
              <label>
                شرح
                <input value={description} onChange={(e) => setDescription(e.target.value)} />
              </label>
              <label>
                شرح دوم
                <input value={description2} onChange={(e) => setDescription2(e.target.value)} />
              </label>
            </div>

            <div className="table-scroll">
              <table className="invoice-lines cards-on-mobile">
                <thead>
                  <tr>
                    <th>خدمت</th>
                    <th>معین هزینه</th>
                    <th>مقدار</th>
                    <th>فی</th>
                    <th>تخفیف</th>
                    <th>اضافات</th>
                    <th>عوارض</th>
                    <th>شرح</th>
                    <th>مبلغ</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line, i) => {
                    const service = serviceById.get(line.itemId)
                    const defaultLabel = service?.expense_account_name
                      ? `پیش‌فرضِ خدمت: ${service.expense_account_code} — ${service.expense_account_name}`
                      : 'معینِ پیش‌فرضِ خدمت'
                    const amount = num(line.qty) * num(line.unitCost) - num(line.discount) + num(line.addition) + num(line.dutyAmount)
                    return (
                      <tr key={i}>
                        <td data-label="خدمت">
                          <ItemPicker
                            items={serviceOptions}
                            value={line.itemId}
                            placeholder="— انتخاب خدمت —"
                            onChange={(id) => updateLine(i, { itemId: id, accountId: '' })}
                          />
                        </td>
                        <td data-label="معین هزینه">
                          <select
                            className="line-account"
                            title={line.accountId ? undefined : defaultLabel}
                            value={line.accountId}
                            onChange={(e) => updateLine(i, { accountId: e.target.value })}
                          >
                            <option value="">{defaultLabel}</option>
                            {expenseAccounts.map((a) => (
                              <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                            ))}
                          </select>
                        </td>
                        <td data-label="مقدار">
                          <div className="qty-with-unit">
                            <NumberInput allowDecimal value={line.qty} onChange={(v) => updateLine(i, { qty: v })} />
                            {unitOf(line.itemId) && <span className="unit-suffix">{unitOf(line.itemId)}</span>}
                          </div>
                        </td>
                        <td data-label="فی">
                          <NumberInput value={line.unitCost} onChange={(v) => updateLine(i, { unitCost: v })} />
                        </td>
                        <td data-label="تخفیف">
                          <NumberInput value={line.discount} onChange={(v) => updateLine(i, { discount: v })} placeholder="۰" />
                        </td>
                        <td data-label="اضافات">
                          <NumberInput value={line.addition} onChange={(v) => updateLine(i, { addition: v })} placeholder="۰" />
                        </td>
                        <td data-label="عوارض">
                          <NumberInput value={line.dutyAmount} onChange={(v) => updateLine(i, { dutyAmount: v })} placeholder="۰" />
                        </td>
                        <td data-label="شرح">
                          <input value={line.description} onChange={(e) => updateLine(i, { description: e.target.value })} />
                        </td>
                        <td className="num" data-label="مبلغ">{line.itemId ? fa(Math.max(amount, 0)) : '—'}</td>
                        <td className="card-actions">
                          <button
                            type="button"
                            className="icon-btn-danger"
                            aria-label="حذف ردیف"
                            disabled={lines.length === 1}
                            onClick={() => setLines((prev) => prev.filter((_, index) => index !== i))}
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="invoice-adjustments">
              <button type="button" onClick={() => setLines((prev) => [...prev, { ...EMPTY_LINE }])}>
                <Plus size={14} /> افزودن ردیف
              </button>
              <label className="adj-field">تخفیف کل<NumberInput value={invoiceDiscount} onChange={setInvoiceDiscount} placeholder="۰" /></label>
              <label className="adj-field">اضافات کل<NumberInput value={invoiceAddition} onChange={setInvoiceAddition} placeholder="۰" /></label>
              <label className="adj-field">عوارض کل<NumberInput value={invoiceDuty} onChange={setInvoiceDuty} placeholder="۰" /></label>
            </div>

            <div className="invoice-deductions">
              <h4><Percent size={14} /> کسورات</h4>
              {types.length === 0 ? (
                <p className="hint">
                  هنوز نوعِ کسرِ فعالی تعریف نشده. برای مالیات تکلیفی یا بیمه، در تبِ «انواع کسورات» یک نوع بسازید.
                </p>
              ) : (
                <>
                  {deductions.length > 0 && (
                    <div className="table-scroll">
                      <table className="cards-on-mobile">
                        <thead>
                          <tr>
                            <th>نوع کسر</th>
                            <th>ماهیت</th>
                            <th>مبنا</th>
                            <th>مبلغ مبنا</th>
                            <th>نرخ (٪)</th>
                            <th>مبلغ کسر</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {computedDeductions.map(({ row, type, basis, amount }, i) => (
                            <tr key={`${row.typeId}-${i}`}>
                              <td className="card-title" data-label="نوع کسر">
                                <select
                                  value={row.typeId}
                                  onChange={(e) => {
                                    const next = typeById.get(e.target.value)
                                    updateDeduction(i, { typeId: e.target.value, rate: next ? String(Number(next.rate)) : row.rate, manual: false, amount: '' })
                                  }}
                                >
                                  {types
                                    .filter((t) => t.id === row.typeId || !deductions.some((d) => d.typeId === t.id))
                                    .map((t) => (
                                      <option key={t.id} value={t.id}>{t.name}</option>
                                    ))}
                                </select>
                              </td>
                              <td data-label="ماهیت">{type ? PURCHASE_DEDUCTION_NATURE_LABELS[type.nature] : '—'}</td>
                              <td data-label="مبنا">{type ? PURCHASE_DEDUCTION_BASIS_LABELS[type.basis] : '—'}</td>
                              <td className="num" data-label="مبلغ مبنا">{fa(basis)}</td>
                              <td data-label="نرخ (٪)">
                                <NumberInput allowDecimal value={row.rate} onChange={(v) => updateDeduction(i, { rate: v, manual: false })} />
                              </td>
                              <td data-label="مبلغ کسر">
                                <NumberInput
                                  value={row.manual ? row.amount : String(amount)}
                                  onChange={(v) => updateDeduction(i, { amount: v, manual: true })}
                                />
                                {row.manual && (
                                  <button type="button" className="link-btn" onClick={() => updateDeduction(i, { manual: false, amount: '' })}>
                                    محاسبه از نرخ
                                  </button>
                                )}
                              </td>
                              <td className="card-actions">
                                <button
                                  type="button"
                                  className="icon-btn-danger"
                                  aria-label="حذف کسر"
                                  onClick={() => setDeductions((prev) => prev.filter((_, index) => index !== i))}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <button type="button" onClick={addDeduction} disabled={unusedTypes.length === 0}>
                    <Plus size={14} /> افزودن کسر
                  </button>
                </>
              )}
            </div>

            <div className="invoice-form-footer">
              <div className="invoice-totals">
                <span>کل: {fa(gross)}</span>
                {lineDiscount + headerDiscount > 0 && <span>تخفیف: {fa(lineDiscount + headerDiscount)}</span>}
                {additionsTotal > 0 && <span>اضافات: {fa(additionsTotal)}</span>}
                {dutiesTotal > 0 && <span>عوارض: {fa(dutiesTotal)}</span>}
                <span>مالیات ({taxRateNum.toLocaleString('fa-IR')}٪): {fa(taxAmount)}</span>
                <span>جمع فاکتور: {fa(invoiceTotal)}</span>
                {computedDeductions.map(({ row, type, amount }, i) => (
                  <span key={`${row.typeId}-sum-${i}`}>{type?.name ?? 'کسر'} (−): {fa(amount)}</span>
                ))}
                <span className="invoice-total">
                  خالص قابل پرداخت به تأمین‌کننده: {fa(payable)}
                  {currencyCode ? ` ${currencyCode}` : ''}
                </span>
                {currencyCode && <span className="hint">معادل ریالی: {fa(payable * rate)}</span>}
              </div>
              <button type="submit" className="btn-primary" disabled={submitting}>
                <Save size={14} /> ثبت فاکتور خرید خدمات
              </button>
            </div>
            {message && <div className="hint">{message}</div>}
          </form>
        </SectionCard>
      </div>

      <InvoiceList
        key={reloadKey}
        token={token}
        me={me}
        kind="purchase"
        purchaseKind="service"
        items={serviceOptions}
        onDuplicate={(invoice) => void handleDuplicate(invoice)}
        onCreatePayment={onCreatePayment}
      />
    </>
  )
}
