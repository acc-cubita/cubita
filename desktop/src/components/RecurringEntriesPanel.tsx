import { useEffect, useMemo, useState } from 'react'
import { Repeat, Plus, Trash2, Save, Play, X, Pencil, PauseCircle, PlayCircle } from 'lucide-react'
import type { AccountCache } from '../electron.d'
import {
  createRecurringEntry,
  deleteRecurringEntry,
  fetchCostCenters,
  fetchRecurringEntries,
  runRecurringDue,
  runRecurringOne,
  setRecurringActive,
  updateRecurringEntry,
  type CostCenterRecord,
  type RecurringEntry,
  type RecurringFrequency,
} from '../api'
import { SectionCard } from './SectionCard'
import { Pager, usePagination } from './Pager'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso, toFaDigits } from '../lib/jalali'

interface DraftLine {
  accountId: string
  debit: string
  credit: string
}

const emptyLine = (): DraftLine => ({ accountId: '', debit: '', credit: '' })

const FREQ_LABEL: Record<RecurringFrequency, string> = { weekly: 'هفتگی', monthly: 'ماهانه', yearly: 'سالانه' }
const FREQ_UNIT: Record<RecurringFrequency, string> = { weekly: 'هفته', monthly: 'ماه', yearly: 'سال' }

function freqText(f: RecurringFrequency, interval: number) {
  return interval > 1 ? `هر ${toFaDigits(interval)} ${FREQ_UNIT[f]}` : FREQ_LABEL[f]
}

const fa = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')

