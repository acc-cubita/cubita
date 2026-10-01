import { useCallback, useEffect, useState } from 'react'
import { RotateCw } from 'lucide-react'
import {
  fetchEnterpriseMarketSyncStatus, fetchEnterpriseMarketPostingErrors, fetchItemsLive,
  retryEnterpriseMarketPosting, repairEnterpriseMarketPostingMapping,
  type EnterpriseMarketPostingError, type ItemRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { ItemPicker } from './ItemPicker'
import { formatJalali } from '../lib/jalali'

export function EnterpriseMarketStatus({ token, side }: { token: string; side: 'buyer' | 'seller' }) {
  const [status, setStatus] = useState<Awaited<ReturnType<typeof fetchEnterpriseMarketSyncStatus>> | null>(null)
  const [errors, setErrors] = useState<EnterpriseMarketPostingError[]>([])
  const [items, setItems] = useState<ItemRecord[]>([])
  const [selected, setSelected] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const refresh = useCallback(async () => {
    try {
      const [state, rows] = await Promise.all([fetchEnterpriseMarketSyncStatus(token), fetchEnterpriseMarketPostingErrors(token)])
      setStatus(state); setErrors(rows.filter(row => row.side === side)); setError('')
    } catch (e) { setError(e instanceof Error ? e.message : 'وضعیت بازار خوانده نشد؛ دوباره تلاش کنید.') }
  }, [token, side])
  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => { void refresh() }, 60_000)
    return () => window.clearInterval(timer)
  }, [refresh])
  async function act(work: () => Promise<unknown>) {
    setBusy(true); setError('')
    try { await work(); await refresh() }
    catch (e) { setError(e instanceof Error ? e.message : 'اصلاح ثبت مالی انجام نشد؛ دوباره تلاش کنید.') }
    finally { setBusy(false) }
  }
  return <SectionCard icon={RotateCw} title="همگام‌سازی بازار" actions={<button type="button" className="btn-ghost" disabled={busy} onClick={() => { void refresh() }}><RotateCw size={14} /> تازه‌سازی وضعیت</button>}>
    {error && <p role="alert" className="form-error">{error}</p>}
    {status && <p role="status">
      {status.access_denied ? 'اعتبار پیوند رد شده؛ مالک شرکت باید پیوند و مجوز را بررسی کند.' : status.offline ? 'ارتباط بازار برقرار نیست یا داده‌ها تازه نیستند؛ اطلاعات ذخیره‌شده فقط برای مشاهده است.' : 'ارتباط بازار برقرار است.'}
      {' '}آخرین دریافت: {status.last_sync_at ? `${formatJalali(status.last_sync_at)}، ${new Date(status.last_sync_at).toLocaleTimeString('fa-IR')}` : 'هنوز انجام نشده'}
    </p>}
    {errors.map(row => <div key={row.event_id} className="section-card">
      <strong>{row.kind === 'return' ? 'مرجوعی' : 'سفارش'} شمارهٔ {Number(row.order_number).toLocaleString('fa-IR')}</strong>
      <p>{row.error_detail || 'ثبت مالی در انتظار پردازش است.'} تلاش‌ها: {row.attempts.toLocaleString('fa-IR')}</p>
      {row.error_code === 'item_mapping_missing' && <>
        <button type="button" className="btn-ghost" disabled={busy} onClick={() => { void act(async () => { setItems(await fetchItemsLive(token)) }) }}>انتخاب کالای اصلاحی</button>
        {items.length > 0 && row.lines.map(line => <div key={line.market_item_ref}>
          <label>{line.name || 'کالای بازار'} ({line.unit})</label>
          <ItemPicker items={items} value={selected[line.market_item_ref] || ''} onChange={id => setSelected(previous => ({ ...previous, [line.market_item_ref]: id }))} />
          <button type="button" className="btn-ghost" disabled={busy || !selected[line.market_item_ref]} onClick={() => { void act(() => repairEnterpriseMarketPostingMapping(token, row.event_id, line.market_item_ref, selected[line.market_item_ref])) }}>ذخیرهٔ نگاشت</button>
        </div>)}
      </>}
      <button type="button" className="btn-primary" disabled={busy || status?.access_denied} onClick={() => { void act(() => retryEnterpriseMarketPosting(token, row.event_id)) }}>تلاش دوبارهٔ ثبت مالی</button>
    </div>)}
  </SectionCard>
}
