import { useEffect, useState } from 'react'
import { createStockAdjustment, fetchStockAdjustments, type StockAdjustmentRecord } from '../api'
import { todayIso } from './jalali'

/** منطقِ مشترکِ «تعدیل دستیِ موجودی» — یک رکورد (کالا/انبار/جهت/مقدار/دلیل/تاریخ) + تاریخچه. */
export function useStockAdjustmentDraft({ token, onAdjusted }: { token: string; onAdjusted?: () => void }) {
  const [itemId, setItemId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [qtyDiff, setQtyDiff] = useState('')
  const [direction, setDirection] = useState<'shortage' | 'surplus'>('shortage')
  const [reason, setReason] = useState('')
  const [adjustmentDate, setAdjustmentDate] = useState(todayIso())
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [history, setHistory] = useState<StockAdjustmentRecord[]>([])

  async function refresh() {
    try {
      setHistory(await fetchStockAdjustments(token))
    } catch {
      // تاریخچه صرفاً نمایشی است؛ خطایش نباید مانعِ ثبت شود.
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const magnitude = Number(qtyDiff)
  const targetValid = !!itemId && !!warehouseId
  const valid = targetValid && !!magnitude && magnitude > 0

  async function submit(): Promise<boolean> {
    setMessage(null)
    if (!valid) {
      setMessage('کالا، انبار و مقدار (بزرگ‌تر از صفر) الزامی است.')
      return false
    }
    setSubmitting(true)
    try {
      await createStockAdjustment(token, {
        item_id: itemId,
        warehouse_id: warehouseId,
        qty_diff: direction === 'shortage' ? -magnitude : magnitude,
        reason,
        adjustment_date: adjustmentDate,
      })
      setQtyDiff('')
      setReason('')
      await refresh()
      onAdjusted?.()
      setMessage('تعدیل موجودی ثبت شد.')
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    itemId,
    setItemId,
    warehouseId,
    setWarehouseId,
    qtyDiff,
    setQtyDiff,
    direction,
    setDirection,
    reason,
    setReason,
    adjustmentDate,
    setAdjustmentDate,
    message,
    setMessage,
    submitting,
    history,
    refresh,
    targetValid,
    valid,
    submit,
  }
}

export type StockAdjustmentDraft = ReturnType<typeof useStockAdjustmentDraft>
