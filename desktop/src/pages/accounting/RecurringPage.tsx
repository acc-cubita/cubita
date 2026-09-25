import { useEffect, useId, useMemo, useRef, useState, type Dispatch, type MouseEvent, type SetStateAction } from 'react'
import { Pencil, Play, Plus, Repeat, Search, Trash2, X } from 'lucide-react'
import {
  createRecurringEntry,
  deleteRecurringEntry,
  fetchAccountsLive,
  fetchCostCenters,
  fetchRecurringEntries,
  runRecurringDue,
  runRecurringOne,
  setRecurringActive,
  updateRecurringEntry,
  type CostCenterRecord,
  type RecurringEntry,
  type RecurringFrequency,
} from '../../api'
import { AccountCombo, type ComboOption } from '../../components/AccountCombo'
import { BalanceFooter } from '../../components/BalanceFooter'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { NumberInput } from '../../components/NumberInput'
import { SearchSelect } from '../../components/SearchSelect'
import { SectionCard } from '../../components/SectionCard'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { AddRowButton, CountBadge, RowAction } from '../../components/form/FormKit'
import { useAlignToGrid } from '../../lib/alignToGrid'
import { balanceState } from '../../lib/balanceState'
import { toNumber } from '../../lib/csv'
import { formatJalali, todayIso, toFaDigits } from '../../lib/jalali'
import {
  blankForm,
  blankLine,
  formFromEntry,
  freqText,
  lineIsFilled,
  lineTotals,
  sortTemplates,
  templateMatches,
  templateProblem,
  toPayload,
  type RecurringLineDraft,
  type TemplateForm,
} from '../../lib/recurringSheet'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { useSheetNav } from '../../lib/useSheetNav'
import { fa, faAmount, faInt, OpsPage, type Msg } from './kit'

/**
 * اسناد تکرارشونده — قالبی که سندِ دوره‌ای (اجاره، بیمه، اقساط، حقوقِ ثابت) را در هر سررسید خودکار
 * می‌سازد. **هم‌سبکِ «سند حسابداری»** (تمِ اکسلی، الگوی «الف» برای فرم و «د» برای فهرست):
 *
 * * **فرمِ قالب** یک سند است: سربرگِ خانه‌ای (عنوان، تناوب، شروع، پایان، …) ستون‌به‌ستون روی گریدِ
 *   ردیف‌ها، گریدِ اکسلیِ حساب/شرح/بدهکار/بستانکار با صفحه‌کلیدِ گریدِ سند، و نوارِ پایینِ توازن. سرور
 *   قالب را کامل جایگزین می‌کند، پس ویرایش همان فرم است که با ردیف‌های قالب پر شده.
 * * **فهرستِ قالب‌ها** گریدِ فقط‌خواندنی: سررسیدشده‌ها بالا و کهربایی، انتخابِ ردیف با شماره و جمعِ
 *   مبلغِ انتخاب‌شده‌ها، و کارهای دسته‌ای (تولید، فعال/غیرفعال، حذف). فعال/غیرفعال خودِ خانه‌ی وضعیت است.
 *
 * منطقِ خالص (اعتبار، بار، ذخیره، ترتیب) در `lib/recurringSheet.ts`.
 */

type LineCol = 'account' | 'description' | 'debit' | 'credit'
const LINE_COLS: LineCol[] = ['account', 'description', 'debit', 'credit']
const LINE_LAYOUT = { fixed: ['num', 'actions'], auto: 'account' } as const
const LIST_LAYOUT = { fixed: ['rowhead', 'actions'], auto: 'title' } as const

const firstLines = () => [blankLine(), blankLine()]

