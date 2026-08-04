import { useEffect, useMemo, useState } from 'react'
import {
  Store,
  Link2,
  Package,
  ShoppingBag,
  KeyRound,
  Copy,
  RefreshCw,
  Save,
  CheckCircle2,
  Rocket,
  PowerOff,
  CreditCard,
  Globe,
} from 'lucide-react'
import {
  confirmStorefrontOrder,
  fetchNativeStorefront,
  fetchStorefrontGateways,
  fetchStorefrontItems,
  fetchStorefrontOrders,
  publishStorefront,
  rotateStorefrontKey,
  unpublishStorefront,
  updateNativeStorefront,
  updateStorefrontFulfillment,
  updateStorefrontGateway,
  updateStorefrontItem,
  type NativeStorefront,
  type StorefrontGateway,
  type StorefrontItem,
  type StorefrontOrder,
} from '../api'
import { SectionCard } from './SectionCard'
import { StatCard } from './StatCard'
import { Pager, usePagination } from './Pager'

const fa = (n: string | number) => Number(n).toLocaleString('fa-IR')

const PAYMENT_LABEL: Record<string, { label: string; tone: string }> = {
  pending: { label: 'در انتظارِ پرداخت', tone: 'warning' },
  paid: { label: 'پرداخت‌شده', tone: 'success' },
  failed: { label: 'ناموفق', tone: 'danger' },
  cancelled: { label: 'لغوشده', tone: 'muted' },
}

const FULFILLMENT: { key: string; label: string }[] = [
  { key: 'new', label: 'جدید' },
  { key: 'confirmed', label: 'تأییدشده' },
  { key: 'shipped', label: 'ارسال‌شده' },
  { key: 'done', label: 'تحویل‌شده' },
  { key: 'cancelled', label: 'لغوشده' },
]

const GATEWAY_LABEL: Record<string, string> = {
  zarinpal: 'زرین‌پال',
  zibal: 'زیبال',
  idpay: 'آی‌دی‌پی',
}

