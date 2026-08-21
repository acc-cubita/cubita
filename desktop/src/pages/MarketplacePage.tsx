import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { Store, Package, ClipboardList, Link2, Check, Boxes, RotateCw, ShoppingCart, Trash2, Plus, Minus, CreditCard, MessageSquare, Undo2 } from 'lucide-react'
import {
  fetchMpCatalog, fetchMpDistributors, fetchMpRetailerConnections, fetchMpRetailerOrders, payMpOrder, placeMpOrder, requestMpConnection,
  fetchMpMessages, sendMpMessage, fetchMpOrderMessages, sendMpOrderMessage,
  type CatalogListing, type DistributorCard, type MpConnection, type MpConnectionStatus, type MpOrder, type MpOrderPlaceIn,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { Tabs } from '../components/Tabs'
import { NumberInput } from '../components/NumberInput'
import { Pager, usePagination } from '../components/Pager'
import { MarketplaceChatDrawer } from '../components/MarketplaceChatDrawer'
import { MpRetailerReturns } from '../components/MpRetailerReturns'

const faMoney = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
const faNum = (v: string | number) => Number(v).toLocaleString('fa-IR')

/** خلاصه‌ی محدودیت‌های سفارشِ یک لیستینگ برای نمایش به فروشگاه (خالی = بی‌حد). */
function orderLimitHint(l: CatalogListing): string {
  const parts: string[] = []
  if (Number(l.min_order_qty) > 0) parts.push(`حداقل ${faNum(l.min_order_qty)}`)
  if (Number(l.max_order_qty) > 0) parts.push(`حداکثر ${faNum(l.max_order_qty)}`)
  if (l.daily_order_limit > 0) parts.push(`${faNum(l.daily_order_limit)} سفارش در روز`)
  return parts.length ? `محدودیت: ${parts.join(' — ')}` : ''
}

const STATUS_BADGE: Record<MpConnectionStatus, { label: string; tone: string }> = {
  pending: { label: 'در انتظارِ تأیید', tone: 'tone-warning' },
  approved: { label: 'متصل', tone: 'tone-success' },
  rejected: { label: 'ردشده', tone: 'tone-muted' },
  blocked: { label: 'مسدود', tone: 'tone-danger' },
}

const ORDER_BADGE: Record<MpOrder['status'], { label: string; tone: string }> = {
  placed: { label: 'ثبت‌شده، در انتظارِ تأییدِ پخش‌کننده', tone: 'tone-warning' },
  confirmed: { label: 'تأییدشده — به انبارتان اضافه شد', tone: 'tone-success' },
  rejected: { label: 'ردشده', tone: 'tone-danger' },
  shipped: { label: 'ارسال‌شده', tone: 'tone-success' },
  received: { label: 'تحویل‌شده', tone: 'tone-success' },
  cancelled: { label: 'لغوشده', tone: 'tone-muted' },
}

/**
 * ماژولِ «بازارِ خرید» — فقط برای حسابِ نوعِ retailer.
 * کشف/اتصال به پخش‌کننده‌ها، دیدنِ کاتالوگِ تأییدشده‌ها، ثبتِ سفارش، و «سفارش‌های من».
 * با تأییدِ پخش‌کننده، کالا خودکار در انبارِ فروشگاه ثبت و تعدادش اضافه می‌شود.
 */
export function MarketplacePage({ token }: { token: string }) {
  return (
    <div className="page panels">
      <PageHeader
        icon={Store}
        title="بازارِ خرید"
        description="از پخش‌کننده‌های متصل، محصولات و پک‌ها را ببینید و سفارش دهید. با تأییدِ پخش‌کننده، کالا خودکار به انبارتان می‌آید و تعدادش اضافه می‌شود."
      />
      <Tabs
        syncPage="marketplace"
        tabs={[
          { key: 'distributors', label: 'پخش‌کننده‌ها', icon: Store, content: <Distributors token={token} /> },
          { key: 'catalog', label: 'کاتالوگ', icon: Package, content: <Catalog token={token} /> },
          { key: 'orders', label: 'سفارش‌های من', icon: ClipboardList, content: <Orders token={token} /> },
          { key: 'returns', label: 'مرجوعی', icon: Undo2, content: <MpRetailerReturns token={token} /> },
        ]}
      />
    </div>
  )
}

function Distributors({ token }: { token: string }) {
  const [dists, setDists] = useState<DistributorCard[]>([])
  const [conns, setConns] = useState<MpConnection[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [chatConn, setChatConn] = useState<MpConnection | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [d, c] = await Promise.all([fetchMpDistributors(token), fetchMpRetailerConnections(token)])
      setDists(d)
      setConns(c)
    } catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  // نگاشتِ پخش‌کننده → اتصال (برای دکمه‌ی گفتگو روی کارتِ پخش‌کننده‌ی متصل).
  const connByDist = useMemo(() => new Map(conns.map((c) => [c.distributor_tenant_id, c])), [conns])

  const kpis = useMemo(() => ({
    total: dists.length,
    connected: dists.filter((d) => d.connection_status === 'approved').length,
    pending: dists.filter((d) => d.connection_status === 'pending').length,
  }), [dists])
  // صفحه‌بندیِ پخش‌کننده‌ها (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const pg = usePagination(dists, 10)

  async function connect(d: DistributorCard) {
    setBusy(d.tenant_id); setError(null)
    try { await requestMpConnection(token, d.tenant_id); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
    finally { setBusy(null) }
  }

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<Store size={18} />} label="پخش‌کننده‌های بازار" value={faNum(kpis.total)} />
        <StatCard icon={<Check size={18} />} label="متصل" value={faNum(kpis.connected)} tone="success" />
        <StatCard icon={<Link2 size={18} />} label="در انتظارِ تأیید" value={faNum(kpis.pending)} tone="warning" />
      </div>

      <SectionCard icon={Store} title="پخش‌کننده‌های بازار" description="برای دیدنِ کاتالوگ و سفارش، ابتدا درخواستِ اتصال بدهید و منتظرِ تأییدِ پخش‌کننده بمانید.">
        {error && <div className="error">{error}</div>}
        {dists.length === 0 ? (
          <EmptyState icon={Store} text="هنوز پخش‌کننده‌ی فعالی در بازار نیست." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table cards-on-mobile">
              <thead><tr><th>پخش‌کننده</th><th>وضعیت</th><th></th></tr></thead>
              <tbody>
                {pg.pageItems.map((d) => {
                  const st = d.connection_status
                  const badge = st ? STATUS_BADGE[st] : null
                  const canRequest = st === null || st === 'rejected'
                  return (
                    <tr key={d.tenant_id}>
                      <td className="card-title"><div className="entity-name">{d.display_name}</div></td>
                      <td data-label="وضعیت">{badge ? <span className={`status-badge ${badge.tone}`}>{badge.label}</span> : <span className="entity-sub">متصل نیستید</span>}</td>
                      <td className="card-actions">
                        <div className="check-actions">
                          {canRequest && (
                            <button type="button" className="btn-primary" disabled={busy === d.tenant_id} onClick={() => void connect(d)}>
                              <Link2 size={13} /> درخواستِ اتصال
                            </button>
                          )}
                          {st === 'approved' && connByDist.get(d.tenant_id) && (
                            <button type="button" className="mp-chat-btn" onClick={() => setChatConn(connByDist.get(d.tenant_id)!)}>
                              <MessageSquare size={13} /> گفتگو
                              {(connByDist.get(d.tenant_id)!.unread_count ?? 0) > 0 && (
                                <span className="mp-unread">{connByDist.get(d.tenant_id)!.unread_count.toLocaleString('fa-IR')}</span>
                              )}
                            </button>
                          )}
                          {st === 'pending' && <span className="entity-sub">منتظرِ تأیید…</span>}
                          {st === 'blocked' && <span className="entity-sub">اتصالِ شما مسدود شده</span>}
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

      {chatConn && (
        <MarketplaceChatDrawer
          threadKey={`conn:${chatConn.id}`}
          title={`گفتگو: ${chatConn.distributor_name}`}
          loadMessages={(after) => fetchMpMessages(token, chatConn.id, after)}
          sendMessage={(body) => sendMpMessage(token, chatConn.id, body)}
          onClose={() => { setChatConn(null); void refresh() }}
        />
      )}
    </>
  )
}

interface CartLine { listing: CatalogListing; qty: string }

function Catalog({ token }: { token: string }) {
  const [items, setItems] = useState<CatalogListing[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedCat, setSelectedCat] = useState('') // '' = همه‌ی دسته‌ها
  const [cart, setCart] = useState<Record<string, CartLine>>({})
  const [placing, setPlacing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null); setLoading(true)
    try { setItems(await fetchMpCatalog(token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
    finally { setLoading(false) }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  // دسته‌های موجود در کاتالوگ (برای فیلترِ سریع). خالی‌ها کنار می‌مانند.
  const categories = useMemo(() => {
    const set = new Set<string>()
    for (const l of items) { const c = l.category?.trim(); if (c) set.add(c) }
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'fa'))
  }, [items])

  const shown = useMemo(() => {
    const q = query.trim()
    return items.filter((l) => {
      if (selectedCat && (l.category?.trim() || '') !== selectedCat) return false
      if (!q) return true
      return l.title.includes(q) || l.distributor_name.includes(q) || l.category.includes(q)
    })
  }, [items, query, selectedCat])
  // صفحه‌بندیِ کاتالوگ (۱۲ کارت در هر صفحه)؛ با تغییرِ جست‌وجو/دسته به اولِ فهرست برمی‌گردد.
  const catalogPg = usePagination(shown, 12, `${query}|${selectedCat}`)

  function addToCart(l: CatalogListing) {
    setMsg(null)
    setCart((c) => ({ ...c, [l.id]: { listing: l, qty: String(Number(c[l.id]?.qty || 0) + 1) } }))
  }
  function setQty(id: string, qty: string) { setCart((c) => ({ ...c, [id]: { ...c[id], qty } })) }
  function removeLine(id: string) { setCart((c) => { const n = { ...c }; delete n[id]; return n }) }

  const cartLines = Object.values(cart)
  const cartTotal = cartLines.reduce((s, ln) => s + Number(ln.listing.wholesale_price) * (Number(ln.qty) || 0), 0)

  async function placeOrders() {
    const valid = cartLines.filter((ln) => Number(ln.qty) > 0)
    if (valid.length === 0) { setMsg('سبد خالی است.'); return }
    // هر سفارش برای یک پخش‌کننده است؛ سبد بر اساسِ پخش‌کننده گروه می‌شود.
    const byDist = new Map<string, MpOrderPlaceIn>()
    for (const ln of valid) {
      const did = ln.listing.distributor_tenant_id
      const g = byDist.get(did) ?? { distributor_tenant_id: did, lines: [] }
      g.lines.push({ listing_id: ln.listing.id, qty: Number(ln.qty) })
      byDist.set(did, g)
    }
    setPlacing(true); setError(null); setMsg(null)
    try {
      for (const payload of byDist.values()) await placeMpOrder(token, payload)
      setCart({})
      setMsg(`سفارش برای ${faNum(byDist.size)} پخش‌کننده ثبت شد. وضعیت را در تبِ «سفارش‌های من» ببینید.`)
    } catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
    finally { setPlacing(false) }
  }

  return (
    <div className="workspace-split shop">
      <SectionCard
        icon={Package}
        title="کاتالوگِ پخش‌کننده‌های متصل"
        description="فقط محصولاتِ منتشرشده‌ی پخش‌کننده‌هایی که اتصالتان را تأیید کرده‌اند."
        actions={
          <div className="check-actions">
            <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جست‌وجو در عنوان، پخش‌کننده یا دسته…" />
            <button type="button" onClick={() => void refresh()}><RotateCw size={13} /> تازه‌سازی</button>
          </div>
        }
      >
        {error && <div className="error">{error}</div>}
        {categories.length > 0 && (
          <div className="cat-chips" role="tablist" aria-label="دسته‌بندی">
            <button
              type="button"
              className={`cat-chip${selectedCat === '' ? ' active' : ''}`}
              onClick={() => setSelectedCat('')}
            >
              همه
            </button>
            {categories.map((c) => (
              <button
                key={c}
                type="button"
                className={`cat-chip${selectedCat === c ? ' active' : ''}`}
                onClick={() => setSelectedCat(selectedCat === c ? '' : c)}
              >
                {c}
              </button>
            ))}
          </div>
        )}
        {shown.length === 0 ? (
          <EmptyState
            icon={Package}
            text={loading ? 'در حال بارگذاری…' : selectedCat ? `کالایی در دستهٔ «${selectedCat}» نیست.` : 'کاتالوگی برای نمایش نیست — تا پخش‌کننده‌ای اتصالتان را تأیید نکند و محصولی منتشر نکند، اینجا خالی است.'}
          />
        ) : (
          <div className="product-grid">
            {catalogPg.pageItems.map((l) => {
              const line = cart[l.id]
              const qty = Number(line?.qty) || 0
              return (
                <article className="product-card" key={l.id}>
                  <div className="product-card-media">
                    {l.images?.[0]
                      ? <img src={l.images[0]} alt={l.title} loading="lazy" />
                      : <div className="product-card-noimg"><Package size={30} /></div>}
                    {l.kind === 'pack' && <span className="product-card-badge"><Boxes size={12} /> پک</span>}
                    {l.category && <span className="product-card-cat">{l.category}</span>}
                  </div>
                  <div className="product-card-body">
                    <h4 className="product-card-title" title={l.title}>{l.title}</h4>
                    <div className="product-card-dist"><Store size={12} /> {l.distributor_name}</div>
                    <div className="product-card-sub">
                      {l.kind === 'pack'
                        ? `${faNum(l.components.length)} قلم در پک`
                        : l.unit}
                    </div>
                    {orderLimitHint(l) && <div className="product-card-limit">{orderLimitHint(l)}</div>}
                    <div className="product-card-price"><strong>{faMoney(l.wholesale_price)}</strong> ریال</div>
                    {Number(l.consumer_price) > Number(l.wholesale_price) && (
                      <div className="product-card-margin">
                        مصرف‌کننده: {faMoney(l.consumer_price)} · سود{' '}
                        <strong>{faMoney(Number(l.consumer_price) - Number(l.wholesale_price))}</strong>
                        {' '}({(((Number(l.consumer_price) - Number(l.wholesale_price)) / Number(l.consumer_price)) * 100).toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪)
                      </div>
                    )}
                  </div>
                  <div className="product-card-foot">
                    {qty > 0 ? (
                      <div className="product-qty">
                        <button type="button" aria-label="کم" onClick={() => (qty <= 1 ? removeLine(l.id) : setQty(l.id, String(qty - 1)))}><Minus size={15} /></button>
                        <span>{faNum(qty)}</span>
                        <button type="button" aria-label="زیاد" onClick={() => addToCart(l)}><Plus size={15} /></button>
                      </div>
                    ) : (
                      <button type="button" className="btn-primary product-add" onClick={() => addToCart(l)}><Plus size={14} /> افزودن به سبد</button>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
        <Pager page={catalogPg.page} pageCount={catalogPg.pageCount} onChange={catalogPg.setPage} />
      </SectionCard>

      <SectionCard icon={ShoppingCart} title="سبدِ سفارش" description="سفارش‌ها بر اساسِ پخش‌کننده جدا ثبت می‌شوند.">
        {cartLines.length === 0 ? (
          <EmptyState icon={ShoppingCart} text="سبد خالی است — از کاتالوگ محصول اضافه کنید." />
        ) : (
          <>
            <div className="entity-table-wrap">
              <table className="entity-table">
                <thead><tr><th>محصول</th><th>تعداد</th><th>جمع</th><th></th></tr></thead>
                <tbody>
                  {cartLines.map((ln) => (
                    <tr key={ln.listing.id}>
                      <td>
                        <div className="entity-name">{ln.listing.title}</div>
                        <div className="entity-sub">{ln.listing.distributor_name}</div>
                      </td>
                      <td style={{ maxWidth: 110 }}><NumberInput allowDecimal value={ln.qty} onChange={(v) => setQty(ln.listing.id, v)} /></td>
                      <td className="money-cell">{faMoney(Number(ln.listing.wholesale_price) * (Number(ln.qty) || 0))}</td>
                      <td><button type="button" className="icon-btn-danger" onClick={() => removeLine(ln.listing.id)} aria-label="حذف"><Trash2 size={14} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="cart-total"><span>جمعِ کل</span><strong className="money-cell">{faMoney(cartTotal)} ریال</strong></div>
            <div className="invoice-form-footer">
              <button type="button" className="btn-primary" disabled={placing} onClick={() => void placeOrders()}>
                <ShoppingCart size={14} /> ثبتِ سفارش
              </button>
            </div>
          </>
        )}
        {msg && <div className="hint">{msg}</div>}
      </SectionCard>
    </div>
  )
}

function Orders({ token }: { token: string }) {
  const [orders, setOrders] = useState<MpOrder[]>([])
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [paying, setPaying] = useState<string | null>(null)
  const [chatOrder, setChatOrder] = useState<MpOrder | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try { setOrders(await fetchMpRetailerOrders(token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])
  // صفحه‌بندیِ سفارش‌های من (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const pg = usePagination(orders, 10)

  async function pay(o: MpOrder) {
    setPaying(o.id); setError(null)
    try {
      const { redirect_url } = await payMpOrder(token, o.id)
      window.open(redirect_url, '_blank', 'noopener')
    } catch (e) { setError(e instanceof Error ? e.message : 'خطای ناشناخته') }
    finally { setPaying(null) }
  }

  return (
    <>
    <SectionCard
      icon={ClipboardList}
      title="سفارش‌های من"
      description="با تأییدِ پخش‌کننده، کالا خودکار به انبارتان اضافه و فاکتورِ خرید صادر می‌شود. سفارشِ آنلاین را اول پرداخت کنید."
      actions={<button type="button" onClick={() => void refresh()}><RotateCw size={13} /> تازه‌سازی</button>}
    >
      {error && <div className="error">{error}</div>}
      {orders.length === 0 ? (
        <EmptyState icon={ClipboardList} text="هنوز سفارشی ثبت نکرده‌اید — از تبِ کاتالوگ سفارش دهید." />
      ) : (
        <div className="entity-table-wrap">
          <table className="entity-table cards-on-mobile">
            <thead><tr><th>سفارش</th><th>پخش‌کننده</th><th>مبلغ</th><th>وضعیت</th><th></th></tr></thead>
            <tbody>
              {pg.pageItems.map((o) => {
                const badge = ORDER_BADGE[o.status]
                const open = expanded === o.id
                const canPay = o.settlement_mode === 'online' && o.payment_status === 'unpaid' && o.status === 'placed'
                return (
                  <Fragment key={o.id}>
                    <tr>
                      <td className="card-title"><button type="button" className="link-btn" onClick={() => setExpanded(open ? null : o.id)}>سفارش #{faNum(o.order_number)}</button></td>
                      <td data-label="پخش‌کننده">{o.distributor_name}</td>
                      <td data-label="مبلغ" className="money-cell">{faMoney(o.total)}</td>
                      <td data-label="وضعیت"><span className={`status-badge ${badge.tone}`}>{badge.label}</span></td>
                      <td className="card-actions">
                        {canPay && (
                          <button type="button" className="btn-primary" disabled={paying === o.id} onClick={() => void pay(o)}>
                            <CreditCard size={13} /> پرداختِ آنلاین
                          </button>
                        )}
                        <button type="button" className="mp-chat-btn" onClick={() => setChatOrder(o)}>
                          <MessageSquare size={13} /> گفتگو
                          {o.unread_count > 0 && <span className="mp-unread">{o.unread_count.toLocaleString('fa-IR')}</span>}
                        </button>
                      </td>
                    </tr>
                    {open && (
                      <tr>
                        <td className="card-full" colSpan={5}>
                          <table className="entity-table">
                            <thead><tr><th>قلم</th><th>قیمتِ واحد</th><th>تعداد</th><th>جمع</th></tr></thead>
                            <tbody>
                              {o.lines.map((ln, i) => (
                                <tr key={i}>
                                  <td>
                                    {ln.image
                                      ? <span className="entity-with-thumb"><img className="list-thumb" src={ln.image} alt="" />{ln.title}</span>
                                      : ln.title}
                                  </td>
                                  <td className="money-cell">{faMoney(ln.unit_price)}</td>
                                  <td>{faNum(ln.qty)}</td>
                                  <td className="money-cell">{faMoney(ln.line_total)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {o.note && <p className="hint">یادداشت: {o.note}</p>}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}
    </SectionCard>
    {chatOrder && (
      <MarketplaceChatDrawer
        threadKey={`order:${chatOrder.id}`}
        title={`گفتگوی سفارش #${faNum(chatOrder.order_number)}`}
        subtitle={chatOrder.distributor_name}
        loadMessages={(after) => fetchMpOrderMessages(token, chatOrder.id, after)}
        sendMessage={(body) => sendMpOrderMessage(token, chatOrder.id, body)}
        onClose={() => { setChatOrder(null); void refresh() }}
      />
    )}
    </>
  )
}
