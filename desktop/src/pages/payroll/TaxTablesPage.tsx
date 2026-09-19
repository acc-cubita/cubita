import { useEffect, useMemo, useState } from 'react'
import { Archive, Calculator, Check, Pencil, Trash2, X } from 'lucide-react'
import {
  TAX_CALC_PURPOSE_LABELS,
  createTaxTable,
  deleteTaxTable,
  fetchPayrollTaxGroups,
  fetchTaxTables,
  updateTaxTable,
  type PayrollTaxGroupRecord,
  type TaxTableRecord,
} from '../../api'
import { EmptyState } from '../../components/EmptyState'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { NumberInput } from '../../components/NumberInput'
import { SectionCard } from '../../components/SectionCard'
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
  TabHead,
} from '../../components/form/FormKit'
import { firstMissing } from '../../components/form/firstMissing'
import { formatJalali, toFaDigits, todayIso } from '../../lib/jalali'
import { AsyncBlock, Note, OpsPage, type Msg } from '../accounting/kit'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * جدول‌های مالیاتِ حقوق.
 *
 * **سالِ تازه یعنی جدولِ تازه، نه ویرایشِ جدولِ پارسال.** جدول‌های گذشته می‌مانند
 * تا محاسبه‌ی گذشته بازتولیدپذیر بماند — و همین است که فهرست را چندساله می‌کند.
 *
 * یک سال می‌تواند چند جدول داشته باشد: یکی به‌ازای هر گروهِ مالیاتی، و یکی
 * به‌ازای هر هدفِ محاسبه (حقوق / عیدی). ترکیبِ «تاریخ اجرا + گروه + نوع» یکتاست،
 * وگرنه محاسبه مبهم می‌شود.
 */

const fa = (n: number | string) => Number(n).toLocaleString('fa-IR')

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

type BracketDraft = { up_to: string; rate: string }

const EMPTY_BRACKETS: BracketDraft[] = [{ up_to: '', rate: '' }]
const capId = (index: number) => `tt-cap-${index}`
const OPEN_ENDED_ID = 'tt-open'

/** درصدِ نمایشی ← کسرِ ذخیره‌شده. ۷٫۵ ⇄ ۰٫۰۷۵ */
const toFraction = (percent: string) => String(Number(percent || 0) / 100)
//: toFixed: بدونِ آن ۰٫۰۷ × ۱۰۰ می‌شد ۷٫۰۰۰۰۰۰۰۰۰۰۰۰۰۰۱ و همان در فیلد می‌نشست.
const toPercent = (fraction: string) => String(Number((Number(fraction || 0) * 100).toFixed(4)))
//: «۲۳۰۴۰۰۰۰۰۰٫۰۰»ِ سرور ← «۲۳۰۴۰۰۰۰۰۰». صفرهای اعشار در فیلد فقط شلوغی‌اند.
const toAmount = (v: string | null) => (v == null || v === '' ? '' : String(Number(v)))

//: هم‌جداکننده‌ی `NumberInput` («،»)، تا «از مبلغ»ِ فقط‌خواندنی کنارِ فیلدهای سقف یکدست بخواند.
const faGrouped = (raw: string) => toFaDigits(raw.replace(/\B(?=(\d{3})+(?!\d))/g, '،'))

//: فوکوس بعد از رندر: فیلدی که باید فوکوس بگیرد گاهی همین حالا ساخته می‌شود.
const focusSoon = (id: string) => requestAnimationFrame(() => document.getElementById(id)?.focus())

