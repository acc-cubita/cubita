import {useRepairDraftMarker} from './repairDraftContext'
import { useRepairPanelActive } from './repairPanelActivity'
import { useEffect, useRef, useState } from 'react'
import { can, fetchRepairCase, fetchRepairCases, fetchRepairMembers, runRepairBulk, type MeResponse, type RepairBulkResult, type RepairCase } from '../../api'
import { BarcodeScanner } from '../../components/BarcodeScanner'
import { SearchSelect } from '../../components/SearchSelect'

interface Props {token:string;me:MeResponse;rows:RepairCase[];busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>;refresh:()=>Promise<void>;open:(id:string)=>Promise<void>}
export function RepairBatchActions({token,me,rows,busy,run,refresh,open}:Props){
 const markRepairDraft=useRepairDraftMarker()

 const panelActive = useRepairPanelActive()

  const [chosen,setChosen]=useState<string[]>([]),[members,setMembers]=useState<{id:string;name:string}[]>([]),[scan,setScan]=useState(false),[code,setCode]=useState('')
  const [action,setAction]=useState<'assign'|'notify'>('assign'),[technician,setTechnician]=useState(''),[reason,setReason]=useState(''),[override,setOverride]=useState(false),[event,setEvent]=useState<'admission'|'ready'|'approval'>('ready'),[result,setResult]=useState<RepairBulkResult|null>(null),[error,setError]=useState('')
  const key=useRef(crypto.randomUUID())
  function changed(){key.current=crypto.randomUUID();setResult(null)}
  useEffect(()=>{if (!panelActive) return;let alive=true;if(can(me,'repair','update'))fetchRepairMembers(token).then(values=>{if(alive)setMembers(values)}).catch(e=>{if(alive)setError(e instanceof Error?e.message:'کاربران دریافت نشدند')});return()=>{alive=false}},[token,me, panelActive])
  async function find(value:string){
    const normalized=value.trim().replace(/[۰-۹]/g,d=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    if(/^cubita:repair:[0-9a-f-]{36}$/i.test(normalized)){const row=await fetchRepairCase(token,normalized.slice(14));await open(row.id)}
    else if(/^R?\d{1,9}$/.test(normalized)){const number=Number(normalized.replace(/^R/,'')),page=await fetchRepairCases(token,'R'+number);const row=page.items.find(r=>r.number===number);if(!row)throw new Error('پروندهٔ مجاز با این شماره پیدا نشد.');await open(row.id)}
    else throw new Error('بارکد پذیرش یا QR داخلی تعمیرگاه را اسکن کنید.')
  }
  const available=rows.filter(row=>chosen.includes(row.id))
  return <section className="repair-panel"><h3>اسکن پرونده</h3>{error&&<p role="alert">{error}</p>}<div className="repair-toolbar"><label>شماره یا کد اسکن‌شده<input value={code} onChange={e=>setCode(e.target.value)}/></label><button disabled={busy||!code.trim()} onClick={()=>run(()=>find(code))}>باز کردن پرونده</button><button disabled={busy} onClick={()=>setScan(true)}>اسکن با دوربین</button></div>{scan&&<BarcodeScanner once onClose={()=>setScan(false)} onDetected={value=>{setScan(false);setCode(value);void run(()=>find(value))}}/>}
    {can(me,'repair','update') && <><details><summary>انتخاب پرونده‌ها برای عملیات گروهی</summary><p>انتخاب‌ها از همین فهرست با فیلتر فعال هستند. نتیجهٔ هر پرونده جداگانه ثبت می‌شود.</p><div className="repair-checks">{rows.map(row=><label key={row.id}><input type="checkbox" disabled={busy} checked={chosen.includes(row.id)} onChange={e=>{setChosen(old=>e.target.checked?[...old,row.id]:old.filter(id=>id!==row.id));changed()}}/>{row.number.toLocaleString('fa-IR')} — {row.owner_snapshot.name}</label>)}</div>
    </details>{available.length>0 && <div className="repair-grid"><label>عملیات<SearchSelect aria-label="عملیات" value={action} onChange={e=>{markRepairDraft();setAction(e.target.value as typeof action);changed()}}><option value="assign">تخصیص تکنسین</option>{can(me,'repair','approve')&&<option value="notify">صف اعلان</option>}</SearchSelect></label>{action==='assign'?<label>تکنسین<SearchSelect aria-label="تکنسین" value={technician} onChange={e=>{markRepairDraft();setTechnician(e.target.value);changed()}}><option value="">رفع ارجاع</option>{members.map(member=><option key={member.id} value={member.id}>{member.name}</option>)}</SearchSelect></label>:<label>اعلان<SearchSelect aria-label="اعلان" value={event} onChange={e=>{markRepairDraft();setEvent(e.target.value as typeof event);changed()}}><option value="admission">پذیرش</option><option value="ready">آمادهٔ تحویل</option><option value="approval">تأیید برآورد</option></SearchSelect></label>}<label>دلیل<textarea value={reason} onChange={e=>{setReason(e.target.value);changed()}}/></label>{can(me,'repair','approve')&&action==='assign'&&<label className="repair-inline"><input type="checkbox" checked={override} onChange={e=>{setOverride(e.target.checked);changed()}}/>اجازهٔ مدیر برای اضافه‌ظرفیت با دلیل ثبت‌شده</label>}<button disabled={busy||!available.length||!reason.trim()||!can(me,'repair',action==='assign'?'update':'approve')} onClick={()=>run(async()=>{setResult(await runRepairBulk(token,{action,cases:available.map(row=>({case_id:row.id,version:row.version})),technician_id:technician||null,reason,capacity_override:override,notification_event:event},key.current));await refresh()})}>اجرای عملیات روی {available.length.toLocaleString('fa-IR')} پرونده</button></div>}</>}
    {result&&<ul aria-live="polite">{result.results.map(item=><li key={item.case_id}>{rows.find(row=>row.id===item.case_id)?.number.toLocaleString('fa-IR')??item.case_id}: {item.ok?(item.status==='unavailable'?'ثبت شد؛ سرویس ارسال تنظیم نیست':item.status?'در صف ارسال؛ هنوز ارسال نشده':'انجام شد'):item.error}</li>)}</ul>}
  </section>
}
