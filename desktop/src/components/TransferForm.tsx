import { ArrowLeftRight, Plus, Trash2, Save } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { useTransferDraft, type TransferDraft } from '../lib/transferDraft'
import { SearchSelect } from '../components/SearchSelect'

/** فرمِ کلاسیکِ «انتقال بین انبار» (پوسته‌های تیره/روشن). منطق در هوکِ مشترکِ [useTransferDraft]. */
export function TransferForm({
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

  return (
    <SectionCard
      icon={ArrowLeftRight}
      title="حواله انتقال بین انبارها"
      description="جابه‌جایی کالا بین دو انبار. جمعِ موجودیِ شرکت عوض نمی‌شود؛ سندِ حسابداری فقط وقتی صادر می‌شود که دو انبار معینِ موجودیِ متفاوت داشته باشند."
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
            <SearchSelect value={d.fromWarehouseId} onChange={(e) => d.setFromWarehouseId(e.target.value)}>
              <option value="">— انتخاب —</option>
              {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
            </SearchSelect>
          </label>
          <label>
            انبار مقصد
            <SearchSelect value={d.toWarehouseId} onChange={(e) => d.setToWarehouseId(e.target.value)}>
              <option value="">— انتخاب —</option>
              {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
            </SearchSelect>
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
                <SearchSelect value={line.itemId} onChange={(e) => d.updateLine(i, { itemId: e.target.value })}>
                  <option value="">— انتخاب کالا —</option>
                  {d.goodsItems.map((it) => (<option key={it.id} value={it.id}>{it.name}</option>))}
                </SearchSelect>
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

