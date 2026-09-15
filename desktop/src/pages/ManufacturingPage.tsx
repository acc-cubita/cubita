import { useEffect, useMemo, useState } from 'react'
import { ClipboardList, Factory, FlaskConical, Plus, Save, Trash2, Hammer, Package, Layers, Pencil, X, Power, ReceiptText } from 'lucide-react'
import {
  changeProductionPlanStatus,
  createBom,
  createProductionOrder,
  createProductionPlan,
  deleteBom,
  updateBom,
  fetchBoms,
  fetchItemsLive,
  fetchProductionOrders,
  fetchProductionPlans,
  fetchWarehousesLive,
  type BomRecord,
  type ItemRecord,
  type ProductionOrderRecord,
  type ProductionPlanRecord,
  type ProductionPlanStatus,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { NumberInput } from '../components/NumberInput'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { Pager, usePagination } from '../components/Pager'
import { ProductionCostDrawer } from '../components/ProductionCostDrawer'
import { formatJalali, todayIso } from '../lib/jalali'

const PLAN_STATUS_LABELS: Record<ProductionPlanStatus, string> = {
  draft: 'پیش‌نویس',
  started: 'شروع‌شده',
  in_progress: 'در حالِ اجرا',
  stopped: 'متوقف‌شده',
  finished: 'تمام‌شده',
  cancelled: 'لغوشده',
}

//: عیناً همان گذارِ سرور (`services/manufacturing.py`).
const PLAN_TRANSITIONS: Record<ProductionPlanStatus, ProductionPlanStatus[]> = {
  draft: ['started', 'cancelled'],
  started: ['in_progress', 'stopped'],
  in_progress: ['stopped', 'finished'],
  stopped: ['in_progress', 'finished'],
  finished: [],
  cancelled: [],
}

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
  const [plans, setPlans] = useState<ProductionPlanRecord[]>([])
  const [orders, setOrders] = useState<ProductionOrderRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setError(null)
    try {
      const [its, ws, bs, ps, os] = await Promise.all([
        fetchItemsLive(token),
        fetchWarehousesLive(token),
        fetchBoms(token),
        fetchProductionPlans(token),
        fetchProductionOrders(token),
      ])
      setItems(its)
      setWarehouses(ws)
      setBoms(bs)
      setPlans(ps)
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
    return { boms: boms.length, active, plans: plans.length, orders: orders.length, producedValue }
  }, [boms, plans, orders])

  return (
    <div className="page panels">
      <PageHeader
        icon={Factory}
        title="تولید و بهای تمام‌شده"
        description="فرمولِ ساختِ محصولات را تعریف کنید، با سفارشِ تولید برنامه‌ریزی کنید و با سندِ تولید مواد اولیه را به محصول تبدیل کنید — بهای تمام‌شده خودکار محاسبه می‌شود."
      />

      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard icon={<FlaskConical size={18} />} label="فرمول‌های ساخت" value={fa(kpis.boms)} />
        <StatCard icon={<Layers size={18} />} label="فرمول‌های فعال" value={fa(kpis.active)} tone="success" />
        <StatCard icon={<ClipboardList size={18} />} label="سفارش‌های تولید" value={fa(kpis.plans)} />
        <StatCard icon={<Hammer size={18} />} label="اسنادِ تولید" value={fa(kpis.orders)} />
        <StatCard icon={<Package size={18} />} label="ارزش تولیدشده" value={fa(kpis.producedValue)} hint="ریال" />
      </div>

      <Tabs
        syncPage="manufacturing"
        tabs={[
          { key: 'boms', label: 'فرمول‌های ساخت', icon: FlaskConical, content: <BomsTab token={token} boms={boms} goodsItems={goodsItems} itemById={itemById} onChanged={refresh} /> },
          { key: 'orders', label: 'سفارش تولید', icon: ClipboardList, content: <OrdersTab token={token} boms={boms} plans={plans} warehouses={warehouses} itemById={itemById} onChanged={refresh} /> },
          { key: 'documents', label: 'سند تولید', icon: Hammer, content: <DocumentsTab token={token} boms={boms} plans={plans} orders={orders} warehouses={warehouses} itemById={itemById} onChanged={refresh} /> },
        ]}
      />
    </div>
  )
}