export function RecurringEntriesPanel({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const [entries, setEntries] = useState<RecurringEntry[]>([])
  const entriesPg = usePagination(entries, 10)
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [frequency, setFrequency] = useState<RecurringFrequency>('monthly')
  const [interval, setIntervalValue] = useState('1')
  const [startDate, setStartDate] = useState(todayIso())
  const [hasEnd, setHasEnd] = useState(false)
  const [endDate, setEndDate] = useState(todayIso())
  const [costCenterId, setCostCenterId] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([emptyLine(), emptyLine()])

  const postableAccounts = useMemo(() => accounts.filter((a) => !a.is_group), [accounts])
  const dueCount = entries.filter((e) => e.is_due).length

  async function refresh() {
    try {
      setEntries(await fetchRecurringEntries(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
    fetchCostCenters(token)
      .then((rows) => setCostCenters(rows.filter((c) => c.is_active)))
      .catch(() => setCostCenters([]))
  }, [])

  function resetForm() {
    setEditingId(null)
    setTitle('')
    setDescription('')
    setFrequency('monthly')
    setIntervalValue('1')
    setStartDate(todayIso())
    setHasEnd(false)
    setEndDate(todayIso())
    setCostCenterId('')
    setLines([emptyLine(), emptyLine()])
  }

  function startEdit(e: RecurringEntry) {
    setEditingId(e.id)
    setTitle(e.title)
    setDescription(e.description)
    setFrequency(e.frequency)
    setIntervalValue(String(e.interval))
    setStartDate(e.start_date)
    setHasEnd(e.end_date != null)
    setEndDate(e.end_date ?? todayIso())
    setCostCenterId(e.cost_center_id ?? '')
    setLines(
      e.lines.map((l) => ({
        accountId: l.account_id,
        debit: Number(l.debit) ? String(Number(l.debit)) : '',
        credit: Number(l.credit) ? String(Number(l.credit)) : '',
      })),
    )
    setMessage(null)
  }

  function updateLine(i: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  }

  const totalDebit = lines.reduce((s, l) => s + (Number(l.debit) || 0), 0)
  const totalCredit = lines.reduce((s, l) => s + (Number(l.credit) || 0), 0)
  const isBalanced = totalDebit === totalCredit && totalDebit > 0

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    setError(null)
    if (!title.trim()) {
      setMessage('عنوان الزامی است.')
      return
    }
    const validLines = lines.filter((l) => l.accountId && ((Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0))
    if (validLines.length < 2 || !isBalanced) {
      setMessage('سند باید حداقل دو ردیف معتبر و متوازن داشته باشد.')
      return
    }
    const payload = {
      title: title.trim(),
      description,
      frequency,
      interval: Math.max(1, Number(interval) || 1),
      start_date: startDate,
      end_date: hasEnd ? endDate : null,
      cost_center_id: costCenterId || null,
      lines: validLines.map((l) => ({
        account_id: l.accountId,
        debit: Number(l.debit) || 0,
        credit: Number(l.credit) || 0,
      })),
    }
    try {
      if (editingId) {
        await updateRecurringEntry(token, editingId, payload)
        setMessage('قالب ویرایش شد.')
      } else {
        await createRecurringEntry(token, payload)
        setMessage('قالب تکرارشونده ثبت شد.')
      }
      resetForm()
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleRunDue() {
    setError(null)
    setMessage(null)
    try {
      const r = await runRecurringDue(token)
      setMessage(
        r.generated === 0
          ? 'سررسیدی برای تولید نبود.'
          : `${toFaDigits(r.generated)} سند تولید شد${r.skipped ? ` (${toFaDigits(r.skipped)} سررسید در دوره‌ی بسته رد شد)` : ''}.`,
      )
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleRunOne(id: string) {
    setError(null)
    try {
      const r = await runRecurringOne(token, id)
      setMessage(r.generated === 0 ? 'سررسیدی برای این قالب نبود.' : `${toFaDigits(r.generated)} سند تولید شد.`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function toggleActive(e: RecurringEntry) {
    try {
      await setRecurringActive(token, e.id, !e.is_active)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteRecurringEntry(token, id)
      if (editingId === id) resetForm()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="split-2col">
      <SectionCard
        icon={editingId ? Pencil : Plus}
        title={editingId ? 'ویرایش قالب تکرارشونده' : 'قالب تکرارشونده جدید'}
        description="یک سند دوره‌ای (اجاره، بیمه، اقساط…) که خودکار در سررسیدهایش ساخته می‌شود."
        actions={
          editingId ? (
            <button type="button" onClick={resetForm}>
              <X size={13} /> انصراف
            </button>
          ) : undefined
        }
      >
        {postableAccounts.length === 0 ? (
          <p className="hint">قبل از ساخت قالب، چارت حساب باید در دسترس باشد (یک‌بار هم‌گام‌سازی کنید).</p>
        ) : (
          <form className="invoice-form" onSubmit={handleSubmit}>
            <label>
              عنوان
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="مثلاً اجاره‌ی دفتر" />
            </label>
            <label>
              شرح سند (اختیاری)
              <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <div className="field-row">
              <label>
                تناوب
                <select value={frequency} onChange={(e) => setFrequency(e.target.value as RecurringFrequency)}>
                  <option value="weekly">هفتگی</option>
                  <option value="monthly">ماهانه</option>
                  <option value="yearly">سالانه</option>
                </select>
              </label>
              <label>
                هر چند دوره یک‌بار
                <NumberInput value={interval} onChange={setIntervalValue} />
              </label>
            </div>
            <div className="field-row">
              <label>
                تاریخ شروع
                <JalaliDatePicker value={startDate} onChange={setStartDate} />
              </label>
              <label>
                <span className="inline-check">
                  <input type="checkbox" checked={hasEnd} onChange={(e) => setHasEnd(e.target.checked)} /> تاریخ پایان
                </span>
                {hasEnd && <JalaliDatePicker value={endDate} onChange={setEndDate} />}
              </label>
            </div>
            {costCenters.length > 0 && (
              <label>
                مرکز هزینه/پروژه (اختیاری)
                <select value={costCenterId} onChange={(e) => setCostCenterId(e.target.value)}>
                  <option value="">— بدون مرکز —</option>
                  {costCenters.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code ? `${c.code} — ${c.name}` : c.name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <div className="table-scroll">
            <table className="invoice-lines">
              <thead>
                <tr>
                  <th>حساب</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, i) => (
                  <tr key={i}>
                    <td>
                      <select value={line.accountId} onChange={(e) => updateLine(i, { accountId: e.target.value })}>
                        <option value="">— انتخاب حساب —</option>
                        {postableAccounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.code} — {a.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <NumberInput
                        value={line.debit}
                        onChange={(v) => updateLine(i, { debit: v, credit: '' })}
                      />
                    </td>
                    <td>
                      <NumberInput
                        value={line.credit}
                        onChange={(v) => updateLine(i, { credit: v, debit: '' })}
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="icon-btn-danger"
                        onClick={() => setLines((prev) => (prev.length > 2 ? prev.filter((_, idx) => idx !== i) : prev))}
                        disabled={lines.length === 2}
                        aria-label="حذف ردیف"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>

            <div className="invoice-form-footer">
              <button type="button" onClick={() => setLines((prev) => [...prev, emptyLine()])}>
                <Plus size={14} /> افزودن ردیف
              </button>
              <span className={isBalanced ? 'invoice-total' : 'invoice-total error'}>
                بدهکار: {fa(totalDebit)} / بستانکار: {fa(totalCredit)}
              </span>
              <button type="submit" className="btn-primary">
                <Save size={14} /> {editingId ? 'ذخیره تغییرات' : 'ثبت قالب'}
              </button>
            </div>
            {message && <div className="hint">{message}</div>}
          </form>
        )}
      </SectionCard>

      <SectionCard
        icon={Repeat}
        title="قالب‌های تکرارشونده"
        description={dueCount > 0 ? `${toFaDigits(dueCount)} قالب سررسید شده` : 'سررسیدها را با یک دکمه بسازید.'}
        actions={
          <button type="button" className={dueCount > 0 ? 'btn-primary' : undefined} onClick={() => void handleRunDue()}>
            <Play size={13} /> تولید سررسیدها
          </button>
        }
      >
        {error && <div className="error">{error}</div>}
        {entries.length === 0 ? (
          <EmptyState icon={Repeat} text="هنوز قالبی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead>
                <tr>
                  <th>عنوان</th>
                  <th>تناوب</th>
                  <th>سررسید بعدی</th>
                  <th>مبلغ</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {entriesPg.pageItems.map((e) => (
                  <tr key={e.id} className={editingId === e.id ? 'row-selected' : undefined}>
                    <td>
                      <div className="entity-name">{e.title}</div>
                      {!e.is_active && <span className="entity-sub">غیرفعال</span>}
                    </td>
                    <td>{freqText(e.frequency, e.interval)}</td>
                    <td>
                      {formatJalali(e.next_run_date)}
                      {e.is_due && <span className="status-badge tone-warning due-badge">سررسید</span>}
                    </td>
                    <td className="money-cell">{fa(e.amount)}</td>
                    <td>
                      <div className="row-actions">
                        <button type="button" onClick={() => startEdit(e)} aria-label="ویرایش">
                          <Pencil size={13} />
                        </button>
                        {e.is_active && (
                          <button type="button" onClick={() => void handleRunOne(e.id)} aria-label="تولید همین حالا">
                            <Play size={13} />
                          </button>
                        )}
                        <button type="button" onClick={() => void toggleActive(e)} aria-label={e.is_active ? 'غیرفعال' : 'فعال'}>
                          {e.is_active ? <PauseCircle size={13} /> : <PlayCircle size={13} />}
                        </button>
                        <button type="button" className="icon-btn-danger" onClick={() => void handleDelete(e.id)} aria-label="حذف">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={entriesPg.page} pageCount={entriesPg.pageCount} onChange={entriesPg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}
