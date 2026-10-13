import {useRef,useState} from 'react'
import {previewRepairWarrantyTransfer,transferRepairWarranty,type RepairCase,type RepairWarrantyTransferPreview} from '../../api'
import {formatJalali} from '../../lib/jalali'
import {useRepairDraftMarker} from './repairDraftContext'

export function RepairWarrantyTransfer({token,row,warrantyId,busy,run,refresh}:{token:string;row:RepairCase;warrantyId:string;busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>;refresh:()=>Promise<void>}){
 const [preview,setPreview]=useState<RepairWarrantyTransferPreview|null>(null),[reason,setReason]=useState('')
 const key=useRef(crypto.randomUUID()),mark=useRepairDraftMarker()
 return <details><summary>انتقال ضمانت به مالک تأییدشده</summary><p>فقط مالکیتِ تأییدشده مبنای انتقال است. تاریخ، پوشش و اسناد مالک قبلی تغییر نمی‌کنند.</p><button disabled={busy} onClick={()=>run(async()=>{setPreview(await previewRepairWarrantyTransfer(token,row,warrantyId));key.current=crypto.randomUUID()})}>بررسی مالک و ضمانت</button>
 {preview&&(preview.ownership_id?<><p>مالک نهایی: {preview.recipient_name}</p><p>پوشش: {preview.warranty.title} — پایان همان ضمانت: {formatJalali(preview.warranty.valid_until)}</p><p>{preview.warranty.terms}</p><p>استثناها: {preview.warranty.exclusions||'ثبت نشده'}</p><label>دلیل تأیید مدیر فنی<textarea value={reason} onChange={e=>{mark();setReason(e.target.value);key.current=crypto.randomUUID()}}/></label><button disabled={busy||reason.trim().length<3} onClick={()=>run(async()=>{await transferRepairWarranty(token,row,warrantyId,{ownership_id:preview.ownership_id!,device_version:preview.device_version,previous_revision:preview.previous_revision,reason},key.current);setPreview(null);setReason('');await refresh()})}>تأیید انتقال با همان پوشش و مهلت</button></>:<p role="status">مالکیت فعلی هنوز تأیید نشده؛ ابتدا از شناسنامهٔ دستگاه، تصمیم مالکیت را ثبت کنید.</p>)}
 </details>
}
