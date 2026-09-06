import { useEffect, useMemo, useRef, useState } from 'react'
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
  type ItemRecord,
  type PurchaseInvoiceRecord,
} from '../api'
import { isElectron } from '../platform'
import type { PickableItem } from '../components/ItemPicker'
import { todayIso } from './jalali'
import { usePersistentState } from './usePersistentState'

export interface PurchaseDraftLine {
  itemId: string
  qty: string
  unitCost: string
  discount: string
}

/**
 * منطقِ مشترکِ «ثبت فاکتور خرید» — state، effectها، محاسبات، ساختِ سریعِ کالا و submit.
 * هم فرمِ کلاسیک ([PurchaseInvoiceForm]) و هم ویزارد ([PurchaseInvoiceWizard]) از این می‌خوانند.
 */
export function usePurchaseInvoiceDraft({
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
  // در حالتِ رونوشت (prefill) پیش‌نویسِ ماندگار نباید بنشیند تا دیتای رونوشت را نیالاید.
  const persistOff = !!prefill
  const [warehouseId, setWarehouseId] = usePersistentState('cubita.draft.purchaseInvoice.warehouseId', '', persistOff)
  const [invoiceDate, setInvoiceDate] = usePersistentState('cubita.draft.purchaseInvoice.invoiceDate', todayIso(), persistOff)
  const [taxRate, setTaxRate] = usePersistentState('cubita.draft.purchaseInvoice.taxRate', '10', persistOff)
  const [invoiceDiscount, setInvoiceDiscount] = usePersistentState('cubita.draft.purchaseInvoice.invoiceDiscount', '', persistOff)
  const [invoiceDiscountMode, setInvoiceDiscountMode] = usePersistentState<'amount' | 'percent'>('cubita.draft.purchaseInvoice.invoiceDiscountMode', 'amount', persistOff)
  const [lines, setLines] = usePersistentState<PurchaseDraftLine[]>('cubita.draft.purchaseInvoice.lines', [{ itemId: '', qty: '1', unitCost: '', discount: '' }], persistOff)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [costCenterId, setCostCenterId] = usePersistentState('cubita.draft.purchaseInvoice.costCenterId', '', persistOff)
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [contactId, setContactId] = usePersistentState('cubita.draft.purchaseInvoice.contactId', '', persistOff)
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [currencyCode, setCurrencyCode] = useState('')
  const [exchangeRate, setExchangeRate] = useState('1')
  // کالاهایی که همین حالا داخلِ همین فاکتور ساخته شده‌اند (کشِ سراسری تا هم‌گام‌سازیِ
  // بعدی به‌روز نمی‌شود). fdedupe در pickItems.
  const [extraItems, setExtraItems] = useState<ItemRecord[]>([])
  const [quickAdd, setQuickAdd] = useState<{ lineIndex: number; name: string } | null>(null)

  const pickItems = useMemo<PickableItem[]>(() => {
    const seen = new Set<string>()
    const out: PickableItem[] = []
    for (const it of [...extraItems, ...items]) {
      if (seen.has(it.id)) continue
      seen.add(it.id)
      out.push(it)
    }
    return out
  }, [extraItems, items])

  useEffect(() => {
    fetchCostCenters(token)
      .then((rows) => setCostCenters(rows.filter((c) => c.is_active)))
      .catch(() => setCostCenters([]))
  }, [token])

  useEffect(() => {
    fetchContacts(token)
      .then((rows) => setContacts(rows.filter((c) => c.type !== 'customer')))
      .catch(() => setContacts([]))
  }, [token])

  useEffect(() => {
    fetchCurrencies(token)
      .then(setCurrencies)
      .catch(() => setCurrencies([]))
  }, [token])

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

  const idempotencyKey = useRef(newIdempotencyKey())

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

  function unitOf(itemId: string): string {
    return items.find((it) => it.id === itemId)?.unit || ''
  }
  function updateLine(index: number, patch: Partial<PurchaseDraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }
  function addLine() {
    setLines((prev) => [...prev, { itemId: '', qty: '1', unitCost: '', discount: '' }])
  }
  function removeLine(index: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev))
  }
  /** کالای تازه‌ساز را محلی نگه می‌دارد و در همان ردیف انتخابش می‌کند (بستنِ فرمِ سریع). */
  function acceptCreatedItem(item: ItemRecord, lineIndex: number) {
    setExtraItems((prev) => [item, ...prev])
    updateLine(lineIndex, { itemId: item.id })
    setQuickAdd(null)
  }

  const gross = lines.reduce((sum, line) => sum + (Number(line.qty) || 0) * (Number(line.unitCost) || 0), 0)
  const discountTotal = lines.reduce((sum, line) => sum + (Number(line.discount) || 0), 0)
  const netAfterLine = gross - discountTotal
  const invoiceDiscountInput = Number(invoiceDiscount) || 0
  const invoiceDiscountAmount = Math.min(
    invoiceDiscountMode === 'percent' ? Math.round((netAfterLine * invoiceDiscountInput) / 100) : invoiceDiscountInput,
    netAfterLine,
  )
  const total = netAfterLine - invoiceDiscountAmount
  const taxRateNum = Math.min(Math.max(Number(taxRate) || 0, 0), 100)
  const taxAmount = Math.round((total * taxRateNum) / 100)
  const grandTotal = total + taxAmount
  const rate = currencyCode ? Number(exchangeRate) || 1 : 1
  const baseGrandTotal = Math.round(grandTotal * rate)

  //: همان هشدارِ لیستِ سیاهِ سمتِ فروش — تأمین‌کننده‌ی مشکل‌دار هم باید دیده شود.
  const blacklisted = contacts.some((c) => c.id === contactId && c.is_blacklisted)

  const validLines = lines.filter((l) => l.itemId && Number(l.qty) > 0)
  const overDiscountLine = validLines.find(
    (l) => (Number(l.discount) || 0) > (Number(l.qty) || 0) * (Number(l.unitCost) || 0),
  )
  const linesValid = validLines.length > 0 && !overDiscountLine

  async function submit(): Promise<boolean> {
    setMessage(null)
    if (!effectiveWarehouseId) {
      setMessage('ابتدا هم‌گام‌سازی کنید تا انبار در دسترس باشد.')
      return false
    }
    if (validLines.length === 0) {
      setMessage('حداقل یک ردیف معتبر (کالا + تعداد) لازم است.')
      return false
    }
    if (overDiscountLine) {
      setMessage('تخفیف نمی‌تواند از مبلغ ردیف بیشتر باشد.')
      return false
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
        unit_cost: Math.round((Number(l.unitCost) || 0) * rate),
        discount: Math.round((Number(l.discount) || 0) * rate),
      })),
    }
    setSubmitting(true)
    try {
      if (isElectron) {
        await window.cubita.queuePurchaseInvoice(payload)
        setMessage('فاکتور خرید در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور ارسال می‌شود.')
      } else {
        await createPurchaseInvoiceDirect(token, payload, idempotencyKey.current)
        setMessage('فاکتور خرید با موفقیت ثبت شد.')
      }
      idempotencyKey.current = newIdempotencyKey()
      setLines([{ itemId: '', qty: '1', unitCost: '', discount: '' }])
      setCostCenterId('')
      setContactId('')
      setCurrencyCode('')
      setInvoiceDiscount('')
      onQueued()
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    warehouseId,
    setWarehouseId,
    effectiveWarehouseId,
    invoiceDate,
    setInvoiceDate,
    taxRate,
    setTaxRate,
    taxRateNum,
    invoiceDiscount,
    setInvoiceDiscount,
    invoiceDiscountMode,
    setInvoiceDiscountMode,
    invoiceDiscountAmount,
    lines,
    updateLine,
    addLine,
    removeLine,
    unitOf,
    costCenters,
    costCenterId,
    setCostCenterId,
    contacts,
    contactId,
    blacklisted,
    setContactId,
    currencies,
    currencyCode,
    setCurrencyCode,
    exchangeRate,
    setExchangeRate,
    pickItems,
    quickAdd,
    setQuickAdd,
    acceptCreatedItem,
    gross,
    discountTotal,
    total,
    taxAmount,
    grandTotal,
    baseGrandTotal,
    linesValid,
    message,
    setMessage,
    submitting,
    submit,
  }
}

export type PurchaseInvoiceDraft = ReturnType<typeof usePurchaseInvoiceDraft>
