import { useEffect, useMemo, useState } from 'react'
import { Factory, FlaskConical, Plus, Save, Trash2, Hammer, Package, Layers, Pencil, X, Power, ReceiptText } from 'lucide-react'
import {
  createBom,
  createProductionOrder,
  deleteBom,
  updateBom,
  fetchBoms,
  fetchItemsLive,
  fetchProductionOrders,
  fetchWarehousesLive,
  type BomRecord,
  type ItemRecord,
  type ProductionOrderRecord,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { NumberInput } from '../components/NumberInput'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { ProductionCostDrawer } from '../components/ProductionCostDrawer'
import { formatJalali, todayIso } from '../lib/jalali'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

// بهای تمام‌شده‌ی هر واحدِ محصول از میانگینِ موزونِ اجزا (÷ بازده)
function bomUnitCost(bom: BomRecord, itemById: Map<string, ItemRecord>): number {
  const yieldQty = Number(bom.yield_qty) || 1
  let cost = 0
  for (const l of bom.lines) {
    const it = itemById.get(l.component_item_id)
    cost += Number(l.qty) * (it ? Number(it.average_cost) : 0)
  }
  return cost / yieldQty
}

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
        <StatCard icon={<Package size={18} />} label="ارزش تولیدشده" value={fa(kpis.producedValue)} hint="ریال" />
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
  const [editingId, setEditingId] = useState<string | null>(null)
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

  function resetForm() {
    setEditingId(null)
    setFinishedId('')
    setName('')
    setYieldQty('1')
    setLines([{ componentId: '', qty: '' }])
    setMsg(null)
  }

  function startEdit(b: BomRecord) {
    setEditingId(b.id)
    setFinishedId(b.finished_item_id)
    setName(b.name)
    setYieldQty(String(Number(b.yield_qty)))
    setLines(b.lines.map((l) => ({ componentId: l.component_item_id, qty: String(Number(l.qty)) })))
    setMsg(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
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
    const linePayload = valid.map((l) => ({ component_item_id: l.componentId, qty: Number(l.qty) }))
    try {
      if (editingId) {
        await updateBom(token, editingId, { name, yield_qty: Number(yieldQty) || 1, lines: linePayload })
        setMsg('فرمولِ ساخت ویرایش شد.')
      } else {
        await createBom(token, {
          finished_item_id: finishedId,
          name: name || undefined,
          yield_qty: Number(yieldQty) || 1,
          lines: linePayload,
        })
        setMsg('فرمولِ ساخت ثبت شد.')
      }
      resetForm()
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function remove(id: string) {
    if (!window.confirm('این فرمولِ ساخت حذف شود؟')) return
    await deleteBom(token, id)
    if (editingId === id) resetForm()
    await onChanged()
  }

  async function toggleActive(b: BomRecord) {
    await updateBom(token, b.id, { is_active: !b.is_active })
    await onChanged()
  }

  const editingFinishedName = editingId ? itemById.get(finishedId)?.name ?? '—' : ''

  return (
    <div className="workspace-split">
      <SectionCard
        icon={editingId ? Pencil : FlaskConical}
        title={editingId ? 'ویرایشِ فرمولِ ساخت' : 'فرمولِ ساختِ جدید'}
        description={editingId ? `محصول: ${editingFinishedName}` : 'محصول و اجزای سازنده‌اش را تعریف کنید.'}
        actions={editingId ? <button type="button" onClick={resetForm}><X size={13} /> انصراف</button> : undefined}
      >
        <form className="invoice-form form-full" onSubmit={submit}>
          <label>
            محصولِ نهایی
            <select value={finishedId} onChange={(e) => setFinishedId(e.target.value)} required disabled={!!editingId}>
              <option value="">— انتخاب —</option>
              {goodsItems.map((i) => (
                <option key={i.id} value={i.id}>{i.name}</option>
              ))}
            </select>
            {editingId && <span className="field-hint">محصولِ یک فرمول قابلِ تغییر نیست؛ برای محصولِ دیگر فرمولِ تازه بسازید.</span>}
          </label>
          <div className="field-row">
            <label>
              نامِ فرمول (اختیاری)
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="مثلاً فرمولِ استاندارد" />
            </label>
            <label>
              بازده (چند واحد در هر اجرا)
              <NumberInput allowDecimal value={yieldQty} onChange={setYieldQty} />
            </label>
          </div>

          <div className="entity-table-wrap">
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
                    <td data-label="جزء">
                      <select value={l.componentId} onChange={(e) => setLine(i, { componentId: e.target.value })}>
                        <option value="">— انتخاب کالا —</option>
                        {goodsItems.map((it) => (
                          <option key={it.id} value={it.id}>{it.name}</option>
                        ))}
                      </select>
                    </td>
                    <td data-label="مقدار">
                      <NumberInput allowDecimal value={l.qty} onChange={(v) => setLine(i, { qty: v })} />
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
            <button type="submit" className="btn-primary"><Save size={14} /> {editingId ? 'ذخیرهٔ تغییرات' : 'ثبت فرمول'}</button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </form>
      </SectionCard>

      <SectionCard icon={Layers} title="فرمول‌های ساخت" description={`${fa(boms.length)} فرمول — بهای تمام‌شده و حاشیهٔ سود از میانگینِ موزونِ اجزا`}>
        {boms.length === 0 ? (
          <EmptyState icon={FlaskConical} text="فرمولی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table bom-table">
              <thead>
                <tr>
                  <th>محصول</th>
                  <th>اجزا</th>
                  <th>بهای واحد</th>
                  <th>حاشیهٔ سود</th>
                  <th>اقدام</th>
                </tr>
              </thead>
              <tbody>
                {boms.map((b) => {
                  const finished = itemById.get(b.finished_item_id)
                  const cost = bomUnitCost(b, itemById)
                  const salePrice = Number(finished?.sales_price ?? 0)
                  const margin = salePrice - cost
                  const pct = salePrice > 0 ? (margin / salePrice) * 100 : null
                  return (
                    <tr key={b.id} className={b.is_active ? '' : 'bom-row-inactive'}>
                      <td className="entity-name">
                        <div className="entity-cell">
                          <div className="entity-avatar">{(finished?.name ?? '؟').trim().charAt(0)}</div>
                          <div>
                            <div className="entity-name">{finished?.name ?? '—'}</div>
                            <div className="entity-sub">
                              {b.name ? `${b.name} · ` : ''}بازده {Number(b.yield_qty).toLocaleString('fa-IR')}
                              {!b.is_active && ' · غیرفعال'}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td data-label="اجزا" className="bom-components">
                        {b.lines.map((l) => `${itemById.get(l.component_item_id)?.name ?? '؟'} (${Number(l.qty).toLocaleString('fa-IR')})`).join('، ')}
                      </td>
                      <td data-label="بهای واحد" className="money-cell">{fa(cost)}</td>
                      <td data-label="حاشیهٔ سود">
                        {salePrice <= 0 ? (
                          <span className="field-hint">قیمت فروش ثبت نشده</span>
                        ) : (
                          <span className={`status-badge ${margin >= 0 ? 'tone-success' : 'tone-danger'}`} title={`قیمت فروش: ${fa(salePrice)} — بهای تمام‌شده: ${fa(cost)}`}>
                            {fa(margin)}{pct != null ? ` (${Math.round(pct)}٪)` : ''}
                          </span>
                        )}
                      </td>
                      <td className="bom-actions">
                        <div className="row-actions">
                          <button type="button" onClick={() => startEdit(b)}><Pencil size={13} /> ویرایش</button>
                          <button type="button" className={b.is_active ? '' : 'btn-muted'} onClick={() => void toggleActive(b)} title={b.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}>
                            <Power size={13} /> {b.is_active ? 'فعال' : 'غیرفعال'}
                          </button>
                          <button type="button" className="icon-btn-danger" onClick={() => void remove(b.id)} aria-label="حذف"><Trash2 size={13} /></button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
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
  const [openOrder, setOpenOrder] = useState<ProductionOrderRecord | null>(null)

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
      setMsg(`تولید ثبت شد ✓ سفارش شماره ${o.number ?? '—'} — بهای هر واحد: ${fa(Number(o.unit_cost))} ریال`)
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
                <NumberInput allowDecimal value={qty} onChange={setQty} required />
              </label>
              <label>
                سربار/دستمزد (اختیاری، ریال)
                <NumberInput value={overhead} onChange={setOverhead} placeholder="۰" />
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

      <SectionCard icon={Factory} title="سفارش‌های تولید" description={`${fa(orders.length)} سفارش — روی «برگهٔ بها» بزنید تا ریزِ بهای تمام‌شده را ببینید`}>
        {orders.length === 0 ? (
          <EmptyState icon={Hammer} text="هنوز تولیدی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table prod-order-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>محصول</th>
                  <th>تعداد</th>
                  <th>بهای واحد</th>
                  <th>تاریخ</th>
                  <th>اقدام</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td data-label="شماره">{o.number != null ? o.number.toLocaleString('fa-IR') : '—'}</td>
                    <td className="entity-name">{itemById.get(o.finished_item_id)?.name ?? '—'}</td>
                    <td data-label="تعداد">{Number(o.qty_produced).toLocaleString('fa-IR')}</td>
                    <td data-label="بهای واحد" className="money-cell"><strong>{fa(Number(o.unit_cost))}</strong></td>
                    <td data-label="تاریخ">{formatJalali(o.production_date)}</td>
                    <td className="prod-order-action">
                      <button type="button" onClick={() => setOpenOrder(o)}><ReceiptText size={13} /> برگهٔ بها</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {openOrder && (
        <ProductionCostDrawer order={openOrder} itemById={itemById} onClose={() => setOpenOrder(null)} />
      )}
    </div>
  )
}
