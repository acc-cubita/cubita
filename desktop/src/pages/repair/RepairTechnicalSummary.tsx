import {useRef,useState} from 'react'
import {can,fetchRepairTechnicalSummaries,previewRepairTechnicalSummary,approveRepairTechnicalSummary,type MeResponse,type RepairCase,type RepairTechnicalSummary as Summary,type RepairSummaryPreview} from '../../api'
import {formatJalali} from '../../lib/jalali'
import {useRepairDraftMarker} from './repairDraftContext'

const labels={condition:'وضعیت فنی دستگاه',repairs:'تعمیرات انجام‌شده',tests:'نتایج آزمون',care:'توصیهٔ نگهداری'}
export function RepairSummaryCards({items}:{items:Summary[]}){
 return <>{items.map(item=><article key={item.id} className="repair-task"><h4>خلاصهٔ فنی مصوب — نسخهٔ {item.revision.toLocaleString('fa-IR')}</h4><p>{formatJalali(item.approved_at.slice(0,10))}</p>{(Object.keys(labels) as (keyof typeof labels)[]).map(key=>item.content[key]&&<div key={key}><strong>{labels[key]}</strong><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{item.content[key]}</p></div>)}</article>)}</>
}

export function RepairTechnicalSummary({token,me,row,busy,run,refresh}:{token:string;me:MeResponse;row:RepairCase;busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>;refresh:()=>Promise<void>}){
 const [items,setItems]=useState<Summary[]>([]),[loaded,setLoaded]=useState(false),[preview,setPreview]=useState<RepairSummaryPreview|null>(null),[content,setContent]=useState({condition:'',repairs:'',tests:'',care:''}),[reason,setReason]=useState(''),[reviewed,setReviewed]=useState(false),[notice,setNotice]=useState('')
 const key=useRef(crypto.randomUUID()),mark=useRepairDraftMarker(),allowed=can(me,'repair_technical_summary','approve')
 const changed=()=>{mark();key.current=crypto.randomUUID();setReviewed(false)}
 return <details><summary>خلاصهٔ فنی قابل انتقال</summary><p>فقط متن بررسی‌شده برای مالک تأییدشدهٔ فعلی نمایش داده می‌شود. اطلاعات مشتری قبلی، مکاتبات، رمز و مبالغ را در متن وارد نکنید.</p>
 <button disabled={busy} onClick={()=>run(async()=>{setItems((await fetchRepairTechnicalSummaries(token,row.id)).items);setLoaded(true)})}>نمایش خلاصه‌های مجاز این مشتری</button>
 {loaded&&!items.length&&<p>خلاصهٔ مصوبی برای مالک این پرونده در دسترس نیست.</p>}<RepairSummaryCards items={items}/>{notice&&<p role="status">{notice}</p>}
 {allowed&&<><button disabled={busy} onClick={()=>run(async()=>{setPreview(await previewRepairTechnicalSummary(token,row.id));key.current=crypto.randomUUID();setReviewed(false)})}>آماده‌سازی خلاصه برای مالک فعلی</button>
 {preview&&(preview.ownership_id?<div data-repair-action><p>گیرندهٔ مجاز: {preview.recipient_name}</p>{(Object.keys(labels) as (keyof typeof labels)[]).map(field=><label key={field}>{labels[field]}<textarea maxLength={field==='repairs'||field==='tests'?4000:2000} value={content[field]} onChange={e=>{changed();setContent({...content,[field]:e.target.value})}}/></label>)}
 <label>دلیل تأیید<textarea maxLength={2000} value={reason} onChange={e=>{changed();setReason(e.target.value)}}/></label>
 <label><input type="checkbox" checked={reviewed} onChange={e=>{mark();key.current=crypto.randomUUID();setReviewed(e.target.checked)}}/>متن را بازبینی کردم؛ فقط اطلاعات فنی مجاز برای این مالک را دارد.</label>
 <button disabled={busy||!reviewed||content.condition.trim().length<3||reason.trim().length<3} onClick={()=>run(async()=>{await approveRepairTechnicalSummary(token,row,{ownership_id:preview.ownership_id!,device_version:preview.device_version,previous_revision:preview.previous_revision,content,reason,privacy_reviewed:true},key.current);setPreview(null);setContent({condition:'',repairs:'',tests:'',care:''});setReason('');setReviewed(false);setNotice('خلاصه برای مالک مشخص‌شده تأیید شد؛ پرونده و اسناد قبلی تغییر نکردند.');await refresh()})}>تأیید و نمایش برای مالک مشخص‌شده</button>
 </div>:<p>ابتدا مالکیت دستگاه را از شناسنامه تأیید کنید.</p>)}</>}
 </details>
}
