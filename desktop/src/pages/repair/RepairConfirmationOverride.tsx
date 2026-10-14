import {useRef,useState,type PointerEvent} from 'react'
import {overrideRepairConfirmation,previewRepairConfirmation,type RepairConfirmationInput,type RepairConfirmation} from '../../api'
import {useRepairDraftMarker} from './repairDraftContext'

interface Props {token:string;caseId:string;data:RepairConfirmationInput;busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>;saved:(result:RepairConfirmation)=>Promise<void>}
interface Receipt {number:string;owner:{name:string};device:{brand?:string;model:string;serial:string};reported_issue:string;appearance:string;accessories:string;terms:string;intake_evidence?:{snapshot:{accessories:{title:string;quantity:number;condition:string}[];tests:{title:string;result:string;reason:string}[];images:unknown[]}}}
export function RepairConfirmationOverride({token,caseId,data,busy,run,saved}:Props){
 const markDraft=useRepairDraftMarker()
 const [preview,setPreview]=useState<{hash:string;version:number;receipt:Receipt}|null>(null),[reason,setReason]=useState(''),[relation,setRelation]=useState(''),[strokes,setStrokes]=useState<number[][][]>([])
 const drawing=useRef(false),key=useRef(crypto.randomUUID())
 function point(e:PointerEvent<SVGSVGElement>){const box=e.currentTarget.getBoundingClientRect();return [Math.max(0,Math.min(1000,(e.clientX-box.left)*1000/box.width)),Math.max(0,Math.min(400,(e.clientY-box.top)*400/box.height))]}
 function clear(){setStrokes([]);drawing.current=false;key.current=crypto.randomUUID()}
 const valid=strokes.filter(stroke=>stroke.length>=2)
 return <details><summary>تأیید جایگزین با امضا و ثبت مسئول</summary><p>این روش با مجوز مستقل شما ثبت می‌شود. گیرنده باید همین نسخه را بررسی و روی صفحه امضا کند.</p>
 <button disabled={busy} onClick={()=>run(async()=>{const result=await previewRepairConfirmation(token,caseId,data);setPreview({hash:result.document_hash,version:data.version,receipt:result.document.intake_document as Receipt});clear()})}>آماده‌سازی نسخه برای امضا</button>
 {preview&&<><p>تأییدکننده: {data.recipient_name} — همراه: {data.recipient_phone}</p><p>مدرک اختیار: {data.authority_evidence}</p>{data.delivery&&<p>لوازم تحویلی: {data.delivery.accessories} — توصیه‌ها: {data.delivery.care_instructions||'ثبت نشده'}</p>}
 <section aria-label="نسخهٔ رسید برای امضا"><h3>رسید {preview.receipt.number}</h3><p>مشتری: {preview.receipt.owner.name} — دستگاه: {preview.receipt.device.brand} {preview.receipt.device.model} — سریال: {preview.receipt.device.serial||'ندارد'}</p><p>ایراد: {preview.receipt.reported_issue}</p><p>ظاهر: {preview.receipt.appearance||'ثبت نشده'} — لوازم: {preview.receipt.accessories||'ثبت نشده'}</p><p>شرایط: {preview.receipt.terms}</p>{preview.receipt.intake_evidence&&<><p>لوازم بررسی‌شده: {preview.receipt.intake_evidence.snapshot.accessories.map(a=>`${a.title} (${a.quantity.toLocaleString('fa-IR')})؛ ${a.condition}`).join('، ')||'ندارد'}</p><p>آزمون‌های اولیه: {preview.receipt.intake_evidence.snapshot.tests.map(t=>`${t.title}: ${{healthy:'سالم',faulty:'معیوب',not_tested:'تست‌نشده',not_applicable:'نامرتبط'}[t.result]??t.result}${t.reason?'؛ '+t.reason:''}`).join('، ')||'ندارد'}</p><p>تعداد تصاویر نسخه: {preview.receipt.intake_evidence.snapshot.images.length.toLocaleString('fa-IR')}. تصاویر و نشانه‌ها را در بخش پذیرش تصویری همین پرونده بررسی کنید.</p></>}</section>
 <label>علت استفاده از روش جایگزین<textarea value={reason} onChange={e=>{setReason(e.target.value);key.current=crypto.randomUUID()}}/></label><label>نسبت یا سمت امضاکننده<input value={relation} onChange={e=>{setRelation(e.target.value);key.current=crypto.randomUUID()}}/></label>
 <svg viewBox="0 0 1000 400" role="img" aria-label="محل رسم امضای تأییدکننده" style={{width:'100%',maxWidth:600,background:'white',border:'1px solid #64748b',touchAction:'none'}}
 onPointerDown={e=>{if(strokes.length>=100)return;markDraft();const p=point(e);e.currentTarget.setPointerCapture(e.pointerId);drawing.current=true;setStrokes(old=>[...old,[p]]);key.current=crypto.randomUUID()}}
 onPointerMove={e=>{if(!drawing.current)return;const p=point(e);setStrokes(old=>old.reduce((n,s)=>n+s.length,0)>=4000?old:old.map((s,i)=>i===old.length-1?[...s,p]:s))}}
 onPointerUp={()=>{drawing.current=false}} onPointerCancel={()=>{drawing.current=false}}>
 {strokes.map((stroke,i)=><polyline key={i} points={stroke.map(p=>p.join(',')).join(' ')} fill="none" stroke="black" strokeWidth="4"/>)}</svg>
 <div className="repair-toolbar"><button disabled={busy} onClick={clear}>پاک کردن امضا</button><button disabled={busy||reason.trim().length<3||!relation.trim()||!valid.length||preview.version!==data.version} onClick={()=>run(async()=>{const result=await overrideRepairConfirmation(token,caseId,{...data,expected_document_hash:preview.hash,override_reason:reason,acknowledgment:{version:data.version,kind:data.kind,signer_name:data.recipient_name,signer_relation:relation,strokes:valid}},key.current);clear();setPreview(null);await saved(result)})}>ثبت امضای این نسخه</button></div>{preview.version!==data.version&&<p role="alert">پرونده تغییر کرده؛ نسخه را دوباره برای امضا آماده کنید.</p>}
 </>}
 </details>
}
