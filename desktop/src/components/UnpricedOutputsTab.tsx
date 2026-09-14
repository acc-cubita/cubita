import { useCallback, useEffect, useMemo, useState } from 'react'
import { BadgeDollarSign } from 'lucide-react'
import { applyReceiptPrices, fetchUnpricedOutputs, type UnpricedOutput } from '../api'
import { formatJalali } from '../lib/jalali'
import { JalaliDatePicker } from './JalaliDatePicker'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')
const faQty = (v: string) => Number(v).toLocaleString('fa-IR', { maximumFractionDigits: 3 })

/** اولِ ماهِ جاری تا امروز — همان دامنه‌ای که کاربر معمولاً می‌خواهد. */
function defaultRange(): { from: string; to: string } {
  const now = new Date()
  const first = new Date(now.getFullYear(), now.getMonth(), 1)
  const iso = (d: Date) => d.toISOString().slice(0, 10)
  return { from: iso(first), to: iso(now) }
}

/**
 * قیمت‌گذاریِ ورودی‌های بی‌فی.
 *
 * رسیدِ انبارِ مستقیم می‌تواند بی فی ثبت شود — کالایی که خارج از سیستم تهیه شده
 * و بهایش هنوز معلوم نیست. تا وقتی فی نخورَد آن کالا در انبار هست و **ارزشش
 * صفر است**؛ یعنی وقتی فروخته شود بهای فروش‌رفته صفر درمی‌آید و سود باد می‌کند.
 *
 * گرید **کالا‌محور** است: یک فی برای یک کالا، و ستونِ «اسناد» می‌گوید آن فی روی
 * کدام رسیدها می‌نشیند. حرکتِ انبارِ تازه‌ای ساخته نمی‌شود — مقدار از قبل وارد
 * شده و فقط بهای همان حرکت پر می‌شود.
 */
export function UnpricedOutputsTab({
  token,
  warehouses,
  onChanged,
}: {
  token: string
  //: فقط شناسه و نام لازم است — هم `WarehouseRecord` جواب می‌دهد هم کشِ سبکِ صفحه.
  warehouses: { id: string; name: string }[]
  onChanged?: () => void
}) {
  const [warehouseId, setWarehouseId] = useState('')
  const [range, setRange] = useState(defaultRange)
  const [rows, setRows] = useState<UnpricedOutput[] | null>(null)
  const [prices, setPrices] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

  useEffect(() => {
    if (!warehouseId && warehouses.length > 0) setWarehouseId(warehouses[0].id)
  }, [warehouses, warehouseId])

  const load = useCallback(async () => {
    if (!warehouseId) return
    setBusy(true)
    try {
      const found = await fetchUnpricedOutputs(token, {
        warehouse_id: warehouseId,
        date_from: range.from,
        date_to: range.to,
      })
      setRows(found)
      setPrices({})
    } catch (e) {
      setMsg({ kind: 'err', text: e instanceof Error ? e.message : 'خطای ناشناخته' })
    } finally {
      setBusy(false)
    }
  }, [token, warehouseId, range.from, range.to])

  useEffect(() => {
    void load()
  }, [load])

  const entered = useMemo(
    () =>
      Object.entries(prices)
        .map(([item_id, raw]) => ({ item_id, unit_cost: Number(raw) }))
        .filter((p) => Number.isFinite(p.unit_cost) && p.unit_cost > 0),
    [prices],
  )

  const total = useMemo(() => {
    const byId = new Map((rows ?? []).map((r) => [r.item_id, Number(r.qty)]))
    return entered.reduce((sum, p) => sum + p.unit_cost * (byId.get(p.item_id) ?? 0), 0)
  }, [entered, rows])

  const submit = async () => {
    if (entered.length === 0) return
    setBusy(true)
    setMsg(null)
    try {
      const result = await applyReceiptPrices(token, {
        warehouse_id: warehouseId,
        date_from: range.from,
        date_to: range.to,
        prices: entered,
      })
      setMsg({
        kind: 'ok',
        text: `فی روی ${fa(result.lines)} ردیف از ${fa(result.receipts)} سند ثبت شد — جمعاً ${fa(Number(result.value))} ریال.`,
      })
      await load()
      onChanged?.()
    } catch (e) {
      setMsg({ kind: 'err', text: e instanceof Error ? e.message : 'خطای ناشناخته' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="stack">
      <p className="muted">
        رسیدِ انبار می‌تواند بی فی ثبت شود — کالایی که خارج از سیستم تهیه شده و بهایش هنوز
        معلوم نیست. تا وقتی فی نخورَد، آن کالا در انبار هست و <strong>ارزشش صفر است</strong>.
        فیِ واردشده روی همان اسنادِ موجود می‌نشیند؛ کالا دوباره وارد انبار نمی‌شود.
      </p>

      <div className="toolbar">
        <label className="field">
          <span>انبار</span>
          <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>از تاریخ</span>
          <JalaliDatePicker value={range.from} onChange={(v) => setRange((r) => ({ ...r, from: v }))} />
        </label>
        <label className="field">
          <span>تا تاریخ</span>
          <JalaliDatePicker value={range.to} onChange={(v) => setRange((r) => ({ ...r, to: v }))} />
        </label>
      </div>

      {msg && <div className={msg.kind === 'ok' ? 'fy-note fy-note--ok' : 'error'}>{msg.text}</div>}

      {rows === null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <p className="muted">
          در این انبار و بازه هیچ ورودیِ بی‌فی‌ای نیست — هر چه وارد شده بهایش را دارد.
        </p>
      ) : (
        <>
          <div className="table-scroll">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>کالا</th>
                  <th>مقدار</th>
                  <th>واحد</th>
                  <th>اسناد</th>
                  <th>فی</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const price = Number(prices[row.item_id] ?? '')
                  const amount = Number.isFinite(price) && price > 0 ? price * Number(row.qty) : 0
                  return (
                    <tr key={row.item_id}>
                      <td data-label="کد">{row.sku || '—'}</td>
                      <td className="card-title" data-label="کالا">
                        {row.name}
                      </td>
                      <td className="num" data-label="مقدار">
                        {faQty(row.qty)}
                      </td>
                      <td data-label="واحد">{row.unit || '—'}</td>
                      <td className="card-wide" data-label="اسناد">
                        {row.receipts
                          .map((r) => `${r.type_label} #${r.number.toLocaleString('fa-IR')} — ${formatJalali(r.receipt_date)}`)
                          .join('، ')}
                      </td>
                      <td data-label="فی">
                        <input
                          type="number"
                          min={0}
                          inputMode="numeric"
                          value={prices[row.item_id] ?? ''}
                          onChange={(e) =>
                            setPrices((p) => ({ ...p, [row.item_id]: e.target.value }))
                          }
                          placeholder="۰"
                        />
                      </td>
                      <td className="num" data-label="مبلغ">
                        {amount > 0 ? fa(amount) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="toolbar">
            <strong>
              {fa(entered.length)} کالا — جمعِ ارزش: {fa(total)} ریال
            </strong>
            <button
              type="button"
              className="btn-primary"
              disabled={busy || entered.length === 0}
              onClick={() => void submit()}
            >
              <BadgeDollarSign size={16} />
              {busy ? 'در حال ثبت…' : 'ثبت فی روی اسناد'}
            </button>
          </div>
        </>
      )}
    </section>
  )
}