// ── تبِ سفارشِ تولید (برنامه) ──────────────────────────
function OrdersTab({
  token,
  boms,
  plans,
  warehouses,
  itemById,
  onChanged,
}: {
  token: string
  boms: BomRecord[]
  plans: ProductionPlanRecord[]
  warehouses: { id: string; name: string }[]
  itemById: Map<string, ItemRecord>
  onChanged: () => Promise<void>
}) {
  const [bomId, setBomId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [qty, setQty] = useState('')
  const [date, setDate] = useState(todayIso())
  const [notes, setNotes] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!warehouseId && warehouses[0]) setWarehouseId(warehouses[0].id)
  }, [warehouses, warehouseId])

  const activeBoms = boms.filter((b) => b.is_active)
  const plansPg = usePagination(plans, 10)

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
      setMsg('تعدادِ برنامه باید بزرگ‌تر از صفر باشد.')
      return
    }
    setBusy(true)
    try {
      const p = await createProductionPlan(
        token,
        { bom_id: bomId, warehouse_id: warehouseId, planned_date: date, qty_planned: Number(qty), notes },
        `production-plan-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setQty('')
      setNotes('')
      setMsg(`سفارش ثبت شد ✓ شماره ${p.number.toLocaleString('fa-IR')}`)
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  async function changeStatus(p: ProductionPlanRecord, next: ProductionPlanStatus) {
    await changeProductionPlanStatus(token, p.id, next)
    await onChanged()
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={ClipboardList} title="ثبتِ سفارشِ تولید" description="فقط برنامه‌ریزی — مواد مصرف نمی‌شود و بهایی محاسبه نمی‌شود.">
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
                تاریخِ برنامه
                <JalaliDatePicker value={date} onChange={setDate} />
              </label>
            </div>
            <label>
              تعدادِ برنامه
              <NumberInput allowDecimal value={qty} onChange={setQty} required />
            </label>
            <label className="form-full">
              توضیحات
              <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="اختیاری" />
            </label>

            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}><ClipboardList size={14} /> {busy ? 'در حال ثبت…' : 'ثبتِ سفارش'}</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        )}
      </SectionCard>

      <SectionCard icon={ClipboardList} title="سفارش‌های تولید" description={`${fa(plans.length)} سفارش`}>
        {plans.length === 0 ? (
          <EmptyState icon={ClipboardList} text="هنوز سفارشی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>محصول</th>
                    <th>مقدارِ برنامه</th>
                    <th>مقدارِ اجراشده</th>
                    <th>تاریخ</th>
                    <th>وضعیت</th>
                    <th>اقدام</th>
                  </tr>
                </thead>
                <tbody>
                  {plansPg.pageItems.map((p) => {
                    const options = PLAN_TRANSITIONS[p.status]
                    return (
                      <tr key={p.id}>
                        <td className="card-title" data-label="شماره">{fa(p.number)}</td>
                        <td data-label="محصول">{itemById.get(p.finished_item_id)?.name ?? '—'}</td>
                        <td data-label="مقدارِ برنامه">{Number(p.qty_planned).toLocaleString('fa-IR')}</td>
                        <td data-label="مقدارِ اجراشده">{Number(p.qty_produced).toLocaleString('fa-IR')}</td>
                        <td data-label="تاریخ">{formatJalali(p.planned_date)}</td>
                        <td data-label="وضعیت">
                          <span className={`status-badge ${p.status === 'finished' ? 'tone-success' : p.status === 'cancelled' ? 'tone-danger' : ''}`}>
                            {PLAN_STATUS_LABELS[p.status]}
                          </span>
                        </td>
                        <td className="card-actions" data-label="اقدام">
                          {options.length > 0 && (
                            <select
                              value=""
                              onChange={(e) => {
                                if (e.target.value) void changeStatus(p, e.target.value as ProductionPlanStatus)
                              }}
                            >
                              <option value="">— تغییرِ وضعیت —</option>
                              {options.map((s) => (
                                <option key={s} value={s}>{PLAN_STATUS_LABELS[s]}</option>
                              ))}
                            </select>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={plansPg.page} pageCount={plansPg.pageCount} onChange={plansPg.setPage} />
          </div>
        )}
      </SectionCard>
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
  // صفحه‌بندیِ فرمول‌های ساخت (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const bomsPg = usePagination(boms, 10)

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
            <div className="table-scroll">
              <table className="invoice-lines cards-on-mobile">
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
                      <td className="card-actions">
                        <button type="button" className="icon-btn-danger" onClick={() => removeLine(i)} disabled={lines.length === 1} aria-label="حذف">
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
            <div className="table-scroll">
              <table className="entity-table bom-table cards-on-mobile">
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
                  {bomsPg.pageItems.map((b) => {
                    const finished = itemById.get(b.finished_item_id)
                    const cost = bomUnitCost(b, itemById)
                    const salePrice = Number(finished?.sales_price ?? 0)
                    const margin = salePrice - cost
                    const pct = salePrice > 0 ? (margin / salePrice) * 100 : null
                    return (
                      <tr key={b.id} className={b.is_active ? '' : 'bom-row-inactive'}>
                        <td className="entity-name" data-label="محصول">
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
                        <td className="bom-actions" data-label="اقدام">
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
            <Pager page={bomsPg.page} pageCount={bomsPg.pageCount} onChange={bomsPg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}

// ── تبِ سندِ تولید (اجرا) ──────────────────────────────
function DocumentsTab({
  token,
  boms,
  plans,
  orders,
  warehouses,
  itemById,
  onChanged,
}: {
  token: string
  boms: BomRecord[]
  plans: ProductionPlanRecord[]
  orders: ProductionOrderRecord[]
  warehouses: { id: string; name: string }[]
  itemById: Map<string, ItemRecord>
  onChanged: () => Promise<void>
}) {
  const [planId, setPlanId] = useState('')
  const [bomId, setBomId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [qty, setQty] = useState('')
  const [overhead, setOverhead] = useState('')
  const [date, setDate] = useState(todayIso())
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [openOrder, setOpenOrder] = useState<ProductionOrderRecord | null>(null)

  useEffect(() => {
    if (!warehouseId && warehouses[0]) setWarehouseId(warehouses[0].id)
  }, [warehouses, warehouseId])

  const activeBoms = boms.filter((b) => b.is_active)
  const selectedBom = boms.find((b) => b.id === bomId)
  //: سفارش‌هایی که هنوز اجرا نشده‌اند (تمام/لغوشده حذف)
  const openPlans = plans.filter((p) => p.status !== 'finished' && p.status !== 'cancelled')
  // صفحه‌بندیِ اسنادِ تولید (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const ordersPg = usePagination(orders, 10)

  //: انتخابِ سفارش، BOM/انبار/مقدارِ باقیمانده را پر می‌کند — کاربر می‌تواند دستی عوضشان کند.
  function pickPlan(id: string) {
    setPlanId(id)
    const p = plans.find((x) => x.id === id)
    if (!p) return
    setBomId(p.bom_id)
    setWarehouseId(p.warehouse_id)
    const remaining = Number(p.qty_planned) - Number(p.qty_produced)
    if (remaining > 0) setQty(String(remaining))
  }

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
    setBusy(true)
    try {
      const o = await createProductionOrder(
        token,
        {
          bom_id: bomId,
          warehouse_id: warehouseId,
          production_date: date,
          qty_produced: Number(qty),
          overhead_cost: Number(overhead) || 0,
          production_plan_id: planId || null,
        },
        `production-order-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setQty('')
      setOverhead('')
      setPlanId('')
      setMsg(`سندِ تولید ثبت شد ✓ شماره ${o.number ?? '—'} — بهای هر واحد: ${fa(Number(o.unit_cost))} ریال`)
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={Hammer} title="ثبتِ سندِ تولید" description="مواد اولیه مصرف و محصول تولید می‌شود؛ بهای تمام‌شده خودکار محاسبه می‌شود.">
        {activeBoms.length === 0 ? (
          <p className="hint">ابتدا از تبِ «فرمول‌های ساخت» یک فرمول تعریف کنید.</p>
        ) : (
          <form className="invoice-form form-full" onSubmit={submit}>
            {openPlans.length > 0 && (
              <label>
                سفارشِ تولیدِ مرتبط (اختیاری)
                <select value={planId} onChange={(e) => pickPlan(e.target.value)}>
                  <option value="">— بدونِ سفارش —</option>
                  {openPlans.map((p) => (
                    <option key={p.id} value={p.id}>
                      {fa(p.number)} — {itemById.get(p.finished_item_id)?.name ?? '—'} (باقی‌مانده: {(Number(p.qty_planned) - Number(p.qty_produced)).toLocaleString('fa-IR')})
                    </option>
                  ))}
                </select>
              </label>
            )}
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
              <button type="submit" className="btn-primary" disabled={busy}><Hammer size={14} /> {busy ? 'در حال ثبت…' : 'ثبتِ سندِ تولید'}</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        )}
      </SectionCard>

      <SectionCard icon={Factory} title="اسنادِ تولید" description={`${fa(orders.length)} سند — روی «برگهٔ بها» بزنید تا ریزِ بهای تمام‌شده را ببینید`}>
        {orders.length === 0 ? (
          <EmptyState icon={Hammer} text="هنوز تولیدی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table prod-order-table cards-on-mobile">
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
                  {ordersPg.pageItems.map((o) => (
                    <tr key={o.id}>
                      <td data-label="شماره">{o.number != null ? o.number.toLocaleString('fa-IR') : '—'}</td>
                      <td className="entity-name" data-label="محصول">{itemById.get(o.finished_item_id)?.name ?? '—'}</td>
                      <td data-label="تعداد">{Number(o.qty_produced).toLocaleString('fa-IR')}</td>
                      <td data-label="بهای واحد" className="money-cell"><strong>{fa(Number(o.unit_cost))}</strong></td>
                      <td data-label="تاریخ">{formatJalali(o.production_date)}</td>
                      <td className="prod-order-action" data-label="اقدام">
                        <button type="button" onClick={() => setOpenOrder(o)}><ReceiptText size={13} /> برگهٔ بها</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={ordersPg.page} pageCount={ordersPg.pageCount} onChange={ordersPg.setPage} />
          </div>
        )}
      </SectionCard>

      {openOrder && (
        <ProductionCostDrawer order={openOrder} itemById={itemById} onClose={() => setOpenOrder(null)} />
      )}
    </div>
  )
}
