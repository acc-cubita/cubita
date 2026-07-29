import { useEffect, useMemo, useState } from 'react'
import { Factory, FlaskConical, Plus, Save, Trash2, Hammer, Package, Layers } from 'lucide-react'
import {
  createBom,
  createProductionOrder,
  deleteBom,
  fetchBoms,
  fetchItemsLive,
  fetchProductionOrders,
  fetchWarehousesLive,
  type BomRecord,
  type ItemRecord,
  type ProductionOrderRecord,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

export function ManufacturingPage({ token }: { token: string }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [boms, setBoms] = useState<BomRecord[]>([])
  const [orders, setOrders] = useState<ProductionOrderRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setError(null)
    try {
      const [its, ws, bs, os] = await Promise.all([
        fetchItemsLive(token),
        fetchWarehousesLive(token),
        fetchBoms(token),
        fetchProductionOrders(token),
      ])
      setItems(its)
      setWarehouses(ws)
      setBoms(bs)
      setOrders(os)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const itemById = useMemo(() => new Map(items.map((i) => [i.id, i])), [items])
  const goodsItems = useMemo(() => items.filter((i) => !i.is_service && i.is_active), [items])

  const kpis = useMemo(() => {
    const active = boms.filter((b) => b.is_active).length
    const producedValue = orders.reduce((s, o) => s + Number(o.qty_produced) * Number(o.unit_cost), 0)
    return { boms: boms.length, active, orders: orders.length, producedValue }
  }, [boms, orders])

  return (
    <div className="page">
      <PageHeader
        icon={Factory}
        title="تولید و بهای تمام‌شده"
        description="فرمولِ ساختِ محصولات را تعریف کنید و با ثبتِ سفارشِ تولید، مواد اولیه به محصول تبدیل و بهای تمام‌شده خودکار محاسبه می‌شود."
      />

      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard icon={<FlaskConical size={18} />} label="فرمول‌های ساخت" value={fa(kpis.boms)} />
        <StatCard icon={<Layers size={18} />} label="فرمول‌های فعال" value={fa(kpis.active)} tone="success" />
        <StatCard icon={<Hammer size={18} />} label="سفارش‌های تولید" value={fa(kpis.orders)} />
        <StatCard icon={<Package size={18} />} label="ارزش تولیدشده" value={fa(kpis.producedValue)} hint="تومان" />
      </div>

      <Tabs
        tabs={[
          { key: 'boms', label: 'فرمول‌های ساخت', icon: FlaskConical, content: <BomsTab token={token} boms={boms} goodsItems={goodsItems} itemById={itemById} onChanged={refresh} /> },
          { key: 'produce', label: 'تولید', icon: Hammer, content: <ProduceTab token={token} boms={boms} orders={orders} warehouses={warehouses} itemById={itemById} onChanged={refresh} /> },
        ]}
      />
    </div>
  )
}

// ── تبِ فرمول‌های ساخت ─────────────────────────────────
function BomsTab({
  token,
  boms,
  goodsItems,
  itemById,
  onChanged,
}: {
  token: string
  boms: BomRecord[]
  goodsItems: ItemRecord[]
  itemById: Map<string, ItemRecord>
  onChanged: () => Promise<void>
}) {
  const [finishedId, setFinishedId] = useState('')
  const [name, setName] = useState('')
  const [yieldQty, setYieldQty] = useState('1')
  const [lines, setLines] = useState<{ componentId: string; qty: string }[]>([{ componentId: '', qty: '' }])
  const [msg, setMsg] = useState<string | null>(null)

  function setLine(i: number, patch: Partial<{ componentId: string; qty: string }>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }
  function addLine() {
    setLines((prev) => [...prev, { componentId: '', qty: '' }])
  }
  function removeLine(i: number) {
    setLines((prev) => (prev.length > 1 ? prev.filter((_, idx) => idx !== i) : prev))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!finishedId) {
      setMsg('محصولِ نهایی را انتخاب کنید.')
      return
    }
    const valid = lines.filter((l) => l.componentId && Number(l.qty) > 0)
    if (valid.length === 0) {
      setMsg('حداقل یک جزءِ معتبر (کالا + مقدار) لازم است.')
      return
    }
    if (valid.some((l) => l.componentId === finishedId)) {
      setMsg('محصولِ نهایی نمی‌تواند جزءِ خودش باشد.')
      return
    }
    try {
      await createBom(token, {
        finished_item_id: finishedId,
        name: name || undefined,
        yield_qty: Number(yieldQty) || 1,
        lines: valid.map((l) => ({ component_item_id: l.componentId, qty: Number(l.qty) })),
      })
      setFinishedId('')
      setName('')
      setYieldQty('1')
      setLines([{ componentId: '', qty: '' }])
      setMsg('فرمولِ ساخت ثبت شد.')
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function remove(id: string) {
    if (!window.confirm('این فرمولِ ساخت حذف شود؟')) return
    await deleteBom(token, id)
    await onChanged()
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={FlaskConical} title="فرمولِ ساختِ جدید" description="محصول و اجزای سازنده‌اش را تعریف کنید.">
        <form className="invoice-form form-full" onSubmit={submit}>
          <label>
            محصولِ نهایی
            <select value={finishedId} onChange={(e) => setFinishedId(e.target.value)} required>
              <option value="">— انتخاب —</option>
              {goodsItems.map((i) => (
                <option key={i.id} value={i.id}>{i.name}</option>
              ))}
            </select>
          </label>
          <div className="field-row">
            <label>
              نامِ فرمول (اختیاری)
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="مثلاً فرمولِ استاندارد" />
            </label>
            <label>
              بازده (چند واحد در هر اجرا)
              <input type="number" min="0" step="any" value={yieldQty} onChange={(e) => setYieldQty(e.target.value)} />
            </label>
          </div>

          <div className="table-scroll">
            <table className="invoice-lines">
              <thead>
                <tr>
                  <th>جزء (ماده اولیه)</th>
                  <th>مقدار</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => (
                  <tr key={i}>
                    <td>
                      <select value={l.componentId} onChange={(e) => setLine(i, { componentId: e.target.value })}>
                        <option value="">— انتخاب کالا —</option>
                        {goodsItems.map((it) => (
                          <option key={it.id} value={it.id}>{it.name}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input type="number" min="0" step="any" value={l.qty} onChange={(e) => setLine(i, { qty: e.target.value })} />
                    </td>
                    <td>
                      <button type="button" className="icon-btn-danger" onClick={() => removeLine(i)} disabled={lines.length === 1} aria-label="حذف">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="invoice-form-footer">
            <button type="button" onClick={addLine}><Plus size={14} /> افزودن جزء</button>
            <button type="submit" className="btn-primary"><Save size={14} /> ثبت فرمول</button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </form>
      </SectionCard>

      <SectionCard icon={Layers} title="فرمول‌های ساخت" description={`${fa(boms.length)} فرمول`}>
        {boms.length === 0 ? (
          <EmptyState icon={FlaskConical} text="فرمولی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead>
                <tr>
                  <th>محصول</th>
                  <th>اجزا</th>
                  <th>بازده</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {boms.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <div className="entity-cell">
                        <div className="entity-avatar">{(itemById.get(b.finished_item_id)?.name ?? '؟').trim().charAt(0)}</div>
                        <div>
                          <div className="entity-name">{itemById.get(b.finished_item_id)?.name ?? '—'}</div>
                          {b.name && <div className="entity-sub">{b.name}</div>}
                        </div>
                      </div>
                    </td>
                    <td>{b.lines.map((l) => `${itemById.get(l.component_item_id)?.name ?? '؟'} (${Number(l.qty).toLocaleString('fa-IR')})`).join('، ')}</td>
                    <td>{Number(b.yield_qty).toLocaleString('fa-IR')}</td>
                    <td>
                      <button type="button" className="icon-btn-danger" onClick={() => void remove(b.id)} aria-label="حذف"><Trash2 size={13} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}

// ── تبِ تولید ──────────────────────────────────────────
function ProduceTab({
  token,
  boms,
  orders,
  warehouses,
  itemById,
  onChanged,
}: {
  token: string
  boms: BomRecord[]
  orders: ProductionOrderRecord[]
  warehouses: { id: string; name: string }[]
  itemById: Map<string, ItemRecord>
  onChanged: () => Promise<void>
}) {
  const [bomId, setBomId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [qty, setQty] = useState('')
  const [overhead, setOverhead] = useState('')
  const [date, setDate] = useState(todayIso())
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!warehouseId && warehouses[0]) setWarehouseId(warehouses[0].id)
  }, [warehouses, warehouseId])

  const activeBoms = boms.filter((b) => b.is_active)
  const selectedBom = boms.find((b) => b.id === bomId)

  // پیش‌نمایشِ بهای تمام‌شده از میانگینِ موزونِ اجزا (سمتِ کلاینت)
  const preview = useMemo(() => {
    if (!selectedBom || !(Number(qty) > 0)) return null
    const batches = Number(qty) / (Number(selectedBom.yield_qty) || 1)
    let componentCost = 0
    for (const l of selectedBom.lines) {
      const it = itemById.get(l.component_item_id)
      componentCost += Number(l.qty) * batches * (it ? Number(it.average_cost) : 0)
    }
    const total = componentCost + (Number(overhead) || 0)
    return { componentCost, total, unit: total / Number(qty) }
  }, [selectedBom, qty, overhead, itemById])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!bomId) {
      setMsg('فرمولِ ساخت را انتخاب کنید.')
      return
    }
    if (!warehouseId) {
      setMsg('انبار را انتخاب کنید.')
      return
    }
    if (!(Number(qty) > 0)) {
      setMsg('تعدادِ تولید باید بزرگ‌تر از صفر باشد.')
      return
    }
    try {
      const o = await createProductionOrder(token, {
        bom_id: bomId,
        warehouse_id: warehouseId,
        production_date: date,
        qty_produced: Number(qty),
        overhead_cost: Number(overhead) || 0,
      })
      setQty('')
      setOverhead('')
      setMsg(`تولید ثبت شد ✓ سفارش شماره ${o.number ?? '—'} — بهای هر واحد: ${fa(Number(o.unit_cost))} تومان`)
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={Hammer} title="ثبتِ سفارشِ تولید" description="مواد اولیه مصرف و محصول تولید می‌شود؛ بهای تمام‌شده خودکار محاسبه می‌شود.">
        {activeBoms.length === 0 ? (
          <p className="hint">ابتدا از تبِ «فرمول‌های ساخت» یک فرمول تعریف کنید.</p>
        ) : (
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              فرمولِ ساخت (محصول)
              <select value={bomId} onChange={(e) => setBomId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {activeBoms.map((b) => (
                  <option key={b.id} value={b.id}>
                    {itemById.get(b.finished_item_id)?.name ?? '—'}{b.name ? ` — ${b.name}` : ''}
                  </option>
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
                تاریخ تولید
                <JalaliDatePicker value={date} onChange={setDate} />
              </label>
            </div>
            <div className="field-row">
              <label>
                تعدادِ تولید
                <input type="number" min="0" step="any" value={qty} onChange={(e) => setQty(e.target.value)} required />
              </label>
              <label>
                سربار/دستمزد (اختیاری، تومان)
                <input type="number" min="0" value={overhead} onChange={(e) => setOverhead(e.target.value)} placeholder="۰" />
              </label>
            </div>

            {preview && (
              <div className="pos-summary" style={{ marginTop: 4 }}>
                <div className="pos-row"><span>بهای مواد اولیه</span><strong>{fa(preview.componentCost)}</strong></div>
                {Number(overhead) > 0 && <div className="pos-row"><span>سربار</span><strong>{fa(Number(overhead))}</strong></div>}
                <div className="pos-row pos-total"><span>بهای هر واحدِ محصول</span><strong>{fa(preview.unit)}</strong></div>
              </div>
            )}

            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Hammer size={14} /> ثبتِ تولید</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        )}
      </SectionCard>

      <SectionCard icon={Factory} title="سفارش‌های تولید" description={`${fa(orders.length)} سفارش`}>
        {orders.length === 0 ? (
          <EmptyState icon={Hammer} text="هنوز تولیدی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>محصول</th>
                  <th>تعداد</th>
                  <th>بهای واحد</th>
                  <th>تاریخ</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td>{o.number != null ? o.number.toLocaleString('fa-IR') : '—'}</td>
                    <td className="entity-name">{itemById.get(o.finished_item_id)?.name ?? '—'}</td>
                    <td>{Number(o.qty_produced).toLocaleString('fa-IR')}</td>
                    <td className="money-cell">{fa(Number(o.unit_cost))}</td>
                    <td>{formatJalali(o.production_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
