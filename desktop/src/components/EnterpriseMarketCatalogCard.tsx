import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Link2, PauseCircle, RotateCw } from 'lucide-react'
import {
  approveEnterpriseMarketCatalog, fetchEnterpriseMarketMappings, fetchMpListings,
  mapEnterpriseMarketListing, pauseEnterpriseMarketCatalog, removeEnterpriseMarketListingMapping,
  type EnterpriseMarketMappings, type Listing,
} from '../api'
import { SectionCard } from './SectionCard'
import { formatJalali } from '../lib/jalali'

export function EnterpriseMarketCatalogCard({ token }: { token: string }) {
  const [listings, setListings] = useState<Listing[]>([])
  const [mappings, setMappings] = useState<EnterpriseMarketMappings | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [local, linked] = await Promise.all([
        fetchMpListings(token), fetchEnterpriseMarketMappings(token),
      ])
      setListings(local); setMappings(linked); setError('')
    } catch (e) { setError(e instanceof Error ? e.message : 'نگاشت کاتالوگ خوانده نشد.') }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(''); setMessage('')
    try { await action(); await refresh(); setMessage(success) }
    catch (e) { setError(e instanceof Error ? e.message : 'عملیات نگاشت انجام نشد.') }
    finally { setBusy(false) }
  }

  const mapped = new Set(mappings?.listings.map(row => row.local_listing_id) ?? [])
  return <SectionCard icon={Link2} title="انتخاب و نگاشت کاتالوگ بازار" description="فقط کالاهای انتخاب‌شده و اطلاعات نمایشیِ آن‌ها به بازار ابری می‌روند؛ بهای خرید، بارها، انبار و اسناد حسابداری منتقل نمی‌شوند.">
    {error && <p className="error" role="alert">{error}</p>}
    {message && <p className="fy-note fy-note--ok">{message}</p>}
    <p className="muted">تا تأیید نهایی، کاتالوگ قدیمیِ حساب پیوندخورده دوباره منتشر نمی‌شود. هر تغییر پس از اتصال اینترنت در همگام‌سازی بعدی اعمال می‌شود.</p>
    <p className="muted">آخرین همگام‌سازی: {mappings?.last_sync_at ? formatJalali(mappings.last_sync_at) : 'هنوز انجام نشده'}</p>
    {mappings?.last_error_code && <p className="error">خطای همگام‌سازی: {mappings.last_error_code}</p>}
    <div className="check-actions">
      <button type="button" onClick={() => void refresh()} disabled={busy}><RotateCw size={14} /> تازه‌سازی</button>
      {mappings?.approved ?
        <button type="button" onClick={() => void run(() => pauseEnterpriseMarketCatalog(token), 'انتشار متوقف شد؛ در همگام‌سازی بعدی به ابر می‌رسد.')} disabled={busy}><PauseCircle size={14} /> توقف انتشار</button> :
        <button type="button" className="btn-primary" onClick={() => void run(() => approveEnterpriseMarketCatalog(token), 'کاتالوگ تأیید شد و در اتصال بعدی منتشر می‌شود.')} disabled={busy || mapped.size === 0}><CheckCircle2 size={14} /> تأیید و انتشار</button>
      }
    </div>
    {listings.length === 0 ? <p className="muted">ابتدا در تب «کاتالوگ» یک قلم از کالاهای محلی بسازید.</p> :
      <div className="table-scroll"><table className="entity-table cards-on-mobile"><thead><tr><th>قلم محلی</th><th>اجزا</th><th>وضعیت نگاشت</th><th>عملیات</th></tr></thead><tbody>
        {listings.map(listing => <tr key={listing.id}>
          <td data-label="قلم محلی">{listing.title}</td>
          <td data-label="اجزا">{listing.components.map(c => c.item_name).join('، ')}</td>
          <td data-label="وضعیت نگاشت">{mapped.has(listing.id) ? 'انتخاب‌شده' : 'انتخاب نشده'}</td>
          <td data-label="عملیات">{!mappings?.approved && (mapped.has(listing.id) ?
            <button type="button" disabled={busy} onClick={() => void run(() => removeEnterpriseMarketListingMapping(token, listing.id), 'نگاشت حذف شد.')} >حذف از بازار</button> :
            <button type="button" disabled={busy} onClick={() => void run(() => mapEnterpriseMarketListing(token, listing), 'قلم و اجزای آن نگاشت شدند.')} >انتخاب برای بازار</button>
          )}</td>
        </tr>)}
      </tbody></table></div>
    }
  </SectionCard>
}
