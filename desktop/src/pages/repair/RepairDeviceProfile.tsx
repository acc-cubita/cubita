import {useRef,useState} from 'react'
import {saveRepairDeviceProfile,type RepairDeviceIdentity} from '../../api'
import {useRepairDraftMarker} from './repairDraftContext'

const labels={manufacturer_part_number:'شمارهٔ فنی سازنده',chassis_number:'شمارهٔ شاسی',board_number:'شمارهٔ برد',engine_number:'شمارهٔ موتور',asset_tag:'برچسب تجهیز',mac_address:'نشانی MAC'}
export function RepairDeviceProfile({token,device,editable,busy,run,refresh}:{token:string;device:RepairDeviceIdentity;editable:boolean;busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>;refresh:()=>Promise<void>}){
 const [hardware,setHardware]=useState(device.hardware_revision??''),[identifiers,setIdentifiers]=useState<Record<string,string>>(device.industry_identifiers??{}),[reason,setReason]=useState(''),[notice,setNotice]=useState('')
 const mark=useRepairDraftMarker(),key=useRef(crypto.randomUUID())
 const changed=()=>{mark();key.current=crypto.randomUUID();setNotice('')}
 return <details><summary>نسخهٔ سخت‌افزار و شناسه‌های فنی</summary><p>فقط مشخصات فنی غیرشخصی دستگاه را ثبت کنید. اصلاح شناسنامه، مشخصات پذیرش‌های قبلی را بازنویسی نمی‌کند.</p>
 {editable?<div data-repair-action><label>نسخهٔ سخت‌افزار<input maxLength={120} value={hardware} onChange={e=>{changed();setHardware(e.target.value)}}/></label>{Object.entries(labels).map(([name,label])=><label key={name}>{label}<input maxLength={120} value={identifiers[name]??''} onChange={e=>{changed();setIdentifiers({...identifiers,[name]:e.target.value})}}/></label>)}<label>دلیل اصلاح مشخصات<textarea maxLength={2000} value={reason} onChange={e=>{changed();setReason(e.target.value)}}/></label><button disabled={busy||reason.trim().length<3} onClick={()=>run(async()=>{await saveRepairDeviceProfile(token,device.id,{version:device.version,hardware_revision:hardware,industry_identifiers:Object.fromEntries(Object.entries(identifiers).filter(([,value])=>value.trim())),reason},key.current);setReason('');setNotice('مشخصات تازه و سابقهٔ اصلاح ثبت شدند.');await refresh()})}>ثبت نسخهٔ مشخصات فنی</button></div>:<><p>نسخهٔ سخت‌افزار: {device.hardware_revision||'ثبت نشده'}</p>{Object.entries(labels).map(([key,label])=>device.industry_identifiers?.[key]&&<p key={key}>{label}: <bdi style={{overflowWrap:'anywhere'}}>{device.industry_identifiers[key]}</bdi></p>)}</>}
 {notice&&<p role="status">{notice}</p>}
 </details>
}
