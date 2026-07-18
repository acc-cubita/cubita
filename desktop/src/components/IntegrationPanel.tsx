import { useEffect, useState } from 'react'
import { Store, RefreshCw, Save } from 'lucide-react'
import {
  fetchItemsLive,
  triggerStorefrontSync,
  updateItemStorefrontMapping,
  type ItemRecord,
  type SyncResult,
} from '../api'
import { SectionCard } from './SectionCard'

export function IntegrationPanel({ token }: { token: string }) {
  const [items, setItems] = useState<ItemRecord[]>([])
  const [pendingMapping, setPendingMapping] = useState<Record<string, string>>({})
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function refresh() {
    setItems((await fetchItemsLive(token)).filter((i) => !i.is_service))
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function saveMapping(itemId: string) {
    setMessage(null)
    const raw = pendingMapping[itemId]
    const value = raw === undefined || raw === '' ? null : Number(raw)
    try {
      await updateItemStorefrontMapping(token, itemId, value)
      await refresh()
      setMessage('نگاشت کالا ذخیره شد.')
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
    <SectionCard
      icon={Store}
      title="اتصال به سایت فروشگاهی (ipnetcity.ir)"
      actions={
        <button className="btn-primary" onClick={() => void handleSync()} disabled={loading}>
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
          {loading ? 'در حال sync...' : 'هم‌گام‌سازی با سایت فروشگاهی'}
        </button>
      }
    >
      <p className="hint">
        این بخش نیاز به اتصال اینترنت دارد و تنظیمات <code>STOREFRONT_API_BASE_URL</code> /{' '}
        <code>STOREFRONT_ADMIN_EMAIL</code> / <code>STOREFRONT_ADMIN_PASSWORD</code> روی بک‌اند را لازم دارد.
        هر sync ابتدا سفارش‌های جدید سایت را به فاکتور فروش (انبار «آنلاین») تبدیل می‌کند، سپس موجودی/قیمت فعلی
        هر کالای نگاشت‌شده را روی سایت به‌روزرسانی می‌کند.
      </p>
      {message && <div className="hint">{message}</div>}

      <h3>نگاشت کالا ↔ محصول سایت</h3>
      <table>
        <thead>
          <tr>
            <th>کد کالا</th>
            <th>نام</th>
            <th>شناسه محصول در سایت</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.sku}</td>
              <td>{item.name}</td>
              <td>
                <input
                  type="number"
                  value={pendingMapping[item.id] ?? item.storefront_product_id ?? ''}
                  onChange={(e) => setPendingMapping((prev) => ({ ...prev, [item.id]: e.target.value }))}
                  style={{ width: 100 }}
                />
              </td>
              <td>
                <button type="button" onClick={() => void saveMapping(item.id)}>
                  <Save size={13} /> ذخیره
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

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
  )
}
