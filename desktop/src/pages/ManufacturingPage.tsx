import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Calculator, ClipboardList, Factory, FlaskConical, Plus, Save, Trash2, Layers, PackageCheck, PackageMinus, Pencil, X, Power } from 'lucide-react'
import {
  calculateProductionCost,
  changeProductionPlanStatus,
  createBom,
  createProductionPlan,
  deleteBom,
  updateBom,
  fetchAllWarehouseReceipts,
  fetchBoms,
  fetchItemsLive,
  fetchProductionPlans,
  fetchStockLevels,
  fetchWarehouseIssueLedger,
  fetchWarehousesLive,
  issueMaterialsToProduction,
  receiveProductionOutput,
  type BomRecord,
  type ItemRecord,
  type ProductionPlanRecord,
  type ProductionPlanStatus,
  type StockLevel,
  type WarehouseIssueRow,
  type WarehouseReceiptFull,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { NumberInput } from '../components/NumberInput'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { Pager, usePagination } from '../components/Pager'
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

//: فقط سفارش‌هایی که واقعاً «باز و در جریان»اند مواد رزرو می‌کنند/تحویلِ مواد و
//: رسیدِ محصول می‌پذیرند — پیش‌نویس هنوز قطعی نشده، تمام/لغوشده دیگر چیزی نمی‌خواهد.
const RESERVING_PLAN_STATUSES = new Set<ProductionPlanStatus>(['started', 'in_progress', 'stopped'])

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

function remainingOf(p: ProductionPlanRecord): number {
  return Number(p.qty_planned) - Number(p.qty_produced)
}

export function ManufacturingPage({ token }: { token: string }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [boms, setBoms] = useState<BomRecord[]>([])
  const [plans, setPlans] = useState<ProductionPlanRecord[]>([])
  const [stockLevels, setStockLevels] = useState<StockLevel[]>([])
  const [materialIssues, setMaterialIssues] = useState<WarehouseIssueRow[]>([])
  const [productReceipts, setProductReceipts] = useState<WarehouseReceiptFull[]>([])
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setError(null)
    try {
      const [its, ws, bs, ps, sl, mi, pr] = await Promise.all([
        fetchItemsLive(token),
        fetchWarehousesLive(token),
        fetchBoms(token),
        fetchProductionPlans(token),
        fetchStockLevels(token),
        fetchWarehouseIssueLedger(token, { issue_type: 'production' }),
        fetchAllWarehouseReceipts(token, { receipt_type: 'production' }),
      ])
      setItems(its)
      setWarehouses(ws)
      setBoms(bs)
      setPlans(ps)
      setStockLevels(sl)
      setMaterialIssues(mi)
      setProductReceipts(pr)
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
    const openPlans = plans.filter((p) => RESERVING_PLAN_STATUSES.has(p.status)).length
    const materialCostIssued = plans.reduce((s, p) => s + Number(p.material_cost_issued), 0)
    return { boms: boms.length, active, plans: plans.length, openPlans, materialCostIssued }
  }, [boms, plans])

  return (
    <div className="page panels">
      <PageHeader
        icon={Factory}
        title="تولید و بهای تمام‌شده"
        description="فرمولِ ساخت تعریف کنید، با سفارشِ تولید برنامه‌ریزی کنید، مواد را به خطِ تولید تحویل دهید، محصول را به انبار برگردانید و دستمزد/سربار را روی بها بنشانید."
      />

      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard icon={<FlaskConical size={18} />} label="فرمول‌های ساخت" value={fa(kpis.boms)} />
        <StatCard icon={<Layers size={18} />} label="فرمول‌های فعال" value={fa(kpis.active)} tone="success" />
        <StatCard icon={<ClipboardList size={18} />} label="سفارش‌های تولید" value={fa(kpis.plans)} />
        <StatCard icon={<PackageMinus size={18} />} label="سفارش‌های بازِ تولید" value={fa(kpis.openPlans)} />
        <StatCard icon={<PackageCheck size={18} />} label="موادِ تحویل‌شده به تولید" value={fa(kpis.materialCostIssued)} hint="ریال" />
      </div>

      <Tabs
        syncPage="manufacturing"
        tabs={[
          { key: 'boms', label: 'فرمول‌های ساخت', icon: FlaskConical, content: <BomsTab token={token} boms={boms} goodsItems={goodsItems} itemById={itemById} onChanged={refresh} /> },
          { key: 'orders', label: 'سفارش تولید', icon: ClipboardList, content: <OrdersTab token={token} boms={boms} plans={plans} warehouses={warehouses} itemById={itemById} onChanged={refresh} /> },
          { key: 'materials', label: 'تحویل مواد', icon: PackageMinus, content: <MaterialIssueTab token={token} boms={boms} plans={plans} itemById={itemById} stockLevels={stockLevels} materialIssues={materialIssues} onChanged={refresh} /> },
          { key: 'receipts', label: 'رسید محصول', icon: PackageCheck, content: <ProductReceiptTab token={token} plans={plans} itemById={itemById} productReceipts={productReceipts} onChanged={refresh} /> },
          { key: 'costing', label: 'محاسبه قیمت تمام‌شده', icon: Calculator, content: <CostCalcTab token={token} plans={plans} itemById={itemById} onChanged={refresh} /> },
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

// ── تبِ تحویلِ مواد به تولید ───────────────────────────
function MaterialIssueTab({
  token,
  boms,
  plans,
  itemById,
  stockLevels,
  materialIssues,
  onChanged,
}: {
  token: string
  boms: BomRecord[]
  plans: ProductionPlanRecord[]
  itemById: Map<string, ItemRecord>
  stockLevels: StockLevel[]
  materialIssues: WarehouseIssueRow[]
  onChanged: () => Promise<void>
}) {
  const [planId, setPlanId] = useState('')
  const [qty, setQty] = useState('')
  const [date, setDate] = useState(todayIso())
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  //: فقط سفارش‌های باز و دارای باقی‌مانده — سفارشِ پیش‌نویس اول باید «شروع» شود.
  const openPlans = plans.filter((p) => RESERVING_PLAN_STATUSES.has(p.status) && remainingOf(p) > 0)
  const plan = plans.find((p) => p.id === planId)
  const bom = plan ? boms.find((b) => b.id === plan.bom_id) : undefined
  const remaining = plan ? remainingOf(plan) : 0
  const effectiveQty = Number(qty) > 0 ? Number(qty) : remaining

  const issuesPg = usePagination(materialIssues, 10)

  //: نیازِ هر جزء برای همین مقدار — پیش‌نمایشِ سمتِ کلاینت، عیناً فرمولِ سرور.
  const needs = useMemo(() => {
    if (!bom || !(effectiveQty > 0)) return []
    const batches = effectiveQty / (Number(bom.yield_qty) || 1)
    const rows = new Map<string, number>()
    for (const l of bom.lines) rows.set(l.component_item_id, (rows.get(l.component_item_id) ?? 0) + Number(l.qty) * batches)
    return [...rows.entries()].map(([itemId, need]) => ({ itemId, need }))
  }, [bom, effectiveQty])

  //: چقدر از هر جزء را سفارش‌های بازِ *دیگر* در همین انبار لازم دارند — مبنای
  //: هشدارِ «جلوگیری از خروجِ مواد» (تصمیمِ کاربر: هشدار، نه قفل).
  const reservedByOtherPlans = useMemo(() => {
    const reserved = new Map<string, number>()
    if (!plan) return reserved
    for (const p of plans) {
      if (p.id === plan.id) continue
      if (p.warehouse_id !== plan.warehouse_id) continue
      if (!RESERVING_PLAN_STATUSES.has(p.status)) continue
      const rem = remainingOf(p)
      if (rem <= 0) continue
      const b = boms.find((x) => x.id === p.bom_id)
      if (!b) continue
      const batches = rem / (Number(b.yield_qty) || 1)
      for (const l of b.lines) reserved.set(l.component_item_id, (reserved.get(l.component_item_id) ?? 0) + Number(l.qty) * batches)
    }
    return reserved
  }, [plans, boms, plan])

  const materialWarnings = useMemo(() => {
    if (!plan) return []
    const rows: { name: string; remaining: number; reserved: number }[] = []
    for (const { itemId, need } of needs) {
      const reserved = reservedByOtherPlans.get(itemId) ?? 0
      if (reserved <= 0) continue
      const stock = stockLevels.find((s) => s.item_id === itemId && s.warehouse_id === plan.warehouse_id)
      const available = stock ? Number(stock.qty) : 0
      const remainingAfter = available - need
      if (remainingAfter < reserved) rows.push({ name: itemById.get(itemId)?.name ?? '؟', remaining: remainingAfter, reserved })
    }
    return rows
  }, [plan, needs, reservedByOtherPlans, stockLevels, itemById])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!planId) {
      setMsg('سفارشِ تولید را انتخاب کنید.')
      return
    }
    setBusy(true)
    try {
      const issue = await issueMaterialsToProduction(
        token, planId,
        { issue_date: date, qty: Number(qty) > 0 ? Number(qty) : null },
        `production-issue-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setQty('')
      setMsg(`حواله ثبت شد ✓ شماره ${issue.number.toLocaleString('fa-IR')} — بهای مواد: ${fa(Number(issue.total_cost))} ریال`)
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={PackageMinus} title="تحویلِ مواد به تولید" description="حواله‌ی خروجِ واقعیِ موادِ اولیه از انبار به خطِ تولید.">
        {openPlans.length === 0 ? (
          <p className="hint">سفارشِ بازی برای تحویلِ مواد نیست. از تبِ «سفارش تولید» یکی بسازید و وضعیتش را «شروع» کنید.</p>
        ) : (
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              سفارشِ تولید
              <select value={planId} onChange={(e) => { setPlanId(e.target.value); setQty('') }} required>
                <option value="">— انتخاب —</option>
                {openPlans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {fa(p.number)} — {itemById.get(p.finished_item_id)?.name ?? '—'} (باقی‌مانده: {fa(remainingOf(p))})
                  </option>
                ))}
              </select>
            </label>
            <div className="field-row">
              <label>
                تاریخِ حواله
                <JalaliDatePicker value={date} onChange={setDate} />
              </label>
              <label>
                مقدار (خالی = کلِ باقی‌مانده)
                <NumberInput allowDecimal value={qty} onChange={setQty} placeholder={plan ? String(remaining) : ''} />
              </label>
            </div>

            {needs.length > 0 && (
              <div className="pos-summary" style={{ marginTop: 4 }}>
                {needs.map(({ itemId, need }) => (
                  <div className="pos-row" key={itemId}>
                    <span>{itemById.get(itemId)?.name ?? '؟'}</span>
                    <strong>{fa(need)}</strong>
                  </div>
                ))}
              </div>
            )}

            {materialWarnings.length > 0 && (
              <div className="credit-banner credit-banner--warn">
                <AlertTriangle size={15} />
                <span>این مواد رزروِ سفارش‌های بازِ دیگر است و بعدِ این حواله کم می‌آید:</span>
                <span className="credit-banner-alert">
                  {materialWarnings.map((w) => `${w.name} (باقی می‌ماند: ${fa(w.remaining)}، رزروِ بقیه: ${fa(w.reserved)})`).join('؛ ')}
                </span>
              </div>
            )}

            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}><PackageMinus size={14} /> {busy ? 'در حال ثبت…' : 'ثبتِ حوالهٔ تحویل'}</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        )}
      </SectionCard>

      <SectionCard icon={PackageMinus} title="حواله‌های تحویل" description={`${fa(materialIssues.length)} حواله`}>
        {materialIssues.length === 0 ? (
          <EmptyState icon={PackageMinus} text="هنوز موادی تحویلِ تولید نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>انبار</th>
                    <th>مقدار</th>
                    <th>بها</th>
                    <th>تاریخ</th>
                  </tr>
                </thead>
                <tbody>
                  {issuesPg.pageItems.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="شماره">{r.number != null ? fa(r.number) : '—'}</td>
                      <td data-label="انبار">{r.warehouse_name}</td>
                      <td data-label="مقدار">{Number(r.total_qty).toLocaleString('fa-IR')}</td>
                      <td data-label="بها" className="money-cell">{fa(Number(r.total_cost))}</td>
                      <td data-label="تاریخ">{formatJalali(r.doc_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={issuesPg.page} pageCount={issuesPg.pageCount} onChange={issuesPg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}

// ── تبِ رسیدِ محصول از تولید ───────────────────────────
function ProductReceiptTab({
  token,
  plans,
  itemById,
  productReceipts,
  onChanged,
}: {
  token: string
  plans: ProductionPlanRecord[]
  itemById: Map<string, ItemRecord>
  productReceipts: WarehouseReceiptFull[]
  onChanged: () => Promise<void>
}) {
  const [planId, setPlanId] = useState('')
  const [qty, setQty] = useState('')
  const [date, setDate] = useState(todayIso())
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const openPlans = plans.filter((p) => RESERVING_PLAN_STATUSES.has(p.status) && remainingOf(p) > 0)
  const plan = plans.find((p) => p.id === planId)
  //: نرخِ مواد از قبلِ تحویل‌شده — همان فرمولِ سرور، فقط پیش‌نمایش.
  const previewUnitCost = plan && Number(plan.qty_planned) > 0 ? Math.round(Number(plan.material_cost_issued) / Number(plan.qty_planned)) : 0

  const receiptsPg = usePagination(productReceipts, 10)

  function pickPlan(id: string) {
    setPlanId(id)
    const p = plans.find((x) => x.id === id)
    if (p) setQty(String(remainingOf(p)))
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!planId) {
      setMsg('سفارشِ تولید را انتخاب کنید.')
      return
    }
    if (!(Number(qty) > 0)) {
      setMsg('مقدارِ دریافتی باید بزرگ‌تر از صفر باشد.')
      return
    }
    setBusy(true)
    try {
      const receipt = await receiveProductionOutput(
        token, planId,
        { receipt_date: date, qty: Number(qty) },
        `production-receipt-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setQty('')
      const line = receipt.lines[0]
      setMsg(`رسید ثبت شد ✓ شماره ${receipt.number.toLocaleString('fa-IR')} — بهای هر واحد: ${fa(Number(line?.unit_cost ?? 0))} ریال`)
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={PackageCheck} title="رسیدِ محصول از تولید" description="ورودِ محصولِ ساخته‌شده به انبار — بهای واحد از موادِ تحویل‌شده‌ی همین سفارش می‌آید.">
        {openPlans.length === 0 ? (
          <p className="hint">سفارشِ بازی با باقی‌مانده نیست.</p>
        ) : (
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              سفارشِ تولید
              <select value={planId} onChange={(e) => pickPlan(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {openPlans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {fa(p.number)} — {itemById.get(p.finished_item_id)?.name ?? '—'} (باقی‌مانده: {fa(remainingOf(p))})
                  </option>
                ))}
              </select>
            </label>
            <div className="field-row">
              <label>
                تاریخِ رسید
                <JalaliDatePicker value={date} onChange={setDate} />
              </label>
              <label>
                مقدارِ دریافتی
                <NumberInput allowDecimal value={qty} onChange={setQty} required />
              </label>
            </div>

            {plan && (
              <div className="pos-summary" style={{ marginTop: 4 }}>
                <div className="pos-row"><span>نرخِ موادِ هر واحد (تا امروز)</span><strong>{fa(previewUnitCost)}</strong></div>
                <div className="pos-row pos-total"><span>ارزشِ این رسید</span><strong>{fa(previewUnitCost * (Number(qty) || 0))}</strong></div>
              </div>
            )}
            <p className="field-hint">دستمزد و سربار این‌جا نیست — بعداً از تبِ «محاسبه قیمت تمام‌شده» روی بها می‌نشیند.</p>

            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}><PackageCheck size={14} /> {busy ? 'در حال ثبت…' : 'ثبتِ رسیدِ محصول'}</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        )}
      </SectionCard>

      <SectionCard icon={PackageCheck} title="رسیدهای محصول" description={`${fa(productReceipts.length)} رسید`}>
        {productReceipts.length === 0 ? (
          <EmptyState icon={PackageCheck} text="هنوز محصولی از تولید دریافت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>محصول</th>
                    <th>مقدار</th>
                    <th>بهای واحد</th>
                    <th>تاریخ</th>
                  </tr>
                </thead>
                <tbody>
                  {receiptsPg.pageItems.map((r) => {
                    const line = r.lines[0]
                    return (
                      <tr key={r.id}>
                        <td className="card-title" data-label="شماره">{fa(r.number)}</td>
                        <td data-label="محصول">{line ? itemById.get(line.item_id)?.name ?? '—' : '—'}</td>
                        <td data-label="مقدار">{line ? Number(line.qty).toLocaleString('fa-IR') : '—'}</td>
                        <td data-label="بهای واحد" className="money-cell">{line ? fa(Number(line.unit_cost)) : '—'}</td>
                        <td data-label="تاریخ">{formatJalali(r.receipt_date)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={receiptsPg.page} pageCount={receiptsPg.pageCount} onChange={receiptsPg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}

// ── تبِ محاسبه‌ی قیمتِ تمام‌شده ─────────────────────────
function CostCalcTab({
  token,
  plans,
  itemById,
  onChanged,
}: {
  token: string
  plans: ProductionPlanRecord[]
  itemById: Map<string, ItemRecord>
  onChanged: () => Promise<void>
}) {
  const [planId, setPlanId] = useState('')
  const [date, setDate] = useState(todayIso())
  const [labor, setLabor] = useState('')
  const [overhead, setOverhead] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  //: فقط سفارش‌هایی که چیزی از رویشان دریافت شده — پیش از رسید هیچ محصولی نیست
  //: که دستمزد/سربار رویش بنشیند.
  const eligiblePlans = plans.filter((p) => Number(p.qty_produced) > 0)
  const plan = plans.find((p) => p.id === planId)
  const addedTotal = (Number(labor) || 0) + (Number(overhead) || 0)
  const perUnit = plan && Number(plan.qty_produced) > 0 ? addedTotal / Number(plan.qty_produced) : 0

  const rowsPg = usePagination(eligiblePlans, 10)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!planId) {
      setMsg('سفارشِ تولید را انتخاب کنید.')
      return
    }
    if (addedTotal <= 0) {
      setMsg('دستمزد یا سربار را وارد کنید.')
      return
    }
    setBusy(true)
    try {
      await calculateProductionCost(
        token, planId,
        { calc_date: date, labor_cost: Number(labor) || 0, overhead_cost: Number(overhead) || 0 },
        `production-cost-calc-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      )
      setLabor('')
      setOverhead('')
      setMsg(`بها به‌روز شد ✓ ${fa(perUnit)} ریال به هر واحدِ محصول اضافه شد`)
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={Calculator} title="محاسبهٔ قیمتِ تمام‌شده" description="توزیعِ دستمزد و سربار روی محصولی که تا امروز از این سفارش دریافت شده.">
        {eligiblePlans.length === 0 ? (
          <p className="hint">هنوز از هیچ سفارشی محصولی دریافت نشده — اول از تبِ «رسید محصول» اقدام کنید.</p>
        ) : (
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              سفارشِ تولید
              <select value={planId} onChange={(e) => setPlanId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {eligiblePlans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {fa(p.number)} — {itemById.get(p.finished_item_id)?.name ?? '—'} (دریافت‌شده: {fa(Number(p.qty_produced))})
                  </option>
                ))}
              </select>
            </label>
            <div className="field-row">
              <label>
                تاریخِ محاسبه
                <JalaliDatePicker value={date} onChange={setDate} />
              </label>
            </div>
            <div className="field-row">
              <label>
                دستمزد (ریال)
                <NumberInput value={labor} onChange={setLabor} placeholder="۰" />
              </label>
              <label>
                سربار (ریال)
                <NumberInput value={overhead} onChange={setOverhead} placeholder="۰" />
              </label>
            </div>

            {plan && addedTotal > 0 && (
              <div className="pos-summary" style={{ marginTop: 4 }}>
                <div className="pos-row pos-total"><span>افزوده به بهای هر واحد</span><strong>{fa(perUnit)}</strong></div>
              </div>
            )}

            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}><Calculator size={14} /> {busy ? 'در حال ثبت…' : 'ثبتِ محاسبه'}</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        )}
      </SectionCard>

      <SectionCard icon={Calculator} title="سفارش‌های دارای محصول" description={`${fa(eligiblePlans.length)} سفارش`}>
        {eligiblePlans.length === 0 ? (
          <EmptyState icon={Calculator} text="هنوز محصولی دریافت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>محصول</th>
                    <th>دریافت‌شده</th>
                    <th>نرخِ موادِ فعلی</th>
                  </tr>
                </thead>
                <tbody>
                  {rowsPg.pageItems.map((p) => {
                    const materialUnit = Number(p.qty_planned) > 0 ? Math.round(Number(p.material_cost_issued) / Number(p.qty_planned)) : 0
                    return (
                      <tr key={p.id}>
                        <td className="card-title" data-label="شماره">{fa(p.number)}</td>
                        <td data-label="محصول">{itemById.get(p.finished_item_id)?.name ?? '—'}</td>
                        <td data-label="دریافت‌شده">{Number(p.qty_produced).toLocaleString('fa-IR')}</td>
                        <td data-label="نرخِ موادِ فعلی" className="money-cell">{fa(materialUnit)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={rowsPg.page} pageCount={rowsPg.pageCount} onChange={rowsPg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}
