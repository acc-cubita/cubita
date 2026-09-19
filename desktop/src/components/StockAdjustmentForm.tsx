import { useState } from 'react'
import { Warehouse, Save } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import type { StockAdjustmentRecord } from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali } from '../lib/jalali'
import { useStockAdjustmentDraft, type StockAdjustmentDraft } from '../lib/stockAdjustmentDraft'
import { SearchSelect } from '../components/SearchSelect'

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
          <SearchSelect value={d.itemId} onChange={(e) => d.setItemId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {items.map((i) => (<option key={i.id} value={i.id}>{i.name}</option>))}
          </SearchSelect>
        </label>
        <label>
          انبار
          <SearchSelect value={d.warehouseId} onChange={(e) => d.setWarehouseId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
          </SearchSelect>
        </label>
        <label>
          نوع تعدیل
          <SearchSelect value={d.direction} onChange={(e) => d.setDirection(e.target.value as 'shortage' | 'surplus')}>
            <option value="shortage">کسری (کاهش موجودی)</option>
            <option value="surplus">اضافی (افزایش موجودی)</option>
          </SearchSelect>
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

/** تاریخچه‌ی تعدیل‌ها — مشترکِ فرم و ویزارد.
 *
 *  ستونِ «وضعیت» و دکمه‌ی ابطال از این‌جا می‌آیند. تعدیل سندی است که کارش اصلاحِ
 *  خطاست و تا امروز خودش اصلاح نمی‌شد: تنها راه، ثبتِ یک تعدیلِ معکوسِ دوم بود که
 *  در همین جدول **دو ردیفِ ظاهراً واقعی** می‌گذاشت، بی هیچ نشانه‌ای که دومی
 *  اشتباهِ اولی را می‌پوشاند. ابطال هر دو را اعتراف می‌کند و ردیفِ اصلی سرِ جایش
 *  می‌ماند — «هرگز حذف نکن». */
export function StockAdjustmentHistory({ d }: { d: StockAdjustmentDraft }) {
  const [voidingId, setVoidingId] = useState<string | null>(null)
  const [why, setWhy] = useState('')

  if (d.history.length === 0) return null
  return (
    <div className="table-scroll">
      <table className="cards-on-mobile">
        <thead>
          <tr><th>تاریخ</th><th>مقدار</th><th>دلیل</th><th>وضعیت</th><th /></tr>
        </thead>
        <tbody>
          {d.history.map((h) => (
            <AdjustmentRow
              key={h.id}
              row={h}
              busy={d.submitting}
              voiding={voidingId === h.id}
              why={why}
              onWhy={setWhy}
              onStart={() => {
                setVoidingId(h.id)
                setWhy('')
              }}
              onCancel={() => setVoidingId(null)}
              onConfirm={() => {
                void d.voidOne(h.id, why).then((ok) => {
                  if (ok) setVoidingId(null)
                })
              }}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AdjustmentRow({
  row,
  busy,
  voiding,
  why,
  onWhy,
  onStart,
  onCancel,
  onConfirm,
}: {
  row: StockAdjustmentRecord
  busy: boolean
  voiding: boolean
  why: string
  onWhy: (v: string) => void
  onStart: () => void
  onCancel: () => void
  onConfirm: () => void
}) {
  const qty = Number(row.qty_diff)
  return (
    <>
      <tr>
        <td data-label="تاریخ">{formatJalali(row.adjustment_date)}</td>
        <td data-label="مقدار" className="num">{qty > 0 ? '+' : ''}{qty.toLocaleString('fa-IR')}</td>
        <td data-label="دلیل" className="card-wide">{row.reason}</td>
        <td data-label="وضعیت">
          {row.voided_at ? (
            <span className="status-badge tone-danger" title={row.void_reason}>باطل</span>
          ) : (
            <span className="status-badge tone-success">ثبت‌شده</span>
          )}
        </td>
        <td className="card-actions">
          {!row.voided_at && !voiding && (
            <button type="button" onClick={onStart}>ابطال</button>
          )}
        </td>
      </tr>
      {voiding && (
        <tr>
          <td className="card-full" colSpan={5}>
            <div className="vr-void">
              <input value={why} onChange={(e) => onWhy(e.target.value)} placeholder="علتِ ابطال" />
              <button
                type="button"
                className="btn-danger"
                disabled={busy || why.trim().length < 3}
                onClick={onConfirm}
              >
                ابطالِ تعدیل
              </button>
              <button type="button" onClick={onCancel}>انصراف</button>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
