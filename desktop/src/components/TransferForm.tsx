import { useEffect, useState } from 'react'
import { ArrowLeftRight, Plus, Trash2, Save, RefreshCw } from 'lucide-react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import { createStockTransfer, fetchStockTransfers, type StockTransferRecord } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

interface DraftLine {
  itemId: string
  qty: string
}

export function TransferForm({
  token,
  warehouses,
  items,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
}) {
  const [fromWarehouseId, setFromWarehouseId] = useState('')
  const [toWarehouseId, setToWarehouseId] = useState('')
  const [transferDate, setTransferDate] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([{ itemId: '', qty: '' }])
  const [message, setMessage] = useState<string | null>(null)
  const [transfers, setTransfers] = useState<StockTransferRecord[]>([])

  const goodsItems = items.filter((i) => !i.is_service)
  const warehouseById = new Map(warehouses.map((w) => [w.id, w]))
  const itemById = new Map(items.map((i) => [i.id, i]))

  async function refresh() {
    try {
      setTransfers(await fetchStockTransfers(token))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  function addLine() {
    setLines((prev) => [...prev, { itemId: '', qty: '' }])
  }

  function removeLine(index: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== index) : prev))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)

    if (!fromWarehouseId || !toWarehouseId) {
      setMessage('انبار مبدأ و مقصد را انتخاب کنید.')
      return
    }
    if (fromWarehouseId === toWarehouseId) {
      setMessage('انبار مبدأ و مقصد نمی‌توانند یکسان باشند.')
      return
    }
    const validLines = lines.filter((l) => l.itemId && Number(l.qty) > 0)
    if (validLines.length === 0) {
      setMessage('حداقل یک ردیف معتبر (کالا + تعداد) لازم است.')
      return
    }

    try {
      await createStockTransfer(token, {
        transfer_date: transferDate,
        from_warehouse_id: fromWarehouseId,
        to_warehouse_id: toWarehouseId,
        description,
        lines: validLines.map((l) => ({ item_id: l.itemId, qty: Number(l.qty) })),
      })
      setLines([{ itemId: '', qty: '' }])
      setDescription('')
      setMessage('حواله انتقال با موفقیت ثبت شد.')
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard
      icon={ArrowLeftRight}
      title="حواله انتقال بین انبارها"
      description="جابه‌جایی کالا بین دو انبار؛ چون فقط محل موجودی تغییر می‌کند، سند حسابداری‌ای ساخته نمی‌شود."
      actions={
        <button onClick={() => void refresh()}>
          <RefreshCw size={13} /> به‌روزرسانی
        </button>
      }
    >
      {warehouses.length < 2 || goodsItems.length === 0 ? (
        <p className="hint">برای ثبت حواله حداقل به دو انبار و یک کالای غیرخدماتی نیاز است.</p>
      ) : (
        <form className="invoice-form" onSubmit={handleSubmit}>
          <label>
            انبار مبدأ
            <select value={fromWarehouseId} onChange={(e) => setFromWarehouseId(e.target.value)}>
              <option value="">— انتخاب —</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            انبار مقصد
            <select value={toWarehouseId} onChange={(e) => setToWarehouseId(e.target.value)}>
              <option value="">— انتخاب —</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            تاریخ حواله
            <JalaliDatePicker value={transferDate} onChange={setTransferDate} />
          </label>
          <label>
            توضیحات
            <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>

          <table className="invoice-lines">
            <thead>
              <tr>
                <th>کالا</th>
                <th>تعداد</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, i) => (
                <tr key={i}>
                  <td>
                    <select value={line.itemId} onChange={(e) => updateLine(i, { itemId: e.target.value })}>
                      <option value="">— انتخاب کالا —</option>
                      {goodsItems.map((it) => (
                        <option key={it.id} value={it.id}>
                          {it.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={line.qty}
                      onChange={(e) => updateLine(i, { qty: e.target.value })}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="icon-btn-danger"
                      onClick={() => removeLine(i)}
                      disabled={lines.length === 1}
                      aria-label="حذف ردیف"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="invoice-form-footer">
            <button type="button" onClick={addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <button type="submit" className="btn-primary">
              <Save size={14} /> ثبت حواله
            </button>
          </div>
          {message && <div className="hint">{message}</div>}
        </form>
      )}

      {transfers.length === 0 ? (
        <EmptyState icon={ArrowLeftRight} text="حواله‌ای ثبت نشده." />
      ) : (
        <table>
          <thead>
            <tr>
              <th>شماره</th>
              <th>تاریخ</th>
              <th>از</th>
              <th>به</th>
              <th>ردیف‌ها</th>
            </tr>
          </thead>
          <tbody>
            {transfers.map((t) => (
              <tr key={t.id}>
                <td>{t.number != null ? t.number.toLocaleString('fa-IR') : '—'}</td>
                <td>{formatJalali(t.transfer_date)}</td>
                <td>{warehouseById.get(t.from_warehouse_id)?.name ?? '—'}</td>
                <td>{warehouseById.get(t.to_warehouse_id)?.name ?? '—'}</td>
                <td>
                  {t.lines
                    .map((l) => `${itemById.get(l.item_id)?.name ?? l.item_id} (${Number(l.qty).toLocaleString('fa-IR')})`)
                    .join('، ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </SectionCard>
  )
}
