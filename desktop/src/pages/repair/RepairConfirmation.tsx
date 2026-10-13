import {SearchSelect} from '../../components/SearchSelect'
import {fetchRepairRepresentatives,type RepairRepresentative} from '../../api'
import {RepairConfirmationOverride} from './RepairConfirmationOverride'
import {useEffect,useRef,useState} from 'react'
import {fetchRepairConfirmationCapabilities,requestRepairConfirmation,verifyRepairConfirmation,consumeRepairIntakeConfirmation,type RepairCase,type RepairConfirmation as Confirmation,type RepairDeliveryDraft} from '../../api'
import {useRepairPanelActive} from './repairPanelActivity'

interface Props {token:string;row:RepairCase;busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>;refresh:()=>Promise<void>;delivery?:RepairDeliveryDraft;canOverride?:boolean;onVerified?:(id:string|null)=>void}
const states:Record<Confirmation['status'],string>={requested:'درخواست ثبت شد',sent:'پیام به سرویس ارسال تحویل شد',failed:'ارسال ناموفق',verified:'کد تأیید شد',expired:'کد منقضی شد',locked:'سقف تلاش ناموفق پر شد',consumed:'تأیید روی سند ثبت شد'}
export function RepairConfirmation({token,row,busy,run,refresh,delivery,onVerified,canOverride=false}:Props){
 const active=useRepairPanelActive(),[expanded,setExpanded]=useState(false),[available,setAvailable]=useState<boolean|null>(null),[error,setError]=useState('')
 const [name,setName]=useState(row.owner_snapshot.name),[phone,setPhone]=useState(row.owner_snapshot.phone),[authority,setAuthority]=useState(''),[code,setCode]=useState(''),[confirmation,setConfirmation]=useState<Confirmation|null>(null)
 const [representatives,setRepresentatives]=useState<RepairRepresentative[]>([]),[representation,setRepresentation]=useState(''),[repCursor,setRepCursor]=useState<string|null>(null)
 const [nextSend,setNextSend]=useState(0),[clock,setClock]=useState(Date.now())
 const keys=useRef({request:crypto.randomUUID(),verify:crypto.randomUUID(),consume:crypto.randomUUID()})
 const inputHash=JSON.stringify({delivery:delivery??{name,phone,authority,revision:row.intake_details?.receipt_revision},representation})
 const previous=useRef(inputHash)
 useEffect(()=>{if(previous.current!==inputHash){previous.current=inputHash;setConfirmation(null);setCode('');keys.current.request=crypto.randomUUID();onVerified?.(null)}},[inputHash,onVerified])
 useEffect(()=>{if(!expanded||!active)return;let alive=true;fetchRepairConfirmationCapabilities(token).then(result=>{if(alive)setAvailable(result.sms_available)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[expanded,active,token])
 useEffect(()=>{if(!expanded||!active)return;const timer=setInterval(()=>setClock(Date.now()),1000);return()=>clearInterval(timer)},[expanded,active])
 const remaining=Math.max(0,Math.ceil((nextSend-clock)/1000)),expired=confirmation?Date.parse(confirmation.expires_at)<=clock:false
 useEffect(()=>{if(expired)onVerified?.(null)},[expired,onVerified])
 const selected=representatives.find(item=>item.id===representation)
 const requestData={...(representation?{representation_id:representation,recipient_contact_id:selected?.contact_id??undefined}:{}),version:row.version,kind:delivery?'delivery' as const:'intake' as const,recipient_name:delivery?.receiver_name??name,recipient_phone:delivery?.receiver_phone??phone,authority_evidence:delivery?.authorization??authority,...(delivery?{delivery:{...delivery,version:row.version}}:{})}
 return <details className="repair-panel" onToggle={e=>setExpanded(e.currentTarget.open)}><summary>تأیید {delivery?'تحویل':'پذیرش'} با کد پیامکی</summary>
 {error&&<p role="alert">{error}</p>}{available===false&&<p role="status">ارسال واقعی تعمیرگاه فعال یا تنظیم نشده است. مدیر سرور باید سرویس را پیش از استفاده راه‌اندازی کند؛ پیامک شبیه‌سازی‌شده تأیید محسوب نمی‌شود.</p>}
 {!delivery&&<div className="repair-grid"><label>نام تأییدکننده<input value={name} onChange={e=>setName(e.target.value)}/></label><label>همراه تأییدکننده<input value={phone} onChange={e=>setPhone(e.target.value)}/></label><label>مدرک اختیار تأییدکننده<textarea value={authority} onChange={e=>setAuthority(e.target.value)}/></label></div>}
 <details><summary>استفاده از نمایندهٔ مصوب</summary><button disabled={busy} onClick={()=>run(async()=>{const result=await fetchRepairRepresentatives(token,row.id);setRepresentatives(result.items);setRepCursor(result.next_cursor)})}>دریافت اختیارهای ثبت‌شده</button><label>نمایندهٔ مجاز<SearchSelect aria-label="نمایندهٔ مجاز" value={representation} onChange={e=>{setRepresentation(e.target.value);const item=representatives.find(r=>r.id===e.target.value);if(item&&!delivery){setName(item.name);setPhone(item.phone);setAuthority('اختیار نمایندگی مصوب همین پرونده')}}}><option value="">بررسی مدرک اختیار هنگام ثبت سند</option>{representatives.filter(r=>!r.revoked&&Date.parse(r.expires_at)>Date.now()&&r.operation===(delivery?'delivery':'intake')).map(r=><option key={r.id} value={r.id}>{r.name} — {r.phone}</option>)}</SearchSelect></label>{selected&&delivery&&<p>گیرندهٔ فرم تحویل باید دقیقاً {selected.name} با همراه {selected.phone} باشد.</p>}{repCursor&&<button disabled={busy} onClick={()=>run(async()=>{const page=await fetchRepairRepresentatives(token,row.id,repCursor);setRepresentatives([...representatives,...page.items]);setRepCursor(page.next_cursor)})}>ادامهٔ نمایندگان</button>}</details>
 <p>کد به گیرنده و نسخهٔ فعلی سند متصل است؛ پنج دقیقه اعتبار و حداکثر پنج تلاش دارد.</p>
 <button disabled={busy||available!==true||remaining>0||!(delivery?.authorization??authority).trim()||!(delivery?.receiver_name??name).trim()||!(delivery?.receiver_phone??phone).trim()} onClick={()=>run(async()=>{const result=await requestRepairConfirmation(token,row.id,requestData,keys.current.request);setConfirmation(result);setCode('');setNextSend(Date.now()+60000);keys.current.request=crypto.randomUUID();onVerified?.(null);await refresh()})}>{remaining>0?`ارسال دوباره پس از ${remaining.toLocaleString('fa-IR')} ثانیه`:'درخواست کد برای نسخهٔ فعلی'}</button>
 {confirmation&&<><p role="status">{expired&&confirmation.status!=='consumed'?'کد منقضی شد':states[confirmation.status]} {confirmation.message}</p>
 {confirmation.status==='sent'&&!expired&&<><label>کد شش‌رقمی<input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={e=>{setCode(e.target.value);keys.current.verify=crypto.randomUUID()}}/></label><p>تلاش باقی‌مانده: {confirmation.attempts_remaining.toLocaleString('fa-IR')}</p><button disabled={busy||code.length!==6} onClick={()=>run(async()=>{const result=await verifyRepairConfirmation(token,row.id,confirmation,code,keys.current.verify);setConfirmation(result);setCode('');keys.current.verify=crypto.randomUUID();onVerified?.(result.status==='verified'?result.id:null)})}>بررسی کد</button></>}
 {!delivery&&confirmation.status==='verified'&&!expired&&<button disabled={busy} onClick={()=>run(async()=>{const result=await consumeRepairIntakeConfirmation(token,row,confirmation,keys.current.consume);setConfirmation(result);await refresh()})}>ثبت تأیید پذیرش روی این نسخه</button>}
 {delivery&&confirmation.status==='verified'&&!expired&&<p>اکنون «ثبت تحویل و رسید» را بزنید؛ کنترل کیفیت و مالی دوباره انجام می‌شود.</p>}
 </>}
 {canOverride&&<RepairConfirmationOverride key={inputHash} token={token} caseId={row.id} data={requestData} busy={busy} run={run} saved={async result=>{setConfirmation(result);onVerified?.(result.status==='verified'?result.id:null);await refresh()}}/>}
 </details>
}
