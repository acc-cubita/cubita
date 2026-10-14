import {useEffect, useRef, useState} from 'react'
import {RepairDeviceProfile} from './RepairDeviceProfile'
import {SearchSelect} from '../../components/SearchSelect'
import {can, fetchContacts, fetchRepairDeviceIdentity, fetchRepairIdentityEvents, searchRepairDeviceIdentities, previewRepairIdentityMergeWithOwners, mergeRepairDeviceIdentity, confirmRepairDeviceOwner, type MeResponse, type RepairDeviceIdentity as Device, type RepairIdentityEvent, type ContactRecord, type RepairMergeOwner, type RepairMergeInput} from '../../api'
import {formatJalali} from '../../lib/jalali'
import {useRepairPanelActive} from './repairPanelActivity'
import {useRepairDraftMarker} from './repairDraftContext'
import {printRepairDeviceIdentity} from '../../api'

interface Props {token:string;me:MeResponse;deviceId:string;busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>}
export function RepairDeviceIdentity({token,me,deviceId,busy,run}:Props){
  const [identityId,setIdentityId]=useState(deviceId)
  useEffect(()=>setIdentityId(deviceId),[deviceId])
  const active=useRepairPanelActive(),mark=useRepairDraftMarker()
  const view=can(me,'repair_identity','view'),approve=can(me,'repair_identity','approve')
  const [expanded,setExpanded]=useState(false),[device,setDevice]=useState<Device|null>(null),[events,setEvents]=useState<RepairIdentityEvent[]>([])
  const [ownerStatus,setOwnerStatus]=useState<'confirmed'|'unverified'>('unverified'),[cursor,setCursor]=useState<string|null>(null)
  const [contacts,setContacts]=useState<ContactRecord[]>([]),[error,setError]=useState(''),[query,setQuery]=useState(''),[candidates,setCandidates]=useState<Device[]>([])
  const [owner,setOwner]=useState(''),[reason,setReason]=useState(''),[evidence,setEvidence]=useState('')
  const [preview,setPreview]=useState<{source:Device;target:Device;owners:{source:RepairMergeOwner|null;target:RepairMergeOwner|null};data:RepairMergeInput}|null>(null)
  const keys=useRef(new Map<string,string>())
  function key(data:unknown){const hash=JSON.stringify(data);let value=keys.current.get(hash);if(!value){value=crypto.randomUUID();keys.current.set(hash,value)}return value}
  async function reload(){setDevice(await fetchRepairDeviceIdentity(token,identityId));if(view){const page=await fetchRepairIdentityEvents(token,identityId);setEvents(page.items);setOwnerStatus(page.ownership_status);setCursor(page.next_cursor)}}
  useEffect(()=>{if(!active||!expanded)return;let alive=true;fetchRepairDeviceIdentity(token,identityId).then(d=>{if(alive)setDevice(d)}).catch(e=>{if(alive)setError(e.message)});if(view)fetchRepairIdentityEvents(token,identityId).then(r=>{if(alive){setEvents(r.items);setOwnerStatus(r.ownership_status);setCursor(r.next_cursor)}}).catch(e=>{if(alive)setError(e.message)});if(approve&&view)fetchContacts(token).then(r=>{if(alive)setContacts(r)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[active,expanded,token,identityId,view,approve])
  const currentOwner=events.find(event=>event.kind==='ownership')
  const editable=approve&&view&&device?.canonical_id===device?.id
  function change(setter:(value:string)=>void,value:string){setter(value);setPreview(null);mark()}
  return <details className="repair-panel" onToggle={e=>setExpanded(e.currentTarget.open)}><summary>شناسنامه و مالکیت دستگاه</summary>
    {error&&<p role="alert">{error}</p>}
    {!device?<p role="status">در حال دریافت شناسنامه…</p>:<>
      <p>شناسهٔ ثابت: <bdi style={{overflowWrap:'anywhere'}}>{device.identifier}</bdi></p>
      <p>{device.brand} {device.model} — سریال: <bdi>{device.serial||'ثبت نشده'}</bdi></p>
      <button disabled={busy} onClick={()=>run(async()=>{await printRepairDeviceIdentity(token,device.id)})}>چاپ برچسب ثابت دستگاه</button>
      <RepairDeviceProfile key={device.id} token={token} device={device} editable={!!editable} busy={busy} run={run} refresh={reload}/>
      {device.canonical_id!==device.id&&<p role="status">این شناسنامه به هویت اصلی ارجاع دارد. پرونده‌های قبلی با شناسهٔ قدیمی محفوظ‌اند. <button disabled={busy} onClick={()=>{setIdentityId(device.canonical_id);setPreview(null);setEvents([])}}>باز کردن شناسنامهٔ اصلی</button></p>}
      {view&&<><p>مالکیت: {ownerStatus==='confirmed'?'تأییدشده؛ مطابق آخرین تصمیم ثبت‌شده':'تأییدنشده؛ از پذیرش قبلی حدس زده نمی‌شود'}</p>
        {events.map(event=><p key={event.id}>{formatJalali(event.created_at.slice(0,10))} — {event.kind==='merge'?'ادغام هویت':event.kind==='profile'?'اصلاح مشخصات فنی':'تأیید مالکیت'} — {event.reason}</p>)}{cursor&&<button disabled={busy} onClick={()=>run(async()=>{const page=await fetchRepairIdentityEvents(token,identityId,cursor);setEvents([...events,...page.items]);setCursor(page.next_cursor)})}>ادامهٔ سابقهٔ شناسنامه</button>}</>}
      {editable&&<div className="repair-form" data-repair-draft>
        <label>دلیل تصمیم<textarea value={reason} onChange={e=>change(setReason,e.target.value)} maxLength={2000}/></label>
        <label>شرح مدرک بررسی‌شده<textarea value={evidence} onChange={e=>change(setEvidence,e.target.value)} maxLength={4000}/></label>
        <label>مالک تأییدشده<SearchSelect aria-label="مالک تأییدشده" value={owner} onChange={e=>change(setOwner,e.target.value)}><option value="">انتخاب شخص</option>{contacts.filter(c=>c.is_active).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</SearchSelect></label>
        <button disabled={busy||(ownerStatus==='confirmed'&&!currentOwner)||!owner||reason.trim().length<3||evidence.trim().length<3} onClick={()=>run(async()=>{const data={version:device.version,contact_id:owner,previous_ownership_id:currentOwner?.id??null,reason,evidence};await confirmRepairDeviceOwner(token,device.id,data,key(data));await reload();setReason('');setEvidence('');setPreview(null)})}>ثبت تصمیم مالکیت</button>
        <details><summary>ادغام با شناسنامهٔ دیگر</summary><p>ابتدا دو هویت را بررسی کنید. پرونده‌ها، بدهی و اسناد قبلی منتقل نمی‌شوند.</p>
          <label>سریال، IMEI یا شناسهٔ دستگاه مقصد<input value={query} onChange={e=>{setQuery(e.target.value);setPreview(null)}}/></label>
          <button disabled={busy||!query.trim()} onClick={()=>run(async()=>{setCandidates((await searchRepairDeviceIdentities(token,query)).items.filter(d=>d.id!==device.id));setPreview(null)})}>جست‌وجوی شناسنامه</button>
          {candidates.map(candidate=><button key={candidate.id} disabled={busy||reason.trim().length<3||evidence.trim().length<3} onClick={()=>run(async()=>{const data={version:device.version,target_device_id:candidate.id,target_version:candidate.version,reason,evidence};const result=await previewRepairIdentityMergeWithOwners(token,device.id,data);setPreview({...result,data})})}>بررسی {candidate.model} — {candidate.serial||candidate.identifier}</button>)}
          {preview&&<div role="status"><p>مبدأ: {preview.source.model} / {preview.source.serial} — مقصد: {preview.target.model} / {preview.target.serial}</p><p style={{overflowWrap:'anywhere'}}>شناسهٔ مقصد: <bdi>{preview.target.identifier}</bdi></p>{(preview.owners.source||preview.owners.target)&&<><p>مالک مبدأ: {preview.owners.source?.name??'تأییدنشده'} — مالک مقصد: {preview.owners.target?.name??'تأییدنشده'}</p><label>مالک نهایی پس از بررسی مدارک<SearchSelect aria-label="مالک نهایی پس از بررسی مدارک" value={preview.data.resolved_owner_contact_id??''} onChange={e=>{mark();setPreview({...preview,data:{...preview.data,source_ownership_id:preview.owners.source?.id??null,target_ownership_id:preview.owners.target?.id??null,resolved_owner_contact_id:e.target.value||null}})}}><option value="">انتخاب صریح مالک</option>{[preview.owners.source,preview.owners.target].filter((o,i,all):o is RepairMergeOwner=>!!o&&all.findIndex(v=>v?.contact_id===o.contact_id)===i).map(o=><option key={o.id} value={o.contact_id}>{o.name}</option>)}</SearchSelect></label></>}<button disabled={busy||!!((preview.owners.source||preview.owners.target)&&!preview.data.resolved_owner_contact_id)} onClick={()=>run(async()=>{await mergeRepairDeviceIdentity(token,device.id,preview.data,key(preview.data));setPreview(null);await reload()})}>تأیید ادغام و حفظ سوابق</button></div>}
        </details>
      </div>}
    </>}
  </details>
}
