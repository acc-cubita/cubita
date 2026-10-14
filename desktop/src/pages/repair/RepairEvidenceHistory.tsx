import {useEffect,useState} from 'react'
import {repairImageUrl,type RepairIntakeEvidence,type RepairEvidenceSnapshot} from '../../api'
import {SearchSelect} from '../../components/SearchSelect'
import {formatJalali} from '../../lib/jalali'
import {useRepairPanelActive} from './repairPanelActivity'

function EvidenceImage({token,caseId,image}:{token:string;caseId:string;image:RepairEvidenceSnapshot['images'][number]}){
 const active=useRepairPanelActive(),[url,setUrl]=useState(''),[error,setError]=useState('')
 useEffect(()=>{if(!active)return;let alive=true,local='';repairImageUrl(token,caseId,image.attachment_id).then(value=>{local=value;if(alive){setUrl(value);setError('')}else URL.revokeObjectURL(value)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false;if(local)URL.revokeObjectURL(local)}},[token,caseId,image.attachment_id,active])
 return <figure style={{margin:0,minWidth:0}}><figcaption>{image.view}</figcaption>{error&&<p role="alert">{error}</p>}{url&&<div style={{position:'relative'}}><img src={url} alt={`نمای ثبت‌شدهٔ ${image.view}`} style={{width:'100%',display:'block'}}/>{image.marks.map((mark,i)=><span key={i} style={{position:'absolute',left:`${mark.x*100}%`,top:`${mark.y*100}%`,background:'#b91c1c',color:'white',borderRadius:'50%',transform:'translate(-50%,-50%)'}}>{(i+1).toLocaleString('fa-IR')}</span>)}</div>}{image.marks.map((mark,i)=><p key={i}>{(i+1).toLocaleString('fa-IR')} — {mark.category}: {mark.description}</p>)}</figure>
}

export function RepairEvidenceHistory({token,caseId,history}:{token:string;caseId:string;history:RepairIntakeEvidence[]}){
 const [expanded,setExpanded]=useState(false),[before,setBefore]=useState(''),[after,setAfter]=useState('')
 const first=history.find(h=>h.id===before)??history.at(-1),last=history.find(h=>h.id===after)??history[0]
 return <details onToggle={e=>setExpanded(e.currentTarget.open)}><summary>تاریخچه و مقایسهٔ تصاویر پذیرش و تحویل</summary>{expanded&&(!first||!last?<p>هنوز نسخهٔ تصویری ثبت نشده است.</p>:<div className="repair-grid">
 {([{label:'پذیرش',phase:'intake',value:before,set:setBefore,record:first},{label:'پیش از تحویل',phase:'delivery',value:after,set:setAfter,record:last}] as const).map(side=><section key={side.phase} style={{minWidth:0}}><h4>{side.label}</h4><label>نسخهٔ {side.label}<SearchSelect aria-label={`نسخهٔ ${side.label}`} value={side.value||side.record.id} onChange={e=>side.set(e.target.value)}>{history.map(h=><option key={h.id} value={h.id}>نسخهٔ {h.revision.toLocaleString('fa-IR')} — {formatJalali(h.created_at.slice(0,10))}</option>)}</SearchSelect></label><p>{side.record.reason}</p><p>لوازم: {side.record.snapshot.accessories.map(a=>`${a.title} (${a.quantity.toLocaleString('fa-IR')})؛ ${a.condition}`).join('، ')||'ندارد'}</p>{side.record.snapshot.images.filter(i=>i.phase===side.phase).map(image=><EvidenceImage key={image.attachment_id} token={token} caseId={caseId} image={image}/>)}{!side.record.snapshot.images.some(i=>i.phase===side.phase)&&<p>تصویری برای این زمان در نسخهٔ انتخاب‌شده نیست.</p>}</section>)}
 </div>)}</details>
}
