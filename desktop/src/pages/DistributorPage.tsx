import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Truck, Package, Boxes, Plus, Trash2, Save, Pencil, X, Eye, EyeOff, Settings as SettingsIcon,
  Link2, Check, Ban, Store, ClipboardList, CheckCircle2,
} from 'lucide-react'
import type { ItemCache } from '../electron.d'
import {
  confirmMpOrder, createMpListing, deleteMpListing, fetchMpDistributorConnections,
  fetchMpDistributorOrders, fetchMpListings, fetchMpSettings, rejectMpOrder,
  setMpConnectionStatus, setMpListingPublished, updateMpListing, updateMpSettings,
  type Listing, type ListingIn, type MarketplaceSettings, type MpConnection, type MpOrder,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { Tabs } from '../components/Tabs'
import { ItemPicker } from '../components/ItemPicker'
import { NumberInput } from '../components/NumberInput'

const CONN_BADGE: Record<MpConnection['status'], { label: string; tone: string }> = {
  pending: { label: 'در انتظارِ تأیید', tone: 'tone-warning' },
  approved: { label: 'تأییدشده', tone: 'tone-success' },
  rejected: { label: 'ردشده', tone: 'tone-muted' },
  blocked: { label: 'مسدود', tone: 'tone-danger' },
}

export const ORDER_BADGE: Record<MpOrder['status'], { label: string; tone: string }> = {
  placed: { label: 'ثبت‌شده', tone: 'tone-warning' },
  confirmed: { label: 'تأییدشده', tone: 'tone-success' },
  rejected: { label: 'ردشده', tone: 'tone-danger' },
  shipped: { label: 'ارسال‌شده', tone: 'tone-success' },
  received: { label: 'تحویل‌شده', tone: 'tone-success' },
  cancelled: { label: 'لغوشده', tone: 'tone-muted' },
}

const faMoney = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')

interface PackRow { itemId: string; qty: string }
const EMPTY_FORM = {
  kind: 'single' as 'single' | 'pack',
  title: '', code: '', unit: 'عدد', wholesalePrice: '', category: '', isPublished: true,
  itemId: '',
  components: [{ itemId: '', qty: '1' }] as PackRow[],
}

/** ماژولِ «پخشِ من» — کاتالوگ (تکی/پک) + تنظیماتِ تسویه. فقط حسابِ distributor. */
export function DistributorPage({ token, items }: { token: string; items: ItemCache[] }) {
  return (
    <div className="page panels">
      <PageHeader
        icon={Truck}
        title="پخشِ من"
        description="محصولاتتان را (تکی یا در قالبِ پکِ چندمحصولی) در بازار منتشر کنید. با تأییدِ سفارشِ فروشگاه، کالا از انبارِ شما کم و به انبارِ او افزوده می‌شود."
      />
      <Tabs
        syncPage="distributor"
        tabs={[
          { key: 'catalog', label: 'کاتالوگ', icon: Package, content: <Catalog token={token} items={items} /> },
          { key: 'orders', label: 'سفارش‌ها', icon: ClipboardList, content: <OrdersPanel token={token} /> },
          { key: 'connections', label: 'اتصال‌ها', icon: Link2, content: <ConnectionsPanel token={token} /> },
          { key: 'settings', label: 'تنظیمات', icon: SettingsIcon, content: <SettingsPanel token={token} /> },
        ]}
      />
    </div>
  )
}

function Catalog({ token, items }: { token: string; items: ItemCache[] }) {
  const [listings, setListings] = useState<Listing[]>([])
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const refresh = useCallback(async () => {
    setError(null)
    try { setListings(await fetchMpListings(token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  const itemName = useMemo(() => new Map(items.map((i) => [i.id, i.name])), [items])
  const kpis = useMemo(() => ({
    total: listings.length,
    published: listings.filter((l) => l.is_published).length,
    packs: listings.filter((l) => l.kind === 'pack').length,
  }), [listings])

  function reset() { setForm({ ...EMPTY_FORM, components: [{ itemId: '', qty: '1' }] }); setEditingId(null); setMsg(null) }

  function startEdit(l: Listing) {
    setEditingId(l.id)
    setForm({
      kind: l.kind,
      title: l.title, code: l.code, unit: l.unit,
      wholesalePrice: String(Number(l.wholesale_price) || ''),
      category: l.category, isPublished: l.is_published,
      itemId: l.item_id ?? '',
      components: l.kind === 'pack' && l.components.length
        ? l.components.map((c) => ({ itemId: c.item_id, qty: String(Number(c.qty)) }))
        : [{ itemId: '', qty: '1' }],
    })
    setMsg(null)
  }

  function setPackRow(i: number, patch: Partial<PackRow>) {
    setForm((f) => ({ ...f, components: f.components.map((r, idx) => (idx === i ? { ...r, ...patch } : r)) }))
  }
  const addPackRow = () => setForm((f) => ({ ...f, components: [...f.components, { itemId: '', qty: '1' }] }))
  const removePackRow = (i: number) =>
    setForm((f) => ({ ...f, components: f.components.length > 1 ? f.components.filter((_, idx) => idx !== i) : f.components }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!form.title.trim()) { setMsg('عنوان الزامی است.'); return }
    if (form.kind === 'single' && !form.itemId) { setMsg('برای کالای تکی، انتخابِ کالا الزامی است.'); return }
    const packRows = form.components.filter((r) => r.itemId && Number(r.qty) > 0)
    if (form.kind === 'pack' && packRows.length === 0) { setMsg('پک حداقل یک جزءِ معتبر لازم دارد.'); return }

    const payload: ListingIn = {
      kind: form.kind,
      title: form.title.trim(),
      code: form.code.trim(),
      unit: form.unit.trim() || 'عدد',
      wholesale_price: Number(form.wholesalePrice) || 0,
      category: form.category.trim(),
      is_published: form.isPublished,
      item_id: form.kind === 'single' ? form.itemId : null,
      components: form.kind === 'pack' ? packRows.map((r) => ({ item_id: r.itemId, qty: Number(r.qty) })) : [],
    }
    setSaving(true)
    try {
      if (editingId) await updateMpListing(token, editingId, payload)
      else await createMpListing(token, payload)
      reset()
      await refresh()
    } catch (e2) { setMsg(e2 instanceof Error ? e2.message : 'خطای ناشناخته') }
    finally { setSaving(false) }
  }

  async function togglePublish(l: Listing) {
    setError(null)
    try { await setMpListingPublished(token, l.id, !l.is_published); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }
  async function remove(l: Listing) {
    if (!window.confirm(`لیستینگِ «${l.title}» حذف شود؟`)) return
    setError(null)
    try { await deleteMpListing(token, l.id); if (editingId === l.id) reset(); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<Package size={18} />} label="کلِ لیستینگ‌ها" value={faMoney(kpis.total)} />
        <StatCard icon={<Eye size={18} />} label="منتشرشده" value={faMoney(kpis.published)} tone="success" />
        <StatCard icon={<Boxes size={18} />} label="پک‌ها" value={faMoney(kpis.packs)} />
      </div>

      <div className="workspace-split">
        <SectionCard
          icon={editingId ? Pencil : Plus}
          title={editingId ? 'ویرایشِ لیستینگ' : 'لیستینگِ جدید'}
          description="کالای تکی یا پکِ چندمحصولی را از روی کالاهای انبارِ خودتان منتشر کنید."
          actions={editingId ? <button onClick={reset}><X size={13} /> انصراف</button> : undefined}
        >
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              نوعِ لیستینگ
              <div className="seg-toggle">
                <button type="button" className={form.kind === 'single' ? 'active' : ''} onClick={() => setForm((f) => ({ ...f, kind: 'single' }))}>کالای تکی</button>
                <button type="button" className={form.kind === 'pack' ? 'active' : ''} onClick={() => setForm((f) => ({ ...f, kind: 'pack' }))}>پکِ چندمحصولی</button>
              </div>
            </label>
            <div className="field-row">
              <label>عنوان
                <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="عنوانِ نمایشیِ بازار" required />
              </label>
              <label>کد (اختیاری)
                <input type="text" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="کدِ داخلی" />
              </label>
            </div>

            {form.kind === 'single' ? (
              <div className="field-row">
                <label>کالا (از انبارِ خودتان)
                  <ItemPicker items={items} value={form.itemId} onChange={(id) => setForm({ ...form, itemId: id })} />
                </label>
                <label>واحد
                  <input type="text" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
                </label>
              </div>
            ) : (
              <div className="table-scroll">
                <table className="invoice-lines">
                  <thead><tr><th>کالا</th><th>تعداد در پک</th><th></th></tr></thead>
                  <tbody>
                    {form.components.map((r, i) => (
                      <tr key={i}>
                        <td data-label="کالا"><ItemPicker items={items} value={r.itemId} onChange={(id) => setPackRow(i, { itemId: id })} /></td>
                        <td data-label="تعداد"><NumberInput allowDecimal value={r.qty} onChange={(v) => setPackRow(i, { qty: v })} /></td>
                        <td><button type="button" className="icon-btn-danger" onClick={() => removePackRow(i)} disabled={form.components.length === 1} aria-label="حذف"><Trash2 size={14} /></button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <button type="button" onClick={addPackRow}><Plus size={14} /> افزودن جزء</button>
              </div>
            )}

            <div className="field-row">
              <label>قیمتِ عمده (ریال{form.kind === 'pack' ? '، کلِ پک' : '، هر واحد'})
                <NumberInput value={form.wholesalePrice} onChange={(v) => setForm({ ...form, wholesalePrice: v })} placeholder="۰" />
              </label>
              <label>دسته (اختیاری)
                <input type="text" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
              </label>
            </div>
            <label className="cal-check-inline">
              <input type="checkbox" checked={form.isPublished} onChange={(e) => setForm({ ...form, isPublished: e.target.checked })} />
              منتشر شود (در بازار برای فروشگاه‌های متصل دیده شود)
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={saving}><Save size={14} /> {editingId ? 'ذخیره' : 'ثبت لیستینگ'}</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        </SectionCard>

        <SectionCard icon={Package} title="کاتالوگ" description={`${faMoney(listings.length)} لیستینگ`}>
          {error && <div className="error">{error}</div>}
          {listings.length === 0 ? (
            <EmptyState icon={Package} text="هنوز لیستینگی نساخته‌اید — از فرمِ کنار، اولین محصول یا پک را منتشر کنید." />
          ) : (
            <div className="entity-table-wrap">
              <table className="entity-table">
                <thead><tr><th>عنوان</th><th>نوع</th><th>قیمتِ عمده</th><th>وضعیت</th><th></th></tr></thead>
                <tbody>
                  {listings.map((l) => (
                    <tr key={l.id}>
                      <td>
                        <div className="entity-name">{l.title}</div>
                        <div className="entity-sub">
                          {l.kind === 'pack'
                            ? `${l.components.length} قلم: ${l.components.map((c) => `${itemName.get(c.item_id) ?? c.item_name}×${faMoney(c.qty)}`).join('، ')}`
                            : (itemName.get(l.item_id ?? '') ?? '—')}
                        </div>
                      </td>
                      <td>{l.kind === 'pack' ? 'پک' : 'تکی'}</td>
                      <td className="money-cell">{faMoney(l.wholesale_price)}</td>
                      <td>
                        <span className={`status-badge ${l.is_published ? 'tone-success' : 'tone-warning'}`}>{l.is_published ? 'منتشرشده' : 'پیش‌نویس'}</span>
                      </td>
                      <td>
                        <div className="check-actions">
                          <button type="button" onClick={() => void togglePublish(l)}>{l.is_published ? <><EyeOff size={13} /> پنهان</> : <><Eye size={13} /> انتشار</>}</button>
                          <button type="button" onClick={() => startEdit(l)}><Pencil size={13} /> ویرایش</button>
                          <button type="button" className="icon-btn-danger" onClick={() => void remove(l)} aria-label="حذف"><Trash2 size={13} /> حذف</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </>
  )
}

function OrdersPanel({ token }: { token: string }) {
  const [orders, setOrders] = useState<MpOrder[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try { setOrders(await fetchMpDistributorOrders(token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  const kpis = useMemo(() => ({
    placed: orders.filter((o) => o.status === 'placed').length,
    confirmed: orders.filter((o) => o.status === 'confirmed').length,
  }), [orders])

  async function act(o: MpOrder, kind: 'confirm' | 'reject') {
    if (kind === 'confirm' && !window.confirm(`سفارشِ #${o.order_number} تأیید شود؟ با تأیید، کالا از انبارِ شما کم و فاکتورِ فروش صادر می‌شود.`)) return
    if (kind === 'reject' && !window.confirm(`سفارشِ #${o.order_number} رد شود؟`)) return
    setBusy(o.id); setError(null)
    try {
      if (kind === 'confirm') await confirmMpOrder(token, o.id)
      else await rejectMpOrder(token, o.id)
      await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
    finally { setBusy(null) }
  }

  const pending = orders.filter((o) => o.status === 'placed')
  const done = orders.filter((o) => o.status !== 'placed')

  function OrderRow({ o }: { o: MpOrder }) {
    const badge = ORDER_BADGE[o.status]
    const open = expanded === o.id
    return (
      <>
        <tr>
          <td>
            <button type="button" className="link-btn" onClick={() => setExpanded(open ? null : o.id)}>#{o.order_number}</button>
            <div className="entity-sub">{o.retailer_name}</div>
          </td>
          <td className="money-cell">{faMoney(o.total)}</td>
          <td><span className={`status-badge ${badge.tone}`}>{badge.label}</span></td>
          <td>{o.settlement_mode === 'online' ? 'آنلاین' : 'اعتباری'}</td>
          <td>
            <div className="check-actions">
              {o.status === 'placed' ? (
                <>
                  <button type="button" className="btn-primary" disabled={busy === o.id} onClick={() => void act(o, 'confirm')}><Check size={13} /> تأیید</button>
                  <button type="button" disabled={busy === o.id} onClick={() => void act(o, 'reject')}><X size={13} /> رد</button>
                </>
              ) : o.status === 'confirmed' ? (
                <span className="entity-sub"><CheckCircle2 size={13} /> فاکتور صادر شد</span>
              ) : null}
            </div>
          </td>
        </tr>
        {open && (
          <tr className="detail-row">
            <td colSpan={5}>
              <table className="entity-table nested">
                <thead><tr><th>قلم</th><th>قیمتِ واحد</th><th>تعداد</th><th>جمع</th></tr></thead>
                <tbody>
                  {o.lines.map((ln, i) => (
                    <tr key={i}>
                      <td>{ln.title}</td>
                      <td className="money-cell">{faMoney(ln.unit_price)}</td>
                      <td>{Number(ln.qty).toLocaleString('fa-IR')}</td>
                      <td className="money-cell">{faMoney(ln.line_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {o.note && <p className="hint">یادداشتِ فروشگاه: {o.note}</p>}
            </td>
          </tr>
        )}
      </>
    )
  }

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<ClipboardList size={18} />} label="در انتظارِ تأیید" value={faMoney(kpis.placed)} tone="warning" />
        <StatCard icon={<CheckCircle2 size={18} />} label="تأییدشده" value={faMoney(kpis.confirmed)} tone="success" />
      </div>
      {error && <div className="error">{error}</div>}
      <SectionCard icon={ClipboardList} title="سفارش‌های در انتظار" description="با تأیید، کالا از انبارِ شما کم و فاکتورِ فروش صادر می‌شود؛ سمتِ فروشگاه هم فاکتورِ خرید و ورودِ انبار می‌خورد.">
        {pending.length === 0 ? (
          <EmptyState icon={ClipboardList} text="سفارشِ در انتظاری ندارید." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead><tr><th>سفارش</th><th>مبلغ</th><th>وضعیت</th><th>تسویه</th><th></th></tr></thead>
              <tbody>{pending.map((o) => <OrderRow key={o.id} o={o} />)}</tbody>
            </table>
          </div>
        )}
      </SectionCard>
      <SectionCard icon={CheckCircle2} title="سفارش‌های رسیدگی‌شده" description="تأییدشده، ردشده یا لغوشده.">
        {done.length === 0 ? (
          <EmptyState icon={ClipboardList} text="هنوز سفارشی رسیدگی نشده است." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead><tr><th>سفارش</th><th>مبلغ</th><th>وضعیت</th><th>تسویه</th><th></th></tr></thead>
              <tbody>{done.map((o) => <OrderRow key={o.id} o={o} />)}</tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  )
}

function ConnectionsPanel({ token }: { token: string }) {
  const [conns, setConns] = useState<MpConnection[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try { setConns(await fetchMpDistributorConnections(token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  const pending = conns.filter((c) => c.status === 'pending')
  const others = conns.filter((c) => c.status !== 'pending')

  async function act(c: MpConnection, status: 'approved' | 'rejected' | 'blocked') {
    setBusy(c.id); setError(null)
    try { await setMpConnectionStatus(token, c.id, status); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
    finally { setBusy(null) }
  }

  function ConnRow({ c, actionable }: { c: MpConnection; actionable: boolean }) {
    const badge = CONN_BADGE[c.status]
    return (
      <tr>
        <td>
          <div className="entity-name">{c.retailer_name}</div>
          <div className="entity-sub">{c.requested_by === 'retailer' ? 'درخواست از سمتِ فروشگاه' : 'دعوت از سمتِ شما'}</div>
        </td>
        <td><span className={`status-badge ${badge.tone}`}>{badge.label}</span></td>
        <td>
          <div className="check-actions">
            {actionable && (
              <>
                <button type="button" className="btn-primary" disabled={busy === c.id} onClick={() => void act(c, 'approved')}><Check size={13} /> تأیید</button>
                <button type="button" disabled={busy === c.id} onClick={() => void act(c, 'rejected')}><X size={13} /> رد</button>
              </>
            )}
            {c.status === 'approved' && (
              <button type="button" className="icon-btn-danger" disabled={busy === c.id} onClick={() => void act(c, 'blocked')}><Ban size={13} /> مسدود</button>
            )}
            {(c.status === 'rejected' || c.status === 'blocked') && (
              <button type="button" className="btn-primary" disabled={busy === c.id} onClick={() => void act(c, 'approved')}><Check size={13} /> تأیید</button>
            )}
          </div>
        </td>
      </tr>
    )
  }

  return (
    <>
      {error && <div className="error">{error}</div>}
      <SectionCard icon={Link2} title="درخواست‌های در انتظار" description="فروشگاه‌هایی که خواسته‌اند به کاتالوگِ شما وصل شوند.">
        {pending.length === 0 ? (
          <EmptyState icon={Store} text="درخواستِ اتصالِ تازه‌ای ندارید." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead><tr><th>فروشگاه</th><th>وضعیت</th><th></th></tr></thead>
              <tbody>{pending.map((c) => <ConnRow key={c.id} c={c} actionable />)}</tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <SectionCard icon={Store} title="فروشگاه‌های متصل" description="اتصال‌های تأییدشده، ردشده یا مسدود.">
        {others.length === 0 ? (
          <EmptyState icon={Store} text="هنوز فروشگاهی تأیید نشده است." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead><tr><th>فروشگاه</th><th>وضعیت</th><th></th></tr></thead>
              <tbody>{others.map((c) => <ConnRow key={c.id} c={c} actionable={false} />)}</tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  )
}

function SettingsPanel({ token }: { token: string }) {
  const [settings, setSettings] = useState<MarketplaceSettings>({ display_name: '', settlement_mode: 'credit', is_active: false })
  const [msg, setMsg] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => { void fetchMpSettings(token).then(setSettings).catch(() => {}) }, [token])

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null); setSaving(true)
    try { setSettings(await updateMpSettings(token, settings)); setMsg('تنظیمات ذخیره شد.') }
    catch (e2) { setMsg(e2 instanceof Error ? e2.message : 'خطای ناشناخته') }
    finally { setSaving(false) }
  }

  return (
    <SectionCard icon={SettingsIcon} title="تنظیماتِ بازار" description="نامِ نمایشی، نحوه‌ی تسویه و فعال‌بودنِ حضورتان در بازار.">
      <form className="invoice-form form-full" onSubmit={save}>
        <label>نامِ نمایشی (اختیاری)
          <input type="text" value={settings.display_name} onChange={(e) => setSettings({ ...settings, display_name: e.target.value })} placeholder="خالی = نامِ کسب‌وکار" />
        </label>
        <label>نحوه‌ی تسویه‌ی سفارش‌ها
          <div className="seg-toggle">
            <button type="button" className={settings.settlement_mode === 'credit' ? 'active' : ''} onClick={() => setSettings({ ...settings, settlement_mode: 'credit' })}>اعتباری (آفلاین)</button>
            <button type="button" className={settings.settlement_mode === 'online' ? 'active' : ''} onClick={() => setSettings({ ...settings, settlement_mode: 'online' })}>آنلاین (درگاه)</button>
          </div>
          <span className="field-hint">اعتباری: سفارش با تأیید، سند می‌خورد و تسویه بعداً. آنلاین: پرداختِ درگاه (به‌زودی).</span>
        </label>
        <label className="cal-check-inline">
          <input type="checkbox" checked={settings.is_active} onChange={(e) => setSettings({ ...settings, is_active: e.target.checked })} />
          حضور در بازار فعال باشد (فروشگاه‌ها بتوانند پیدا و درخواستِ اتصال بدهند)
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={saving}><Save size={14} /> ذخیره تنظیمات</button>
        </div>
        {msg && <div className="hint">{msg}</div>}
      </form>
    </SectionCard>
  )
}