export function RecurringListPage({ token }: { token: string }) {
  const [accounts, setAccounts] = useState<{ id: string; code: string; name: string; is_group: number }[]>([])
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [entries, setEntries] = useState<RecurringEntry[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [form, setForm] = useState<TemplateForm>(() => blankForm(todayIso()))
  const [lines, setLines] = useState<RecurringLineDraft[]>(firstLines)
  const [editing, setEditing] = useState<RecurringEntry | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(null)
  //: آنچه فرم با آن باز شد — برای «تغییرِ ذخیره‌نشده» پیش از کنارگذاشتن.
  const [pristine, setPristine] = useState(() => JSON.stringify([blankForm(todayIso()), firstLines()]))
  const formRef = useRef<HTMLFormElement>(null)
  const titleRef = useRef<HTMLInputElement>(null)
  const uid = useId()
  //: سربرگ و نوار روی پنج خانه‌ی گریدِ ردیف‌ها: ردیف+حساب، شرح، بدهکار، بستانکار، آیکون — همان گریدِ سند.
  useAlignToGrid(formRef, '.jh-bar, .jf-foot--cols', { table: '.rc-lines' })

  async function refresh() {
    try {
      setEntries(await fetchRecurringEntries(token))
      setListError(null)
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
    fetchAccountsLive(token)
      .then(setAccounts)
      .catch(() => setAccounts([]))
    fetchCostCenters(token)
      .then((rows) => setCostCenters(rows.filter((c) => c.is_active)))
      .catch(() => setCostCenters([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const accountOptions: ComboOption[] = useMemo(
    () => accounts.filter((a) => !a.is_group).map((a) => ({ value: a.id, label: `${a.code} — ${a.name}` })),
    [accounts],
  )
  const totals = lineTotals(lines)
  const state = balanceState(totals.debit, totals.credit, Math.abs(totals.debit - totals.credit) < 0.005)
  const dirty = JSON.stringify([form, lines]) !== pristine
  const set = <K extends keyof TemplateForm>(key: K, value: TemplateForm[K]) => setForm((f) => ({ ...f, [key]: value }))

  function load(next: RecurringEntry | null) {
    const loaded = next ? formFromEntry(next) : { form: blankForm(todayIso()), lines: firstLines() }
    //: قالبِ یک‌ردیفه (ناممکن در سرور، ولی ارزان) همیشه دست‌کم دو ردیف نشان می‌دهد.
    while (loaded.lines.length < 2) loaded.lines.push(blankLine())
    setForm(loaded.form)
    setLines(loaded.lines)
    setEditing(next)
    setPristine(JSON.stringify([loaded.form, loaded.lines]))
  }

  /** بازکردنِ قالب در فرم — اگر فرم تغییرِ ذخیره‌نشده دارد، اول می‌پرسد. */
  function startEdit(e: RecurringEntry) {
    if (dirty && !window.confirm('تغییراتِ ذخیره‌نشده‌ی فرم کنار گذاشته شود؟')) return
    load(e)
    setMsg(null)
    formRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    requestAnimationFrame(() => titleRef.current?.focus())
  }

  function cancelEdit() {
    if (dirty && !window.confirm('تغییراتِ ذخیره‌نشده‌ی فرم کنار گذاشته شود؟')) return
    load(null)
    setMsg(null)
  }

  async function submit() {
    const problem = templateProblem(form, lines)
    if (problem) {
      setMsg({ text: problem, kind: 'err' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const payload = toPayload(form, lines)
      if (editing) await updateRecurringEntry(token, editing.id, payload)
      else await createRecurringEntry(token, payload)
      load(null)
      setMsg({ text: editing ? `قالبِ «${payload.title}» ذخیره شد.` : `قالبِ «${payload.title}» ثبت شد.`, kind: 'ok' })
      await refresh()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      canvas
      icon={Repeat}
      title="اسناد تکرارشونده"
      description="قالبِ سندهای دوره‌ای — اجاره، بیمه، اقساط، حقوقِ ثابت — که در هر سررسید خودکار ثبت می‌شوند. قالب را یک‌بار بسازید؛ سررسیدها با «تولید سررسیدها» سند می‌شوند."
    >
      <form
        ref={formRef}
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          if (!busy) void submit()
        }}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.code === 'KeyS') {
            e.preventDefault()
            if (!busy) void submit()
          }
        }}
      >
        <SectionCard
          icon={editing ? Pencil : Plus}
          title={editing ? `ویرایشِ قالبِ «${editing.title}»` : 'قالبِ تازه'}
          tip="یک سندِ دوره‌ای که خودکار در سررسیدهایش ساخته می‌شود. تا جمعِ بدهکار و بستانکار برابر نشود، ثبت نمی‌شود."
          badge={<CountBadge>{fa(lines.filter(lineIsFilled).length)} ردیفِ معتبر</CountBadge>}
          actions={
            editing && (
              <button type="button" className="ef-btn-secondary" onClick={cancelEdit}>
                <X size={14} /> انصراف از ویرایش
              </button>
            )
          }
        >
          <div className="jh-bar">
            <div className="jh-row">
              <div className="jh-field jh-field--grow">
                <label className="jh-label" htmlFor={`${uid}-title`}>
                  عنوانِ قالب <span className="jh-req" aria-hidden="true">*</span>
                </label>
                <input
                  ref={titleRef}
                  id={`${uid}-title`}
                  value={form.title}
                  onChange={(e) => set('title', e.target.value)}
                  placeholder="مثلاً اجاره‌ی دفتر"
                />
              </div>
              <div className="jh-field jh-field--date">
                <label className="jh-label" htmlFor={`${uid}-freq`}>
                  تناوب
                </label>
                <SearchSelect
                  id={`${uid}-freq`}
                  value={form.frequency}
                  onChange={(e) => set('frequency', e.target.value as RecurringFrequency)}
                >
                  <option value="weekly">هفتگی</option>
                  <option value="monthly">ماهانه</option>
                  <option value="yearly">سالانه</option>
                </SearchSelect>
              </div>
              <div className="jh-field jh-field--tail">
                <label
                  className="jh-label"
                  htmlFor={`${uid}-interval`}
                  title="۱ یعنی هر دوره؛ ۳ با تناوبِ ماهانه یعنی هر سه ماه یک‌بار."
                >
                  هر چند دوره یک‌بار
                </label>
                <NumberInput
                  id={`${uid}-interval`}
                  value={form.interval}
                  onChange={(v) => set('interval', v)}
                  group={false}
                />
              </div>
            </div>
            <div className="jh-row jh-row--sub">
              <div className="jh-field">
                <label className="jh-label" htmlFor={`${uid}-desc`}>
                  شرحِ سند
                </label>
                <input
                  id={`${uid}-desc`}
                  value={form.description}
                  onChange={(e) => set('description', e.target.value)}
                  placeholder="شرحِ کلیِ سندی که هر بار ساخته می‌شود"
                />
              </div>
              {costCenters.length > 0 && (
                <div className="jh-field">
                  <label className="jh-label" htmlFor={`${uid}-center`}>
                    مرکز هزینه / پروژه
                  </label>
                  <SearchSelect
                    id={`${uid}-center`}
                    value={form.cost_center_id}
                    onChange={(e) => set('cost_center_id', e.target.value)}
                  >
                    <option value="">— بدون مرکز —</option>
                    {costCenters.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code ? `${c.code} — ${c.name}` : c.name}
                      </option>
                    ))}
                  </SearchSelect>
                </div>
              )}
              <div className="jh-field">
                <label className="jh-label" htmlFor={`${uid}-start`}>
                  تاریخِ شروع <span className="jh-req" aria-hidden="true">*</span>
                </label>
                <JalaliDatePicker id={`${uid}-start`} value={form.start_date} onChange={(v) => set('start_date', v)} />
              </div>
              <div className="jh-field">
                <label
                  className="jh-label"
                  htmlFor={`${uid}-end`}
                  title="خالی یعنی تا وقتی قالب را غیرفعال نکنید ادامه می‌دهد."
                >
                  تاریخِ پایان
                </label>
                <JalaliDatePicker
                  id={`${uid}-end`}
                  value={form.end_date}
                  onChange={(v) => set('end_date', v)}
                  placeholder="بی‌پایان"
                  clearLabel="بی‌پایان"
                />
              </div>
            </div>
          </div>

          <LinesSheet lines={lines} setLines={setLines} options={accountOptions} />
        </SectionCard>

        <BalanceFooter
          totalDebit={totals.debit}
          totalCredit={totals.credit}
          state={state}
          submitting={busy}
          message={msg}
          submitLabel={editing ? 'ذخیره‌ی قالب' : 'ثبتِ قالب'}
          shortcut
          columns
        />
      </form>

      <TemplatesCard
        token={token}
        entries={entries}
        error={listError}
        editingId={editing?.id ?? null}
        onEdit={startEdit}
        onChanged={refresh}
        onRemoved={(ids) => {
          if (editing && ids.includes(editing.id)) load(null)
        }}
      />
    </OpsPage>
  )
}

/** سرستونِ ردیفِ اکسلی: کلیک انتخاب، Ctrl+کلیک افزودن، Shift+کلیک بازه؛ بیرون از Tab. */
function RowHead({ n, selected, onPick, hideOnCard = false }: { n: number; selected: boolean; onPick: (e: MouseEvent) => void; hideOnCard?: boolean }) {
  return (
    <td className={`ef-col-min jg-num xl-rowhead ${hideOnCard ? 'card-hide' : 'card-title'}`}>
      <button
        type="button"
        tabIndex={-1}
        className="xl-rowhead-btn"
        aria-pressed={selected}
        aria-label={`انتخابِ ردیفِ ${fa(n)}`}
        onClick={onPick}
      >
        {fa(n)}
      </button>
    </td>
  )
}

/** گریدِ ردیف‌های قالب — همان گریدِ سند: حساب، شرحِ ردیف، بدهکار، بستانکار. */
function LinesSheet({
  lines,
  setLines,
  options,
}: {
  lines: RecurringLineDraft[]
  setLines: Dispatch<SetStateAction<RecurringLineDraft[]>>
  options: ComboOption[]
}) {
  const gridRef = useRef<HTMLDivElement>(null)
  const cw = useColumnWidths('cubita.grid.recurring.shares', LINE_LAYOUT)
  const { selected, click, clear } = useRowSelection()
  //: افزودن/حذفِ ردیف شاخص‌ها را جابه‌جا می‌کند؛ انتخابِ کهنه ردیفِ اشتباه را می‌گرفت.
  useEffect(() => clear(), [lines.length, clear])
  const rows = [...selected].map(Number).sort((a, b) => a - b)
  const order = lines.map((_, i) => String(i))

  const update = (i: number, patch: Partial<RecurringLineDraft>) =>
    setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  //: سند دست‌کم دو ردیف می‌خواهد؛ گرید هیچ‌وقت کمتر از دو ردیف نشان نمی‌دهد.
  const remove = (idx: number[]) =>
    setLines((ls) => {
      const keep = ls.filter((_, j) => !idx.includes(j))
      while (keep.length < 2) keep.push(blankLine())
      return keep
    })
  const append = () => setLines((ls) => [...ls, blankLine()])

  const nav = useSheetNav<LineCol>({
    gridRef,
    cols: LINE_COLS,
    rowCount: lines.length,
    //: ردیفی که بدهکار گرفته تمام است — Enter از بستانکارش می‌پرد و به حسابِ ردیفِ بعد می‌رود.
    enterPath: (row, col) => col !== 'credit' || !lines[row]?.debit,
    onAppendRow: append,
    onDeleteRow: (row) => {
      remove(rows.length > 0 ? rows : [row])
      return true
    },
    rowHasContent: (row) =>
      Boolean(lines[row] && (lines[row].account_id || lines[row].description || lines[row].debit || lines[row].credit)),
  })
  const head = (id: string, label: string, next: string) => (
    <th data-col={id}>
      {label}
      {cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  const sum = (side: 'debit' | 'credit') => rows.reduce((s, r) => s + toNumber(lines[r]?.[side] ?? ''), 0)

  return (
    <div className="ob-block">
      <h3 className="ef-block-title">ردیف‌های سند</h3>
      <div className="jg">
        <div
          ref={gridRef}
          className="table-scroll ef-table-wrap jg-wrap"
          onKeyDown={nav.onKeyDown}
          role="grid"
          aria-label="ردیف‌های سندِ تکرارشونده"
        >
          <table ref={cw.frame} className="ef-table ef-table--edit jg-table xl-grid table-plain rc-lines">
            <colgroup>
              <col className="jg-c-num" style={cw.col('num')} />
              <col className="jg-c-account" style={cw.col('account')} />
              <col className="jg-c-note" style={cw.col('description')} />
              <col className="jg-c-amount" style={cw.col('debit')} />
              <col className="jg-c-amount" style={cw.col('credit')} />
              <col className="jg-c-act1" style={cw.col('actions')} />
            </colgroup>
            <thead>
              <tr>
                <th className="ef-col-min xl-rowhead" data-col="num">
                  ردیف
                </th>
                {head('account', 'حساب', 'description')}
                {head('description', 'شرحِ ردیف', 'debit')}
                {head('debit', 'بدهکار', 'credit')}
                {head('credit', 'بستانکار', 'actions')}
                <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={i} className={selected.has(String(i)) ? 'is-selected' : undefined}>
                  <RowHead n={i + 1} selected={selected.has(String(i))} onPick={(e) => click(order, String(i), modsOf(e))} />
                  <td className="ef-col-wide" data-cell={`${i}-0`}>
                    <AccountCombo
                      aria-label={`حسابِ ردیفِ ${fa(i + 1)}`}
                      value={l.account_id}
                      options={options}
                      onChange={(v) => update(i, { account_id: v })}
                      onCommit={(how) => nav.commit(i, 'account', how)}
                    />
                  </td>
                  <td data-cell={`${i}-1`}>
                    <input
                      aria-label={`شرحِ ردیفِ ${fa(i + 1)}`}
                      value={l.description}
                      onChange={(e) => update(i, { description: e.target.value })}
                      placeholder="اختیاری"
                    />
                  </td>
                  <td data-cell={`${i}-2`}>
                    <NumberInput
                      aria-label={`بدهکارِ ردیفِ ${fa(i + 1)}`}
                      value={l.debit}
                      onChange={(v) => update(i, { debit: v, credit: '' })}
                    />
                  </td>
                  <td data-cell={`${i}-3`}>
                    <NumberInput
                      aria-label={`بستانکارِ ردیفِ ${fa(i + 1)}`}
                      value={l.credit}
                      onChange={(v) => update(i, { credit: v, debit: '' })}
                    />
                  </td>
                  <td className="ef-col-min jg-actions">
                    <div className="row-actions">
                      <RowAction
                        icon={Trash2}
                        label="حذف ردیف"
                        danger
                        disabled={lines.length <= 2}
                        title={lines.length <= 2 ? 'سند دست‌کم دو ردیف می‌خواهد.' : 'حذف ردیف (Ctrl+Delete)'}
                        onClick={() => remove([i])}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length > 0 && (
          <SelectionBar count={rows.length} unit="ردیف" onClear={clear}>
            <span>
              جمع بدهکار <b className="num">{fa(sum('debit'))}</b>
            </span>
            <span>
              جمع بستانکار <b className="num">{fa(sum('credit'))}</b>
            </span>
            <button type="button" className="xl-selbar-danger" onClick={() => remove(rows)}>
              <Trash2 size={14} aria-hidden="true" /> حذفِ ردیف‌ها (Ctrl+Delete)
            </button>
          </SelectionBar>
        )}
      </div>
      <AddRowButton onClick={append}>افزودن ردیف (Ctrl+Enter)</AddRowButton>
    </div>
  )
}

/**
 * فهرستِ قالب‌ها — گریدِ فقط‌خواندنیِ اکسلی (الگوی «د»). سررسیدشده‌ها بالا و کهربایی، فعال‌ها نوارِ سبز،
 * غیرفعال‌ها کم‌رنگ؛ قالبی که در فرم باز است ته‌رنگِ accent دارد. کارهای تکی روی ردیف، کارهای دسته‌ای
 * روی نوارِ انتخاب — پشتِ‌سرِ‌هم، تا اگر یکی خطا داد بقیه انجام شوند و خطا نام ببرد.
 */
function TemplatesCard({
  token,
  entries,
  error,
  editingId,
  onEdit,
  onChanged,
  onRemoved,
}: {
  token: string
  entries: RecurringEntry[] | null
  error: string | null
  editingId: string | null
  onEdit: (e: RecurringEntry) => void
  onChanged: () => Promise<void>
  onRemoved: (ids: string[]) => void
}) {
  const [find, setFind] = useState('')
  const [note, setNote] = useState<Msg>(null)
  const [working, setWorking] = useState(false)
  const cw = useColumnWidths('cubita.grid.recurringList.shares', LIST_LAYOUT)
  const { selected, click, clear } = useRowSelection()
  const all = useMemo(() => entries ?? [], [entries])
  const rows = useMemo(() => sortTemplates(all.filter((e) => templateMatches(e, find))), [all, find])
  const order = rows.map((e) => e.id)
  const chosen = rows.filter((e) => selected.has(e.id))
  const due = all.filter((e) => e.is_due && e.is_active).length
  const colIds = ['rowhead', 'title', 'freq', 'next', 'last', 'amount', 'state', 'actions']

  /** چند کار پشتِ‌سرِ‌هم؛ خطای هر قالب با نامش جمع می‌شود و بقیه ادامه می‌یابند. */
  async function each(targets: RecurringEntry[], act: (e: RecurringEntry) => Promise<unknown>, done: (n: number) => string) {
    setWorking(true)
    setNote(null)
    const failed: string[] = []
    let ok = 0
    for (const e of targets) {
      try {
        await act(e)
        ok++
      } catch (err) {
        failed.push(`«${e.title}»: ${err instanceof Error ? err.message : 'خطای ناشناخته'}`)
      }
    }
    await onChanged()
    setWorking(false)
    setNote(failed.length ? { text: `${done(ok)} ${failed.join(' — ')}`, kind: 'err' } : { text: done(ok), kind: 'ok' })
  }

  async function runDue() {
    setWorking(true)
    setNote(null)
    try {
      const r = await runRecurringDue(token)
      setNote({
        text:
          r.generated === 0
            ? 'سررسیدی برای تولید نبود.'
            : `${toFaDigits(r.generated)} سند ساخته شد${r.skipped ? ` (${toFaDigits(r.skipped)} سررسید در دوره‌ی بسته رد شد)` : ''}.`,
        kind: 'ok',
      })
      await onChanged()
    } catch (err) {
      setNote({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setWorking(false)
    }
  }

  const runSome = (targets: RecurringEntry[]) => {
    let made = 0
    return each(
      targets.filter((e) => e.is_active),
      async (e) => {
        made += (await runRecurringOne(token, e.id)).generated
      },
      () => (made === 0 ? 'سررسیدی برای این قالب‌ها نبود.' : `${toFaDigits(made)} سند ساخته شد.`),
    )
  }
  const setActive = (targets: RecurringEntry[], on: boolean) =>
    each(
      targets.filter((e) => e.is_active !== on),
      (e) => setRecurringActive(token, e.id, on),
      (n) => `${toFaDigits(n)} قالب ${on ? 'فعال' : 'غیرفعال'} شد.`,
    )
  const remove = (targets: RecurringEntry[]) => {
    const names = targets.length === 1 ? `قالبِ «${targets[0].title}»` : `${toFaDigits(targets.length)} قالب`
    if (!window.confirm(`${names} حذف شود؟ سندهایی که تا امروز ساخته شده‌اند دست نمی‌خورند.`)) return
    onRemoved(targets.map((e) => e.id))
    clear()
    return each(targets, (e) => deleteRecurringEntry(token, e.id), (n) => `${toFaDigits(n)} قالب حذف شد.`)
  }

  const head = (id: string, label: string) => (
    <th data-col={id}>
      {label}
      {cw.canResize(id, colIds[colIds.indexOf(id) + 1]) && <ColResizer onBegin={(ev) => cw.begin(ev, id)} onReset={cw.reset} />}
    </th>
  )

  return (
    <SectionCard
      icon={Repeat}
      title="قالب‌ها"
      badge={<CountBadge accent>{faInt(all.length)} قالب</CountBadge>}
      description={
        due > 0 ? `${toFaDigits(due)} قالب سررسید شده و منتظرِ تولید است.` : 'هیچ قالبی سررسید نشده است.'
      }
      actions={
        <div className="jg-head-actions">
          <div className={`jg-find${find ? ' has-query' : ''}`} role="search">
            <Search size={14} aria-hidden="true" />
            <input
              type="search"
              value={find}
              onChange={(e) => setFind(e.target.value)}
              placeholder="عنوان، شرح یا حساب…"
              aria-label="جست‌وجوی قالب"
            />
          </div>
          <button
            type="button"
            className={due > 0 ? 'btn-primary' : 'ef-btn-secondary'}
            disabled={working}
            onClick={() => void runDue()}
          >
            <Play size={14} /> تولید سررسیدها
          </button>
        </div>
      }
    >
      {(error || note) && (
        <p className={`ef-message ef-block-note ${error || note?.kind === 'err' ? 'ef-message--warn' : 'ef-message--ok'}`} role="status">
          {error ?? note?.text}
        </p>
      )}
      {entries === null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : all.length === 0 ? (
        <p className="muted rc-empty">هنوز قالبی نیست — اولین سندِ دوره‌ای (مثلاً اجاره) را در فرمِ بالا بسازید.</p>
      ) : rows.length === 0 ? (
        <p className="muted rc-empty">قالبی با «{find}» پیدا نشد.</p>
      ) : (
        <div className="jg">
          <div className="table-scroll ef-table-wrap">
            <table ref={cw.frame} className="cards-on-mobile acc-table ef-table xl-grid rc-list">
              <colgroup>
                {colIds.map((id) => (
                  <col key={id} className={`rc-c-${id}`} style={cw.col(id)} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  <th className="xl-rowhead" data-col="rowhead" aria-label="انتخاب" />
                  {head('title', 'عنوان')}
                  {head('freq', 'تناوب')}
                  {head('next', 'سررسیدِ بعدی')}
                  {head('last', 'آخرین تولید')}
                  {head('amount', 'مبلغ')}
                  {head('state', 'وضعیت')}
                  <th className="ef-col-min" data-col="actions">
                    عملیات
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e, idx) => {
                  const on = selected.has(e.id)
                  const tone = !e.is_active ? 'acc-row--muted' : e.is_due ? 'xl-row--temp' : 'xl-row--perm'
                  return (
                    <tr
                      key={e.id}
                      className={[tone, on && 'is-selected', e.id === editingId && 'xl-row--editing'].filter(Boolean).join(' ')}
                    >
                      <RowHead n={idx + 1} selected={on} hideOnCard onPick={(ev) => click(order, e.id, modsOf(ev))} />
                      <td className="card-title xl-ellipsis" data-label="عنوان" title={e.description || e.title}>
                        {e.title}
                        {e.description && <span className="xl-ro-note">{e.description}</span>}
                      </td>
                      <td data-label="تناوب">{freqText(e.frequency, e.interval)}</td>
                      <td data-label="سررسیدِ بعدی">
                        {formatJalali(e.next_run_date)}
                        {e.is_due && e.is_active && <span className="status-badge tone-warning rc-due">سررسید</span>}
                        {e.end_date && <span className="xl-ro-note">تا {formatJalali(e.end_date)}</span>}
                      </td>
                      <td data-label="آخرین تولید">{e.last_run_date ? formatJalali(e.last_run_date) : '—'}</td>
                      <td className="num" data-label="مبلغ">
                        {faAmount(e.amount)}
                      </td>
                      <td data-label="وضعیت" className="rc-state">
                        <button
                          type="button"
                          className={`xl-toggle${e.is_active ? ' is-on' : ''}`}
                          aria-pressed={e.is_active}
                          disabled={working}
                          title={e.is_active ? 'غیرفعال‌کردن — دیگر سند نمی‌سازد' : 'فعال‌کردن'}
                          onClick={() => void setActive([e], !e.is_active)}
                        >
                          {e.is_active ? 'فعال' : 'غیرفعال'}
                        </button>
                      </td>
                      <td className="card-actions ef-col-min">
                        <div className="row-actions ef-row-actions">
                          <RowAction icon={Pencil} label="ویرایش در فرم" onClick={() => onEdit(e)} />
                          <RowAction
                            icon={Play}
                            label="تولیدِ سررسیدهای همین قالب"
                            disabled={!e.is_active || working}
                            title={!e.is_active ? 'قالبِ غیرفعال سند نمی‌سازد.' : undefined}
                            onClick={() => void runSome([e])}
                          />
                          <RowAction icon={Trash2} label="حذف" danger disabled={working} onClick={() => void remove([e])} />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {chosen.length > 0 && (
            <SelectionBar count={chosen.length} unit="قالب" onClear={clear}>
              <span>
                جمع مبلغ <b className="num">{faAmount(chosen.reduce((s, e) => s + Number(e.amount), 0))}</b>
              </span>
              <button type="button" disabled={working} onClick={() => void runSome(chosen)}>
                <Play size={14} aria-hidden="true" /> تولید
              </button>
              <button type="button" disabled={working} onClick={() => void setActive(chosen, true)}>
                فعال
              </button>
              <button type="button" disabled={working} onClick={() => void setActive(chosen, false)}>
                غیرفعال
              </button>
              <button type="button" className="xl-selbar-danger" disabled={working} onClick={() => void remove(chosen)}>
                <Trash2 size={14} aria-hidden="true" /> حذف
              </button>
            </SelectionBar>
          )}
        </div>
      )}
    </SectionCard>
  )
}
