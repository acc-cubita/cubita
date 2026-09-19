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
import { SearchSelect } from './SearchSelect'
import {
  ActionBar,
  AddRowButton,
  CountBadge,
  FormField,
  FormGrid,
  FormStatus,
  InputAffix,
  RowAction,
  Switch,
} from './form/FormKit'
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
    <>
      {postableAccounts.length === 0 ? (
        <SectionCard icon={Plus} title="قالب تکرارشونده جدید">
          <div className="ef-empty">قبل از ساخت قالب، چارت حساب باید در دسترس باشد (یک‌بار هم‌گام‌سازی کنید).</div>
        </SectionCard>
      ) : (
        <form noValidate onSubmit={handleSubmit}>
          <SectionCard
            icon={editingId ? Pencil : Plus}
            title={editingId ? 'ویرایش قالب تکرارشونده' : 'قالب تکرارشونده جدید'}
            tip="یک سندِ دوره‌ای (اجاره، بیمه، اقساط…) که خودکار در سررسیدهایش ساخته می‌شود."
          >
            <FormGrid>
              <FormField id="rc-title" label="عنوان" required>
                {(id) => (
                  <input
                    id={id}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="مثلاً اجاره‌ی دفتر"
                  />
                )}
              </FormField>
              <FormField label="شرح سند" optional>
                {(id) => <input id={id} value={description} onChange={(e) => setDescription(e.target.value)} />}
              </FormField>
              <FormField label="تناوب" required>
                {(id) => (
                  <SearchSelect
                    id={id}
                    value={frequency}
                    onChange={(e) => setFrequency(e.target.value as RecurringFrequency)}
                  >
                    <option value="weekly">هفتگی</option>
                    <option value="monthly">ماهانه</option>
                    <option value="yearly">سالانه</option>
                  </SearchSelect>
                )}
              </FormField>
              <FormField label="هر چند دوره یک‌بار" required>
                {(id) => <NumberInput id={id} value={interval} onChange={setIntervalValue} group={false} />}
              </FormField>
              <FormField label="تاریخ شروع" required>
                {(id) => <JalaliDatePicker id={id} value={startDate} onChange={setStartDate} />}
              </FormField>
              <FormField
                label="تاریخ پایان"
                optional
                tip="اگر خاموش باشد، قالب تا وقتی غیرفعالش نکنید ادامه می‌دهد."
                message={
                  <Switch checked={hasEnd} onChange={setHasEnd} label={hasEnd ? 'تاریخ پایان دارد' : 'بدون تاریخ پایان'} />
                }
              >
                {(id) =>
                  hasEnd ? (
                    <JalaliDatePicker id={id} value={endDate} onChange={setEndDate} />
                  ) : (
                    <input id={id} value="" disabled placeholder="—" readOnly />
                  )
                }
              </FormField>
              {costCenters.length > 0 && (
                <FormField label="مرکز هزینه / پروژه" optional>
                  {(id) => (
                    <SearchSelect id={id} value={costCenterId} onChange={(e) => setCostCenterId(e.target.value)}>
                      <option value="">— بدون مرکز —</option>
                      {costCenters.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.code ? `${c.code} — ${c.name}` : c.name}
                        </option>
                      ))}
                    </SearchSelect>
                  )}
                </FormField>
              )}
            </FormGrid>

            <div className="ef-block">
              <h3 className="ef-block-title">ردیف‌های سند</h3>
              <div className="table-scroll ef-table-wrap">
                <table className="cards-on-mobile ef-table ef-table--edit">
                  <thead>
                    <tr>
                      <th className="ef-col-min">ردیف</th>
                      <th>حساب</th>
                      <th>بدهکار</th>
                      <th>بستانکار</th>
                      <th className="ef-col-min" aria-label="حذف" />
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((line, i) => (
                      <tr key={i}>
                        <td className="card-title ef-col-min" data-label="ردیف">
                          ردیف {fa(i + 1)}
                        </td>
                        <td className="card-wide ef-col-wide" data-label="حساب">
                          <SearchSelect
                            aria-label={`حسابِ ردیفِ ${fa(i + 1)}`}
                            value={line.accountId}
                            onChange={(e) => updateLine(i, { accountId: e.target.value })}
                          >
                            <option value="">— انتخاب حساب —</option>
                            {postableAccounts.map((a) => (
                              <option key={a.id} value={a.id}>
                                {a.code} — {a.name}
                              </option>
                            ))}
                          </SearchSelect>
                        </td>
                        <td className="card-wide" data-label="بدهکار">
                          <InputAffix unit="ریال">
                            <NumberInput
                              aria-label={`بدهکارِ ردیفِ ${fa(i + 1)}`}
                              value={line.debit}
                              onChange={(v) => updateLine(i, { debit: v, credit: '' })}
                            />
                          </InputAffix>
                        </td>
                        <td className="card-wide" data-label="بستانکار">
                          <InputAffix unit="ریال">
                            <NumberInput
                              aria-label={`بستانکارِ ردیفِ ${fa(i + 1)}`}
                              value={line.credit}
                              onChange={(v) => updateLine(i, { credit: v, debit: '' })}
                            />
                          </InputAffix>
                        </td>
                        <td className="card-actions ef-col-min">
                          <RowAction
                            icon={Trash2}
                            label="حذف ردیف"
                            danger
                            disabled={lines.length === 2}
                            title={lines.length === 2 ? 'سند دست‌کم دو ردیف می‌خواهد.' : undefined}
                            onClick={() =>
                              setLines((prev) => (prev.length > 2 ? prev.filter((_, idx) => idx !== i) : prev))
                            }
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <AddRowButton onClick={() => setLines((prev) => [...prev, emptyLine()])}>افزودن ردیف</AddRowButton>
            </div>
          </SectionCard>
          <ActionBar
            status={
              <FormStatus
                msg={message ? { text: message, kind: 'ok' } : null}
                idle={
                  <span className={isBalanced ? 'is-ok' : 'is-err'}>
                    بدهکار {fa(totalDebit)} · بستانکار {fa(totalCredit)}
                    {isBalanced ? ' — متوازن' : ' — نامتوازن'}
                  </span>
                }
              />
            }
          >
            {editingId && (
              <button type="button" className="ef-btn-secondary" onClick={resetForm}>
                <X size={15} /> انصراف
              </button>
            )}
            <button type="submit" className="btn-primary">
              <Save size={16} /> {editingId ? 'ذخیرهٔ تغییرات' : 'ثبت قالب'}
            </button>
          </ActionBar>
        </form>
      )}

      <SectionCard
        icon={Repeat}
        title="قالب‌های تکرارشونده"
        badge={<CountBadge accent>{toFaDigits(entries.length)} قالب</CountBadge>}
        description={dueCount > 0 ? `${toFaDigits(dueCount)} قالب سررسید شده است.` : 'سررسیدها را با یک دکمه بسازید.'}
        actions={
          <button
            type="button"
            className={dueCount > 0 ? 'btn-primary' : 'ef-btn-secondary'}
            onClick={() => void handleRunDue()}
          >
            <Play size={14} /> تولید سررسیدها
          </button>
        }
      >
        {error && <p className="ef-message ef-message--warn ef-block-note">{error}</p>}
        {entries.length === 0 ? (
          <EmptyState icon={Repeat} text="هنوز قالبی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll ef-table-wrap">
              <table className="entity-table cards-on-mobile ef-table">
                <thead>
                  <tr>
                    <th>عنوان</th>
                    <th>تناوب</th>
                    <th>سررسید بعدی</th>
                    <th>مبلغ</th>
                    <th className="ef-col-min">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {entriesPg.pageItems.map((e) => (
                    <tr key={e.id} className={editingId === e.id ? 'row-selected' : undefined}>
                      <td className="card-title" data-label="عنوان">
                        <div className="entity-name">{e.title}</div>
                        {!e.is_active && <span className="entity-sub">غیرفعال</span>}
                      </td>
                      <td data-label="تناوب">{freqText(e.frequency, e.interval)}</td>
                      <td data-label="سررسید بعدی">
                        {formatJalali(e.next_run_date)}
                        {e.is_due && <span className="status-badge tone-warning due-badge">سررسید</span>}
                      </td>
                      <td className="money-cell" data-label="مبلغ">{fa(e.amount)}</td>
                      <td className="card-actions ef-col-min">
                        <div className="row-actions ef-row-actions">
                          <RowAction
                            icon={Pencil}
                            label="ویرایش"
                            onClick={() => {
                              startEdit(e)
                              document.getElementById('rc-title')?.focus()
                            }}
                          />
                          <RowAction
                            icon={Play}
                            label="تولید همین حالا"
                            onClick={() => void handleRunOne(e.id)}
                            disabled={!e.is_active}
                            title={!e.is_active ? 'قالبِ غیرفعال سند تولید نمی‌کند.' : undefined}
                          />
                          <RowAction
                            icon={e.is_active ? PauseCircle : PlayCircle}
                            label={e.is_active ? 'غیرفعال‌کردن' : 'فعال‌کردن'}
                            onClick={() => void toggleActive(e)}
                          />
                          <RowAction icon={Trash2} label="حذف" danger onClick={() => void handleDelete(e.id)} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={entriesPg.page} pageCount={entriesPg.pageCount} onChange={entriesPg.setPage} />
          </div>
        )}
      </SectionCard>
    </>
  )
}
