import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Truck, Package, Boxes, Plus, Trash2, Save, Pencil, X, Eye, EyeOff, Settings as SettingsIcon,
  Link2, Check, Ban, Store, ClipboardList, CheckCircle2, Percent, AlertCircle, MessageSquare,
  MapPin, Undo2, Layers,
} from 'lucide-react'
import type { ItemCache } from '../electron.d'
import {
  confirmMpOrder, deliverMpOrder, deleteMpListing, fetchMpDistributorConnections,
  fetchMpDistributorOrders, fetchMpListings, fetchMpSettings, fetchMyMpCommissions, rejectMpOrder,
  setMpConnectionStatus, setMpListingPublished, updateMpSettings,
  fetchMpMessages, sendMpMessage, fetchMpOrderMessages, sendMpOrderMessage,
  fetchMpZones, assignMpConnectionZone,
  fetchWarehousesLive,
  type Listing, type MarketplaceSettings, type MpCommissionPeriod, type MpConnection, type MpOrder, type MpZone,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { CatalogAllocationDrawer } from '../components/CatalogAllocationDrawer'
import { Tabs } from '../components/Tabs'
import { useNavSection } from '../components/navContext'
import { useTrades, labelOfTrade } from '../lib/useTrades'
import { TradePicker, ExtraTradesHint } from '../components/TradePicker'
import { toFaDigits } from '../lib/jalali'
import { ItemPicker } from '../components/ItemPicker'
import { NumberInput } from '../components/NumberInput'
import { ImageUploader } from '../components/ImageUploader'
import { Pager, usePagination } from '../components/Pager'
import { ListingWizard } from '../components/wizard/ListingWizard'
import { MarketplaceChatDrawer } from '../components/MarketplaceChatDrawer'
import { MpZonesPanel } from '../components/MpZonesPanel'
import { MpDistributorReturns } from '../components/MpDistributorReturns'
import { useListingDraft } from '../lib/listingDraft'
import { formatJalali } from '../lib/jalali'
import { useGuidedForms } from '../lib/experienceMode'
import { SearchSelect } from '../components/SearchSelect'

const CONN_BADGE: Record<MpConnection['status'], { label: string; tone: string }> = {
  pending: { label: 'در انتظارِ تأیید', tone: 'tone-warning' },
  approved: { label: 'تأییدشده', tone: 'tone-success' },
  rejected: { label: 'ردشده', tone: 'tone-muted' },
  blocked: { label: 'مسدود', tone: 'tone-danger' },
}

export const ORDER_BADGE: Record<MpOrder['status'], { label: string; tone: string }> = {
  placed: { label: 'ثبت‌شده', tone: 'tone-warning' },
  confirmed: { label: 'تأییدشده', tone: 'tone-success' },
  delivered: { label: 'تحویل‌شده', tone: 'tone-success' },
  rejected: { label: 'ردشده', tone: 'tone-danger' },
  shipped: { label: 'ارسال‌شده', tone: 'tone-success' },
  received: { label: 'تحویل‌شده', tone: 'tone-success' },
  cancelled: { label: 'لغوشده', tone: 'tone-muted' },
}

const faMoney = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
// "1405-05" → "۱۴۰۵/۰۵"
const faPeriod = (p: string) =>
  p.replace('-', '/').replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)])

/** ماژولِ «پخشِ من» — کاتالوگ (تکی/پک) + تنظیماتِ تسویه. فقط حسابِ distributor. */
export function DistributorPage({ token, items }: { token: string; items: ItemCache[] }) {
  const nav = useNavSection()
  // فعال‌بودنِ حضور در بازار — برای بنرِ هشدار. null=هنوز نمی‌دانیم (بنر نشان نده).
  const [active, setActive] = useState<boolean | null>(null)
  useEffect(() => {
    void fetchMpSettings(token).then((s) => setActive(s.is_active)).catch(() => {})
  }, [token])

  return (
    <div className="page panels">
      <PageHeader
        icon={Truck}
        title="پخشِ من"
        description="محصولاتتان را (تکی یا در قالبِ پکِ چندمحصولی) در بازار منتشر کنید. با تأییدِ سفارشِ فروشگاه، کالا از انبارِ شما کم و به انبارِ او افزوده می‌شود."
      />

      {active === false && (
        <div className="mp-inactive-banner">
          <AlertCircle size={20} />
          <div className="mp-inactive-banner-text">
            <strong>حضورِ شما در بازار غیرفعال است.</strong>{' '}
            تا آن را فعال نکنید، هیچ فروشگاهی شما را نمی‌بیند و نمی‌تواند درخواستِ اتصال یا سفارش بدهد — حتی اگر کاتالوگتان منتشر شده باشد.
          </div>
          <button type="button" className="btn-primary" onClick={() => nav?.setSection('settings')}>
            <SettingsIcon size={14} /> فعال‌سازی در تنظیمات
          </button>
        </div>
      )}

      <Tabs
        syncPage="distributor"
        tabs={[
          { key: 'catalog', label: 'کاتالوگ', icon: Package, content: <Catalog token={token} items={items} /> },
          { key: 'orders', label: 'سفارش‌ها', icon: ClipboardList, content: <OrdersPanel token={token} /> },
          { key: 'returns', label: 'مرجوعی‌ها', icon: Undo2, content: <MpDistributorReturns token={token} /> },
          { key: 'connections', label: 'اتصال‌ها', icon: Link2, content: <ConnectionsPanel token={token} /> },
          { key: 'zones', label: 'زون‌ها', icon: MapPin, content: <MpZonesPanel token={token} /> },
          { key: 'commission', label: 'کمیسیون', icon: Percent, content: <CommissionPanel token={token} /> },
          { key: 'settings', label: 'تنظیمات', icon: SettingsIcon, content: <SettingsPanel token={token} onActiveChange={setActive} /> },
        ]}
      />
    </div>
  )
}

