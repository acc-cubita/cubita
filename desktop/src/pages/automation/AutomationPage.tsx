import { useEffect, useRef, useState } from 'react'
import { Archive, ClipboardList, FilePenLine, FileText, History, Paperclip, Send } from 'lucide-react'
import {
  can, completeOfficeReferral, createOfficeLetter, downloadOfficeFile,
  fetchOfficeLetters, fetchOfficeRecipients, officeLetterAction, printOfficeLetter,
  referOfficeLetter, removeOfficeFile, updateOfficeLetter, uploadOfficeFile,
  type MeResponse, type OfficeFilters, type OfficeLetter, type OfficeLetterInput,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { SearchSelect } from '../../components/SearchSelect'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { EmptyState } from '../../components/EmptyState'
import { AsyncBlock, Note, OpsPage, useAsync } from '../accounting/kit'
import { formatJalali, todayIso, toFaDigits } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import './automation.css'

const KINDS = { incoming: 'وارده', outgoing: 'صادره', internal: 'داخلی' }
const STATUSES = { draft: 'پیش‌نویس', registered: 'ثبت‌شده', archived: 'بایگانی‌شده' }
const BOXES = { inbox: 'دریافتی‌های من', sent: 'ارجاع‌های ارسالی من', drafts: 'پیش‌نویس‌های من', all: 'همهٔ نامه‌های مجاز', archive: 'بایگانی' }
type Message = { text: string; kind: 'ok' | 'err' } | null
type Props = { token: string; me: MeResponse; mode: 'inbox' | 'new' | 'registry'; onNavigate: (page: PageKey) => void }
const errorText = (e: unknown) => e instanceof Error ? e.message : 'ارتباط با سرور برقرار نشد؛ دوباره تلاش کنید.'
const emptyLetter = (): OfficeLetterInput => ({ kind: 'incoming', subject: '', body: '', sender: '', addressee: '', external_number: '', external_date: null, letter_date: todayIso(), due_date: null, priority: 'normal' })
const letterInput = (row: OfficeLetter): OfficeLetterInput => ({ kind: row.kind, subject: row.subject, body: row.body, sender: row.sender, addressee: row.addressee, external_number: row.external_number, external_date: row.external_date, letter_date: row.letter_date, due_date: row.due_date, priority: row.priority })

export function AutomationPage(props: Props) {
  if (!can(props.me, 'automation', 'view')) return <OpsPage icon={ClipboardList} title="اتوماسیون اداری" description="مکاتبات و پیگیری ارجاع‌ها"><p role="alert">اجازهٔ مشاهدهٔ مکاتبات ندارید؛ از مدیر کسب‌وکار بخواهید دسترسی اتوماسیون را بررسی کند.</p></OpsPage>
  return <Workspace key={`${props.mode}:${props.token}`} {...props} />
}

function Workspace({ token, me, mode, onNavigate }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [generation, setGeneration] = useState(0)
  const title = mode === 'new' ? 'نامه جدید' : mode === 'inbox' ? 'کارتابل من' : 'دبیرخانه و بایگانی'
  return <OpsPage icon={ClipboardList} title={title} description="ثبت مکاتبات، ارجاع به همکاران و پیگیری پاسخ‌ها؛ بدون اثر مالی." canvas>
    <section className="office-toolbar" aria-label="بخش‌های اتوماسیون">
      <button type="button" onClick={() => onNavigate('automation')}>کارتابل من</button>
      <button type="button" onClick={() => onNavigate('letterlist')}>دبیرخانه و بایگانی</button>
      {can(me, 'automation', 'create') && <button type="button" onClick={() => { setSelected(null); setGeneration(v => v + 1); onNavigate('letternew') }}>نامه جدید</button>}
    </section>
    {selected ? <LetterDetail key={selected} id={selected} token={token} me={me} onBack={() => { setSelected(null); setGeneration(v => v + 1) }} />
      : mode === 'new' ? can(me, 'automation', 'create')
        ? <SectionCard icon={FilePenLine} title="پیش‌نویس نامه" description="ابتدا پیش‌نویس را ذخیره کنید، سپس پیوست‌ها را اضافه کرده و نامه را ثبت نهایی کنید.">
          <LetterEditor key={generation} initial={emptyLetter()} save={data => createOfficeLetter(token, data)} onSaved={row => setSelected(row.id)} />
        </SectionCard>
        : <p role="alert">اجازهٔ ساخت نامه ندارید؛ از مدیر کسب‌وکار بخواهید دسترسی ایجاد را بررسی کند.</p>
      : <LetterList key={generation} token={token} mode={mode} onOpen={setSelected} />}
  </OpsPage>
}

function LetterList({ token, mode, onOpen }: { token: string; mode: 'inbox' | 'registry'; onOpen: (id: string) => void }) {
  const initial: OfficeFilters = { box: mode === 'inbox' ? 'inbox' : 'all', q: '', kind: '', date_from: '', date_to: '', unread: false, overdue: false }
  const [filters, setFilters] = useState(initial)
  const [applied, setApplied] = useState(initial)
  const [cursor, setCursor] = useState('')
  const list = useAsync(() => fetchOfficeLetters(token, applied, cursor), [token, applied, cursor])
  const rows = list.data?.items ?? []
  return <SectionCard icon={ClipboardList} title={mode === 'inbox' ? 'پیگیری مکاتبات من' : 'دفتر مکاتبات'} description="فقط نامه‌های مجاز نمایش داده می‌شوند. دسترسی دبیرخانه اجازهٔ مشاهدهٔ همهٔ مکاتبات همین کسب‌وکار را می‌دهد.">
    <form className="office-grid office-filters" onSubmit={e => { e.preventDefault(); setCursor(''); setApplied({ ...filters }) }}>
      <label>پوشه<SearchSelect value={filters.box} onChange={e => setFilters({ ...filters, box: e.target.value as OfficeFilters['box'] })}>
        {(mode === 'inbox' ? ['inbox', 'sent'] as const : ['all', 'drafts', 'archive'] as const).map(key => <option key={key} value={key}>{BOXES[key]}</option>)}
      </SearchSelect></label>
      <label>نوع نامه<SearchSelect value={filters.kind} onChange={e => setFilters({ ...filters, kind: e.target.value as OfficeFilters['kind'] })}><option value="">همهٔ انواع</option>{Object.entries(KINDS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</SearchSelect></label>
      <label className="office-wide">جست‌وجوی موضوع، شماره یا طرف مکاتبه<input maxLength={300} value={filters.q} onChange={e => setFilters({ ...filters, q: e.target.value })} /></label>
      <div><label htmlFor="office-from">از تاریخ نامه</label><JalaliDatePicker id="office-from" value={filters.date_from ?? ''} onChange={date_from => setFilters({ ...filters, date_from })} clearLabel="بدون محدودیت" /></div>
      <div><label htmlFor="office-to">تا تاریخ نامه</label><JalaliDatePicker id="office-to" value={filters.date_to ?? ''} onChange={date_to => setFilters({ ...filters, date_to })} clearLabel="بدون محدودیت" /></div>
      <div className="office-toolbar office-wide">
        <label className="office-check"><input type="checkbox" checked={filters.unread} onChange={e => setFilters({ ...filters, unread: e.target.checked })} />خوانده‌نشده‌های من</label>
        <label className="office-check"><input type="checkbox" checked={filters.overdue} onChange={e => setFilters({ ...filters, overdue: e.target.checked })} />ارجاع‌های معوق من</label>
        <button type="submit" className="btn-primary" disabled={list.loading}>اعمال فیلتر</button>
        <button type="button" onClick={list.reload} disabled={list.loading}>تازه‌سازی</button>
      </div>
    </form>
    <AsyncBlock loading={list.loading} error={list.error} empty={false}>
      {!rows.length ? <EmptyState icon={Archive} text="نامه‌ای با این شرایط پیدا نشد؛ فیلترها را تغییر دهید یا از «نامه جدید» مکاتبه را شروع کنید." /> : <div className="table-scroll">
        <table className="cards-on-mobile office-table"><thead><tr><th>موضوع</th><th>شماره / نوع</th><th>تاریخ</th><th>فرستنده ← گیرنده</th><th>مهلت</th><th>وضعیت</th><th>مشاهده</th></tr></thead>
          <tbody>{rows.map(row => <tr key={row.id}>
            <td className="card-title">{row.unread && <span className="office-unread">خوانده‌نشده · </span>}{row.subject}</td>
            <td data-label="شماره / نوع">{row.number === null ? 'بدون شماره' : toFaDigits(row.number)} · {KINDS[row.kind]}</td>
            <td data-label="تاریخ">{formatJalali(row.letter_date)}</td>
            <td data-label="طرف مکاتبه">{row.sender || '—'} ← {row.addressee || '—'}</td>
            <td data-label="مهلت نامه">{formatJalali(row.due_date)}</td>
            <td data-label="وضعیت">{STATUSES[row.status]}{row.priority === 'urgent' && ' · فوری'}</td>
            <td className="card-actions"><button type="button" onClick={() => onOpen(row.id)} aria-label={`باز کردن ${row.subject}`}>باز کردن</button></td>
          </tr>)}</tbody></table>
      </div>}
      <div className="office-toolbar"><span>{rows.length.toLocaleString('fa-IR')} نامه در این صفحه</span><button type="button" disabled={!cursor} onClick={() => setCursor('')}>صفحهٔ نخست</button><button type="button" disabled={!list.data?.next_cursor} onClick={() => setCursor(list.data?.next_cursor ?? '')}>صفحهٔ بعد</button></div>
    </AsyncBlock>
  </SectionCard>
}

function LetterEditor({ initial, save, onSaved, onCancel }: { initial: OfficeLetterInput; save: (data: OfficeLetterInput) => Promise<OfficeLetter>; onSaved: (row: OfficeLetter) => void; onCancel?: () => void }) {
  const [data, setData] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Message>(null)
  const lock = useRef(false)
  const change = <K extends keyof OfficeLetterInput>(key: K, value: OfficeLetterInput[K]) => setData(old => ({ ...old, [key]: value }))
  return <form onSubmit={async e => {
    e.preventDefault()
    if (lock.current) return
    if (!data.subject.trim() || !data.letter_date) { setMsg({ kind: 'err', text: 'موضوع و تاریخ نامه را تکمیل کنید.' }); return }
    lock.current = true; setBusy(true); setMsg(null)
    try { onSaved(await save(data)) } catch (err) { setMsg({ kind: 'err', text: errorText(err) }) }
    finally { lock.current = false; setBusy(false) }
  }}>
    <fieldset disabled={busy} className="office-grid">
      <label>نوع نامه<SearchSelect value={data.kind} onChange={e => change('kind', e.target.value as OfficeLetterInput['kind'])}>{Object.entries(KINDS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</SearchSelect></label>
      <label>اولویت<SearchSelect value={data.priority} onChange={e => change('priority', e.target.value as OfficeLetterInput['priority'])}><option value="normal">عادی</option><option value="urgent">فوری</option></SearchSelect></label>
      <label className="office-wide">موضوع<input required maxLength={300} value={data.subject} onChange={e => change('subject', e.target.value)} /></label>
      <label>فرستنده<input maxLength={200} value={data.sender} onChange={e => change('sender', e.target.value)} /></label>
      <label>گیرندهٔ نامه<input maxLength={200} value={data.addressee} onChange={e => change('addressee', e.target.value)} /></label>
      <div><label htmlFor="office-date">تاریخ نامه (الزامی)</label><JalaliDatePicker id="office-date" value={data.letter_date} onChange={v => change('letter_date', v)} /></div>
      <div><label htmlFor="office-due">مهلت پیگیری</label><JalaliDatePicker id="office-due" value={data.due_date ?? ''} onChange={v => change('due_date', v || null)} clearLabel="بدون مهلت" /></div>
      <label>شمارهٔ نامهٔ مرجع<input maxLength={100} value={data.external_number} onChange={e => change('external_number', e.target.value)} /></label>
      <div><label htmlFor="office-external-date">تاریخ نامهٔ مرجع</label><JalaliDatePicker id="office-external-date" value={data.external_date ?? ''} onChange={v => change('external_date', v || null)} clearLabel="بدون تاریخ" /></div>
      <label className="office-wide">متن نامه<textarea rows={9} maxLength={50000} value={data.body} onChange={e => change('body', e.target.value)} /></label>
      <div className="office-toolbar office-wide"><button type="submit" className="btn-primary">{busy ? 'در حال ذخیره…' : 'ذخیره پیش‌نویس'}</button>{onCancel && <button type="button" onClick={onCancel}>انصراف از ویرایش</button>}</div>
    </fieldset><Note msg={msg} />
  </form>
}

function LetterDetail({ id, token, me, onBack }: { id: string; token: string; me: MeResponse; onBack: () => void }) {
  const [row, setRow] = useState<OfficeLetter | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)
  const [msg, setMsg] = useState<Message>(null)
  const [retry, setRetry] = useState(0)
  const lock = useRef(false)
  useEffect(() => {
    let active = true
    setLoading(true); setMsg(null); setRow(null)
    // بازکردنِ نامه رسیدِ خواندن می‌سازد؛ چاپ و دانلود چنین اثر جانبی ندارند.
    officeLetterAction(token, id, 'read').then(r => { if (active) setRow(r) })
      .catch(err => { if (active) setMsg({ kind: 'err', text: errorText(err) }) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id, token, retry])
  async function run(action: () => Promise<OfficeLetter | void>, success: string): Promise<boolean> {
    if (lock.current) return false
    lock.current = true; setBusy(true); setMsg(null)
    try { const result = await action(); if (result) setRow(result); setMsg({ kind: 'ok', text: success }); return true }
    catch (err) { setMsg({ kind: 'err', text: errorText(err) }); return false }
    finally { lock.current = false; setBusy(false) }
  }
  const writable = can(me, 'automation', 'update')
  const editable = row?.status === 'draft' && row.can_edit
  return <>
    <section><div className="office-toolbar"><button type="button" disabled={busy} onClick={onBack}>بازگشت</button><button type="button" disabled={busy || loading} onClick={() => { setEditing(false); setRetry(v => v + 1) }}>بازخوانی نامه</button></div><Note msg={msg} />{loading && <p className="muted">در حال بارگذاری نامه…</p>}</section>
    {!loading && row && <>
      <SectionCard icon={FileText} title={row.subject} description={`${KINDS[row.kind]} · ${STATUSES[row.status]} · ${row.number === null ? 'هنوز شماره ندارد' : `شمارهٔ ${toFaDigits(row.number)}`}`}>
        {editing && editable ? <LetterEditor key={row.version} initial={letterInput(row)} save={data => updateOfficeLetter(token, row.id, data, row.version)} onSaved={r => { setRow(r); setEditing(false); setMsg({ kind: 'ok', text: 'پیش‌نویس ذخیره شد.' }) }} onCancel={() => setEditing(false)} /> : <>
          <dl className="office-metadata">
            <div><dt>از</dt><dd>{row.sender || '—'}</dd></div><div><dt>به</dt><dd>{row.addressee || '—'}</dd></div>
            <div><dt>تاریخ نامه</dt><dd>{formatJalali(row.letter_date)}</dd></div><div><dt>مهلت پیگیری</dt><dd>{formatJalali(row.due_date)}</dd></div>
            <div><dt>مرجع</dt><dd>{row.external_number ? toFaDigits(row.external_number) : '—'} · {formatJalali(row.external_date)}</dd></div>
            <div><dt>تنظیم‌کننده / اولویت</dt><dd>{row.creator_name} · {row.priority === 'urgent' ? 'فوری' : 'عادی'}</dd></div>
          </dl><div className="office-body">{row.body || 'متن نامه وارد نشده است.'}</div>
          <div className="office-toolbar">
            <button type="button" disabled={busy} onClick={() => void run(() => printOfficeLetter(token, id), 'نسخهٔ چاپی باز شد.')}>چاپ نامه</button>
            {editable && <><button type="button" disabled={busy} onClick={() => setEditing(true)}>ویرایش پیش‌نویس</button><button type="button" className="btn-primary" disabled={busy} onClick={() => { if (window.confirm('پس از ثبت نهایی، متن و پیوست‌ها قابل تغییر نیستند و شمارهٔ قطعی اختصاص می‌یابد. نامه ثبت شود؟')) void run(() => officeLetterAction(token, id, 'register', row.version), 'نامه با شمارهٔ قطعی ثبت شد.') }}>ثبت نهایی و شماره‌گذاری</button></>}
            {row.status === 'registered' && row.can_edit && <button type="button" disabled={busy || row.referrals.some(r => !r.completed_at)} title="همهٔ ارجاع‌ها باید تکمیل شده باشند" onClick={() => { if (window.confirm('نامه بایگانی شود؟ پس از آن ارجاع تازه ممکن نیست.')) void run(() => officeLetterAction(token, id, 'archive', row.version), 'نامه بایگانی شد.') }}>بایگانی نامه</button>}
          </div>
        </>}
      </SectionCard>
      {!editing && <>
        <SectionCard icon={Paperclip} title="پیوست‌ها" description="فایل PDF، PNG یا JPEG؛ هر فایل حداکثر ۵ مگابایت، مجموع ۲۰ مگابایت و حداکثر ۱۰ فایل. فقط پیش از ثبت نهایی قابل تغییر است.">
          {row.attachments.length ? <ul className="office-files">{row.attachments.map(file => <li key={file.id}><span dir="auto">{file.filename}</span><small>{Math.ceil(file.size / 1024).toLocaleString('fa-IR')} کیلوبایت</small><button type="button" disabled={busy} onClick={() => void run(() => downloadOfficeFile(token, file), 'پیوست دریافت شد.')}>دریافت</button>{editable && <button type="button" disabled={busy} onClick={() => { if (window.confirm(`پیوست «${file.filename}» از پیش‌نویس حذف شود؟`)) void run(() => removeOfficeFile(token, file.id), 'پیوست حذف شد.') }}>حذف پیوست</button>}</li>)}</ul> : <p className="muted">این نامه پیوست ندارد.</p>}
          {editable && <label className="office-upload">افزودن پیوست<input type="file" accept=".pdf,.png,.jpg,.jpeg" disabled={busy} onChange={e => {
            const file = e.currentTarget.files?.[0]; e.currentTarget.value = ''
            if (!file) return
            if (file.size > 5 * 1024 * 1024) { setMsg({ kind: 'err', text: 'اندازهٔ فایل بیشتر از ۵ مگابایت است؛ فایل کوچک‌تری انتخاب کنید.' }); return }
            void run(() => uploadOfficeFile(token, id, file), 'پیوست ذخیره شد.')
          }} /></label>}
        </SectionCard>
        <SectionCard icon={Send} title="ارجاع‌ها و پاسخ‌ها" description="رسید خواندن و پاسخ هر گیرنده جداگانه نگهداری می‌شود.">
          {!row.referrals.length && <p className="muted">نامه هنوز به همکاران ارجاع نشده است.</p>}
          <div className="office-referrals">{row.referrals.map(ref => <article key={ref.id}>
            <h3>{ref.from_name} ← {ref.to_name}</h3><p className="office-body">{ref.instruction}</p>
            <p>مهلت: {formatJalali(ref.due_date ?? row.due_date)} · {ref.completed_at ? `تکمیل‌شده در ${formatJalali(ref.completed_at)}` : ref.read_at ? `خوانده‌شده در ${formatJalali(ref.read_at)}` : 'هنوز خوانده نشده'}</p>
            {ref.response && <p className="office-body"><strong>پاسخ: </strong>{ref.response}</p>}
            {writable && row.status === 'registered' && ref.can_complete && <ResponseForm busy={busy} onComplete={response => run(() => completeOfficeReferral(token, ref.id, response), 'پاسخ ثبت و ارجاع تکمیل شد.')} />}
          </article>)}</div>
          {writable && row.status === 'registered' && <ReferralForm token={token} busy={busy} onRefer={(ids, instruction, due) => run(() => referOfficeLetter(token, id, ids, instruction, due), 'نامه به همکاران انتخاب‌شده ارجاع شد.')} />}
          {row.status === 'draft' && <p className="muted">برای ارجاع، ابتدا نامه را ثبت نهایی کنید.</p>}
        </SectionCard>
        <SectionCard icon={History} title="سابقهٔ مکاتبه" description="سابقهٔ عملیات قابل ویرایش یا حذف نیست."><ol className="office-history">{row.events.map(event => <li key={event.id}><span>{toFaDigits(event.description)}</span><small>{event.actor_name} · {formatJalali(event.created_at)}</small></li>)}</ol></SectionCard>
      </>}
    </>}
  </>
}

function ReferralForm({ token, busy, onRefer }: { token: string; busy: boolean; onRefer: (ids: string[], instruction: string, due: string | null) => Promise<boolean> }) {
  const recipients = useAsync(() => fetchOfficeRecipients(token), [token])
  const [ids, setIds] = useState<string[]>([])
  const [instruction, setInstruction] = useState('')
  const [due, setDue] = useState('')
  const [search, setSearch] = useState('')
  return <form className="office-refer-form" onSubmit={async e => { e.preventDefault(); if (await onRefer(ids, instruction, due || null)) { setIds([]); setInstruction(''); setDue('') } }}>
    <h3>ارجاع تازه</h3><AsyncBlock loading={recipients.loading} error={recipients.error} empty={false}>
      <fieldset disabled={busy} className="office-grid">
        <label className="office-wide">جست‌وجوی همکار<input value={search} onChange={e => setSearch(e.target.value)} /></label>
        <div className="office-recipients office-wide" role="group" aria-label="گیرندگان ارجاع">{(recipients.data ?? []).filter(r => r.name.includes(search)).map(r => <label key={r.id} className="office-check"><input type="checkbox" checked={ids.includes(r.id)} disabled={!ids.includes(r.id) && ids.length >= 20} onChange={e => setIds(old => e.target.checked ? [...old, r.id] : old.filter(id => id !== r.id))} />{r.name}</label>)}{!recipients.data?.length && <p>همکار مجاز دیگری پیدا نشد؛ عضویت و دسترسی اتوماسیون را در مدیریت کاربران بررسی کنید.</p>}</div>
        <label className="office-wide">دستور ارجاع<textarea required maxLength={4000} rows={3} value={instruction} onChange={e => setInstruction(e.target.value)} /></label>
        <div><label htmlFor="office-ref-due">مهلت این ارجاع (اختیاری)</label><JalaliDatePicker id="office-ref-due" value={due} onChange={setDue} clearLabel="مهلت نامه" /></div>
        <div className="office-toolbar"><button type="submit" disabled={!ids.length || !instruction.trim()} className="btn-primary">ارجاع به {ids.length.toLocaleString('fa-IR')} همکار</button></div>
      </fieldset>
    </AsyncBlock>{recipients.error && <button type="button" onClick={recipients.reload}>تلاش دوباره برای دریافت همکاران</button>}
  </form>
}

function ResponseForm({ busy, onComplete }: { busy: boolean; onComplete: (response: string) => Promise<boolean> }) {
  const [response, setResponse] = useState('')
  return <form onSubmit={async e => { e.preventDefault(); if (window.confirm('پاسخ نهایی ثبت شود؟ پس از ثبت قابل تغییر نیست.') && await onComplete(response)) setResponse('') }}>
    <label>پاسخ / گزارش اقدام<textarea required rows={3} maxLength={10000} disabled={busy} value={response} onChange={e => setResponse(e.target.value)} /></label>
    <button type="submit" disabled={busy || !response.trim()}>ثبت پاسخ و تکمیل ارجاع</button>
  </form>
}
