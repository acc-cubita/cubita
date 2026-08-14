import type { ItemCache, WarehouseCache } from '../../electron.d'
import { useStockAdjustmentDraft, type StockAdjustmentDraft } from '../../lib/stockAdjustmentDraft'
import { NumberInput } from '../NumberInput'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { StockAdjustmentHistory } from '../StockAdjustmentForm'
import { TaskFlow, type WizardStep } from './TaskFlow'

/** ویزاردِ «تعدیل دستیِ موجودی» — دو مرحله + پیش‌نمایشِ زنده؛ تاریخچه زیرِ ویزارد. */
export function StockAdjustmentWizard({
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

  const steps: WizardStep[] = [
    {
      key: 'target',
      title: 'کالا و انبار',
      subtitle: 'کالا، انبار و نوعِ تعدیل (کسری یا اضافی) را انتخاب کنید.',
      canAdvance: d.targetValid,
      blockHint: 'کالا و انبار را انتخاب کنید.',
      body: (
        <div className="invoice-form">
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
        </div>
      ),
    },
    {
      key: 'amount',
      title: 'مقدار و دلیل',
      subtitle: 'مقدارِ تعدیل، دلیل و تاریخ را وارد کنید، بعد ثبت را بزنید.',
      body: (
        <div className="invoice-form">
          <label>
            مقدار
            <NumberInput allowDecimal value={d.qtyDiff} onChange={d.setQtyDiff} />
          </label>
          <label>
            دلیل
            <input type="text" value={d.reason} onChange={(e) => d.setReason(e.target.value)} />
          </label>
          <label>
            تاریخ
            <JalaliDatePicker value={d.adjustmentDate} onChange={d.setAdjustmentDate} />
          </label>
        </div>
      ),
    },
  ]

  return (
    <>
      <p className="hint">این عملیات آنلاین‌محور است و مستقیم روی سرور ثبت می‌شود.</p>
      <TaskFlow
        title="تعدیل دستیِ موجودی"
        steps={steps}
        submitLabel="ثبت تعدیل"
        submitting={d.submitting}
        message={d.message}
        preview={<LivePreview d={d} items={items} warehouses={warehouses} />}
        onSubmit={() => void d.submit()}
      />
      <section>
        <div className="section-card-header"><div className="section-card-heading"><div><h2>تاریخچه‌ی تعدیل‌ها</h2></div></div></div>
        <StockAdjustmentHistory d={d} />
      </section>
    </>
  )
}

function LivePreview({ d, items, warehouses }: { d: StockAdjustmentDraft; items: ItemCache[]; warehouses: WarehouseCache[] }) {
  const item = items.find((i) => i.id === d.itemId)
  const warehouse = warehouses.find((w) => w.id === d.warehouseId)
  const mag = Number(d.qtyDiff) || 0
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ تعدیل</p>
      <div className="live-preview-row"><span>کالا</span><strong>{item?.name ?? '—'}</strong></div>
      <div className="live-preview-row"><span>انبار</span><strong>{warehouse?.name ?? '—'}</strong></div>
      <div className="live-preview-row"><span>نوع</span><strong>{d.direction === 'shortage' ? 'کسری' : 'اضافی'}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total">
        <span>تغییرِ موجودی</span>
        <strong>{mag ? `${d.direction === 'shortage' ? '−' : '+'}${mag.toLocaleString('fa-IR')}` : '—'} {item?.unit ?? ''}</strong>
      </div>
    </div>
  )
}
