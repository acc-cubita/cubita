import { useState } from 'react'
import { Plus } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../../electron.d'
import { useTransferDraft, type TransferDraft } from '../../lib/transferDraft'
import { JalaliDatePicker } from '../JalaliDatePicker'
import { TransferLinesTable } from '../TransferForm'
import { TaskFlow, type WizardStep } from './TaskFlow'

/** ویزاردِ «انتقال بین انبار» — دو مرحله + پیش‌نمایشِ زنده. فهرست را صفحه زیرِ ویزارد می‌گذارد. */
export function TransferWizard({
  token,
  warehouses,
  items,
  onCreated,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onCreated?: () => void
}) {
  const d = useTransferDraft({ token, warehouses, items, onCreated })
  const [resetTick, setResetTick] = useState(0)

  if (warehouses.length < 2 || d.goodsItems.length === 0) {
    return (
      <section className="taskflow">
        <h2 className="taskflow-title">حواله انتقال بین انبارها</h2>
        <p className="hint">برای ثبت حواله حداقل به دو انبار و یک کالای غیرخدماتی نیاز است.</p>
      </section>
    )
  }

  const steps: WizardStep[] = [
    {
      key: 'route',
      title: 'مبدأ و مقصد',
      subtitle: 'انبارِ مبدأ و مقصد و تاریخِ حواله را مشخص کنید.',
      canAdvance: d.routeValid,
      blockHint: 'انبار مبدأ و مقصدِ متفاوت را انتخاب کنید.',
      body: (
        <div className="invoice-form">
          <label>
            انبار مبدأ
            <select value={d.fromWarehouseId} onChange={(e) => d.setFromWarehouseId(e.target.value)}>
              <option value="">— انتخاب —</option>
              {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
            </select>
          </label>
          <label>
            انبار مقصد
            <select value={d.toWarehouseId} onChange={(e) => d.setToWarehouseId(e.target.value)}>
              <option value="">— انتخاب —</option>
              {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
            </select>
          </label>
          <label>
            تاریخ حواله
            <JalaliDatePicker value={d.transferDate} onChange={d.setTransferDate} />
          </label>
          <label className="field-full">
            توضیحات
            <input type="text" value={d.description} onChange={(e) => d.setDescription(e.target.value)} />
          </label>
        </div>
      ),
    },
    {
      key: 'lines',
      title: 'اقلام',
      subtitle: 'کالاها و تعدادِ انتقالی را وارد کنید.',
      canAdvance: d.linesValid,
      blockHint: 'حداقل یک ردیف با کالا و تعداد لازم است.',
      body: (
        <>
          <TransferLinesTable d={d} />
          <div>
            <button type="button" onClick={d.addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
          </div>
        </>
      ),
    },
  ]

  return (
    <TaskFlow
      title="حواله انتقال بین انبارها"
      steps={steps}
      submitLabel="ثبت حواله"
      submitting={d.submitting}
      message={d.message}
      resetKey={resetTick}
      preview={<LivePreview d={d} warehouses={warehouses} />}
      onSubmit={() => {
        void d.submit().then((ok) => {
          if (ok) setResetTick((t) => t + 1)
        })
      }}
    />
  )
}

function LivePreview({ d, warehouses }: { d: TransferDraft; warehouses: WarehouseCache[] }) {
  const from = warehouses.find((w) => w.id === d.fromWarehouseId)
  const to = warehouses.find((w) => w.id === d.toWarehouseId)
  const lineCount = d.lines.filter((l) => l.itemId && Number(l.qty) > 0).length
  const totalQty = d.lines.reduce((s, l) => (l.itemId ? s + (Number(l.qty) || 0) : s), 0)
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ حواله</p>
      <div className="live-preview-row"><span>از انبار</span><strong>{from?.name ?? '—'}</strong></div>
      <div className="live-preview-row"><span>به انبار</span><strong>{to?.name ?? '—'}</strong></div>
      <div className="live-preview-row"><span>تاریخ</span><strong>{d.transferDate}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row"><span>تعداد ردیف</span><strong>{lineCount.toLocaleString('fa-IR')}</strong></div>
      <div className="live-preview-row live-preview-total"><span>مجموع مقدار</span><strong>{totalQty.toLocaleString('fa-IR')}</strong></div>
    </div>
  )
}
