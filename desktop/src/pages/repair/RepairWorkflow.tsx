import { useEffect, useRef, useState } from 'react'
import { addRepairTask, assignRepairCase, can, changeRepairTask, fetchRepairTechnicians, transitionRepairCase, type MeResponse, type RepairCase } from '../../api'
import { SearchSelect } from '../../components/SearchSelect'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { formatJalali } from '../../lib/jalali'

import { REPAIR_STATES } from './repairShared'

export function RepairWorkflow({ token, me, row, busy, run, refresh }: { token: string; me: MeResponse; row: RepairCase; busy: boolean; run: (action: () => Promise<void>) => Promise<void>; refresh: () => Promise<void> }) {
  const [technicians, setTechnicians] = useState<{ id: string; name: string }[]>([]), [assignee, setAssignee] = useState(row.assigned_to_id ?? '')
  const [state, setState] = useState(''), [reason, setReason] = useState(''), [exceptional, setExceptional] = useState(false)
  const [title, setTitle] = useState(''), [note, setNote] = useState(''), [due, setDue] = useState('')
  const [loadError, setLoadError] = useState('')
  const taskKey = useRef(crypto.randomUUID()), update = can(me,'repair','update')
  useEffect(() => { let active = true; fetchRepairTechnicians(token,row.branch_id).then(values => { if(active) setTechnicians(values) }).catch(e => { if(active) setLoadError(e instanceof Error ? e.message : 'فهرست تکنسین‌ها دریافت نشد.') }); return () => { active = false } }, [token,row.branch_id])
  useEffect(() => { setAssignee(row.assigned_to_id ?? ''); setState('') }, [row.id,row.version,row.assigned_to_id])
  const finished = ['cancelled','delivered','closed'].includes(row.status)
  return <section><h3>گردش تعمیر — {REPAIR_STATES[row.status]}</h3>{row.pause_reason && <p>دلیل انتظار: {row.pause_reason}</p>}
    {loadError && <p role="alert">{loadError}</p>}
    {update && !finished && <div className="repair-grid"><label>تکنسین مسئول<SearchSelect value={assignee} onChange={e => setAssignee(e.target.value)}><option value="">بدون ارجاع</option>{technicians.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</SearchSelect></label><label>دلیل تغییر وضعیت یا ارجاع<textarea value={reason} onChange={e => setReason(e.target.value)} /></label><button disabled={busy || !reason.trim()} onClick={() => run(async () => { await assignRepairCase(token,row,assignee || null,reason); await refresh() })}>ثبت ارجاع یا تحویل داخلی</button>
      <label>وضعیت بعدی<SearchSelect value={state} onChange={e => setState(e.target.value)}><option value="">انتخاب وضعیت</option>{(exceptional ? Object.entries(REPAIR_STATES).filter(([k]) => !['ready','delivered','closed',row.status].includes(k)).map(([key,label]) => ({ key,label })) : row.allowed_statuses ?? []).map(s => <option key={s.key} value={s.key}>{s.label}</option>)}</SearchSelect></label>{can(me,'repair','approve') && <label className="repair-inline"><input type="checkbox" checked={exceptional} onChange={e => { setExceptional(e.target.checked); setState('') }} />گذار استثنایی با دلیل</label>}<button disabled={busy || !state} onClick={() => run(async () => { await transitionRepairCase(token,row,state,reason,exceptional); await refresh(); setReason('') })}>ثبت وضعیت</button></div>}
    <h3>کارها و یادداشت داخلی</h3><p className="field-hint">این یادداشت‌ها روی رسید مشتری چاپ نمی‌شوند. رمز دستگاه را در یادداشت وارد نکنید.</p>
    {row.tasks?.map(task => <article className="repair-task" key={task.id}><strong>{task.title}</strong><p>{task.internal_note}</p><p>{task.due_date ? `موعد: ${formatJalali(task.due_date)}` : ''} — {task.status === 'pending' ? 'شروع نشده' : task.status === 'working' ? 'در حال انجام' : 'پایان یافته'}</p>{update && !finished && task.status !== 'done' && <button disabled={busy} onClick={() => run(async () => { await changeRepairTask(token,row,task.id,task.status === 'pending' ? 'working' : 'done'); await refresh() })}>{task.status === 'pending' ? 'شروع کار' : 'پایان کار'}</button>}</article>)}
    {update && !finished && <div className="repair-grid"><label>عنوان کار<input value={title} onChange={e => { setTitle(e.target.value); taskKey.current = crypto.randomUUID() }} /></label><label>یادداشت داخلی<textarea value={note} onChange={e => { setNote(e.target.value); taskKey.current = crypto.randomUUID() }} /></label><label>موعد کار<JalaliDatePicker value={due} onChange={v => { setDue(v); taskKey.current = crypto.randomUUID() }} /></label><button disabled={busy || !title.trim()} onClick={() => run(async () => { await addRepairTask(token,row,title,note,due || null,taskKey.current); await refresh(); setTitle(''); setNote(''); setDue(''); taskKey.current = crypto.randomUUID() })}>ثبت کار</button></div>}
  </section>
}