function Catalog({ token, items }: { token: string; items: ItemCache[] }) {
  const { groups: tradeGroups } = useTrades()
  //: اصنافِ کلیِ خودِ پخش‌کننده لازم است چون «اضافه» روی «همه» بی‌اثر است؛ بدونِ
  //: دانستنش نمی‌شود این را به کاربر گفت و انتخابش بی‌صدا بی‌نتیجه می‌ماند.
  const [ownTargets, setOwnTargets] = useState<string[]>([])
  useEffect(() => {
    void fetchMpSettings(token)
      .then((st) => setOwnTargets(st.target_trades ?? []))
      .catch(() => setOwnTargets([]))
  }, [token])
  const guided = useGuidedForms()
  const [listings, setListings] = useState<Listing[]>([])
  const [error, setError] = useState<string | null>(null)
  //: §۶ — درایورِ «از کدام بار چه‌قدر در کاتالوگ عرضه شود».
  const [allocFor, setAllocFor] = useState<Listing | null>(null)
  const [warehouseId, setWarehouseId] = useState('')
  useEffect(() => {
    void fetchWarehousesLive(token)
      .then((ws) => setWarehouseId(ws[0]?.id ?? ''))
      .catch(() => setWarehouseId(''))
  }, [token])

  const refresh = useCallback(async () => {
    setError(null)
    try { setListings(await fetchMpListings(token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  // منطقِ مشترکِ فرم (state + submit) — همان هوکی که ویزارد هم مصرف می‌کند.
  const draft = useListingDraft({ token, onSaved: refresh })
  const { form, setForm } = draft

  const itemName = useMemo(() => new Map(items.map((i) => [i.id, i.name])), [items])
  const kpis = useMemo(() => ({
    total: listings.length,
    published: listings.filter((l) => l.is_published).length,
    packs: listings.filter((l) => l.kind === 'pack').length,
  }), [listings])
  // صفحه‌بندیِ کاتالوگِ لیستینگ‌ها (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const pg = usePagination(listings, 10)

  async function togglePublish(l: Listing) {
    setError(null)
    try { await setMpListingPublished(token, l.id, !l.is_published); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }
  async function remove(l: Listing) {
    if (!window.confirm(`لیستینگِ «${l.title}» حذف شود؟`)) return
    setError(null)
    try { await deleteMpListing(token, l.id); if (draft.editingId === l.id) draft.reset(); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }

  // فرمِ کلاسیک (پوسته‌های تیره/روشن) — منطق از هوکِ مشترک.
  const formCard = (
    <SectionCard
      icon={draft.editingId ? Pencil : Plus}
      title={draft.editingId ? 'ویرایشِ لیستینگ' : 'لیستینگِ جدید'}
      description="کالای تکی یا پکِ چندمحصولی را از روی کالاهای انبارِ خودتان منتشر کنید."
      actions={draft.editingId ? <button onClick={draft.reset}><X size={13} /> انصراف</button> : undefined}
    >
      <form className="invoice-form form-full" onSubmit={(e) => { e.preventDefault(); void draft.submit() }}>
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
            <table className="invoice-lines cards-on-mobile">
              <thead><tr><th>کالا</th><th>تعداد در پک</th><th></th></tr></thead>
              <tbody>
                {form.components.map((r, i) => (
                  <tr key={i}>
                    <td data-label="کالا"><ItemPicker items={items} value={r.itemId} onChange={(id) => draft.setPackRow(i, { itemId: id })} /></td>
                    <td data-label="تعداد"><NumberInput allowDecimal value={r.qty} onChange={(v) => draft.setPackRow(i, { qty: v })} /></td>
                    <td className="card-actions"><button type="button" className="icon-btn-danger" onClick={() => draft.removePackRow(i)} disabled={form.components.length === 1} aria-label="حذف"><Trash2 size={14} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button type="button" onClick={draft.addPackRow}><Plus size={14} /> افزودن جزء</button>
          </div>
        )}

        <div className="field-row">
          <label>قیمتِ عمده (ریال{form.kind === 'pack' ? '، کلِ پک' : '، هر واحد'})
            <NumberInput value={form.wholesalePrice} onChange={(v) => setForm({ ...form, wholesalePrice: v })} placeholder="۰" />
          </label>
          <label>قیمتِ مصرف‌کننده (اختیاری)
            <NumberInput value={form.consumerPrice} onChange={(v) => setForm({ ...form, consumerPrice: v })} placeholder="برای نمایشِ حاشیه‌ی سود" />
            {(() => {
              const buy = Number(form.wholesalePrice) || 0
              const sell = Number(form.consumerPrice) || 0
              if (buy > 0 && sell > buy) {
                const pct = ((sell - buy) / sell) * 100
                return <span className="hint">حاشیه‌ی سود: {faMoney(sell - buy)} ({pct.toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪)</span>
              }
              return null
            })()}
          </label>
        </div>
        <label>دسته (اختیاری)
          <input type="text" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
        </label>
        <label>عکس‌های محصول (اختیاری)
          <ImageUploader value={form.images} onChange={(imgs) => setForm({ ...form, images: imgs })} />
        </label>

        <fieldset className="mp-limits">
          <legend>محدودیتِ سفارش (اختیاری — ۰/خالی یعنی بدون محدودیت)</legend>
          <div className="field-row">
            <label>حداقلِ هر سفارش
              <NumberInput allowDecimal value={form.minOrderQty} onChange={(v) => setForm({ ...form, minOrderQty: v })} placeholder="بدون حداقل" />
            </label>
            <label>حداکثرِ هر سفارش
              <NumberInput allowDecimal value={form.maxOrderQty} onChange={(v) => setForm({ ...form, maxOrderQty: v })} placeholder="بدون سقف" />
            </label>
            <label>سقفِ دفعاتِ سفارش در روز
              <NumberInput value={form.dailyOrderLimit} onChange={(v) => setForm({ ...form, dailyOrderLimit: v })} placeholder="بدون سقف" />
            </label>
          </div>
          <span className="field-hint">هر فروشگاه در هر سفارش باید بین حداقل و حداکثر سفارش دهد؛ و در هر روز حداکثر به تعدادِ تعیین‌شده می‌تواند سفارش ثبت کند.</span>
        </fieldset>

        {tradeGroups.length > 0 && (
          <fieldset className="mp-limits">
            <legend>ارائه به اصنافِ دیگر (اختیاری)</legend>
            <ExtraTradesHint count={form.extraTrades.length} ownTargets={ownTargets} />
            <TradePicker
              groups={tradeGroups}
              value={form.extraTrades}
              onChange={(next) => setForm({ ...form, extraTrades: next })}
            />
          </fieldset>
        )}

        <label className="cal-check-inline">
          <input type="checkbox" checked={form.isPublished} onChange={(e) => setForm({ ...form, isPublished: e.target.checked })} />
          منتشر شود (در بازار برای فروشگاه‌های متصل دیده شود)
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={draft.saving}><Save size={14} /> {draft.editingId ? 'ذخیره' : 'ثبت لیستینگ'}</button>
        </div>
        {draft.msg && <div className="hint">{draft.msg}</div>}
      </form>
    </SectionCard>
  )

  const listCard = (
    <SectionCard icon={Package} title="کاتالوگ" description={`${faMoney(listings.length)} لیستینگ`}>
      {error && <div className="error">{error}</div>}
      {listings.length === 0 ? (
        <EmptyState icon={Package} text="هنوز لیستینگی نساخته‌اید — از فرمِ کنار، اولین محصول یا پک را منتشر کنید." />
      ) : (
        <div className="entity-table-wrap">
          <div className="table-scroll">
            <table className="entity-table cards-on-mobile">
              <thead><tr><th>عنوان</th><th>نوع</th><th>قیمتِ عمده</th><th>وضعیت</th><th></th></tr></thead>
              <tbody>
                {pg.pageItems.map((l) => (
                  <tr key={l.id}>
                    <td className="card-title" data-label="عنوان">
                      <div className="entity-with-thumb">
                        {l.images?.[0]
                          ? <img className="list-thumb" src={l.images[0]} alt="" />
                          : <span className="list-thumb list-thumb-empty"><Package size={16} /></span>}
                        <div>
                          <div className="entity-name">{l.title}</div>
                          <div className="entity-sub">
                            {l.kind === 'pack'
                              ? `${l.components.length} قلم: ${l.components.map((c) => `${itemName.get(c.item_id) ?? c.item_name}×${faMoney(c.qty)}`).join('، ')}`
                              : (itemName.get(l.item_id ?? '') ?? '—')}
                            {/* وضعیتی که دیده نشود عملاً وجود ندارد: بدونِ این نشان،
                                پخش‌کننده نمی‌داند کدام قلمش اصنافِ اضافه دارد. */}
                            {(l.extra_trades?.length ?? 0) > 0 && (
                              <span
                                className="status-badge tone-info trade-extra-badge"
                                title={l.extra_trades.map((k) => labelOfTrade(tradeGroups, k)).join('، ')}
                              >
                                +{toFaDigits(String(l.extra_trades.length))} صنف
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td data-label="نوع">{l.kind === 'pack' ? 'پک' : 'تکی'}</td>
                    <td data-label="قیمتِ عمده" className="money-cell">{faMoney(l.wholesale_price)}</td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${l.is_published ? 'tone-success' : 'tone-warning'}`}>{l.is_published ? 'منتشرشده' : 'پیش‌نویس'}</span>
                    </td>
                    <td className="card-actions">
                      <div className="check-actions">
                        <button type="button" onClick={() => void togglePublish(l)}>{l.is_published ? <><EyeOff size={13} /> پنهان</> : <><Eye size={13} /> انتشار</>}</button>
                        <button type="button" onClick={() => draft.startEdit(l)}><Pencil size={13} /> ویرایش</button>
                        {/* §۶ — «چه‌قدر از کدام بار در کاتالوگ عرضه شود». */}
                        <button type="button" onClick={() => setAllocFor(l)}><Layers size={13} /> بارها</button>
                        <button type="button" className="icon-btn-danger" onClick={() => void remove(l)} aria-label="حذف"><Trash2 size={13} /> حذف</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}
      {allocFor && warehouseId && (
        <CatalogAllocationDrawer
          token={token}
          listing={allocFor}
          warehouseId={warehouseId}
          onClose={() => setAllocFor(null)}
        />
      )}
    </SectionCard>
  )

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<Package size={18} />} label="کلِ لیستینگ‌ها" value={faMoney(kpis.total)} />
        <StatCard icon={<Eye size={18} />} label="منتشرشده" value={faMoney(kpis.published)} tone="success" />
        <StatCard icon={<Boxes size={18} />} label="پک‌ها" value={faMoney(kpis.packs)} />
      </div>

      {guided ? (
        <>
          <ListingWizard draft={draft} items={items} ownTargets={ownTargets} />
          {listCard}
        </>
      ) : (
        <div className="workspace-split">
          {formCard}
          {listCard}
        </div>
      )}
    </>
  )
}

/** دیالوگِ تأیید/تحویلِ سفارش با تعیینِ درصدِ نقد/اعتباری (سهمِ نقد در خزانه ثبت می‌شود). */
function CashConfirmDialog({
  order, busy, mode = 'confirm', onCancel, onConfirm,
}: {
  order: MpOrder
  busy: boolean
  mode?: 'confirm' | 'deliver'
  onCancel: () => void
  onConfirm: (cashPct: number) => void
}) {
  const [pct, setPct] = useState('0')
  const total = Number(order.total) || 0
  const p = Math.min(Math.max(Number(pct) || 0, 0), 100)
  const cash = Math.round((total * p) / 100)
  const credit = total - cash
  const deliver = mode === 'deliver'

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" onClick={onCancel}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span>{deliver ? <Truck size={16} /> : <Check size={16} />} {deliver ? 'ثبتِ تحویلِ سفارشِ' : 'تأییدِ سفارشِ'} #{order.order_number}</span>
          <button type="button" onClick={onCancel} aria-label="بستن"><X size={18} /></button>
        </div>
        <div className="modal-body">
          <p className="hint">
            {deliver
              ? 'با ثبتِ تحویل، کالا به انبارِ فروشگاه اضافه و اسنادِ فروش/خرید صادر می‌شود. سهمِ نقدِ دریافتی هنگامِ تحویل را وارد کنید. '
              : 'با تأیید، کالا از انبارِ شما کم و فاکتورِ فروش صادر می‌شود. '}
            مبلغِ کل: <strong className="money-cell">{faMoney(total)}</strong> ریال.
          </p>
          <label>{deliver ? 'درصدِ نقدِ دریافتی هنگامِ تحویل (بقیه اعتباری)' : 'درصدِ نقد (بقیه اعتباری ثبت می‌شود)'}
            <div className="cash-split-row">
              <input type="range" min={0} max={100} step={5} value={p} onChange={(e) => setPct(e.target.value)} />
              <div className="cash-pct-box"><NumberInput value={pct} onChange={setPct} /><span>٪</span></div>
            </div>
          </label>
          <div className="cash-split-preview">
            <div><span>نقد ({faMoney(p)}٪)</span><strong className="money-cell">{faMoney(cash)}</strong></div>
            <div><span>اعتباری</span><strong className="money-cell">{faMoney(credit)}</strong></div>
          </div>
          {order.settlement_mode === 'online' && (
            <p className="field-hint">این سفارش «آنلاین» است و از راهِ درگاه تسویه می‌شود؛ درصدِ نقد اینجا اثری ندارد.</p>
          )}
        </div>
        <div className="modal-foot">
          <button type="button" onClick={onCancel}>انصراف</button>
          <button type="button" className="btn-primary" disabled={busy} onClick={() => onConfirm(p)}>
            {deliver ? <><Truck size={14} /> ثبتِ تحویل</> : <><Check size={14} /> تأیید و صدور فاکتور</>}
          </button>
        </div>
      </div>
    </div>
  )
}

function OrdersPanel({ token }: { token: string }) {
  const [orders, setOrders] = useState<MpOrder[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [confirmTarget, setConfirmTarget] = useState<MpOrder | null>(null)
  const [deliverTarget, setDeliverTarget] = useState<MpOrder | null>(null)
  const [chatOrder, setChatOrder] = useState<MpOrder | null>(null)

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

  async function reject(o: MpOrder) {
    if (!window.confirm(`سفارشِ #${o.order_number} رد شود؟`)) return
    setBusy(o.id); setError(null)
    try { await rejectMpOrder(token, o.id); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
    finally { setBusy(null) }
  }

  // تأیید با سهمِ نقد (٪) که در دیالوگ گرفته می‌شود؛ بقیه اعتباری ثبت می‌شود.
  async function doConfirm(o: MpOrder, cashPct: number) {
    setBusy(o.id); setError(null)
    try {
      await confirmMpOrder(token, o.id, cashPct)
      setConfirmTarget(null)
      await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
    finally { setBusy(null) }
  }

  // ثبتِ تحویل (مامور حمل) — ورودِ کالا به انبارِ فروشگاه + سهمِ نقدِ دریافتی هنگامِ تحویل.
  async function doDeliver(o: MpOrder, cashPct: number) {
    setBusy(o.id); setError(null)
    try {
      await deliverMpOrder(token, o.id, cashPct)
      setDeliverTarget(null)
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
          <td className="card-title card-actions">
            <button type="button" className="link-btn" onClick={() => setExpanded(open ? null : o.id)}>سفارش #{o.order_number}</button>
            <div className="entity-sub">{o.retailer_name}</div>
          </td>
          <td data-label="مبلغ" className="money-cell">{faMoney(o.total)}</td>
          <td data-label="وضعیت"><span className={`status-badge ${badge.tone}`}>{badge.label}</span></td>
          <td data-label="تسویه">{o.settlement_mode === 'online' ? 'آنلاین' : 'اعتباری'}</td>
          <td className="card-actions">
            <div className="check-actions">
              {o.status === 'placed' ? (
                <>
                  <button type="button" className="btn-primary" disabled={busy === o.id} onClick={() => setConfirmTarget(o)}><Check size={13} /> تأیید</button>
                  <button type="button" disabled={busy === o.id} onClick={() => void reject(o)}><X size={13} /> رد</button>
                </>
              ) : o.status === 'confirmed' && !o.retailer_purchase_invoice_id ? (
                // گردشِ کارِ تحویل: تأیید شده ولی هنوز تحویل/سند نخورده — «مامور حمل» تحویل می‌زند.
                <button type="button" className="btn-primary" disabled={busy === o.id} onClick={() => setDeliverTarget(o)}><Truck size={13} /> تحویل شد</button>
              ) : o.status === 'confirmed' ? (
                <span className="entity-sub"><CheckCircle2 size={13} /> فاکتور صادر شد</span>
              ) : o.status === 'delivered' ? (
                <span className="entity-sub"><Truck size={13} /> تحویل شد</span>
              ) : null}
              <button type="button" className="mp-chat-btn" onClick={() => setChatOrder(o)}>
                <MessageSquare size={13} /> گفتگو
                {o.unread_count > 0 && <span className="mp-unread">{o.unread_count.toLocaleString('fa-IR')}</span>}
              </button>
            </div>
          </td>
        </tr>
        {open && (
          <tr className="detail-row">
            <td className="card-full" colSpan={5}>
              <div className="table-scroll">
                <table className="entity-table nested cards-on-mobile">
                  <thead><tr><th>قلم</th><th>قیمتِ واحد</th><th>تعداد</th><th>جمع</th></tr></thead>
                  <tbody>
                    {o.lines.map((ln, i) => (
                      <tr key={i}>
                        <td data-label="قلم">
                          {ln.image
                            ? <span className="entity-with-thumb"><img className="list-thumb" src={ln.image} alt="" />{ln.title}</span>
                            : ln.title}
                        </td>
                        <td className="money-cell" data-label="قیمتِ واحد">{faMoney(ln.unit_price)}</td>
                        <td data-label="تعداد">{Number(ln.qty).toLocaleString('fa-IR')}</td>
                        <td className="money-cell" data-label="جمع">{faMoney(ln.line_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {o.status === 'confirmed' && !o.retailer_purchase_invoice_id && (
                <p className="hint"><Truck size={13} /> در انتظارِ تحویل توسطِ مامور حمل — با ثبتِ تحویل، کالا به انبارِ فروشگاه اضافه و اسناد صادر می‌شود.</p>
              )}
              {o.retailer_purchase_invoice_id && (
                <p className="hint">
                  تسویه — نقد: <span className="money-cell">{faMoney(o.cash_amount)}</span> ریال، اعتباری: <span className="money-cell">{faMoney(Number(o.total) - Number(o.cash_amount))}</span> ریال
                </p>
              )}
              {o.status === 'delivered' && o.delivered_by_name && (
                <p className="hint"><Truck size={13} /> تحویل توسطِ «{o.delivered_by_name}»{o.delivered_at ? ` — ${formatJalali(o.delivered_at)}` : ''}</p>
              )}
              {o.note && <p className="hint">یادداشتِ فروشگاه: {o.note}</p>}
            </td>
          </tr>
        )}
      </>
    )
  }

  return (
    <>
      {confirmTarget && (
        <CashConfirmDialog
          order={confirmTarget}
          busy={busy === confirmTarget.id}
          onCancel={() => setConfirmTarget(null)}
          onConfirm={(pct) => void doConfirm(confirmTarget, pct)}
        />
      )}
      {deliverTarget && (
        <CashConfirmDialog
          order={deliverTarget}
          mode="deliver"
          busy={busy === deliverTarget.id}
          onCancel={() => setDeliverTarget(null)}
          onConfirm={(pct) => void doDeliver(deliverTarget, pct)}
        />
      )}
      {chatOrder && (
        <MarketplaceChatDrawer
          threadKey={`order:${chatOrder.id}`}
          title={`گفتگوی سفارش #${chatOrder.order_number.toLocaleString('fa-IR')}`}
          subtitle={chatOrder.retailer_name}
          loadMessages={(after) => fetchMpOrderMessages(token, chatOrder.id, after)}
          sendMessage={(body) => sendMpOrderMessage(token, chatOrder.id, body)}
          onClose={() => { setChatOrder(null); void refresh() }}
        />
      )}
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
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead><tr><th>سفارش</th><th>مبلغ</th><th>وضعیت</th><th>تسویه</th><th></th></tr></thead>
                <tbody>{pending.map((o) => <OrderRow key={o.id} o={o} />)}</tbody>
              </table>
            </div>
          </div>
        )}
      </SectionCard>
      <SectionCard icon={CheckCircle2} title="سفارش‌های رسیدگی‌شده" description="تأییدشده، ردشده یا لغوشده.">
        {done.length === 0 ? (
          <EmptyState icon={ClipboardList} text="هنوز سفارشی رسیدگی نشده است." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead><tr><th>سفارش</th><th>مبلغ</th><th>وضعیت</th><th>تسویه</th><th></th></tr></thead>
                <tbody>{done.map((o) => <OrderRow key={o.id} o={o} />)}</tbody>
              </table>
            </div>
          </div>
        )}
      </SectionCard>
    </>
  )
}

function ConnectionsPanel({ token }: { token: string }) {
  const [conns, setConns] = useState<MpConnection[]>([])
  const [zones, setZones] = useState<MpZone[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [chatConn, setChatConn] = useState<MpConnection | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [cs, zs] = await Promise.all([fetchMpDistributorConnections(token), fetchMpZones(token).catch(() => [])])
      setConns(cs)
      setZones(zs)
    }
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

  async function assignZone(c: MpConnection, zoneId: string) {
    setBusy(c.id); setError(null)
    try { await assignMpConnectionZone(token, c.id, zoneId || null); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
    finally { setBusy(null) }
  }

  function ConnRow({ c, actionable, showZone }: { c: MpConnection; actionable: boolean; showZone?: boolean }) {
    const badge = CONN_BADGE[c.status]
    return (
      <tr>
        <td className="card-title">
          <div className="entity-name">{c.retailer_name}</div>
          <div className="entity-sub">{c.requested_by === 'retailer' ? 'درخواست از سمتِ فروشگاه' : 'دعوت از سمتِ شما'}</div>
        </td>
        <td data-label="وضعیت"><span className={`status-badge ${badge.tone}`}>{badge.label}</span></td>
        {showZone && (
          <td data-label="زون">
            {c.status === 'approved' ? (
              <SearchSelect value={c.zone_id ?? ''} disabled={busy === c.id} onChange={(e) => void assignZone(c, e.target.value)}>
                <option value="">— بدونِ زون —</option>
                {zones.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
              </SearchSelect>
            ) : '—'}
          </td>
        )}
        <td className="card-actions">
          <div className="check-actions">
            {actionable && (
              <>
                <button type="button" className="btn-primary" disabled={busy === c.id} onClick={() => void act(c, 'approved')}><Check size={13} /> تأیید</button>
                <button type="button" disabled={busy === c.id} onClick={() => void act(c, 'rejected')}><X size={13} /> رد</button>
              </>
            )}
            {c.status === 'approved' && (
              <>
                <button type="button" className="mp-chat-btn" onClick={() => setChatConn(c)}>
                  <MessageSquare size={13} /> گفتگو
                  {c.unread_count > 0 && <span className="mp-unread">{c.unread_count.toLocaleString('fa-IR')}</span>}
                </button>
                <button type="button" className="icon-btn-danger" disabled={busy === c.id} onClick={() => void act(c, 'blocked')}><Ban size={13} /> مسدود</button>
              </>
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
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead><tr><th>فروشگاه</th><th>وضعیت</th><th></th></tr></thead>
                <tbody>{pending.map((c) => <ConnRow key={c.id} c={c} actionable />)}</tbody>
              </table>
            </div>
          </div>
        )}
      </SectionCard>

      <SectionCard icon={Store} title="فروشگاه‌های متصل" description="اتصال‌های تأییدشده، ردشده یا مسدود. برای مدیریتِ سریع‌ترِ ارسال، هر فروشگاهِ متصل را در یک زون بگذارید.">
        {others.length === 0 ? (
          <EmptyState icon={Store} text="هنوز فروشگاهی تأیید نشده است." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead><tr><th>فروشگاه</th><th>وضعیت</th><th>زون</th><th></th></tr></thead>
                <tbody>{others.map((c) => <ConnRow key={c.id} c={c} actionable={false} showZone />)}</tbody>
              </table>
            </div>
          </div>
        )}
      </SectionCard>

      {chatConn && (
        <MarketplaceChatDrawer
          threadKey={`conn:${chatConn.id}`}
          title={`گفتگو: ${chatConn.retailer_name}`}
          loadMessages={(after) => fetchMpMessages(token, chatConn.id, after)}
          sendMessage={(body) => sendMpMessage(token, chatConn.id, body)}
          onClose={() => { setChatConn(null); void refresh() }}
        />
      )}
    </>
  )
}

function CommissionPanel({ token }: { token: string }) {
  const [rows, setRows] = useState<MpCommissionPeriod[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    fetchMyMpCommissions(token)
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : 'خطای ناشناخته'))
  }, [token])

  const totalAll = rows.reduce((s, r) => s + r.total_amount, 0)
  const totalPending = rows.reduce((s, r) => s + r.pending_amount, 0)

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<Percent size={18} />} label="کلِ کمیسیونِ ۲٪" value={faMoney(totalAll)} hint="ریال" />
        <StatCard
          icon={<AlertCircle size={18} />}
          label="پرداخت‌نشده"
          value={faMoney(totalPending)}
          tone={totalPending > 0 ? 'warning' : 'success'}
          hint="ریال — باید به حسابِ پلتفرم واریز شود"
        />
      </div>
      {error && <div className="error">{error}</div>}
      <SectionCard
        icon={Percent}
        title="صورتِ کمیسیونِ ماهانه (۲٪)"
        description="۲٪ از جمعِ سفارش‌های قطعی‌شده‌ی هر ماه، کمیسیونِ پلتفرم (کوبیتا) است و باید ماهانه به حسابِ ما واریز شود. پس از واریز و تأیید، وضعیت «تسویه‌شده» می‌شود."
      >
        {rows.length === 0 ? (
          <EmptyState icon={Percent} text="هنوز سفارشِ قطعی‌ای ندارید؛ کمیسیونی ثبت نشده است." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>ماه</th>
                    <th>سفارش‌ها</th>
                    <th>جمعِ فاکتورها</th>
                    <th>کمیسیونِ ۲٪</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.period}>
                      <td className="card-title" data-label="ماه">{faPeriod(r.period)}</td>
                      <td data-label="سفارش‌ها">{faMoney(r.order_count)}</td>
                      <td data-label="جمعِ فاکتورها" className="money-cell">{faMoney(r.total_base)}</td>
                      <td data-label="کمیسیونِ ۲٪" className="money-cell">{faMoney(r.total_amount)}</td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${r.status === 'settled' ? 'tone-success' : 'tone-warning'}`}>
                          {r.status === 'settled' ? 'تسویه‌شده' : 'پرداخت‌نشده'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </SectionCard>
    </>
  )
}

function SettingsPanel({ token, onActiveChange }: { token: string; onActiveChange?: (active: boolean) => void }) {
  const [settings, setSettings] = useState<MarketplaceSettings>({ display_name: '', settlement_mode: 'credit', is_active: false })
  const [msg, setMsg] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const { groups: tradeGroups } = useTrades()

  const targets = settings.target_trades ?? []

  useEffect(() => {
    void fetchMpSettings(token).then((s) => { setSettings(s); onActiveChange?.(s.is_active) }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null); setSaving(true)
    try {
      const s = await updateMpSettings(token, settings)
      setSettings(s)
      onActiveChange?.(s.is_active)
      setMsg('تنظیمات ذخیره شد.')
    }
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

        <fieldset className="mp-limits">
          <legend>تحویلِ بار (مامور حمل)</legend>
          <label className="cal-check-inline">
            <input type="checkbox" checked={settings.require_delivery ?? false} onChange={(e) => setSettings({ ...settings, require_delivery: e.target.checked })} />
            گردشِ کارِ «تحویل با مامور حمل» فعال باشد
          </label>
          <span className="field-hint">
            با فعال‌کردن، تأییدِ سفارشِ اعتباری فقط آن را می‌پذیرد؛ ورودِ کالا به انبارِ فروشگاه و
            صدورِ فاکتور هنگامِ ثبتِ «تحویل» انجام می‌شود. برای اپراتورِ حمل، در «مدیریتِ کاربران» نقشِ
            «مامور حمل/انتقال» را بدهید تا فقط بتواند سفارش‌ها را ببیند و تحویل را ثبت کند.
          </span>
        </fieldset>

        {tradeGroups.length > 0 && (
          <fieldset className="mp-limits">
            <legend>اصنافی که به آن‌ها جنس می‌دهید</legend>
            {/* فهرستِ خالی رفتار را عوض نمی‌کند (همه می‌بینندتان)، ولی بی‌هشدار
                گذاشتنش یعنی پخش‌کننده هرگز نمی‌فهمد این قابلیت هست. */}
            {targets.length === 0 ? (
              <p className="mp-limit-hint">
                هنوز صنفی انتخاب نکرده‌اید، پس <b>همه‌ی فروشگاه‌ها</b> شما را در بازار می‌بینند.
                با انتخابِ صنف، فقط فروشگاه‌های همان اصناف شما را می‌بینند.
              </p>
            ) : (
              <p className="field-hint">
                {toFaDigits(String(targets.length))} صنف انتخاب شده — فقط فروشگاه‌های همین
                اصناف شما را در بازار می‌بینند.
              </p>
            )}
            <TradePicker
              groups={tradeGroups}
              value={targets}
              onChange={(next) => setSettings({ ...settings, target_trades: next })}
            />
          </fieldset>
        )}

        <fieldset className="mp-limits">
          <legend>سیاستِ مرجوعی</legend>
          <label>متنِ سیاستِ مرجوعی (به فروشگاه نشان داده می‌شود)
            <textarea
              value={settings.return_policy ?? ''}
              onChange={(e) => setSettings({ ...settings, return_policy: e.target.value })}
              rows={3}
              placeholder="مثلاً: مرجوعی تا ۷ روز، فقط کالای سالم و در بسته‌بندیِ اصلی."
            />
          </label>
          <label>مهلتِ مرجوعی (روز — ۰ یعنی بدونِ محدودیت)
            <NumberInput value={String(settings.return_window_days ?? 0)} onChange={(v) => setSettings({ ...settings, return_window_days: Number(v) || 0 })} placeholder="۰" />
          </label>
        </fieldset>

        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={saving}><Save size={14} /> ذخیره تنظیمات</button>
        </div>
        {msg && <div className="hint">{msg}</div>}
      </form>
    </SectionCard>
  )
}
