import { useCallback, useEffect, useState } from 'react'
import { RotateCw } from 'lucide-react'
import {
  fetchEnterpriseMarketSyncStatus, fetchEnterpriseMarketPostingErrors, fetchItemsLive,
  retryEnterpriseMarketPosting, repairEnterpriseMarketPostingMapping,
  approveEnterpriseMarketQuantity,
  fetchItemUnits,
  type EnterpriseMarketPostingError, type ItemRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { ItemPicker } from './ItemPicker'
import { formatJalali, toFaDigits } from '../lib/jalali'
import { TransactionUnitPicker, type TransactionUnitPatch } from './TransactionUnitPicker'

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
      {row.kind === 'order' && row.lines.map((line,index) => line.local_item_id && line.qty &&
        <PrivateQuantityInput key={index} token={token} eventId={row.event_id} index={index}
          line={line} side={side} busy={busy || Boolean(status?.access_denied)} act={act} />)}
      <button type="button" className="btn-primary" disabled={busy || status?.access_denied} onClick={() => { void act(() => retryEnterpriseMarketPosting(token, row.event_id)) }}>تلاش دوبارهٔ ثبت مالی</button>
    </div>)}
  </SectionCard>
}

function PrivateQuantityInput({token,eventId,index,line,side,busy,act}: {
  token:string; eventId:string; index:number; line:EnterpriseMarketPostingError['lines'][number];
  side:'buyer'|'seller'; busy:boolean; act:(work:()=>Promise<unknown>)=>Promise<void>
}) {
  const [unit,setUnit]=useState<TransactionUnitPatch>({})
  useEffect(()=>{
    let cancelled=false
    setUnit({})
    if (!line.local_item_id) return
    fetchItemUnits(token,line.local_item_id).then(rows=>{
      const base=rows.find(row=>row.is_base && row.is_active && (side==='buyer'?row.purchase_allowed:row.sale_allowed))
      if (!cancelled && base) setUnit(previous=>previous.unitId?previous:{...previous,unitId:base.unit_id})
    }).catch(()=>{ /* The picker displays the same request's actionable error. */ })
    return ()=>{cancelled=true}
  },[token,line.local_item_id,side])
  return <details><summary>واحد و نسبت واقعی محلیِ {line.name || 'این ردیف'}</summary>
    <p>مقدار معامله: {toFaDigits(line.qty || '')} {line.unit}</p>
    <p className="hint">مقدار معامله در واحد محلی انتخاب‌شده ثبت می‌شود. نسبت واقعی را برای همین رویداد وارد کنید؛ این اندازه‌گیری به ابر ارسال نمی‌شود.</p>
    <TransactionUnitPicker token={token} itemId={line.local_item_id || ''} qty={line.qty || ''}
      unitId={unit.unitId} observations={unit.observations} context={side==='buyer'?'purchase':'sale'}
      onChange={(patch)=>setUnit(previous=>({...previous,...patch}))} />
    <button type="button" className="btn-ghost" disabled={busy || !unit.unitId || !unit.baseQtyPreview}
      onClick={()=>{void act(()=>approveEnterpriseMarketQuantity(token,eventId,{
        line_index:index,unit_id:unit.unitId!,observations:unit.observations || []}))}}>تأیید مقدار و نسبت محلی</button>
  </details>
}
