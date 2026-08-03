import { useEffect, useMemo, useState } from 'react'
import { Store, RefreshCw, Save, Plug, Package, Link2, Unlink, CheckCircle2, AlertTriangle, PowerOff } from 'lucide-react'
import {
  fetchItemsLive,
  fetchStorefrontSettings,
  triggerStorefrontSync,
  updateItemCost,
  updateItemStorefrontMapping,
  updateStorefrontSettings,
  type ItemRecord,
  type StorefrontSettingsIn,
  type SyncResult,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { StatCard } from './StatCard'

const EMPTY_SETTINGS: StorefrontSettingsIn = {
  base_url: '',
  admin_email: '',
  admin_password: '',
  cutover_order_id: 0,
  is_active: false,
}

const fa = (n: string | number) => Number(n).toLocaleString('fa-IR')
type MapFilter = 'all' | 'mapped' | 'unmapped'

export function IntegrationPanel({ token }: { token: string }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [pendingMapping, setPendingMapping] = useState<Record<string, string>>({})
  const [pendingCost, setPendingCost] = useState<Record<string, string>>({})
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [mapFilter, setMapFilter] = useState<MapFilter>('all')
  const [search, setSearch] = useState('')

  // تنظیماتِ اتصالِ همین کسب‌وکار (پرمستأجر)
  const [settings, setSettings] = useState<StorefrontSettingsIn>(EMPTY_SETTINGS)
  const [hasPassword, setHasPassword] = useState(false)
  const [savingSettings, setSavingSettings] = useState(false)

  async function refreshItems() {
    setItems((await fetchItemsLive(token)).filter((i) => !i.is_service))
  }

  async function refreshSettings() {
    const s = await fetchStorefrontSettings(token)
    setSettings({
      base_url: s.base_url,
      admin_email: s.admin_email,
      admin_password: '', // هرگز از سرور نمی‌آید؛ خالی = رمزِ فعلی حفظ شود
      cutover_order_id: s.cutover_order_id,
      is_active: s.is_active,
    })
    setHasPassword(s.has_password)
  }

  useEffect(() => {
    void refreshItems()
    void refreshSettings().catch(() => {})
  }, [])

  // وضعیتِ اتصال از روی تنظیمات مشتق می‌شود
  const configured = !!(settings.base_url && settings.admin_email && (hasPassword || settings.admin_password))
  const connState: 'unconfigured' | 'inactive' | 'active' = !configured ? 'unconfigured' : settings.is_active ? 'active' : 'inactive'

  const mapped = useMemo(() => items.filter((i) => i.storefront_product_id != null), [items])
  const unmappedCount = items.length - mapped.length

  const visibleItems = useMemo(() => {
    return items.filter((i) => {
      if (mapFilter === 'mapped' && i.storefront_product_id == null) return false
      if (mapFilter === 'unmapped' && i.storefront_product_id != null) return false
      if (search && !i.name.includes(search) && !i.sku.includes(search)) return false
      return true
    })
  }, [items, mapFilter, search])

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    setSavingSettings(true)
    try {
      await updateStorefrontSettings(token, settings)
      await refreshSettings()
      setMessage('تنظیمات اتصال ذخیره شد.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setSavingSettings(false)
    }
  }

  async function saveRow(item: ItemRecord) {
    setMessage(null)
    try {
      // نگاشتِ فروشگاه اگر تغییر کرده
      const rawMap = pendingMapping[item.id]
      if (rawMap !== undefined) {
        await updateItemStorefrontMapping(token, item.id, rawMap === '' ? null : Number(rawMap))
      }
      // بهای تمام‌شده اگر تغییر کرده
      const rawCost = pendingCost[item.id]
      if (rawCost !== undefined && rawCost !== '') {
        await updateItemCost(token, item.id, Number(rawCost) || 0)
      }
      await refreshItems()
      setPendingMapping((p) => ({ ...p, [item.id]: undefined as unknown as string }))
      setPendingCost((p) => ({ ...p, [item.id]: undefined as unknown as string }))
      setMessage('کالا ذخیره شد.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleSync() {
    setMessage(null)
    setLoading(true)
    try {
      const result = await triggerStorefrontSync(token)
      setSyncResult(result)
      setMessage(
        `sync کامل شد — سفارش وارد‌شده: ${result.orders_imported.length}, رد‌شده: ${result.orders_skipped.length}, کالای push‌شده: ${result.items_pushed.length}, ناموفق: ${result.items_push_failed.length}`,
      )
      await refreshItems()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  const STATUS_META = {
    unconfigured: { icon: PowerOff, label: 'تنظیم‌نشده', tone: 'muted', text: 'آدرس، ایمیل و رمزِ سایت را وارد و ذخیره کنید.' },
    inactive: { icon: AlertTriangle, label: 'غیرفعال', tone: 'warning', text: 'تنظیمات کامل است اما اتصال فعال نیست؛ تیکِ «اتصال فعال باشد» را بزنید.' },
    active: { icon: CheckCircle2, label: 'فعال و متصل', tone: 'success', text: 'اتصال فعال است؛ می‌توانید هم‌گام‌سازی را اجرا کنید.' },
  } as const
  const status = STATUS_META[connState]
  const StatusIcon = status.icon

  const filters: { key: MapFilter; label: string; count: number }[] = [
    { key: 'all', label: 'همه', count: items.length },
    { key: 'mapped', label: 'نگاشت‌شده', count: mapped.length },
    { key: 'unmapped', label: 'بدون نگاشت', count: unmappedCount },
  ]

  return (
    <>
      <div className={`integration-status tone-${status.tone}`}>
        <StatusIcon size={18} />
        <div>
          <strong>وضعیتِ اتصال: {status.label}</strong>
          <span>{status.text}</span>
        </div>
      </div>

      <div className="stat-grid">
        <StatCard icon={<Package size={18} />} label="کل کالاها" value={fa(items.length)} />
        <StatCard icon={<Link2 size={18} />} label="نگاشت‌شده به سایت" value={fa(mapped.length)} tone="success" />
        <StatCard icon={<Unlink size={18} />} label="بدون نگاشت" value={fa(unmappedCount)} tone={unmappedCount > 0 ? 'warning' : 'default'} />
        <StatCard icon={<Store size={18} />} label="وضعیتِ اتصال" value={status.label} tone={status.tone === 'muted' ? 'default' : status.tone} />
      </div>

      <div className="workspace-split">
        <SectionCard icon={Plug} title="تنظیمات اتصال به فروشگاه" description="اطلاعاتِ فروشگاهِ اینترنتیِ خودتان را وارد کنید تا نرم‌افزار به آن وصل شود.">
          <form className="invoice-form form-full" onSubmit={saveSettings}>
            <label>
              آدرس سایت (API)
              <input
                type="text"
                dir="ltr"
                placeholder="https://example.ir"
                value={settings.base_url}
                onChange={(e) => setSettings({ ...settings, base_url: e.target.value })}
              />
            </label>
            <div className="field-row">
              <label>
                ایمیل ادمین سایت
                <input
                  type="text"
                  dir="ltr"
                  value={settings.admin_email}
                  onChange={(e) => setSettings({ ...settings, admin_email: e.target.value })}
                />
              </label>
              <label>
                رمز ادمین سایت
                <input
                  type="password"
                  dir="ltr"
                  placeholder={hasPassword ? '•••••• (تنظیم‌شده — برای تغییر وارد کنید)' : 'رمز عبور'}
                  value={settings.admin_password}
                  onChange={(e) => setSettings({ ...settings, admin_password: e.target.value })}
                />
              </label>
            </div>
            <div className="field-row">
              <label>
                آستانه‌ی سفارش (cutover)
                <NumberInput
                  value={settings.cutover_order_id || ''}
                  onChange={(v) => setSettings({ ...settings, cutover_order_id: Number(v) || 0 })}
                />
                <span className="field-hint">سفارش‌های با شماره‌ی کوچک‌تر/مساویِ این مقدار وارد نمی‌شوند (سفارش‌های قدیمیِ پیش از اتصال).</span>
              </label>
              <label className="check-inline">
                <input
                  type="checkbox"
                  checked={settings.is_active}
                  onChange={(e) => setSettings({ ...settings, is_active: e.target.checked })}
                />
                اتصال فعال باشد
              </label>
            </div>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={savingSettings}>
                <Save size={14} /> {savingSettings ? 'در حال ذخیره...' : 'ذخیره تنظیمات'}
              </button>
            </div>
          </form>
          {message && <div className="hint">{message}</div>}
        </SectionCard>

        <SectionCard
          icon={Store}
          title="نگاشت کالا و هم‌گام‌سازی"
          description="هر کالای حسابداری را به شناسه‌ی محصولِ سایت وصل کنید؛ سپس هم‌گام‌سازی بزنید."
          actions={
            <button className="btn-primary" onClick={() => void handleSync()} disabled={loading || connState !== 'active'}>
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
              {loading ? 'در حال sync...' : 'هم‌گام‌سازی با سایت'}
            </button>
          }
        >
          <p className="hint">
            هر sync ابتدا سفارش‌های جدید سایت را به فاکتور فروش (انبار «آنلاین») تبدیل می‌کند، سپس موجودی و قیمتِ
            هر کالای نگاشت‌شده را روی سایت به‌روزرسانی می‌کند. {connState !== 'active' && '— ابتدا اتصال را تنظیم و فعال کنید.'}
          </p>

          {syncResult && (
            <div className="report-kpis integration-result">
              <div className="report-kpi tone-ok"><span>سفارشِ وارد‌شده</span><strong>{fa(syncResult.orders_imported.length)}</strong></div>
              <div className={`report-kpi ${syncResult.orders_skipped.length > 0 ? 'tone-warn' : ''}`}><span>سفارشِ رد‌شده</span><strong>{fa(syncResult.orders_skipped.length)}</strong></div>
              <div className="report-kpi tone-ok"><span>کالای به‌روزشده</span><strong>{fa(syncResult.items_pushed.length)}</strong></div>
              <div className={`report-kpi ${syncResult.items_push_failed.length > 0 ? 'tone-bad' : ''}`}><span>کالای ناموفق</span><strong>{fa(syncResult.items_push_failed.length)}</strong></div>
            </div>
          )}

          <div className="inst-filters">
            {filters.map((f) => (
              <button key={f.key} type="button" className={mapFilter === f.key ? 'chip-active' : ''} onClick={() => setMapFilter(f.key)}>
                {f.label} ({fa(f.count)})
              </button>
            ))}
            <input type="text" className="integration-search" placeholder="جستجوی کالا…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>

          <div className="entity-table-wrap">
            <table className="entity-table integration-table">
              <thead>
                <tr>
                  <th>کد کالا</th>
                  <th>نام</th>
                  <th>وضعیت</th>
                  <th>قیمت فروش</th>
                  <th>بهای تمام‌شده</th>
                  <th>شناسه محصول در سایت</th>
                  <th>اقدام</th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((item) => (
                  <tr key={item.id}>
                    <td data-label="کد کالا">{item.sku}</td>
                    <td className="entity-name">{item.name}</td>
                    <td data-label="وضعیت">
                      {item.storefront_product_id != null
                        ? <span className="status-badge tone-success">متصل</span>
                        : <span className="status-badge tone-muted">بدون نگاشت</span>}
                    </td>
                    <td data-label="قیمت فروش" className="money-cell">{Number(item.sales_price).toLocaleString('fa-IR')}</td>
                    <td data-label="بهای تمام‌شده">
                      <NumberInput
                        className="integration-num"
                        value={pendingCost[item.id] ?? String(Number(item.average_cost) || 0)}
                        onChange={(v) => setPendingCost((prev) => ({ ...prev, [item.id]: v }))}
                      />
                    </td>
                    <td data-label="شناسه محصول در سایت">
                      <NumberInput
                        group={false}
                        className="integration-num"
                        placeholder="—"
                        value={pendingMapping[item.id] ?? item.storefront_product_id ?? ''}
                        onChange={(v) => setPendingMapping((prev) => ({ ...prev, [item.id]: v }))}
                      />
                    </td>
                    <td className="integration-action">
                      <button type="button" onClick={() => void saveRow(item)}>
                        <Save size={13} /> ذخیره
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {syncResult && (syncResult.orders_skipped.length > 0 || syncResult.items_push_failed.length > 0) && (
            <div>
              {syncResult.orders_skipped.length > 0 && (
                <>
                  <h3>سفارش‌های رد‌شده</h3>
                  <ul className="outbox-list">
                    {syncResult.orders_skipped.map((s, idx) => (
                      <li key={idx}>
                        سفارش #{s.order_id ?? '—'}: {s.reason}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {syncResult.items_push_failed.length > 0 && (
                <>
                  <h3>کالاهای push‌نشده</h3>
                  <ul className="outbox-list">
                    {syncResult.items_push_failed.map((f, idx) => (
                      <li key={idx}>
                        {f.sku}: {f.error}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </SectionCard>
      </div>
    </>
  )
}
