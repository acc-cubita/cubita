import { useEffect, useMemo, useState } from 'react'
import { CalendarClock, PackagePlus, Trash2, AlertTriangle, ScanBarcode } from 'lucide-react'
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
import { BatchDetailDrawer } from './BatchDetailDrawer'
import { formatJalali, todayIso } from '../lib/jalali'

const SOURCE_LABEL: Record<string, { label: string; tone: string }> = {
  purchase_invoice: { label: 'خرید', tone: 'tone-success' },
  marketplace: { label: 'بازار', tone: 'tone-success' },
  manual: { label: 'دستی', tone: 'tone-muted' },
}

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
  const [detail, setDetail] = useState<StockBatchRecord | null>(null)

  const [itemId, setItemId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [batchNumber, setBatchNumber] = useState('')
  const [expiry, setExpiry] = useState('')
  const [production, setProduction] = useState('')
  const [qty, setQty] = useState('')
  const [unitCost, setUnitCost] = useState('')
  const [consumerPrice, setConsumerPrice] = useState('')
  const [received, setReceived] = useState(todayIso())

  async function refresh() {
    setError(null)
    try {
      const [its, ws, bs] = await Promise.all([fetchItemsLive(token), fetchWarehousesLive(token), fetchStockBatches(token)])
      setItems(its.filter((i) => !i.is_service && i.is_active))
      setWarehouses(ws)
      if (ws[0] && !warehouseId) setWarehouseId(ws[0].id)
      setBatches(bs)
      // اگر درایورِ جزئیات باز است، همان بار را تازه نگه دار (مقدار/معیوب به‌روز شود)
      setDetail((cur) => (cur ? bs.find((b) => b.id === cur.id) ?? null : null))
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
        production_date: production || null,
        qty: Number(qty) || 0,
        unit_cost: Number(unitCost) || 0,
        consumer_price: Number(consumerPrice) || 0,
        received_date: received,
      })
      setBatchNumber('')
      setExpiry('')
      setProduction('')
      setQty('')
      setUnitCost('')
      setConsumerPrice('')
      setMsg('بار ثبت شد.')
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
      <SectionCard icon={PackagePlus} title="ثبتِ بارِ دستی" description="معمولاً بارها با فاکتورِ خرید خودکار ساخته می‌شوند؛ این فرم برای بارِ دستی (مثلاً موجودیِ اول دوره) است.">
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
              قیمتِ خرید (واحد)
              <NumberInput value={unitCost} onChange={setUnitCost} placeholder="۰" />
            </label>
          </div>
          <div className="field-row">
            <label>
              قیمتِ مصرف‌کننده
              <NumberInput value={consumerPrice} onChange={setConsumerPrice} placeholder="برای حاشیه‌ی سود" />
            </label>
            {(() => {
              const buy = Number(unitCost) || 0, sell = Number(consumerPrice) || 0
              if (buy > 0 && sell > buy) {
                const pct = ((sell - buy) / sell) * 100
                return <div className="hint" style={{ alignSelf: 'end' }}>سود: {fa(sell - buy)} ({pct.toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪)</div>
              }
              return <div />
            })()}
          </div>
          <div className="field-row">
            <label>
              تاریخِ تولید
              <JalaliDatePicker value={production || todayIso()} onChange={setProduction} />
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

      <SectionCard
        icon={CalendarClock}
        title="بارهای ورودی (بچ)"
        description={`${fa(batches.length)} بار — هر خرید خودکار یک بار می‌سازد. روی «مدیریت» بزنید تا سریالِ کارتن اضافه یا کسری/معیوب ثبت کنید.`}
      >
        {error && <div className="error">{error}</div>}
        {batches.length === 0 ? (
          <EmptyState icon={CalendarClock} text="باری ثبت نشده — با ثبتِ فاکتورِ خرید خودکار ساخته می‌شود." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr><th>کالا</th><th>بار</th><th>منشأ</th><th>ورودی/مانده</th><th>کسری</th><th>سریال</th><th>انقضا</th><th></th></tr>
              </thead>
              <tbody>
                {pg.pageItems.map((b) => {
                  const d = daysUntil(b.expiry_date)
                  const soon = d !== null && d <= 30
                  const expired = d !== null && d < 0
                  const src = SOURCE_LABEL[b.source_type] ?? SOURCE_LABEL.manual
                  const defect = Number(b.defect_qty)
                  return (
                    <tr key={b.id}>
                      <td className="entity-name card-title">{itemById.get(b.item_id)?.name ?? '—'}</td>
                      <td className="ltr-cell" data-label="بار">{b.batch_number}</td>
                      <td data-label="منشأ"><span className={`status-badge ${src.tone}`}>{src.label}</span></td>
                      <td data-label="ورودی/مانده">{fa(Number(b.received_qty))} / <strong>{fa(Number(b.qty))}</strong></td>
                      <td data-label="کسری" className={defect > 0 ? 'stock-over' : undefined}>{defect > 0 ? fa(defect) : '—'}</td>
                      <td data-label="سریال">{b.serial_count > 0 ? fa(b.serial_count) : '—'}</td>
                      <td data-label="انقضا">
                        {b.expiry_date ? (
                          <span className={`status-badge ${expired ? 'tone-danger' : soon ? 'tone-warning' : 'tone-success'}`}>
                            {(expired || soon) && <AlertTriangle size={12} />}
                            {formatJalali(b.expiry_date)}
                            {d !== null && (expired ? ' (منقضی)' : soon ? ` (${fa(d)} روز)` : '')}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="card-actions">
                        <div className="check-actions">
                          <button type="button" onClick={() => setDetail(b)}><ScanBarcode size={13} /> مدیریت</button>
                          <button type="button" className="icon-btn-danger" onClick={() => void remove(b.id)} aria-label="حذف"><Trash2 size={13} /> حذف</button>
                        </div>
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

      {detail && (
        <BatchDetailDrawer
          token={token}
          batch={detail}
          itemName={itemById.get(detail.item_id)?.name ?? '—'}
          onClose={() => setDetail(null)}
          onChanged={() => void refresh()}
        />
      )}
    </div>
  )
}
