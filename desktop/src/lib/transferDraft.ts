import { useRef, useState } from 'react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { createStockTransfer, newIdempotencyKey } from '../api'
import { todayIso } from './jalali'

export interface TransferDraftLine {
  itemId: string
  qty: string
}

/**
 * منطقِ مشترکِ «انتقال بین انبار» — مبدأ/مقصد/تاریخ/اقلام.
 *
 * فهرستِ حواله‌ها دیگر این‌جا نیست: همان «فهرستِ خروج‌ها» با نوعِ انتقال زیرِ تب
 * می‌نشیند، تا از یک داده دو نما نماند.
 */
export function useTransferDraft({
  token,
  warehouses,
  items,
  onCreated,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  /** پس از ثبتِ موفق — فهرستِ زیرِ تب خودش را تازه می‌کند. */
  onCreated?: () => void
}) {
  const [fromWarehouseId, setFromWarehouseId] = useState('')
  const [toWarehouseId, setToWarehouseId] = useState('')
  const [transferDate, setTransferDate] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [lines, setLines] = useState<TransferDraftLine[]>([{ itemId: '', qty: '' }])
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  //: کلید به *این* حواله گره می‌خورد و فقط پس از موفقیت نو می‌شود: پاسخِ گم‌شده و
  //: کلیکِ دوباره نباید کالا را دو بار جابه‌جا کند.
  const idempotencyKey = useRef(newIdempotencyKey())

  const goodsItems = items.filter((i) => !i.is_service)
  const warehouseById = new Map(warehouses.map((w) => [w.id, w]))
  const itemById = new Map(items.map((i) => [i.id, i]))

  function updateLine(index: number, patch: Partial<TransferDraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }
  function addLine() {
    setLines((prev) => [...prev, { itemId: '', qty: '' }])
  }
  function removeLine(index: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev))
  }

  const routeValid = !!fromWarehouseId && !!toWarehouseId && fromWarehouseId !== toWarehouseId
  const validLines = lines.filter((l) => l.itemId && Number(l.qty) > 0)
  const linesValid = validLines.length > 0

  async function submit(): Promise<boolean> {
    setMessage(null)
    if (!fromWarehouseId || !toWarehouseId) {
      setMessage('انبار مبدأ و مقصد را انتخاب کنید.')
      return false
    }
    if (fromWarehouseId === toWarehouseId) {
      setMessage('انبار مبدأ و مقصد نمی‌توانند یکسان باشند.')
      return false
    }
    if (validLines.length === 0) {
      setMessage('حداقل یک ردیف معتبر (کالا + تعداد) لازم است.')
      return false
    }
    setSubmitting(true)
    try {
      const transfer = await createStockTransfer(
        token,
        {
          transfer_date: transferDate,
          from_warehouse_id: fromWarehouseId,
          to_warehouse_id: toWarehouseId,
          description,
          lines: validLines.map((l) => ({ item_id: l.itemId, qty: Number(l.qty) })),
        },
        idempotencyKey.current,
      )
      idempotencyKey.current = newIdempotencyKey()
      setLines([{ itemId: '', qty: '' }])
      setDescription('')
      setMessage(
        transfer.journal_entry_id
          ? 'حواله ثبت شد؛ چون دو انبار معینِ موجودیِ متفاوت دارند، سندِ جابه‌جایی هم صادر شد.'
          : 'حواله انتقال با موفقیت ثبت شد.',
      )
      onCreated?.()
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    fromWarehouseId,
    setFromWarehouseId,
    toWarehouseId,
    setToWarehouseId,
    transferDate,
    setTransferDate,
    description,
    setDescription,
    lines,
    updateLine,
    addLine,
    removeLine,
    message,
    setMessage,
    submitting,
    goodsItems,
    warehouseById,
    itemById,
    routeValid,
    linesValid,
    submit,
  }
}

export type TransferDraft = ReturnType<typeof useTransferDraft>
