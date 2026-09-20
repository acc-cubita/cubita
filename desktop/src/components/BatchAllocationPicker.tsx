import { useEffect, useMemo, useState } from 'react'
import { Layers, RotateCcw } from 'lucide-react'
import { fetchAvailableBatches, type StockBatchRecord } from '../api'
import {
  allocationError,
  allocationTotal,
  fefoOrder,
  fefoPlan,
  totalSellable,
  type Allocation,
} from '../lib/batchAllocation'
import { formatJalali } from '../lib/jalali'
import { NumberInput } from './NumberInput'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * انتخابِ بارِ یک ردیفِ خروج — پیش‌فرض FEFO، قابلِ نقض (§۱۱).
 *
 * **پیش‌فرض هیچ‌وقت خالی نیست.** اگر کاربر دست نزند، همین پیشنهاد فرستاده
 * می‌شود و سرور هم مستقلاً همان را حساب می‌کند؛ پس نمایش و ثبت یکی می‌مانند.
 * نقض‌کردنش کارِ انبارداری است که جلوی قفسه ایستاده، نه ما.
 *
 * منطقِ خالص در [lib/batchAllocation](../lib/batchAllocation.ts) است تا تست‌پذیر
 * بماند — محیطِ vitest این پروژه DOM ندارد.
 */
export function BatchAllocationPicker({
  token,
  itemId,
  warehouseId,
  qty,
  value,
  onChange,
}: {
  token: string
  itemId: string
  warehouseId: string
  qty: number
  value: Allocation[] | null
  onChange: (next: Allocation[] | null) => void
}) {
  const [batches, setBatches] = useState<StockBatchRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    let alive = true
    setBatches(null)
    setError(null)
    if (!itemId || !warehouseId) return
    fetchAvailableBatches(token, itemId, warehouseId)
      .then((rows) => {
        if (alive) setBatches(rows)
      })
      .catch((err) => {
        if (alive) setError(err instanceof Error ? err.message : 'خطای ناشناخته')
      })
    return () => {
      alive = false
    }
  }, [token, itemId, warehouseId])

  const options = useMemo(
    () =>
      (batches ?? []).map((b) => ({
        id: b.id,
        batch_number: b.batch_number,
        expiry_date: b.expiry_date,
        sellable_qty: b.sellable_qty,
      })),
    [batches],
  )

  //: پیشنهادِ پیش‌فرض هر بار که مقدار یا کالا عوض شود بازمحاسبه می‌شود — تا وقتی
  //: کاربر صریحاً دست نزده باشد.
  const suggestion = useMemo(() => (qty > 0 ? fefoPlan(options, qty) : []), [options, qty])
  const current = value ?? suggestion

  useEffect(() => {
    if (value === null && suggestion.length > 0) onChange(suggestion)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestion])

  if (!itemId || !warehouseId) return null
  if (error) return <div className="error">{error}</div>
  if (batches === null) return <p className="muted">در حال خواندنِ بارها…</p>

  const capacity = totalSellable(options)
  if (options.length === 0) {
    return (
      <div className="fy-note">
        هیچ بارِ قابلِ فروشی برای این کالا در این انبار نیست. بارِ منقضی، مسدود یا در انتظارِ
        کنترلِ کیفیت شمرده نمی‌شود.
      </div>
    )
  }

  const byId = new Map(options.map((o) => [o.id, o]))
  const problem = qty > 0 ? allocationError(current, qty, options) : null

  function setQty(batchId: string, raw: string) {
    const n = Number(raw) || 0
    const next = current.filter((a) => a.batch_id !== batchId)
    if (n > 0) next.push({ batch_id: batchId, qty: n })
    onChange(next)
  }

  return (
    <div className="batch-allocation">
      {!editing ? (
        <div className="batch-allocation-summary">
          <Layers size={13} />
          <span>
            {current.length === 0
              ? 'باری انتخاب نشده'
              : current
                  .map((a) => `${byId.get(a.batch_id)?.batch_number ?? '؟'}: ${fa(a.qty)}`)
                  .join(' · ')}
          </span>
          <button type="button" onClick={() => setEditing(true)}>تغییرِ بار</button>
        </div>
      ) : (
        <div className="batch-allocation-edit">
          <div className="table-scroll">
            <table className="entity-table cards-on-mobile table-plain">
              <thead>
                <tr><th>بار</th><th>انقضا</th><th>قابلِ فروش</th><th>برداشت</th></tr>
              </thead>
              <tbody>
                {fefoOrder(options).map((o) => (
                  <tr key={o.id}>
                    <td className="card-title ltr-cell" data-label="بار">{o.batch_number}</td>
                    <td data-label="انقضا">{o.expiry_date ? formatJalali(o.expiry_date) : '—'}</td>
                    <td className="num" data-label="قابلِ فروش">{fa(Number(o.sellable_qty))}</td>
                    <td data-label="برداشت">
                      <NumberInput
                        allowDecimal
                        value={String(current.find((a) => a.batch_id === o.id)?.qty ?? '')}
                        onChange={(v) => setQty(o.id, v)}
                        placeholder="۰"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="batch-allocation-foot">
            <span>
              جمع: {fa(allocationTotal(current))} از {fa(qty)}
            </span>
            <button type="button" onClick={() => { onChange(null); setEditing(false) }}>
              <RotateCcw size={13} /> بازگشت به پیشنهادِ خودکار
            </button>
          </div>
        </div>
      )}
      {problem && <div className="hint stock-over">{problem}</div>}
      {!problem && qty > capacity && (
        <div className="hint stock-over">
          مجموعِ قابلِ فروشِ بارها {fa(capacity)} است و کمتر از مقدارِ این ردیف.
        </div>
      )}
    </div>
  )
}
