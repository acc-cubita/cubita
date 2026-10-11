import {useRepairDraftMarker} from './repairDraftContext'
import { useRepairPanelActive } from './repairPanelActivity'
import {useEffect,useState} from 'react'
import {fetchRepairQuantityOptions,type ItemUnitRecord,type ItemConversionRule,type UnitObservation} from '../../api'
import {SearchSelect} from '../../components/SearchSelect'
import {asciiNumber} from './repairShared'
export type RepairQuantitySelection={unit_id:string|null;batch_id:string|null;observations:UnitObservation[]}

export function RepairUnitSelection({token,itemId,warehouseId,value,onChange}:{token:string;itemId:string;warehouseId:string;value:RepairQuantitySelection;onChange:(value:RepairQuantitySelection)=>void}){
 const markRepairDraft=useRepairDraftMarker()

 const panelActive = useRepairPanelActive()

  const [units,setUnits]=useState<ItemUnitRecord[]>([]),[rules,setRules]=useState<ItemConversionRule[]>([]),[batches,setBatches]=useState<{id:string;batch_number:string;qty:string}[]>([]),[error,setError]=useState('')
  useEffect(()=>{if (!panelActive) return;let active=true;setUnits([]);setRules([]);setBatches([]);setError('');if(itemId)fetchRepairQuantityOptions(token,itemId,warehouseId).then(data=>{if(active){setUnits(data.units);setRules(data.rules);setBatches(data.batches)}}).catch(e=>{if(active)setError(e instanceof Error?e.message:'واحد و بار دریافت نشد.')});return()=>{active=false}},[token,itemId,warehouseId, panelActive])
  if(!itemId)return null
  return <details><summary>واحد درخواست و بار قطعه</summary>{error&&<p role="alert">{error}</p>}<div className="repair-grid"><label>واحد مقدار واردشده<SearchSelect aria-label="واحد مقدار واردشده" value={value.unit_id??''} onChange={e=>{markRepairDraft();return onChange({...value,unit_id:e.target.value||null,observations:[]})}}><option value="">واحد پایهٔ کالا</option>{units.map(u=><option key={u.unit_id} value={u.unit_id}>{u.unit_name}</option>)}</SearchSelect></label><label>بار مبدأ (اختیاری)<SearchSelect aria-label="بار مبدأ (اختیاری)" value={value.batch_id??''} onChange={e=>{markRepairDraft();return onChange({...value,batch_id:e.target.value||null})}}><option value="">انتخاب خودکار انبار</option>{batches.map(b=><option key={b.id} value={b.id}>{b.batch_number} — مقدار {b.qty.replace(/[0-9]/g,c=>'۰۱۲۳۴۵۶۷۸۹'[Number(c)])}</option>)}</SearchSelect></label></div>{value.unit_id&&rules.filter(r=>r.mode==='variable').map(rule=>{const observation=value.observations.find(o=>o.rule_id===rule.id);return <div className="repair-grid" key={rule.id}><label>مشاهدهٔ واقعی: مقدار {units.find(u=>u.unit_id===rule.from_unit_id)?.unit_name??'واحد مبدأ'}<input inputMode="decimal" value={observation?.from_qty??''} onChange={e=>onChange({...value,observations:[...value.observations.filter(o=>o.rule_id!==rule.id),{rule_id:rule.id,from_qty:asciiNumber(e.target.value),to_qty:observation?.to_qty??''}]})}/></label><label>معادل واقعی در {units.find(u=>u.unit_id===rule.to_unit_id)?.unit_name??'واحد مقصد'}<input inputMode="decimal" value={observation?.to_qty??''} onChange={e=>onChange({...value,observations:[...value.observations.filter(o=>o.rule_id!==rule.id),{rule_id:rule.id,from_qty:observation?.from_qty??'',to_qty:asciiNumber(e.target.value)}]})}/></label></div>})}<p className="field-hint">قیمت قطعه همچنان فی هر واحد پایه است. نسبت تبدیل همراه درخواست محفوظ می‌شود؛ مقدار گردش‌های بعدی در واحد پایه است.</p></details>
}
