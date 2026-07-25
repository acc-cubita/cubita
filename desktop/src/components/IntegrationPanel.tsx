import { useEffect, useState } from 'react'
import { Store, RefreshCw, Save, Plug } from 'lucide-react'
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

const EMPTY_SETTINGS: StorefrontSettingsIn = {
  base_url: '',
  admin_email: '',
  admin_password: '',
  cutover_order_id: 0,
  is_active: false,
}

export function IntegrationPanel({ token }: { token: string }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [pendingMapping, setPendingMapping] = useState<Record<string, string>>({})
  const [pendingCost, setPendingCost] = useState<Record<string, string>>({})
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

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
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  return (
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
              <input
                type="number"
                min="0"
                value={settings.cutover_order_id || ''}
                onChange={(e) => setSettings({ ...settings, cutover_order_id: Number(e.target.value) || 0 })}
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
          <button className="btn-primary" onClick={() => void handleSync()} disabled={loading || !settings.is_active}>
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            {loading ? 'در حال sync...' : 'هم‌گام‌سازی با سایت'}
          </button>
        }
      >
        <p className="hint">
          هر sync ابتدا سفارش‌های جدید سایت را به فاکتور فروش (انبار «آنلاین») تبدیل می‌کند، سپس موجودی و قیمتِ
          هر کالای نگاشت‌شده را روی سایت به‌روزرسانی می‌کند. {!settings.is_active && '— ابتدا اتصال را تنظیم و فعال کنید.'}
        </p>

        <div className="entity-table-wrap">
          <table className="entity-table">
            <thead>
              <tr>
                <th>کد کالا</th>
                <th>نام</th>
                <th>قیمت فروش</th>
                <th>بهای تمام‌شده</th>
                <th>شناسه محصول در سایت</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.sku}</td>
                  <td className="entity-name">{item.name}</td>
                  <td className="money-cell">{Number(item.sales_price).toLocaleString('fa-IR')}</td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      style={{ width: 110 }}
                      value={pendingCost[item.id] ?? String(Number(item.average_cost) || 0)}
                      onChange={(e) => setPendingCost((prev) => ({ ...prev, [item.id]: e.target.value }))}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      style={{ width: 100 }}
                      value={pendingMapping[item.id] ?? item.storefront_product_id ?? ''}
                      onChange={(e) => setPendingMapping((prev) => ({ ...prev, [item.id]: e.target.value }))}
                    />
                  </td>
                  <td>
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
  )
}
