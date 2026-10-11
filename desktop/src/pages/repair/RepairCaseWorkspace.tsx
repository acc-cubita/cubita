import {useEffect,useRef,useState} from 'react'
import {can,downloadRepairFile,fetchRepairFiles,fetchRepairTechnicians,printRepairReceipt,relocateRepairCase,uploadRepairFile,type MeResponse,type RepairCase,type RepairBranch,type RepairDeviceType,type RepairFile} from '../../api'
import {formatJalali} from '../../lib/jalali'
import {REPAIR_STATES} from './repairShared'
import {RepairWorkspaceTabs,RepairRetainedPanel} from './RepairWorkspaceTabs'
import {RepairWorkflow} from './RepairWorkflow'
import {RepairDailyTools} from './RepairDailyTools'
import {RepairTechnicalTools} from './RepairTechnicalTools'
import {RepairEstimates} from './RepairEstimates'
import {RepairOperations} from './RepairOperations'
import {RepairDeviceAccess} from './RepairDeviceAccess'
import {RepairSupplyTools} from './RepairSupplyTools'
import {RepairFinance} from './RepairFinance'
import {RepairBusinessTools} from './RepairBusinessTools'
import {RepairNotifications} from './RepairNotifications'
import {RepairParticipationTools} from './RepairParticipationTools'
import {RepairTechnicianFees} from './RepairTechnicianFees'
import {RepairCoverage} from './RepairCoverage'
import {RepairCustody} from './RepairCustody'
import {RepairWarranty} from './RepairWarranty'
import {RepairCustomerPortal} from './RepairCustomerPortal'
interface Props {token:string;me:MeResponse;row:RepairCase;branches:RepairBranch[];types:RepairDeviceType[];busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>;refresh:()=>Promise<void>;open:(id:string)=>Promise<void>;refreshTypes:()=>Promise<void>;onBack:()=>void;revisit:()=>void;initialTab?:string}
export function RepairCaseWorkspace({token,me,row,branches,types,busy,run,refresh,open,refreshTypes,onBack,revisit,initialTab='summary'}:Props){
 const [caseTab,setCaseTab]=useState(initialTab),[location,setLocation]=useState(row.storage_location),[files,setFiles]=useState<RepairFile[]>([]),[technicians,setTechnicians]=useState<{id:string;name:string}[]>([]),[error,setError]=useState('')
 const fileInput=useRef<HTMLInputElement>(null),create=can(me,'repair','create'),update=can(me,'repair','update')
 useEffect(()=>{let alive=true;fetchRepairTechnicians(token,row.branch_id).then(t=>{if(alive)setTechnicians(t)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[token,row.branch_id])
 useEffect(()=>{if(caseTab!=='messages')return;let alive=true;fetchRepairFiles(token,row.id).then(f=>{if(alive)setFiles(f)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[token,row.id,caseTab])
 return <>{error&&<p role="alert">{error}</p>}<article key={row.id} data-repair-draft className="repair-case-workspace"><button disabled={busy} onClick={onBack}>بازگشت به فهرست</button><header className="repair-case-heading"><strong>پذیرش {row.number.toLocaleString('fa-IR')}</strong><p>{row.owner_snapshot.name} — {row.device_snapshot.model} — {REPAIR_STATES[row.status]} — تکنسین: {row.assigned_to_id ? technicians.find(t=>t.id===row.assigned_to_id)?.name??'در حال دریافت' : 'تخصیص نیافته'}{row.due_date && ` — موعد ${formatJalali(row.due_date)}`}</p></header><RepairWorkspaceTabs panelIdPrefix={row.id} label="بخش‌های پرونده" value={caseTab} onChange={setCaseTab} tabs={[{id:"summary",label:"خلاصه و پذیرش"},{id:"repair",label:"تشخیص و تعمیر"},{id:"parts",label:"قطعات و امانت"},{id:"finance",label:"برآورد و مالی"},{id:"delivery",label:"تحویل و ضمانت"},{id:"messages",label:"پیام‌ها و سوابق"}]} /><RepairRetainedPanel id={row.id+"-panel-summary"} labelledBy={row.id+"-summary"} active={caseTab === "summary"}><div className="repair-panel"><div className="repair-toolbar"><h2>پذیرش {row.number.toLocaleString('fa-IR')} — {row.owner_snapshot.name}</h2><button disabled={busy} onClick={() => run(async () => printRepairReceipt(token, row.id))}>چاپ رسید و برچسب</button>{create && <details><summary>سایر اقدام‌ها</summary><button disabled={busy} onClick={revisit}>مراجعهٔ مجدد همین دستگاه</button></details>}</div>
      <p>{row.device_snapshot.category} / {row.device_snapshot.brand} / {row.device_snapshot.model}</p><p>{row.reported_issue}</p><p>وضعیت ظاهری: {row.appearance} — لوازم: {row.accessories}</p>
      {!!row.open_case_warnings?.length && <div role="status" className="repair-warning">این دستگاه پروندهٔ باز دیگری دارد: {row.open_case_warnings.map(c => c.number.toLocaleString('fa-IR')).join('، ')}</div>}
      <div data-repair-action><label>محل نگهداری<input disabled={!update} value={location} onChange={e => setLocation(e.target.value)} /></label>{update && <button disabled={busy || !location.trim()} onClick={() => run(async () => { await relocateRepairCase(token, row, location); await refresh() })}>ثبت محل نگهداری</button>}</div>
</div>
      <RepairDailyTools key={'daily-'+row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} />
      </RepairRetainedPanel>
      <RepairRetainedPanel id={row.id+"-panel-repair"} labelledBy={row.id+"-repair"} active={caseTab === "repair"}>
      <RepairEstimates mode="diagnosis" key={'diagnosis-' + row.id} token={token} me={me} row={row} types={types} branches={branches} busy={busy} run={run} refresh={async () => { await refresh() }} refreshTypes={async () => refreshTypes()} />
      <RepairDailyTools mode="timer" key={'timer-'+row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} />
      <RepairWorkflow key={row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async () => { await refresh() }} />
      <RepairTechnicalTools key={'technical-'+row.id} types={types} token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} open={open} />
      <RepairOperations key={'operations-' + row.id} token={token} me={me} row={row} types={types} busy={busy} run={run} refresh={async () => { await refresh() }} refreshTypes={async () => refreshTypes()} />
      <RepairDeviceAccess key={'access-' + row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async () => refresh()} />
      </RepairRetainedPanel>
      <RepairRetainedPanel id={row.id+"-panel-parts"} labelledBy={row.id+"-parts"} active={caseTab === "parts"}>
      <RepairOperations mode="parts" key={'parts-' + row.id} token={token} me={me} row={row} types={types} busy={busy} run={run} refresh={async () => { await refresh() }} refreshTypes={async () => refreshTypes()} />
      <RepairSupplyTools token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} />
      <RepairCustody token={token} me={me} row={row} branches={branches} busy={busy} run={run} refresh={async()=>{await refresh()}} />
      </RepairRetainedPanel>
      <RepairRetainedPanel id={row.id+"-panel-finance"} labelledBy={row.id+"-finance"} active={caseTab === "finance"}>
      <RepairEstimates key={'estimate-' + row.id} token={token} me={me} row={row} types={types} branches={branches} busy={busy} run={run} refresh={async () => { await refresh() }} refreshTypes={async () => refreshTypes()} />
      <RepairTechnicalTools mode="agreement" types={types} token={token} me={me} row={row} busy={busy} run={run} refresh={refresh} open={open}/>
      <RepairFinance key={'finance-' + row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async () => {await refresh()}} />
      <RepairParticipationTools token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} />
      <RepairTechnicianFees token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} />
      <RepairCoverage token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} />
      </RepairRetainedPanel>
      <RepairRetainedPanel id={row.id+"-panel-delivery"} labelledBy={row.id+"-delivery"} active={caseTab === "delivery"}>
      <RepairFinance mode="delivery" key={'delivery-finance-' + row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async () => {await refresh()}} />
      <RepairDailyTools mode="delivery" key={'delivery-'+row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} />
      <RepairWarranty token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} open={async id=>{await open(id)}} />
      </RepairRetainedPanel>
      <RepairRetainedPanel id={row.id+"-panel-messages"} labelledBy={row.id+"-messages"} active={caseTab === "messages"}>
      <h3>پیوست‌های پذیرش</h3>{update && <label>تصویر JPEG/PNG یا PDF؛ حداکثر پنج مگابایت<button type="button" disabled={busy} onClick={()=>fileInput.current?.click()}>انتخاب فایل پیوست</button><input ref={fileInput} hidden type="file" accept="image/jpeg,image/png,application/pdf" disabled={busy} onChange={e => { const file = e.target.files?.[0]; e.target.value = ''; if (file) void run(async () => { await uploadRepairFile(token, row.id, file); setFiles(await fetchRepairFiles(token, row.id)) }) }} /></label>}{files.map(file => <button key={file.id} disabled={busy} onClick={() => run(async () => downloadRepairFile(token, row.id, file))}>{file.filename}</button>)}
      <h3>سوابق مراجعهٔ دستگاه</h3>{row.visits?.map(v => <button key={v.id} disabled={busy} onClick={() => run(async () => open(v.id))}>پذیرش {v.number.toLocaleString('fa-IR')} — {formatJalali(v.admission_date)}</button>)}

      <RepairBusinessTools key={'business-'+row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async()=>{await refresh()}} />
      <RepairNotifications key={'notifications-' + row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async () => {await refresh()}} />
      <RepairCustomerPortal key={'portal-' + row.id} token={token} me={me} row={row} busy={busy} run={run} refresh={async () => {await refresh()}} />
      <h3>تاریخچهٔ پذیرش</h3>{row.events?.map(event => <p key={event.id}>{formatJalali(event.created_at.slice(0,10))} — {({ admitted:'پذیرش ثبت شد', relocated:'محل نگهداری تغییر کرد', assigned:'ارجاع ثبت شد', status_changed:'وضعیت تغییر کرد', task_added:'کار ثبت شد', task_working:'کار شروع شد', task_done:'کار پایان یافت', diagnosed:'عیب‌یابی ثبت شد',estimate_created:'برآورد تازه ثبت شد',estimate_decided:'تصمیم مشتری ثبت شد',part_requested:'درخواست قطعه ثبت شد',part_reserve:'قطعه رزرو شد',part_dispatch:'قطعه تحویل محل تعمیر شد',part_release:'رزرو آزاد شد',part_consume:'مصرف قطعه ثبت شد',part_return_unused:'قطعهٔ مصرف‌نشده برگشت',part_return_consumed:'مصرف قطعه اصلاح شد',part_waste:'ضایعات ثبت شد',part_supplier_return:'قطعه به تأمین‌کننده برگشت',work_recorded:'کار تکنسین ثبت شد',quality_checked:'کنترل کیفیت ثبت شد',outsourced:'برون‌سپاری ثبت شد',outsource_returned:'کار برون‌سپاری بازگشت',removed_part_recorded:'تکلیف قطعهٔ بازشده ثبت شد',purchase_requested:'درخواست تأمین ثبت شد',purchase_request_updated:'درخواست تأمین به‌روز شد',device_secret_set:'رمز دستگاه حفاظت شد',device_secret_viewed:'رمز با مجوز مشاهده شد',device_secret_cleared:'رمز دستگاه پاک شد',device_secret_expired:'مهلت نگهداری رمز پایان یافت' } as Record<string,string>)[event.action] ?? 'عملیات پرونده ثبت شد'}{event.action==='status_changed' && <>: {REPAIR_STATES[event.detail.from]} ← {REPAIR_STATES[event.detail.to]}</>}{event.detail.reason && <> — {event.detail.reason}</>}</p>)}
    </RepairRetainedPanel></article></>
}
