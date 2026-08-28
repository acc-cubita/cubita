import { ArrowLeftRight, Plus, Trash2, Save, RefreshCw } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali } from '../lib/jalali'
import { useTransferDraft, type TransferDraft } from '../lib/transferDraft'

/** فرمِ کلاسیکِ «انتقال بین انبار» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ [useTransferDraft]. */
export function TransferForm({
  token,
  warehouses,
  items,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
}) {
  const d = useTransferDraft({ token, warehouses, items })

  return (
    <SectionCard
      icon={ArrowLeftRight}
      title="حواله انتقال بین انبارها"
      description="جابه‌جایی کالا بین دو انبار؛ چون فقط محل موجودی تغییر می‌کند، سند حسابداری‌ای ساخته نمی‌شود."
      actions={
        <button onClick={() => void d.refresh()}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      {warehouses.length < 2 || d.goodsItems.length === 0 ? (
        <p className="hint">برای ثبت حواله حداقل به دو انبار و یک کالای غیرخدماتی نیاز است.</p>
      ) : (
        <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void d.submit()
          }}
        >
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
          <label>
            توضیحات
            <input type="text" value={d.description} onChange={(e) => d.setDescription(e.target.value)} />
          </label>

          <TransferLinesTable d={d} />

          <div className="invoice-form-footer">
            <button type="button" onClick={d.addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <button type="submit" className="btn-primary" disabled={d.submitting}>
              <Save size={14} /> ثبت حواله
            </button>
          </div>
          {d.message && <div className="hint">{d.message}</div>}
        </form>
      )}

      <TransfersList d={d} />
    </SectionCard>
  )
}

/** گریدِ ردیف‌های انتقال (کالا + تعداد) — مشترکِ فرم و ویزارد. */
export function TransferLinesTable({ d }: { d: TransferDraft }) {
  return (
    <div className="table-scroll">
      <table className="invoice-lines cards-on-mobile">
        <thead>
          <tr><th>کالا</th><th>تعداد</th><th></th></tr>
        </thead>
        <tbody>
          {d.lines.map((line, i) => (
            <tr key={i}>
              <td data-label="کالا">
                <select value={line.itemId} onChange={(e) => d.updateLine(i, { itemId: e.target.value })}>
                  <option value="">— انتخاب کالا —</option>
                  {d.goodsItems.map((it) => (<option key={it.id} value={it.id}>{it.name}</option>))}
                </select>
              </td>
              <td data-label="تعداد">
                <NumberInput allowDecimal value={line.qty} onChange={(v) => d.updateLine(i, { qty: v })} />
              </td>
              <td className="card-actions">
                <button type="button" className="icon-btn-danger" onClick={() => d.removeLine(i)} disabled={d.lines.length === 1} aria-label="حذف ردیف">
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** فهرستِ حواله‌های ثبت‌شده — مشترکِ فرم و ویزارد. */
export function TransfersList({ d }: { d: TransferDraft }) {
  if (d.transfers.length === 0) {
    return <EmptyState icon={ArrowLeftRight} text="حواله‌ای ثبت نشده." />
  }
  return (
    <div className="table-scroll">
      <table className="cards-on-mobile">
        <thead>
          <tr><th>شماره</th><th>تاریخ</th><th>از</th><th>به</th><th>ردیف‌ها</th></tr>
        </thead>
        <tbody>
          {d.transfers.map((t) => (
            <tr key={t.id}>
              <td data-label="شماره">{t.number != null ? t.number.toLocaleString('fa-IR') : '—'}</td>
              <td data-label="تاریخ">{formatJalali(t.transfer_date)}</td>
              <td data-label="از">{d.warehouseById.get(t.from_warehouse_id)?.name ?? '—'}</td>
              <td data-label="به">{d.warehouseById.get(t.to_warehouse_id)?.name ?? '—'}</td>
              <td data-label="ردیف‌ها">
                {t.lines.map((l) => `${d.itemById.get(l.item_id)?.name ?? l.item_id} (${Number(l.qty).toLocaleString('fa-IR')})`).join('، ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
