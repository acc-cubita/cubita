import { useEffect, useMemo, useState } from 'react'
import { Plus, Save, Trash2, X } from 'lucide-react'
import {
  fetchAccountsLive, fetchAnalytics, fetchCostCenters, updateJournalEntry,
  type JournalEditLineInput, type JournalEntryRecord,
} from '../api'
import { formatJalali, toFaDigits } from '../lib/jalali'
import { entryErrorText } from '../lib/entryPresentation'
import { JalaliDatePicker } from './JalaliDatePicker'
import { NumberInput } from './NumberInput'
import { SearchSelect } from './SearchSelect'

type Row = JournalEditLineInput & { key: string }
type Accounts = Awaited<ReturnType<typeof fetchAccountsLive>>
type Analytics = Awaited<ReturnType<typeof fetchAnalytics>>
type Centers = Awaited<ReturnType<typeof fetchCostCenters>>

const newRow = (): Row => ({ key: crypto.randomUUID(), account_id: '', debit: '', credit: '', description: '' })

export function JournalEntryEditForm({ token, entry, onSaved, onCancel }: {
  token: string
  entry: JournalEntryRecord
  onSaved: (updated: JournalEntryRecord) => void
  onCancel: () => void
}) {
  const [accounts, setAccounts] = useState<Accounts | null>(null)
  const [analytics, setAnalytics] = useState<Analytics>([])
  const [centers, setCenters] = useState<Centers>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [date, setDate] = useState(entry.entry_date)
  const [description, setDescription] = useState(entry.description)
  const [subNumber, setSubNumber] = useState(entry.sub_number ?? '')
  const [reason, setReason] = useState('')
  const [rows, setRows] = useState<Row[]>(entry.lines.map((line) => ({
    ...line, key: line.id, debit: line.debit, credit: line.credit, description: line.description,
  })))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    Promise.all([fetchAccountsLive(token), fetchAnalytics(token), fetchCostCenters(token)])
      .then(([a, b, c]) => { if (alive) { setAccounts(a); setAnalytics(b); setCenters(c) } })
      .catch((err) => { if (alive) setLoadError(entryErrorText(err)) })
    return () => { alive = false }
  }, [token])

  const accountOptions = useMemo(() => (accounts ?? []).filter((a) => !a.is_group), [accounts])
  const update = (key: string, patch: Partial<Row>) => setRows((old) => old.map((row) => row.key === key ? { ...row, ...patch } : row))
  const debit = rows.reduce((sum, row) => sum + BigInt(row.debit || '0'), 0n)
  const credit = rows.reduce((sum, row) => sum + BigInt(row.credit || '0'), 0n)
  const valid = rows.length >= 2 && rows.every((row) => row.account_id && (BigInt(row.debit || '0') > 0n || BigInt(row.credit || '0') > 0n)) && debit === credit && debit > 0n

  async function save() {
    if (saving) return
    setError(null)
    if (!entry.updated_at) { setError('نسخهٔ سند قدیمی است؛ کشو را ببندید و دوباره باز کنید.'); return }
    if (!valid) { setError('دست‌کم دو ردیفِ دارای حساب و مبلغ لازم است و جمع بدهکار و بستانکار باید برابر باشد.'); return }
    if (reason.trim().length < 3) { setError('دلیل اصلاح را دست‌کم در سه نویسه بنویسید.'); return }
    setSaving(true)
    try {
      const updated = await updateJournalEntry(token, entry.id, {
        expected_updated_at: entry.updated_at,
        reason: reason.trim(), entry_date: date, description, sub_number: subNumber.trim() || null,
        status: entry.status,
        lines: rows.map((row) => ({
          id: row.id || undefined, account_id: row.account_id,
          debit: row.debit, credit: row.credit, description: row.description,
          cost_center_id: row.cost_center_id || null, analytic_id: row.analytic_id || null,
          currency_code: row.currency_code || null,
          fx_amount: row.currency_code ? row.fx_amount || null : null,
          fx_rate: row.currency_code ? row.fx_rate || null : null,
          tracking_no: row.tracking_no || null, tracking_date: row.tracking_date || null,
        })),
      })
      onSaved(updated)
    } catch (err) { setError(entryErrorText(err)) }
    finally { setSaving(false) }
  }

  return <section className="entry-edit" aria-label="ویرایش سند ثبت‌شده">
    <header className="entry-edit-heading">
      <div><h3>اصلاح سند {toFaDigits(entry.number ?? '—')}</h3>
        <p>شماره، عطف، منشأ و وضعیت ثابت می‌مانند. اصلاح فقط در دورهٔ مالی باز ذخیره می‌شود.</p></div>
      <button type="button" className="ef-btn-secondary" onClick={onCancel} disabled={saving}><X size={15} /> انصراف</button>
    </header>
    {loadError && <div className="entry-edit-error" role="alert">فهرست حساب‌ها دریافت نشد: {loadError} · اتصال را بررسی کنید و سند را دوباره باز کنید.</div>}
    {!accounts && !loadError && <p role="status">در حال دریافت چارت و ابعاد سند…</p>}
    {accounts && <>
      <div className="entry-edit-fields">
        <label>تاریخ سند <JalaliDatePicker value={date} onChange={setDate} /></label>
        <label>شمارهٔ فرعی <input value={subNumber} maxLength={30} onChange={(e) => setSubNumber(e.target.value)} placeholder="اختیاری" /></label>
        <label className="entry-edit-wide">شرح سند <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="شرح کلی سند" /></label>
      </div>
      <div className="entry-edit-lines-heading"><h4>ردیف‌های سند</h4><span>مبالغ به ریال</span></div>
      <div className="entry-edit-lines">
        {rows.map((row, index) => <div className="entry-edit-line" key={row.key}>
          <div className="entry-edit-line-main">
            <span className="entry-edit-line-number">{toFaDigits(index + 1)}</span>
            <label>حساب <SearchSelect value={row.account_id} onChange={(e) => update(row.key, { account_id: e.target.value })} forceSearch>
              <option value="">انتخاب حساب</option>
              {accountOptions.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
            </SearchSelect></label>
            <label>بدهکار <NumberInput value={row.debit} onChange={(v) => update(row.key, { debit: v, credit: v && v !== '0' ? '0' : row.credit })} aria-label={`بدهکار ردیف ${index + 1}`} /></label>
            <label>بستانکار <NumberInput value={row.credit} onChange={(v) => update(row.key, { credit: v, debit: v && v !== '0' ? '0' : row.debit })} aria-label={`بستانکار ردیف ${index + 1}`} /></label>
            <button type="button" className="entry-edit-remove" aria-label={`حذف ردیف ${index + 1}`} onClick={() => setRows((old) => old.filter((item) => item.key !== row.key))} disabled={rows.length <= 2}><Trash2 size={16} /></button>
          </div>
          <label className="entry-edit-line-desc">شرح ردیف <input value={row.description} onChange={(e) => update(row.key, { description: e.target.value })} placeholder="اختیاری" /></label>
          <details><summary>تفصیلی، مرکز هزینه، ارز و پیگیری</summary>
            <div className="entry-edit-extra">
              <label>تفصیلی <SearchSelect value={row.analytic_id ?? ''} onChange={(e) => update(row.key, { analytic_id: e.target.value || null })}>
                <option value="">بدون تفصیلی</option>{analytics.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
              </SearchSelect></label>
              <label>مرکز هزینه <SearchSelect value={row.cost_center_id ?? ''} onChange={(e) => update(row.key, { cost_center_id: e.target.value || null })}>
                <option value="">بدون مرکز</option>{centers.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
              </SearchSelect></label>
              <label>کد ارز <input value={row.currency_code ?? ''} maxLength={3} onChange={(e) => update(row.key, { currency_code: e.target.value.toUpperCase() })} placeholder="مثلاً USD" /></label>
              <label>مبلغ ارزی <NumberInput allowDecimal value={row.fx_amount ?? ''} onChange={(v) => update(row.key, { fx_amount: v })} /></label>
              <label>نرخ ارز <NumberInput allowDecimal value={row.fx_rate ?? ''} onChange={(v) => update(row.key, { fx_rate: v })} /></label>
              <label>شماره پیگیری <input value={row.tracking_no ?? ''} maxLength={50} onChange={(e) => update(row.key, { tracking_no: e.target.value })} /></label>
              <label>تاریخ پیگیری <JalaliDatePicker value={row.tracking_date ?? ''} onChange={(v) => update(row.key, { tracking_date: v || null })} clearLabel="پاک‌کردن تاریخ" /></label>
            </div>
          </details>
        </div>)}
      </div>
      <button type="button" className="ef-btn-secondary" onClick={() => setRows((old) => [...old, newRow()])}><Plus size={15} /> افزودن ردیف</button>
      <div className={`entry-edit-balance${valid ? ' is-balanced' : ''}`}>
        <span>جمع بدهکار: {toFaDigits(debit.toLocaleString('en-US'))}</span>
        <span>جمع بستانکار: {toFaDigits(credit.toLocaleString('en-US'))}</span>
        <strong>{valid ? 'سند تراز است' : 'سند ناتراز یا ناقص است'}</strong>
      </div>
      <label className="entry-edit-reason">دلیل اصلاح <span>این توضیح همراه با نام شما و تغییرات قبل/بعد در تاریخچه می‌ماند.</span>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} rows={3} placeholder="مثلاً اصلاح مبلغ و حسابِ ردیف دوم پس از بررسی" required /></label>
      {error && <div className="entry-edit-error" role="alert">{error}</div>}
      <div className="entry-edit-actions"><button type="button" className="btn" disabled={saving || !valid || reason.trim().length < 3} onClick={() => void save()}><Save size={16} /> {saving ? 'در حال ثبت اصلاح…' : 'ثبت اصلاح و تاریخچه'}</button>
        <small>تاریخ فعلی: {formatJalali(entry.entry_date)}</small></div>
    </>}
  </section>
}
