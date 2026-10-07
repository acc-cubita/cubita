import {useRepairDraftMarker} from './repairDraftContext'
import {useEffect,useRef,useState} from 'react'
import {fetchRepairSuggestions,saveRepairCapacity,fetchRepairSkills,setRepairSkills,type MeResponse,type RepairDeviceType,type RepairTechnicianSuggestion,can} from '../../api'
import {SearchSelect} from '../../components/SearchSelect'
export function RepairTeamSettings({token,me,branch,types,busy,run}:{token:string;me:MeResponse;branch:string;types:RepairDeviceType[];busy:boolean;run:(action:()=>Promise<void>)=>Promise<void>}) {
 const markRepairDraft=useRepairDraftMarker()

 const [techs,setTechs]=useState<RepairTechnicianSuggestion[]>([]),[tech,setTech]=useState(''),[limit,setLimit]=useState(''),[skills,setSkills]=useState<string[]>([]),[error,setError]=useState('')
 const generation=useRef(0)
 useEffect(()=>{let alive=true;fetchRepairSuggestions(token,branch).then(t=>{if(alive)setTechs(t)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[token,branch])
 useEffect(()=>{let alive=true;const current=++generation.current;setSkills([]);if(tech)fetchRepairSkills(token,tech).then(s=>{if(alive&&current===generation.current)setSkills(s.type_ids)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[token,tech])
 const selectedCapacity=techs.find(t=>t.id===tech)?.max_active_cases
 useEffect(()=>setLimit(String(selectedCapacity??'')),[tech,selectedCapacity])
 if(!can(me,'repair','approve'))return null
 return <details className="repair-panel"><summary>تخصص و ظرفیت تکنسین‌ها</summary>{error&&<p role="alert">{error}</p>}<label>تکنسین تنظیمات<SearchSelect aria-label="تکنسین تنظیمات" value={tech} onChange={e=>{markRepairDraft();return setTech(e.target.value)}}><option value="">انتخاب تکنسین</option>{techs.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</SearchSelect></label>{tech&&<><label>سقف پروندهٔ فعال<input inputMode="numeric" placeholder="خالی: بدون سقف" value={limit} onChange={e=>setLimit(e.target.value)}/></label><div className="repair-checks">{types.map(t=><label key={t.id}><input type="checkbox" checked={skills.includes(t.id)} onChange={e=>setSkills(old=>e.target.checked?[...old,t.id]:old.filter(id=>id!==t.id))}/>{t.name}</label>)}</div><button disabled={busy} onClick={()=>run(async()=>{if(limit&&!/^[1-9]\d*$/.test(limit))throw new Error('ظرفیت باید عدد مثبت باشد.');await saveRepairCapacity(token,techs.find(t=>t.id===tech)!,limit?Number(limit):null);setTechs(await fetchRepairSuggestions(token,branch))})}>ذخیره سقف ظرفیت تکنسین</button><button disabled={busy} onClick={()=>run(async()=>{await setRepairSkills(token,tech,skills);setSkills((await fetchRepairSkills(token,tech)).type_ids)})}>ذخیرهٔ تخصص</button></>}</details>
}
