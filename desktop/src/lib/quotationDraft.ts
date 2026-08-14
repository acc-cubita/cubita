import { useEffect, useState } from 'react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import {
  createSalesQuotation,
  updateSalesQuotation,
  fetchContacts,
  fetchStockLevels,
  type ContactRecord,
  type SalesQuotationRecord,
  type StockLevel,
} from '../api'
import { todayIso } from './jalali'

export interface QuotationDraftLine {
  itemId: string
  qty: string
  unitPrice: string
}

/**
 * منطقِ مشترکِ «ثبت/ویرایشِ پیش‌فاکتور» — state، effectها، محاسبات و submit. هم فرمِ
 * کلاسیک ([QuotationForm]) و هم ویزاردِ نسخه‌ی جدید ([QuotationWizard]) از این می‌خوانند.
 */
export function useQuotationDraft({
  token,
  warehouses,
  items,
  onCreated,
  editing = null,
  onDoneEditing,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onCreated: () => void
  editing?: SalesQuotationRecord | null
  onDoneEditing?: () => void
}) {
  const [warehouseId, setWarehouseId] = useState('')
  const [quotationDate, setQuotationDate] = useState(todayIso())
  const [validUntil, setValidUntil] = useState('')
  const [description, setDescription] = useState('')
  const [lines, setLines] = useState<QuotationDraftLine[]>([{ itemId: '', qty: '1', unitPrice: '' }])
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // مشتری: از فهرستِ اشخاص یا دستی
  const [customerMode, setCustomerMode] = useState<'list' | 'manual'>('list')
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [contactId, setContactId] = useState('')
  const [customerName, setCustomerName] = useState('')

  // موجودی: خواندن از انبار یا دستی
  const [stockMode, setStockMode] = useState<'warehouse' | 'manual'>('warehouse')
  const [stockLevels, setStockLevels] = useState<StockLevel[]>([])

  const effectiveWarehouseId = warehouseId || warehouses[0]?.id || ''

  useEffect(() => {
    fetchContacts(token)
      .then((rows) => setContacts(rows.filter((c) => c.type !== 'supplier')))
      .catch(() => setContacts([]))
  }, [token])

  useEffect(() => {
    fetchStockLevels(token)
      .then(setStockLevels)
      .catch(() => setStockLevels([]))
  }, [token])

  function resetForm() {
    setWarehouseId('')
    setQuotationDate(todayIso())
    setValidUntil('')
    setDescription('')
    setLines([{ itemId: '', qty: '1', unitPrice: '' }])
    setCustomerMode('list')
    setContactId('')
    setCustomerName('')
  }

  // پرکردنِ فرم هنگامِ ویرایش (فقط با تغییرِ پیش‌فاکتورِ انتخاب‌شده).
  useEffect(() => {
    if (!editing) return
    setWarehouseId(editing.warehouse_id)
    setQuotationDate(editing.quotation_date)
    setValidUntil(editing.valid_until ?? '')
    setDescription(editing.description ?? '')
    if (editing.contact_id) {
      setCustomerMode('list')
      setContactId(editing.contact_id)
      setCustomerName('')
    } else {
      setCustomerMode('manual')
      setCustomerName(editing.customer_name ?? '')
      setContactId('')
    }
    setLines(
      editing.lines.length
        ? editing.lines.map((l) => ({ itemId: l.item_id, qty: String(Number(l.qty)), unitPrice: String(Number(l.unit_price)) }))
        : [{ itemId: '', qty: '1', unitPrice: '' }],
    )
    setMessage(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing?.id])

  function unitOf(itemId: string): string {
    return items.find((it) => it.id === itemId)?.unit || ''
  }
  function isService(itemId: string): boolean {
    return !!items.find((it) => it.id === itemId)?.is_service
  }
  function availableStock(itemId: string): number | null {
    if (!itemId || !effectiveWarehouseId) return null
    const row = stockLevels.find((s) => s.item_id === itemId && s.warehouse_id === effectiveWarehouseId)
    return row ? Number(row.qty) : 0
  }
  function updateLine(index: number, patch: Partial<QuotationDraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }
  function chooseLineItem(index: number, itemId: string) {
    if (!itemId) {
      updateLine(index, { itemId: '', unitPrice: '' })
      return
    }
    const it = items.find((x) => x.id === itemId)
    const price = it ? Number(it.sales_price) : 0
    updateLine(index, { itemId, unitPrice: price ? String(price) : '' })
  }
  function useInventoryPrice(index: number, itemId: string) {
    const it = items.find((x) => x.id === itemId)
    if (it) updateLine(index, { unitPrice: String(Number(it.sales_price)) })
  }
  function addLine() {
    setLines((prev) => [...prev, { itemId: '', qty: '1', unitPrice: '' }])
  }
  function removeLine(index: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev))
  }

  const total = lines.reduce((sum, line) => sum + (Number(line.qty) || 0) * (Number(line.unitPrice) || 0), 0)
  const validLines = lines.filter((l) => l.itemId && Number(l.qty) > 0)
  const linesValid = validLines.length > 0

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
    const payload = {
      quotation_date: quotationDate,
      valid_until: validUntil || null,
      warehouse_id: effectiveWarehouseId,
      contact_id: customerMode === 'list' ? contactId || null : null,
      customer_name: customerMode === 'manual' ? customerName.trim() || null : null,
      description,
      lines: validLines.map((l) => ({
        item_id: l.itemId,
        qty: Number(l.qty),
        unit_price: Number(l.unitPrice) || 0,
        description: '',
      })),
    }
    setSubmitting(true)
    try {
      if (editing) {
        await updateSalesQuotation(token, editing.id, payload)
        onCreated()
        onDoneEditing?.()
        resetForm()
        setMessage('پیش‌فاکتور ویرایش شد.')
      } else {
        await createSalesQuotation(token, payload)
        resetForm()
        setMessage('پیش‌فاکتور ثبت شد.')
        onCreated()
      }
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    editing,
    warehouseId,
    setWarehouseId,
    effectiveWarehouseId,
    quotationDate,
    setQuotationDate,
    validUntil,
    setValidUntil,
    description,
    setDescription,
    lines,
    updateLine,
    chooseLineItem,
    useInventoryPrice,
    addLine,
    removeLine,
    customerMode,
    setCustomerMode,
    contacts,
    contactId,
    setContactId,
    customerName,
    setCustomerName,
    stockMode,
    setStockMode,
    unitOf,
    isService,
    availableStock,
    total,
    linesValid,
    message,
    setMessage,
    submitting,
    submit,
    resetForm,
  }
}

export type QuotationDraft = ReturnType<typeof useQuotationDraft>
