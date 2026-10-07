import {useRepairDraftMarker} from './repairDraftContext'
import { useRepairPanelActive } from './repairPanelActivity'
import {useEffect,useRef,useState} from 'react'
import {can,fetchRepairLinkableDocuments,linkRepairDocument,openInvoicePrintView,voidRepairDocument,type MeResponse,type RepairCase,type RepairFinancial} from '../../api'
import {SearchSelect} from '../../components/SearchSelect'
import {JalaliDatePicker} from '../../components/JalaliDatePicker'
import {todayIso} from '../../lib/jalali'

export function RepairDocuments({token,me,row,financial,busy,run,refresh}:{token:string;me:MeResponse;row:RepairCase;financial:RepairFinancial|null;busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>;refresh:()=>Promise<void>}){
 const markRepairDraft=useRepairDraftMarker()

 const panelActive = useRepairPanelActive()

  const [kind,setKind]=useState('receipt'),[documents,setDocuments]=useState<{id:string;number:number|null}[]>([]),[selected,setSelected]=useState(''),[reason,setReason]=useState(''),[on,setOn]=useState(todayIso()),[error,setError]=useState('')
  const key=useRef(crypto.randomUUID()),voidKeys=useRef<Record<string,string>>({})
  const allowed=can(me,'repair','approve')&&can(me,'invoices','view')&&can(me,'checks_bank','view')
  useEffect(()=>{if (!panelActive) return;let active=true;if(allowed)fetchRepairLinkableDocuments(token,row,kind).then(d=>{if(active){setDocuments(d);setError('')}}).catch(e=>{if(active)setError(e instanceof Error?e.message:'اسناد دریافت نشد.')});return()=>{active=false}},[token,row,kind,allowed, panelActive])
  function changed(){key.current=crypto.randomUUID();voidKeys.current={}}
  return <>{allowed&&<details onChange={changed}><summary>پیوند سند خزانه یا برگشت از فروش موجود</summary>{error&&<p role="alert">{error}</p>}<div className="repair-grid"><label>نوع سند<SearchSelect aria-label="نوع سند" value={kind} onChange={e=>{markRepairDraft();setSelected('');return setKind(e.target.value)}}><option value="receipt">رسید دریافت، شامل چک</option><option value="payment">اعلامیه پرداخت</option><option value="sales_return">برگشت فاکتور همین پرونده</option></SearchSelect></label><label>سند واقعی همین مشتری<SearchSelect aria-label="سند واقعی همین مشتری" value={selected} onChange={e=>{markRepairDraft();return setSelected(e.target.value)}}><option value="">انتخاب سند</option>{documents.map(d=><option key={d.id} value={d.id}>شماره {d.number?.toLocaleString('fa-IR')}</option>)}</SearchSelect></label><label>دلیل پیوند<textarea value={reason} onChange={e=>setReason(e.target.value)}/></label></div><button disabled={busy||!selected||!reason.trim()} onClick={()=>run(async()=>{await linkRepairDocument(token,row,kind,selected,reason,key.current);await refresh();changed()})}>ثبت پیوند و تخصیص معتبر</button></details>}
    {can(me,'repair','approve')&&financial?.documents.some(d=>!d.voided)&&<details onChange={changed}><summary>اصلاح با ابطال سند و حفظ سابقه</summary><p>این عملیات سند انتخابی و تسویه‌های وابستهٔ همین پرونده را برمی‌گرداند. خروج مستقل قطعه با ابطال فاکتور حذف نمی‌شود. برگشت فعال یا تخصیص خارج پرونده باید ابتدا در مسیر اصلی تعیین تکلیف شود.</p><label>تاریخ اصلاح<JalaliDatePicker value={on} onChange={v=>{markRepairDraft();setOn(v);changed()}}/></label><label>دلیل ابطال<textarea value={reason} onChange={e=>setReason(e.target.value)}/></label>{financial.documents.filter(d=>!d.voided).map(d=><button key={d.id} disabled={busy||!reason.trim()||!can(me,d.document_type==='receipt'||d.document_type==='payment'?'checks_bank':'invoices',d.document_type==='receipt'||d.document_type==='payment'?'update':'delete')} onClick={()=>run(async()=>{const requestKey=voidKeys.current[d.id]??crypto.randomUUID();voidKeys.current[d.id]=requestKey;await voidRepairDocument(token,row,d.id,on,reason,requestKey);await refresh();changed()})}>ابطال {{sales_invoice:'فاکتور',receipt:'رسید دریافت',payment:'پرداخت',sales_return:'برگشت فروش'}[d.document_type]} {d.number?.toLocaleString('fa-IR')}</button>)}</details>}
    {['delivered','closed'].includes(row.status)&&<button disabled={busy} onClick={()=>run(()=>openInvoicePrintView(token,`/api/repair/cases/${row.id}/delivery-receipt`))}>چاپ رسید تحویل دستگاه</button>}
  </>
}
