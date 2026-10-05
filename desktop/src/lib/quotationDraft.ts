import { useEffect, useRef, useState } from 'react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import {
  createSalesQuotationIdempotent,
  updateSalesQuotation,
  fetchContacts,
  fetchStockLevels,
  newIdempotencyKey,
  resolvePrice,
  type ContactRecord,
  type SalesQuotationRecord,
  type StockLevel,
} from '../api'
import { todayIso } from './jalali'
import { usePersistentState } from './usePersistentState'
import type { TransactionUnitPatch } from '../components/TransactionUnitPicker'

export interface QuotationDraftLine extends TransactionUnitPatch {
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
  // در حالتِ ویرایش، پیش‌نویسِ ماندگار نباید بنشیند (تا دیتای ویرایش را نیالاید).
  const persistOff = !!editing
  const [warehouseId, setWarehouseId] = usePersistentState('cubita.draft.quotation.warehouseId', '', persistOff)
  const [quotationDate, setQuotationDate] = usePersistentState('cubita.draft.quotation.quotationDate', todayIso(), persistOff)
  const [validUntil, setValidUntil] = usePersistentState('cubita.draft.quotation.validUntil', '', persistOff)
  const [description, setDescription] = usePersistentState('cubita.draft.quotation.description', '', persistOff)
  const [lines, setLines] = usePersistentState<QuotationDraftLine[]>('cubita.draft.quotation.lines', [{ itemId: '', qty: '1', unitPrice: '' }], persistOff)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const idempotencyKey = useRef(newIdempotencyKey())

  // مشتری: از فهرستِ اشخاص یا دستی
  const [customerMode, setCustomerMode] = usePersistentState<'list' | 'manual'>('cubita.draft.quotation.customerMode', 'list', persistOff)
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [contactId, setContactId] = usePersistentState('cubita.draft.quotation.contactId', '', persistOff)
  const [customerName, setCustomerName] = usePersistentState('cubita.draft.quotation.customerName', '', persistOff)

  // موجودی: خواندن از انبار یا دستی
  const [stockMode, setStockMode] = useState<'warehouse' | 'manual'>('warehouse')
  const [stockLevels, setStockLevels] = useState<StockLevel[]>([])

  const effectiveWarehouseId = warehouseId || warehouses[0]?.id || ''

  useEffect(() => {
    fetchContacts(token)
      .then((rows) => setContacts(rows.filter((c) => c.is_customer)))
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
        ? editing.lines.map((l) => ({ itemId: l.item_id, qty: l.qty,
            unitId: l.entered_unit_id ?? undefined, unitName: l.unit_snapshot,
            observations: (l.unit_conversion_snapshot?.path ?? []).flatMap(step => step.observation
              ? [{ rule_id: step.rule_id, from_qty: step.observation.from_qty, to_qty: step.observation.to_qty }] : []),
            unitPrice: l.unit_price }))
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
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line,
      ...(patch.itemId !== undefined && patch.itemId !== line.itemId ? {
        unitId: undefined, unitName: undefined, observations: [], baseQtyPreview: undefined,
      } : {}), ...(patch.qty !== undefined ? { baseQtyPreview: undefined } : {}), ...patch } : line)))
  }
  function changeLineUnit(index: number, patch: TransactionUnitPatch) {
    updateLine(index, patch)
    if (patch.unitId === undefined) return
    const itemId = lines[index].itemId
    updateLine(index, { unitPrice: '' })
    fillUnitPrice(index, itemId, patch.unitId)
  }
  function fillUnitPrice(index: number, itemId: string, unitId?: string) {
    void resolvePrice(token, itemId, { unitId, on: quotationDate,
      contactId: contactId || null }).then(rule => setLines(prev => prev.map((line, i) =>
        i === index && line.itemId === itemId && line.unitId === unitId
          ? { ...line, unitPrice: rule ? rule.unit_price
              : unitId ? '' : items.find(item => item.id === itemId)?.sales_price ?? '' } : line))).catch(() => {})
  }
  function chooseLineItem(index: number, itemId: string) {
    if (!itemId) {
      updateLine(index, { itemId: '', unitPrice: '' })
      return
    }
    const it = items.find((x) => x.id === itemId)
    const price = it ? Number(it.sales_price) : 0
    updateLine(index, { itemId, unitPrice: price ? String(price) : '' })
    fillUnitPrice(index, itemId)
  }
  function useInventoryPrice(index: number, itemId: string) {
    if (lines[index].unitId) {
      changeLineUnit(index, { unitId: lines[index].unitId })
      return
    }
    const it = items.find((x) => x.id === itemId)
    if (it) updateLine(index, { unitPrice: String(Number(it.sales_price)) })
    fillUnitPrice(index, itemId)
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
        qty: l.qty,
        unit_id: l.unitId ?? null,
        observations: l.observations ?? [],
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
        await createSalesQuotationIdempotent(token, payload, idempotencyKey.current)
        idempotencyKey.current = newIdempotencyKey()
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
    token,
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
    changeLineUnit,
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