export function NativeStorefrontPanel({ token }: { token: string }) {
  const [sf, setSf] = useState<NativeStorefront | null>(null)
  const [items, setItems] = useState<StorefrontItem[]>([])
  const [gateways, setGateways] = useState<StorefrontGateway[]>([])
  const [orders, setOrders] = useState<StorefrontOrder[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // ویرایش‌های محلیِ تنظیمات (تا با هر تایپ به سرور نرود)
  const [seoTitle, setSeoTitle] = useState('')
  const [seoDesc, setSeoDesc] = useState('')
  const [phone, setPhone] = useState('')
  const [primary, setPrimary] = useState('#E31F24')
  const [allowedOrigin, setAllowedOrigin] = useState('')

  // ویرایش‌های محلیِ ردیف‌ها
  const [itemEdits, setItemEdits] = useState<Record<string, { is_listed: boolean; slug: string }>>({})
  const [gwEdits, setGwEdits] = useState<Record<string, { merchant_id: string; is_active: boolean }>>({})
  const [search, setSearch] = useState('')

  function loadSettings(s: NativeStorefront) {
    setSf(s)
    setSeoTitle(s.seo_title)
    setSeoDesc(s.seo_description)
    setPhone(String((s.contact_block as Record<string, unknown>)?.phone ?? ''))
    setPrimary(String((s.theme_config as Record<string, unknown>)?.primary ?? '#E31F24'))
    setAllowedOrigin(s.allowed_origin)
  }

  async function refreshAll() {
    const [s, it, gw, or] = await Promise.all([
      fetchNativeStorefront(token),
      fetchStorefrontItems(token),
      fetchStorefrontGateways(token),
      fetchStorefrontOrders(token),
    ])
    loadSettings(s)
    setItems(it)
    setGateways(gw)
    setOrders(or)
  }

  useEffect(() => {
    void refreshAll().catch((e) => setMessage(e instanceof Error ? e.message : 'خطای ناشناخته'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const published = sf?.status === 'published'
  const listedCount = useMemo(() => items.filter((i) => i.is_listed).length, [items])
  const pendingOrders = useMemo(() => orders.filter((o) => o.payment_status === 'pending').length, [orders])

  const filteredItems = useMemo(
    () => items.filter((i) => !search || i.name.includes(search) || i.sku.includes(search)),
    [items, search],
  )
  const itemsPg = usePagination(filteredItems, 10, search)
  const ordersPg = usePagination(orders, 10)

  async function guard(fn: () => Promise<void>) {
    setBusy(true)
    setMessage(null)
    try {
      await fn()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  const saveSettings = () =>
    guard(async () => {
      const s = await updateNativeStorefront(token, {
        theme_id: sf?.theme_id ?? 'general',
        theme_config: { ...(sf?.theme_config ?? {}), primary },
        seo_title: seoTitle,
        seo_description: seoDesc,
        contact_block: { ...(sf?.contact_block ?? {}), phone },
        allowed_origin: allowedOrigin,
      })
      loadSettings(s)
      setMessage('تنظیمات ذخیره شد.')
    })

  const togglePublish = () =>
    guard(async () => {
      const s = published ? await unpublishStorefront(token) : await publishStorefront(token)
      loadSettings(s)
      setMessage(published ? 'فروشگاه از انتشار خارج شد.' : 'فروشگاه منتشر شد.')
    })

  const rotateKey = () =>
    guard(async () => {
      const s = await rotateStorefrontKey(token)
      loadSettings(s)
      setMessage('کلید تازه ساخته شد — سایتِ دانلودشده را دوباره بسازید.')
    })

  const copyKey = async () => {
    if (!sf) return
    try {
      await navigator.clipboard.writeText(sf.publishable_key)
      setMessage('کلید کپی شد.')
    } catch {
      setMessage('کپی نشد؛ دستی انتخاب کنید.')
    }
  }

  const saveItem = (item: StorefrontItem) =>
    guard(async () => {
      const edit = itemEdits[item.item_id] ?? { is_listed: item.is_listed, slug: item.slug }
      const updated = await updateStorefrontItem(token, item.item_id, {
        is_listed: edit.is_listed,
        slug: edit.slug,
        images: item.images,
        long_description: item.long_description,
        badge: item.badge,
        sort: item.sort,
      })
      setItems((prev) => prev.map((i) => (i.item_id === item.item_id ? updated : i)))
      setItemEdits((prev) => {
        const next = { ...prev }
        delete next[item.item_id]
        return next
      })
      setMessage(`«${item.name}» ذخیره شد.`)
    })

  const saveGateway = (provider: string) =>
    guard(async () => {
      const edit = gwEdits[provider] ?? { merchant_id: '', is_active: false }
      const updated = await updateStorefrontGateway(token, provider, edit)
      setGateways((prev) => prev.map((g) => (g.provider === provider ? updated : g)))
      setGwEdits((prev) => {
        const next = { ...prev }
        delete next[provider]
        return next
      })
      setMessage(`درگاهِ ${GATEWAY_LABEL[provider] ?? provider} ذخیره شد.`)
    })

  const confirmPayment = (order: StorefrontOrder) =>
    guard(async () => {
      const updated = await confirmStorefrontOrder(token, order.id)
      setOrders((prev) => prev.map((o) => (o.id === order.id ? updated : o)))
      setMessage(`سفارش #${fa(order.order_number)} تأیید و به فاکتور فروش تبدیل شد.`)
      // موجودی تغییر کرده؛ کالاها را تازه کن
      fetchStorefrontItems(token).then(setItems).catch(() => {})
    })

  const changeFulfillment = (order: StorefrontOrder, status: string) =>
    guard(async () => {
      const updated = await updateStorefrontFulfillment(token, order.id, status)
      setOrders((prev) => prev.map((o) => (o.id === order.id ? updated : o)))
    })

  if (!sf) {
    return <p className="hint">{message ?? 'در حال بارگذاری…'}</p>
  }

  const shopUrlHint = allowedOrigin ? `${allowedOrigin}` : 'هنوز دامنه‌ای ثبت نشده'

  return (
    <div className="storefront-native">
      <div className={`integration-status tone-${published ? 'success' : 'warning'}`}>
        {published ? <CheckCircle2 size={18} /> : <PowerOff size={18} />}
        <div>
          <strong>وضعیت: {published ? 'منتشرشده' : 'پیش‌نویس (منتشرنشده)'}</strong>
          <span>
            {published
              ? 'سایت زنده است و با کلید به این حساب وصل می‌شود.'
              : 'برای اینکه سایتِ دانلودشده کار کند، پس از تنظیم، «انتشار» را بزنید.'}
          </span>
        </div>
      </div>

      <div className="stat-grid">
        <StatCard icon={<Store size={18} />} label="وضعیتِ فروشگاه" value={published ? 'منتشرشده' : 'پیش‌نویس'} tone={published ? 'success' : 'default'} />
        <StatCard icon={<Package size={18} />} label="کالاهای روی سایت" value={fa(listedCount)} tone="success" />
        <StatCard icon={<ShoppingBag size={18} />} label="کل سفارش‌ها" value={fa(orders.length)} />
        <StatCard icon={<CreditCard size={18} />} label="در انتظارِ پرداخت" value={fa(pendingOrders)} tone={pendingOrders > 0 ? 'warning' : 'default'} />
      </div>

      {message && <div className="hint storefront-msg">{message}</div>}

      <div className="workspace-split">
        <SectionCard icon={Link2} title="پیوند و انتشار" description="شناسه و کلیدِ فروشگاه که در سایتِ دانلودشده بیک می‌شوند.">
          <div className="sf-field">
            <label>شناسه‌ی فروشگاه (Shop-Slug)</label>
            <input type="text" dir="ltr" readOnly value={sf.slug} />
          </div>
          <div className="sf-field">
            <label>کلیدِ اتصال (Publishable Key)</label>
            <div className="sf-key-row">
              <input type="text" dir="ltr" readOnly value={sf.publishable_key} />
              <button type="button" onClick={() => void copyKey()} title="کپی"><Copy size={14} /></button>
              <button type="button" onClick={() => void rotateKey()} disabled={busy} title="کلیدِ تازه"><KeyRound size={14} /></button>
            </div>
            <span className="field-hint">این کلید در مرورگرِ خریدار دیده می‌شود؛ فقط عملیاتِ عمومی را مجاز می‌کند. با ساختِ کلیدِ تازه، باید سایت را دوباره دانلود کنید.</span>
          </div>
          <div className="sf-field">
            <label><Globe size={13} /> دامنه‌ی هاستِ فروشگاه (originِ مجاز)</label>
            <input type="text" dir="ltr" placeholder="https://myshop.ir" value={allowedOrigin} onChange={(e) => setAllowedOrigin(e.target.value)} />
            <span className="field-hint">آدرسی که سایت را روی آن آپلود می‌کنید — تا API درخواستِ آن دامنه را بپذیرد. {shopUrlHint}</span>
          </div>
          <div className="sf-actions">
            <button type="button" className="btn-primary" onClick={() => void saveSettings()} disabled={busy}>
              <Save size={14} /> ذخیره
            </button>
            <button type="button" className={published ? 'btn-danger-soft' : 'btn-primary'} onClick={() => void togglePublish()} disabled={busy}>
              {published ? <><PowerOff size={14} /> لغوِ انتشار</> : <><Rocket size={14} /> انتشار</>}
            </button>
          </div>
        </SectionCard>

        <SectionCard icon={Store} title="ظاهر و سئو" description="عنوان/توضیحِ سئو، رنگِ اصلی و تلفنِ تماسِ فوترِ سایت.">
          <div className="sf-field">
            <label>عنوانِ سئو</label>
            <input type="text" value={seoTitle} onChange={(e) => setSeoTitle(e.target.value)} placeholder="نام فروشگاه | شعار" />
          </div>
          <div className="sf-field">
            <label>توضیحِ سئو</label>
            <textarea value={seoDesc} onChange={(e) => setSeoDesc(e.target.value)} rows={2} placeholder="توضیحِ کوتاهِ فروشگاه برای گوگل" />
          </div>
          <div className="field-row">
            <div className="sf-field">
              <label>رنگِ اصلی</label>
              <input type="color" value={primary} onChange={(e) => setPrimary(e.target.value)} className="sf-color" />
            </div>
            <div className="sf-field">
              <label>تلفنِ تماس</label>
              <input type="text" dir="ltr" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="021…" />
            </div>
          </div>
          <div className="sf-actions">
            <button type="button" className="btn-primary" onClick={() => void saveSettings()} disabled={busy}>
              <Save size={14} /> ذخیره ظاهر
            </button>
          </div>
        </SectionCard>
      </div>

      <SectionCard icon={Package} title="کالاهای فروشگاه" description="تعیین کنید کدام کالا روی سایت دیده شود و نشانیِ (slug) صفحه‌اش چه باشد.">
        <div className="inst-filters">
          <input type="text" className="integration-search" placeholder="جستجوی کالا…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {items.length === 0 ? (
          <p className="hint">هنوز کالایی ثبت نکرده‌اید. اول از ماژولِ «انبار → کالاها» کالا بسازید.</p>
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table sf-table">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>قیمت</th>
                  <th>روی سایت</th>
                  <th>نشانی (slug)</th>
                  <th>اقدام</th>
                </tr>
              </thead>
              <tbody>
                {itemsPg.pageItems.map((item) => {
                  const edit = itemEdits[item.item_id] ?? { is_listed: item.is_listed, slug: item.slug }
                  const setEdit = (patch: Partial<{ is_listed: boolean; slug: string }>) =>
                    setItemEdits((prev) => ({ ...prev, [item.item_id]: { ...edit, ...patch } }))
                  return (
                    <tr key={item.item_id}>
                      <td className="entity-name">
                        <span>{item.name}</span>
                        <div className="entity-sub ltr-cell">{item.sku}</div>
                      </td>
                      <td data-label="قیمت" className="money-cell">{fa(item.sales_price)}</td>
                      <td data-label="روی سایت">
                        <label className="sf-switch">
                          <input type="checkbox" checked={edit.is_listed} onChange={(e) => setEdit({ is_listed: e.target.checked })} />
                          <span>{edit.is_listed ? 'نمایش' : 'پنهان'}</span>
                        </label>
                      </td>
                      <td data-label="نشانی">
                        <input type="text" dir="ltr" className="sf-slug-input" placeholder="خودکار از SKU" value={edit.slug} onChange={(e) => setEdit({ slug: e.target.value })} />
                      </td>
                      <td className="integration-action">
                        <button type="button" onClick={() => void saveItem(item)} disabled={busy}><Save size={13} /> ذخیره</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Pager page={itemsPg.page} pageCount={itemsPg.pageCount} onChange={itemsPg.setPage} />
          </div>
        )}
      </SectionCard>

      <SectionCard icon={CreditCard} title="درگاهِ پرداخت" description="اطلاعاتِ درگاهِ خودتان — پولِ فروشِ سایت مستقیم به حسابِ شما می‌رود.">
        <div className="entity-table-wrap">
          <table className="entity-table sf-table">
            <thead>
              <tr>
                <th>درگاه</th>
                <th>مرچنت / کلید</th>
                <th>فعال</th>
                <th>اقدام</th>
              </tr>
            </thead>
            <tbody>
              {gateways.map((g) => {
                const edit = gwEdits[g.provider] ?? { merchant_id: '', is_active: g.is_active }
                const setEdit = (patch: Partial<{ merchant_id: string; is_active: boolean }>) =>
                  setGwEdits((prev) => ({ ...prev, [g.provider]: { ...edit, ...patch } }))
                return (
                  <tr key={g.provider}>
                    <td className="entity-name">{GATEWAY_LABEL[g.provider] ?? g.provider}</td>
                    <td data-label="مرچنت">
                      <input
                        type="password"
                        dir="ltr"
                        className="sf-slug-input"
                        placeholder={g.has_merchant ? '•••••• (ثبت‌شده — برای تغییر وارد کنید)' : 'کدِ مرچنت'}
                        value={edit.merchant_id}
                        onChange={(e) => setEdit({ merchant_id: e.target.value })}
                      />
                    </td>
                    <td data-label="فعال">
                      <label className="sf-switch">
                        <input type="checkbox" checked={edit.is_active} onChange={(e) => setEdit({ is_active: e.target.checked })} />
                        <span>{edit.is_active ? 'فعال' : 'غیرفعال'}</span>
                      </label>
                    </td>
                    <td className="integration-action">
                      <button type="button" onClick={() => void saveGateway(g.provider)} disabled={busy}><Save size={13} /> ذخیره</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard
        icon={ShoppingBag}
        title="سفارش‌ها"
        description="سفارش‌های سایت این‌جا می‌آیند؛ با «تأیید پرداخت» به فاکتور فروش تبدیل و موجودی کم می‌شود."
        actions={<button onClick={() => void refreshAll()} disabled={busy}><RefreshCw size={13} className={busy ? 'spin' : ''} /> به‌روزرسانی</button>}
      >
        {orders.length === 0 ? (
          <p className="hint">هنوز سفارشی ثبت نشده است.</p>
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table sf-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>مشتری</th>
                  <th>مبلغ</th>
                  <th>پرداخت</th>
                  <th>وضعیتِ ارسال</th>
                  <th>اقدام</th>
                </tr>
              </thead>
              <tbody>
                {ordersPg.pageItems.map((o) => {
                  const pay = PAYMENT_LABEL[o.payment_status] ?? { label: o.payment_status, tone: 'muted' }
                  return (
                    <tr key={o.id}>
                      <td data-label="#">
                        <strong>{fa(o.order_number)}</strong>
                        <div className="entity-sub ltr-cell">{o.tracking_code}</div>
                      </td>
                      <td className="entity-name">
                        <span>{o.customer_name}</span>
                        <div className="entity-sub ltr-cell">{o.customer_phone}</div>
                      </td>
                      <td data-label="مبلغ" className="money-cell">{fa(o.total)}</td>
                      <td data-label="پرداخت"><span className={`status-badge tone-${pay.tone}`}>{pay.label}</span></td>
                      <td data-label="وضعیتِ ارسال">
                        <select
                          className="sf-slug-input"
                          value={o.fulfillment_status}
                          disabled={busy || o.payment_status !== 'paid'}
                          onChange={(e) => void changeFulfillment(o, e.target.value)}
                        >
                          {FULFILLMENT.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
                        </select>
                      </td>
                      <td className="integration-action">
                        {o.payment_status === 'pending' ? (
                          <button type="button" className="btn-primary" onClick={() => void confirmPayment(o)} disabled={busy}>
                            <CheckCircle2 size={13} /> تأیید پرداخت
                          </button>
                        ) : o.sales_invoice_id ? (
                          <span className="status-badge tone-success">فاکتور صادر شد</span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Pager page={ordersPg.page} pageCount={ordersPg.pageCount} onChange={ordersPg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}
