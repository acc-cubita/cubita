import { useEffect, useState } from 'react'
import { Warehouse, Save } from 'lucide-react'
import { createStockAdjustment, fetchStockAdjustments, type StockAdjustmentRecord } from '../api'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

export function StockAdjustmentForm({
  token,
  warehouses,
  items,
  onAdjusted,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onAdjusted?: () => void
}) {
  const [itemId, setItemId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [qtyDiff, setQtyDiff] = useState('')
  const [direction, setDirection] = useState<'shortage' | 'surplus'>('shortage')
  const [reason, setReason] = useState('')
  const [adjustmentDate, setAdjustmentDate] = useState(todayIso())
  const [message, setMessage] = useState<string | null>(null)
  const [history, setHistory] = useState<StockAdjustmentRecord[]>([])

  async function refresh() {
    try {
      setHistory(await fetchStockAdjustments(token))
    } catch {
      // فهرست تاریخچه صرفاً نمایشی است؛ خطای آن نباید مانع ثبت تعدیل جدید شود
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    const magnitude = Number(qtyDiff)
    if (!itemId || !warehouseId || !magnitude || magnitude <= 0) {
      setMessage('کالا، انبار و مقدار (بزرگ‌تر از صفر) الزامی است.')
      return
    }
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
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard icon={Warehouse} title="انبارگردانی (تعدیل موجودی)">
      <p className="hint">این عملیات آنلاین‌محور است و مستقیم روی سرور ثبت می‌شود.</p>
      <form className="invoice-form" onSubmit={handleSubmit}>
        <label>
          کالا
          <select value={itemId} onChange={(e) => setItemId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          انبار
          <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          نوع تعدیل
          <select value={direction} onChange={(e) => setDirection(e.target.value as 'shortage' | 'surplus')}>
            <option value="shortage">کسری (کاهش موجودی)</option>
            <option value="surplus">اضافی (افزایش موجودی)</option>
          </select>
        </label>
        <label>
          مقدار
          <input type="number" min="0" step="any" value={qtyDiff} onChange={(e) => setQtyDiff(e.target.value)} />
        </label>
        <label>
          دلیل
          <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={adjustmentDate} onChange={setAdjustmentDate} />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary"><Save size={14} /> ثبت تعدیل</button>
        </div>
        {message && <div className="hint">{message}</div>}
      </form>

      {history.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>تاریخ</th>
              <th>مقدار</th>
              <th>دلیل</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id}>
                <td>{formatJalali(h.adjustment_date)}</td>
                <td>{Number(h.qty_diff) > 0 ? '+' : ''}{Number(h.qty_diff).toLocaleString('fa-IR')}</td>
                <td>{h.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionCard>
  )
}
