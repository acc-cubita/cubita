import { Warehouse, Save } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali } from '../lib/jalali'
import { useStockAdjustmentDraft, type StockAdjustmentDraft } from '../lib/stockAdjustmentDraft'

/** فرمِ کلاسیکِ «تعدیل دستیِ موجودی» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ
 *  [useStockAdjustmentDraft]. */
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
  const d = useStockAdjustmentDraft({ token, onAdjusted })

  return (
    <SectionCard icon={Warehouse} title="انبارگردانی (تعدیل موجودی)">
      <p className="hint">این عملیات آنلاین‌محور است و مستقیم روی سرور ثبت می‌شود.</p>
      <form
        className="invoice-form"
        onSubmit={(e) => {
          e.preventDefault()
          void d.submit()
        }}
      >
        <label>
          کالا
          <select value={d.itemId} onChange={(e) => d.setItemId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {items.map((i) => (<option key={i.id} value={i.id}>{i.name}</option>))}
          </select>
        </label>
        <label>
          انبار
          <select value={d.warehouseId} onChange={(e) => d.setWarehouseId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
          </select>
        </label>
        <label>
          نوع تعدیل
          <select value={d.direction} onChange={(e) => d.setDirection(e.target.value as 'shortage' | 'surplus')}>
            <option value="shortage">کسری (کاهش موجودی)</option>
            <option value="surplus">اضافی (افزایش موجودی)</option>
          </select>
        </label>
        <label>
          مقدار
          <NumberInput allowDecimal allowNegative value={d.qtyDiff} onChange={d.setQtyDiff} />
        </label>
        <label>
          دلیل
          <input type="text" value={d.reason} onChange={(e) => d.setReason(e.target.value)} />
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={d.adjustmentDate} onChange={d.setAdjustmentDate} />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={d.submitting}><Save size={14} /> ثبت تعدیل</button>
        </div>
        {d.message && <div className="hint">{d.message}</div>}
      </form>

      <StockAdjustmentHistory d={d} />
    </SectionCard>
  )
}

/** تاریخچه‌ی تعدیل‌ها — مشترکِ فرم و ویزارد. */
export function StockAdjustmentHistory({ d }: { d: StockAdjustmentDraft }) {
  if (d.history.length === 0) return null
  return (
    <div className="table-scroll">
      <table className="cards-on-mobile">
        <thead>
          <tr><th>تاریخ</th><th>مقدار</th><th>دلیل</th></tr>
        </thead>
        <tbody>
          {d.history.map((h) => (
            <tr key={h.id}>
              <td data-label="تاریخ">{formatJalali(h.adjustment_date)}</td>
              <td data-label="مقدار">{Number(h.qty_diff) > 0 ? '+' : ''}{Number(h.qty_diff).toLocaleString('fa-IR')}</td>
              <td data-label="دلیل">{h.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
