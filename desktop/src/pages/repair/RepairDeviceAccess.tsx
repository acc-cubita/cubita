import { useRepairPanelActive } from './repairPanelActivity'
import { useEffect, useState } from 'react'
import { can, clearRepairDeviceSecret, fetchRepairAccessCapabilities, revealRepairDeviceSecret, setRepairDeviceSecret, type MeResponse, type RepairCase } from '../../api'

export function RepairDeviceAccess({token,me,row,busy,run,refresh}:{token:string;me:MeResponse;row:RepairCase;busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>;refresh:()=>Promise<void>}) {
 const panelActive = useRepairPanelActive()

  const [available,setAvailable] = useState(false), [loadError,setLoadError] = useState(''), [secret,setSecret] = useState(''), [days,setDays] = useState('1'), [reason,setReason] = useState(''), [revealed,setRevealed] = useState('')
  useEffect(() => {if (!panelActive) return; let active = true;fetchRepairAccessCapabilities(token).then(c => { if(active) setAvailable(c.encrypted_storage_available) }).catch(e => { if(active) setLoadError(e instanceof Error ? e.message : 'وضعیت حفاظت رمز دریافت نشد.') });return () => { active = false } },[token, panelActive])
  useEffect(() => {; if(!revealed) return;const timer=setTimeout(()=>setRevealed(''),20000);return()=>clearTimeout(timer) },[revealed])
  const update = can(me,'repair_access','update'), view = can(me,'repair_access','view')
  if(!update && !view) return null
  return <details><summary>دسترسی محدود به رمز دستگاه</summary>{loadError && <p role="alert">{loadError}</p>}<p>ثبت رمز اختیاری است. مشاهده در تاریخچه ثبت می‌شود و پس از کنترل کیفیت موفق پاک می‌شود.</p>{!available && <p>کلید حفاظت روی سرور آماده نیست؛ ذخیرهٔ رمز فعال نیست.</p>}
    {update && available && !['ready','cancelled','delivered','closed'].includes(row.status) && <div className="repair-grid"><label>رمز دستگاه<input type="password" autoComplete="new-password" maxLength={200} value={secret} onChange={e=>setSecret(e.target.value)} /></label><label>حداکثر نگهداری (روز)<input type="number" min="1" max="30" value={days} onChange={e=>setDays(e.target.value)} /></label><button disabled={busy || !secret} onClick={()=>run(async()=>{await setRepairDeviceSecret(token,row,secret,Number(days));setSecret('');await refresh()})}>ذخیرهٔ حفاظت‌شده</button></div>}
    {row.has_device_secret && view && <div className="repair-grid"><label>دلیل مشاهده<input value={reason} onChange={e=>setReason(e.target.value)} /></label><button disabled={busy || !reason.trim()} onClick={()=>run(async()=>setRevealed((await revealRepairDeviceSecret(token,row,reason)).secret))}>مشاهده با ثبت سابقه</button></div>}{revealed && <div><output dir="ltr">{revealed}</output><button onClick={()=>setRevealed('')}>پنهان کردن</button></div>}{row.has_device_secret && update && <button disabled={busy} onClick={()=>run(async()=>{await clearRepairDeviceSecret(token,row);setRevealed('');await refresh()})}>پاک کردن رمز پس از پایان نیاز</button>}
  </details>
}