export function TaxTablesPage({ token }: { token: string }) {
  const [rows, setRows] = useState<TaxTableRecord[] | null>(null)
  const [groups, setGroups] = useState<PayrollTaxGroupRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [listMsg, setListMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)

  const [editing, setEditing] = useState<TaxTableRecord | null>(null)
  const [title, setTitle] = useState('')
  const [title2, setTitle2] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [groupId, setGroupId] = useState('')
  const [purpose, setPurpose] = useState('salary')
  const [brackets, setBrackets] = useState<BracketDraft[]>(EMPTY_BRACKETS)
  //: فقط پله‌ی آخر می‌تواند بی‌سقف باشد — و موتور همین را می‌خواهد — پس یک پرچم برای کلِ پلکان کافی است.
  const [openEnded, setOpenEnded] = useState(true)

  async function refresh() {
    try {
      const [tables, taxGroups] = await Promise.all([fetchTaxTables(token), fetchPayrollTaxGroups(token)])
      setRows(tables)
      setGroups(taxGroups)
      setError(null)
    } catch (err) {
      setError(errText(err))
    }
  }

  useEffect(() => {
    void refresh()
  }, [token])

  function clearForm() {
    setEditing(null)
    setTitle('')
    setTitle2('')
    setEffectiveFrom('')
    setGroupId('')
    setPurpose('salary')
    setBrackets(EMPTY_BRACKETS)
    setOpenEnded(true)
    setMsg(null)
  }

  function edit(table: TaxTableRecord) {
    setEditing(table)
    setTitle(table.title)
    setTitle2(table.title2)
    setEffectiveFrom(table.effective_from)
    setGroupId(table.tax_group_id ?? '')
    setPurpose(table.calculation_type)
    setBrackets(
      table.brackets.length
        ? table.brackets.map((b) => ({ up_to: toAmount(b.up_to), rate: toPercent(b.rate) }))
        : EMPTY_BRACKETS,
    )
    setOpenEnded(table.brackets.length === 0 || table.brackets[table.brackets.length - 1].up_to == null)
    setMsg(null)
    focusSoon('tt-title')
  }

  /** اولین کمبودِ فرم را فوکوس می‌کند و پیامش را برمی‌گرداند. */
  function missingField(): string | null {
    const last = brackets.length - 1
    const missing = firstMissing([
      [title, 'tt-title', 'عنوانِ جدول را وارد کنید.'],
      [effectiveFrom, 'tt-date', 'تاریخِ اجرا را انتخاب کنید.'],
      ...brackets.map((b, i): [unknown, string, string] => [
        i === last && openEnded ? 'بی‌سقف' : b.up_to,
        capId(i),
        `سقفِ پله‌ی ${fa(i + 1)} را وارد کنید.`,
      ]),
    ])
    if (missing) return missing
    if (!openEnded) {
      document.getElementById(OPEN_ENDED_ID)?.focus()
      return 'پله‌ی آخر باید بدون سقف باشد. برای پله‌ی بالاتر «افزودن پله» را بزنید.'
    }
    return null
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const missing = missingField()
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const last = brackets.length - 1
      const body = {
        title: title.trim(),
        title2: title2.trim(),
        effective_from: effectiveFrom,
        tax_group_id: groupId || null,
        calculation_type: purpose,
        brackets: brackets.map((b, i) => ({
          up_to: i === last && openEnded ? null : b.up_to.trim(),
          rate: toFraction(b.rate),
        })),
      }
      if (editing) {
        await updateTaxTable(token, editing.id, body)
      } else {
        await createTaxTable(token, body)
      }
      clearForm()
      setMsg({ text: editing ? `«${body.title}» به‌روز شد.` : `«${body.title}» ثبت شد.`, kind: 'ok' })
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function remove(table: TaxTableRecord) {
    setBusy(true)
    setListMsg(null)
    try {
      await deleteTaxTable(token, table.id)
      setListMsg({ text: `«${table.title}» حذف شد.`, kind: 'ok' })
      if (editing?.id === table.id) clearForm()
      await refresh()
    } catch (err) {
      setListMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Calculator}
      title="جداول مالیات"
      description="پله‌های مالیات حقوق، به تفکیک تاریخ اجرا، گروه مالیاتی و نوع محاسبه."
    >
      <div className="ef-form">
        <form onSubmit={submit} noValidate>
          <SectionCard
            icon={Calculator}
            title={editing ? `ویرایش «${editing.title}»` : 'جدول مالیات جدید'}
            tip="سالِ تازه جدولِ تازه می‌گیرد؛ جدولِ پارسال دست نمی‌خورد تا محاسبه‌ی گذشته بازتولیدپذیر بماند."
          >
            <FormGrid cols={2}>
              <FormField id="tt-title" label="عنوان" required>
                {(id) => (
                  <input
                    id={id}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    maxLength={200}
                    placeholder="مثلاً: جدول مالیات حقوق ۱۴۰۵"
                  />
                )}
              </FormField>
              <FormField
                label="گروه مالیاتی"
                tip="هر گروه نرخ‌های خودش را دارد؛ نرخ از همین جدول می‌آید، نه از ضربِ درصد گروه."
              >
                {(id) => (
                  <SearchSelect id={id} value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                    <option value="">— پیش‌فرض (حکم‌های بدون گروه) —</option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </SearchSelect>
                )}
              </FormField>
              <FormField id="tt-date" label="تاریخ اجرا" required>
                {(id) => <JalaliDatePicker id={id} value={effectiveFrom} onChange={setEffectiveFrom} />}
              </FormField>
              <FormField label="نوع محاسبه" required tip="جدولِ حقوق برای عیدی به کار نمی‌رود — آستانه‌هایشان یکی نیست.">
                {(id) => (
                  <SearchSelect id={id} value={purpose} onChange={(e) => setPurpose(e.target.value)}>
                    {Object.entries(TAX_CALC_PURPOSE_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </SearchSelect>
                )}
              </FormField>
              <FormField
                label="توضیح"
                optional
                span="full"
                tip="فقط نمایشی است و زیرِ عنوان در فهرست می‌آید؛ در انتخابِ جدول نقشی ندارد."
              >
                {(id) => (
                  <input
                    id={id}
                    value={title2}
                    onChange={(e) => setTitle2(e.target.value)}
                    maxLength={200}
                    placeholder="مثلاً: مصوبه‌ی قانون بودجه"
                  />
                )}
              </FormField>
            </FormGrid>

            <BracketEditor
              brackets={brackets}
              openEnded={openEnded}
              onChange={setBrackets}
              onOpenEndedChange={setOpenEnded}
            />
          </SectionCard>
          <ActionBar status={<FormStatus msg={msg} />}>
            {editing && (
              <button type="button" className="ef-btn-secondary" onClick={clearForm} disabled={busy}>
                <X size={15} /> انصراف
              </button>
            )}
            <button type="submit" className="btn-primary" disabled={busy}>
              <Check size={16} /> {busy ? 'در حال ثبت…' : editing ? 'ذخیره تغییرات' : 'ثبت جدول مالیات'}
            </button>
          </ActionBar>
        </form>

        <TaxTableList
          rows={rows}
          error={error}
          busy={busy}
          editingId={editing?.id ?? null}
          msg={listMsg}
          onEdit={edit}
          onDelete={(table) => void remove(table)}
        />
      </div>
    </OpsPage>
  )
}

/**
 * پلکانِ مالیات به مدلِ «سقفِ تجمعی»: هر پله فقط سقف و نرخ می‌گیرد و «از مبلغ»ش سقفِ پله‌ی
 * قبل است — پس شکاف و همپوشانی ساختاراً ناممکن‌اند. «از مبلغ» برای همین ورودی نیست؛ جعبه‌ی
 * فقط‌خواندنیِ هم‌شکل است تا ردیف یکدست دیده شود ولی دو نما از یک عدد ساخته نشود.
 */
function BracketEditor({
  brackets,
  openEnded,
  onChange,
  onOpenEndedChange,
}: {
  brackets: BracketDraft[]
  openEnded: boolean
  onChange: (next: BracketDraft[]) => void
  onOpenEndedChange: (v: boolean) => void
}) {
  const last = brackets.length - 1

  function set(index: number, patch: Partial<BracketDraft>) {
    onChange(brackets.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  function add() {
    //: پله‌ی تازه بالاترین پله است و بی‌سقف؛ پله‌ای که تا حالا آخر بود حالا سقف می‌خواهد.
    onChange([...brackets, { up_to: '', rate: '' }])
    onOpenEndedChange(true)
    focusSoon(capId(last))
  }

  function toggleOpenEnded(v: boolean) {
    onOpenEndedChange(v)
    if (!v) focusSoon(capId(last))
  }

  return (
    <div className="ef-block">
      <TabHead
        title="پله‌های مالیاتی"
        tip="«از مبلغِ» هر پله خودکار سقفِ پله‌ی قبل است. سقف‌ها باید صعودی باشند و پله‌ی آخر بدون سقف."
      />
      {/* audit-r9-exempt: پله‌ها همیشه دستِ‌کم یک ردیف دارند و به‌جای حالتِ خالی
          دکمه‌ی «افزودن پله» می‌گیرند. */}
      <div className="table-scroll ef-table-wrap">
        <table className="cards-on-mobile ef-table ef-table--edit">
          <thead>
            <tr>
              <th className="ef-col-min">ردیف</th>
              <th>از مبلغ</th>
              <th>تا مبلغ</th>
              <th>نرخ</th>
              <th className="ef-col-min" aria-label="حذف" />
            </tr>
          </thead>
          <tbody>
            {brackets.map((row, index) => {
              const from = index === 0 ? '0' : brackets[index - 1].up_to
              const capInput = (
                <InputAffix unit="ریال">
                  <NumberInput
                    id={capId(index)}
                    aria-label={`سقفِ پله‌ی ${fa(index + 1)} (ریال)`}
                    value={row.up_to}
                    onChange={(v) => set(index, { up_to: v })}
                  />
                </InputAffix>
              )
              return (
                <tr key={index}>
                  <td className="card-title ef-col-min" data-label="ردیف">
                    پله {fa(index + 1)}
                  </td>
                  <td className="card-wide" data-label="از مبلغ">
                    <InputAffix unit="ریال" readOnly>
                      {from.trim() === '' ? '—' : faGrouped(from)}
                    </InputAffix>
                  </td>
                  <td className="card-wide" data-label="تا مبلغ">
                    {index === last ? (
                      <div className="ef-cap">
                        {!openEnded && capInput}
                        <Switch
                          id={OPEN_ENDED_ID}
                          checked={openEnded}
                          onChange={toggleOpenEnded}
                          label="بدون سقف (تا بی‌نهایت)"
                        />
                      </div>
                    ) : (
                      capInput
                    )}
                  </td>
                  <td className="card-wide" data-label="نرخ">
                    <InputAffix unit="٪">
                      <NumberInput
                        aria-label={`نرخِ پله‌ی ${fa(index + 1)} (درصد)`}
                        allowDecimal
                        value={row.rate}
                        onChange={(v) => set(index, { rate: v })}
                        placeholder="۰"
                      />
                    </InputAffix>
                  </td>
                  <td className="card-actions ef-col-min">
                    <RowAction
                      icon={Trash2}
                      label="حذفِ پله"
                      danger
                      disabled={brackets.length === 1}
                      title={brackets.length === 1 ? 'جدول دست‌کم یک پله می‌خواهد.' : undefined}
                      onClick={() => onChange(brackets.filter((_, i) => i !== index))}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <AddRowButton onClick={add}>افزودن پله</AddRowButton>
    </div>
  )
}

type TableStatus = 'current' | 'upcoming' | 'archived'

const STATUS_BADGE: Record<TableStatus, { label: string; tone: string; hint: string }> = {
  current: { label: 'جاری', tone: 'tone-success', hint: 'همین حالا در محاسبه‌ی حقوق به کار می‌رود.' },
  upcoming: { label: 'آینده', tone: 'tone-info', hint: 'از تاریخِ اجرایش به کار می‌افتد.' },
  archived: {
    label: 'بایگانی',
    tone: 'tone-muted',
    hint: 'جدولِ تازه‌تری جایش را گرفته؛ برای بازخوانیِ گذشته مانده است.',
  },
}

/**
 * وضعیتِ هر جدول در دامنه‌ی خودش (گروهِ مالیاتی + نوعِ محاسبه) — همان قاعده‌ی حل‌کننده‌ی سرور
 * (`resolve_tax_table`): تازه‌ترین جدولی که تاریخِ اجرایش رسیده «جاری» است، قبلی‌ها «بایگانی»،
 * نرسیده‌ها «آینده».
 */
function statusByTable(rows: TaxTableRecord[], today: string): Map<string, TableStatus> {
  const current = new Map<string, TaxTableRecord>()
  for (const t of rows) {
    if (t.effective_from > today) continue
    const scope = `${t.tax_group_id ?? ''}|${t.calculation_type}`
    const best = current.get(scope)
    if (!best || t.effective_from > best.effective_from) current.set(scope, t)
  }
  const currentIds = new Set([...current.values()].map((t) => t.id))
  return new Map(
    rows.map((t): [string, TableStatus] => [
      t.id,
      t.effective_from > today ? 'upcoming' : currentIds.has(t.id) ? 'current' : 'archived',
    ]),
  )
}

function TaxTableList({
  rows,
  error,
  busy,
  editingId,
  msg,
  onEdit,
  onDelete,
}: {
  rows: TaxTableRecord[] | null
  error: string | null
  busy: boolean
  editingId: string | null
  msg: Msg
  onEdit: (table: TaxTableRecord) => void
  onDelete: (table: TaxTableRecord) => void
}) {
  const status = useMemo(() => (rows ? statusByTable(rows, todayIso()) : new Map<string, TableStatus>()), [rows])

  return (
    <SectionCard
      icon={Archive}
      title="فهرست جداول مالیات"
      badge={rows && rows.length > 0 ? <CountBadge accent>{fa(rows.length)} جدول ثبت‌شده</CountBadge> : undefined}
      description="سوابق جداول مالیاتی جهت محاسبات و بازخوانی سال‌های گذشته حفظ می‌شوند."
    >
      <AsyncBlock loading={rows == null} error={error}>
        {rows == null || rows.length === 0 ? (
          <EmptyState icon={Calculator} text="هنوز جدول مالیاتی ثبت نشده. برای سال جاری یکی بسازید." />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead>
                <tr>
                  <th>عنوان</th>
                  <th>تاریخ اجرا</th>
                  <th>گروه مالیاتی</th>
                  <th>نوع محاسبه</th>
                  <th>پله‌ها</th>
                  <th>وضعیت</th>
                  <th className="ef-col-min">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((table) => {
                  const badge = STATUS_BADGE[status.get(table.id) ?? 'archived']
                  return (
                    <tr key={table.id} className={table.id === editingId ? 'is-editing' : undefined}>
                      <td className="card-title" data-label="عنوان">
                        <div className="ef-cell-title">
                          <span>{table.title}</span>
                          {table.title2 && <small>{table.title2}</small>}
                        </div>
                      </td>
                      <td data-label="تاریخ اجرا">{formatJalali(table.effective_from)}</td>
                      <td data-label="گروه مالیاتی">
                        {table.tax_group_name || <span className="muted">پیش‌فرض</span>}
                      </td>
                      <td data-label="نوع محاسبه">
                        {TAX_CALC_PURPOSE_LABELS[table.calculation_type] ?? table.calculation_type}
                      </td>
                      <td data-label="پله‌ها">
                        <CountBadge>{fa(table.brackets.length)} پله</CountBadge>
                      </td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${badge.tone}`} title={badge.hint}>
                          {badge.label}
                        </span>
                      </td>
                      <td className="card-actions ef-col-min">
                        <div className="row-actions ef-row-actions">
                          <RowAction icon={Pencil} label="ویرایش" onClick={() => onEdit(table)} />
                          <RowAction
                            icon={Trash2}
                            label="حذف"
                            danger
                            onClick={() => onDelete(table)}
                            disabled={busy || table.in_use}
                            title={
                              table.in_use
                                ? 'فیش‌هایی به این جدول استناد کرده‌اند؛ حذف‌شدنی نیست. برای سالِ تازه جدولِ تازه بسازید.'
                                : undefined
                            }
                          />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </AsyncBlock>
      <Note msg={msg} />
    </SectionCard>
  )
}
