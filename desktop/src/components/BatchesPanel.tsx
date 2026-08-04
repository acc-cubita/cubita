import { useEffect, useMemo, useState } from 'react'
import { CalendarClock, PackagePlus, Trash2, AlertTriangle } from 'lucide-react'
import {
  createStockBatch,
  deleteStockBatch,
  fetchItemsLive,
  fetchStockBatches,
  fetchWarehousesLive,
  type ItemRecord,
  type StockBatchRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

const fa = (n: number) => n.toLocaleString('fa-IR')

function daysUntil(iso: string | null): number | null {
  if (!iso) return null
  const ms = new Date(iso).getTime() - Date.now()
  return Math.ceil(ms / 86_400_000)
}

export function BatchesPanel({ token }: { token: string }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [batches, setBatches] = useState<StockBatchRecord[]>([])
  const pg = usePagination(batches, 10)
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const [itemId, setItemId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [batchNumber, setBatchNumber] = useState('')
  const [expiry, setExpiry] = useState('')
  const [qty, setQty] = useState('')
  const [received, setReceived] = useState(todayIso())

  async function refresh() {
    setError(null)
    try {
      const [its, ws, bs] = await Promise.all([fetchItemsLive(token), fetchWarehousesLive(token), fetchStockBatches(token)])
      setItems(its.filter((i) => !i.is_service && i.is_active))
      setWarehouses(ws)
      if (ws[0] && !warehouseId) setWarehouseId(ws[0].id)
      setBatches(bs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const itemById = useMemo(() => new Map(items.map((i) => [i.id, i])), [items])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!itemId || !warehouseId || !batchNumber.trim()) {
      setMsg('کالا، انبار و شماره‌ی بچ الزامی است.')
      return
    }
    try {
      await createStockBatch(token, {
        item_id: itemId,
        warehouse_id: warehouseId,
        batch_number: batchNumber.trim(),
        expiry_date: expiry || null,
        qty: Number(qty) || 0,
        received_date: received,
      })
      setBatchNumber('')
      setExpiry('')
      setQty('')
      setMsg('بچ ثبت شد.')
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function remove(id: string) {
    await deleteStockBatch(token, id)
    await refresh()
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={PackagePlus} title="ثبتِ بچ / سری" description="بچِ کالا را با تاریخِ انقضا ثبت کنید تا نزدیکِ انقضا هشدار بگیرید.">
        <form className="invoice-form form-full" onSubmit={submit}>
          <label>
            کالا
            <select value={itemId} onChange={(e) => setItemId(e.target.value)} required>
              <option value="">— انتخاب —</option>
              {items.map((i) => (
                <option key={i.id} value={i.id}>{i.name}</option>
              ))}
            </select>
          </label>
          <div className="field-row">
            <label>
              انبار
              <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </label>
            <label>
              شماره‌ی بچ/سری
              <input type="text" value={batchNumber} onChange={(e) => setBatchNumber(e.target.value)} placeholder="مثلاً L-1403-05" />
            </label>
          </div>
          <div className="field-row">
            <label>
              تعداد
              <NumberInput allowDecimal value={qty} onChange={setQty} />
            </label>
            <label>
              تاریخِ انقضا
              <JalaliDatePicker value={expiry || todayIso()} onChange={setExpiry} />
            </label>
          </div>
          <label>
            تاریخِ ورود
            <JalaliDatePicker value={received} onChange={setReceived} />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><PackagePlus size={14} /> ثبتِ بچ</button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </form>
      </SectionCard>

      <SectionCard icon={CalendarClock} title="بچ‌ها و تاریخِ انقضا" description={`${fa(batches.length)} بچ`}>
        {error && <div className="error">{error}</div>}
        {batches.length === 0 ? (
          <EmptyState icon={CalendarClock} text="بچی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead>
                <tr><th>کالا</th><th>بچ</th><th>تعداد</th><th>انقضا</th><th></th></tr>
              </thead>
              <tbody>
                {pg.pageItems.map((b) => {
                  const d = daysUntil(b.expiry_date)
                  const soon = d !== null && d <= 30
                  const expired = d !== null && d < 0
                  return (
                    <tr key={b.id}>
                      <td className="entity-name">{itemById.get(b.item_id)?.name ?? '—'}</td>
                      <td className="ltr-cell">{b.batch_number}</td>
                      <td>{Number(b.qty).toLocaleString('fa-IR')}</td>
                      <td>
                        {b.expiry_date ? (
                          <span className={`status-badge ${expired ? 'tone-danger' : soon ? 'tone-warning' : 'tone-success'}`}>
                            {(expired || soon) && <AlertTriangle size={12} />}
                            {formatJalali(b.expiry_date)}
                            {d !== null && (expired ? ' (منقضی)' : soon ? ` (${fa(d)} روز)` : '')}
                          </span>
                        ) : '—'}
                      </td>
                      <td>
                        <button type="button" className="icon-btn-danger" onClick={() => void remove(b.id)} aria-label="حذف"><Trash2 size={13} /></button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}
