import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import { BarChart3, ChevronsLeft, History, Search, Target, Trash2 } from 'lucide-react'
import {
  createBudgetLine,
  deleteBudgetLine,
  fetchAccountsLive,
  fetchBudgetLines,
  fetchCostCenters,
  type BudgetLineRecord,
  type CostCenterRecord,
} from '../../api'
import { AccountCombo, type ComboOption } from '../../components/AccountCombo'
import { NumberInput } from '../../components/NumberInput'
import { SearchSelect } from '../../components/SearchSelect'
import { SectionCard } from '../../components/SectionCard'
import { SheetFooter, type SheetState } from '../../components/SheetFooter'
import { SelectionBar } from '../../components/XlGrid'
import { CountBadge, RowAction } from '../../components/form/FormKit'
import {
  MONTHS,
  blankFresh,
  budgetYears,
  cellChanged,
  cellText,
  copyFromYear,
  emptyDraft,
  fillEmptyMonths,
  freshIsBlank,
  parseBudgetDraft,
  pendingCount,
  pendingOps,
  rowTotal,
  savedRows,
  sheetProblems,
  withTrailingBlank,
  type BudgetDraft,
  type FreshRow,
  type SavedRow,
} from '../../lib/budgetSheet'
import { toNumber } from '../../lib/csv'
import { JALALI_MONTH_NAMES, isoToJalali, jalaliToIso, toFaDigits, todayIso } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { tenantKey } from '../../lib/tenantScope'
import { useSheetNav } from '../../lib/useSheetNav'
import { fa, faAmount, faInt, OpsPage, type Msg } from './kit'

/**
 * بودجه‌بندی — برگه‌ی اکسلیِ یک سالِ شمسی: هر ردیف یک حساب، هر ستون یک ماه، و جمعِ ردیف و ستون. همان
 * چیزی که حسابدار در اکسل می‌سازد، با تمِ «سند حسابداری» (الگوی «ب»: ویرایشِ درجا، ذخیره‌ی یک‌جا).
 *
 * * **دامنه:** سال و «کلِ کسب‌وکار» یا یک مرکزِ هزینه، سرِ کارت. سرور هر خانه را یک ردیفِ بودجه (حساب، اولِ
 *   ماه، مرکز) می‌داند و `POST` رویش upsert است؛ خانه‌ای که خالی شود ردیفش حذف می‌شود.
 * * **ردیفِ تازه:** حساب را در ردیفِ خالیِ ته انتخاب کنید و ماه‌ها را پر کنید. «تکرار در ماه‌های خالی»
 *   اولین مبلغِ ردیف را در بقیه‌ی ماه‌ها می‌نشاند؛ «از سالِ قبل» بودجه‌ی پارسال را در خانه‌های خالی می‌آورد.
 * * **ذخیره:** Ctrl+S یا دکمه‌ی نوار، پشتِ‌سرِ‌هم؛ خانه‌ای که سرور رد کرد ورودی‌اش را نگه می‌دارد و ردیفش
 *   قرمز می‌شود. پیش‌نویس در نشست می‌ماند.
 *
 * دوازده ستونِ مبلغ در عرضِ صفحه جا نمی‌شوند؛ برگه در قابِ خودش افقی می‌لغزد و «ردیف» و «حساب» مثلِ
 * «ثابت‌کردنِ ستون»ِ اکسل سرِ جایشان می‌مانند. منطقِ خالص در `lib/budgetSheet.ts`.
 */

type Col = 'account' | `m${number}`
const COLS: Col[] = ['account', ...Array.from({ length: MONTHS }, (_, i) => `m${i + 1}` as Col)]
const DRAFT_KEY = 'cubita.budget.draft'

type Row =
  | { kind: 'saved'; key: string; row: SavedRow; texts: string[] }
  | { kind: 'fresh'; key: string; fresh: FreshRow; texts: string[] }

let seq = 0
const newKey = () => `n-${Date.now().toString(36)}-${++seq}`

export function BudgetListPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey, section?: string) => void }) {
  const thisYear = isoToJalali(todayIso()).jy
  const [lines, setLines] = useState<BudgetLineRecord[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [accounts, setAccounts] = useState<{ id: string; code: string; name: string; is_group: number }[]>([])
  const [centers, setCenters] = useState<CostCenterRecord[]>([])
  const [draft, setDraft] = useState<BudgetDraft>(() => {
    const key = tenantKey(DRAFT_KEY)
    let d: BudgetDraft | null = null
    try {
      d = key ? parseBudgetDraft(sessionStorage.getItem(key)) : null
    } catch {
      d = null
    }
    return d ?? emptyDraft(thisYear, '')
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(null)
  const [find, setFind] = useState('')
  const gridRef = useRef<HTMLDivElement>(null)
  const findRef = useRef<HTMLInputElement>(null)
  const { jy, center } = draft

  async function reload() {
    try {
      const rows = await fetchBudgetLines(token)
      setLines(rows)
      setLoadError(null)
      return rows
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'خطای ناشناخته')
      return null
    }
  }

  useEffect(() => {
    void reload()
    fetchAccountsLive(token)
      .then(setAccounts)
      .catch(() => setAccounts([]))
    fetchCostCenters(token)
      .then((rows) => setCenters(rows.filter((c) => c.is_active)))
      .catch(() => setCenters([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  //: پیش‌نویس در نشستِ همین کسب‌وکار؛ برگه‌ی بی‌تغییر چیزی نگه نمی‌دارد.
  useEffect(() => {
    const key = tenantKey(DRAFT_KEY)
    if (!key) return
    try {
      const empty = Object.keys(draft.edits).length === 0 && draft.fresh.every(freshIsBlank)
      if (empty) sessionStorage.removeItem(key)
      else sessionStorage.setItem(key, JSON.stringify(draft))
    } catch {
      // ذخیره‌نشدنِ پیش‌نویس کار را خراب نمی‌کند.
    }
  }, [draft])

  const accountOptions: ComboOption[] = useMemo(
    () => accounts.filter((a) => !a.is_group).map((a) => ({ value: a.id, label: `${a.code} — ${a.name}` })),
    [accounts],
  )
  const labelOf = (id: string) => accountOptions.find((o) => o.value === id)?.label ?? 'حساب'

  const saved = useMemo(() => savedRows(lines ?? [], jy, center), [lines, jy, center])
  const fresh = useMemo(() => withTrailingBlank(draft.fresh, () => blankFresh(newKey())), [draft.fresh])
  const q = find.trim()
  const rows: Row[] = [
    ...saved
      .filter((r) => !q || r.code.includes(q) || r.name.includes(q))
      .map((r): Row => ({ kind: 'saved', key: `s:${r.account_id}`, row: r, texts: Array.from({ length: MONTHS }, (_, m) => cellText(r, m, draft)) })),
    ...fresh.map((f): Row => ({ kind: 'fresh', key: f.key, fresh: f, texts: f.cells })),
  ]
  const counts = pendingCount(saved, draft)
  const pending = counts.fresh + counts.edited
  const state: SheetState = Object.keys(errors).length > 0 ? 'err' : pending > 0 ? 'dirty' : 'clean'
  const monthTotals = Array.from({ length: MONTHS }, (_, m) => rows.reduce((s, r) => s + toNumber(r.texts[m] ?? ''), 0))
  const grand = monthTotals.reduce((a, b) => a + b, 0)

  const { selected, click, clear } = useRowSelection()
  const order = rows.map((r) => r.key)
  const picked = rows.filter((r) => selected.has(r.key))

  /** ردیفِ تازه‌ای که هنوز فقط ردیفِ خالیِ ته است، با اولین تایپ واردِ پیش‌نویس می‌شود. */
  const withFresh = (d: BudgetDraft, r: Extract<Row, { kind: 'fresh' }>, patch: (f: FreshRow) => FreshRow) => ({
    ...d,
    fresh: (d.fresh.some((f) => f.key === r.key) ? d.fresh : [...d.fresh, r.fresh]).map((f) => (f.key === r.key ? patch(f) : f)),
  })
  function setCell(r: Row, m: number, value: string) {
    setDraft((d) =>
      r.kind === 'saved'
        ? { ...d, edits: { ...d.edits, [r.row.account_id]: { ...d.edits[r.row.account_id], [String(m + 1)]: value } } }
        : withFresh(d, r, (f) => ({ ...f, cells: f.cells.map((c, i) => (i === m ? value : c)) })),
    )
  }
  function setAccount(r: Row, accountId: string) {
    if (r.kind === 'fresh') setDraft((d) => withFresh(d, r, (f) => ({ ...f, account_id: accountId })))
  }
  /** «تکرار در ماه‌های خالی» روی یک ردیف. */
  function fillRow(r: Row) {
    const next = fillEmptyMonths(r.texts)
    next.forEach((v, m) => {
      if (v !== r.texts[m]) setCell(r, m, v)
    })
  }
  /** حذفِ ردیف‌ها: ثبت‌شده همه‌ی ماه‌هایش خالی می‌شود (با ذخیره حذف)، تازه همان‌جا می‌رود. */
  function removeRows(targets: Row[]) {
    setDraft((d) => {
      const edits = { ...d.edits }
      for (const r of targets)
        if (r.kind === 'saved') edits[r.row.account_id] = Object.fromEntries(Array.from({ length: MONTHS }, (_, m) => [String(m + 1), '']))
      const gone = new Set(targets.filter((r) => r.kind === 'fresh').map((r) => r.key))
      return { ...d, edits, fresh: withTrailingBlank(d.fresh.filter((f) => !gone.has(f.key)), () => blankFresh(newKey())) }
    })
    clear()
  }

  /** عوض‌کردنِ سال یا مرکز — پیش‌نویسِ دامنه‌ی قبلی، اگر هست، با تأیید کنار می‌رود. */
  function setScope(nextJy: number, nextCenter: string) {
    if (nextJy === jy && nextCenter === center) return
    if (pending > 0 && !window.confirm('تغییراتِ ذخیره‌نشده‌ی این برگه کنار گذاشته شود؟')) return
    setDraft(emptyDraft(nextJy, nextCenter))
    setErrors({})
    setMsg(null)
    clear()
  }

  function copyPrevYear() {
    const { draft: next, filled } = copyFromYear(lines ?? [], jy - 1, saved, draft, newKey)
    if (filled === 0) {
      setMsg({ text: `در ${toFaDigits(jy - 1)} بودجه‌ای برای خانه‌های خالیِ این برگه نیست.`, kind: 'err' })
      return
    }
    setDraft(next)
    setMsg({ text: `${faInt(filled)} خانه از بودجه‌ی ${toFaDigits(jy - 1)} پر شد — بررسی کنید و ذخیره کنید.`, kind: 'ok' })
  }

  async function save() {
    const problems = sheetProblems(saved, draft, labelOf)
    const ops = pendingOps(saved, draft)
    if (ops.length === 0 && Object.keys(problems).length === 0) {
      setMsg({ text: 'تغییری برای ذخیره نیست.', kind: 'ok' })
      return
    }
    setBusy(true)
    setMsg(null)
    //: متنِ خامِ هر خانه پیش از ارسال — خانه‌ای که رد شد با همین برمی‌گردد.
    const rawOf = (acc: string, month: number) =>
      draft.edits[acc]?.[String(month)] ?? draft.fresh.find((f) => f.account_id === acc)?.cells[month - 1] ?? ''
    const failed: { acc: string; month: number; raw: string; error: string }[] = []
    let done = 0
    //: یکی‌یکی و نه موازی: خطای هر خانه مالِ همان خانه است.
    for (const op of ops) {
      try {
        if (op.kind === 'delete') await deleteBudgetLine(token, op.id)
        else
          await createBudgetLine(token, {
            account_id: op.account_id,
            period_date: jalaliToIso(jy, op.month, 1),
            amount: op.amount,
            notes: op.notes,
            cost_center_id: center || null,
          })
        done++
      } catch (err) {
        failed.push({ acc: op.account_id, month: op.month, raw: rawOf(op.account_id, op.month), error: err instanceof Error ? err.message : 'خطای ناشناخته' })
      }
    }
    const reloaded = (await reload()) ?? lines ?? []
    const nextSaved = new Set(savedRows(reloaded, jy, center).map((r) => r.account_id))
    //: ردیف‌های تازه‌ای که به سرور نرفتند (بی‌حساب، تکراری) همان‌طور می‌مانند؛ خانه‌های ردشده برمی‌گردند —
    //: روی ردیفِ ثبت‌شده به‌صورتِ ویرایش، و اگر حساب هنوز هیچ ماهی ندارد، در ردیفِ تازه.
    const edits: BudgetDraft['edits'] = {}
    const keep: FreshRow[] = draft.fresh.filter((f) => problems[f.key])
    const rowErrors: Record<string, string> = { ...problems }
    for (const f of failed) {
      const where = `${JALALI_MONTH_NAMES[f.month - 1]}: ${f.error}`
      if (nextSaved.has(f.acc)) {
        edits[f.acc] = { ...edits[f.acc], [String(f.month)]: f.raw }
        rowErrors[`s:${f.acc}`] = rowErrors[`s:${f.acc}`] ? `${rowErrors[`s:${f.acc}`]} — ${where}` : where
      } else {
        let row = keep.find((r) => r.account_id === f.acc)
        if (!row) {
          row = { ...blankFresh(newKey()), account_id: f.acc }
          keep.push(row)
        }
        row.cells[f.month - 1] = f.raw
        rowErrors[row.key] = rowErrors[row.key] ? `${rowErrors[row.key]} — ${where}` : where
      }
    }
    setDraft((d) => ({ ...d, edits, fresh: withTrailingBlank(keep, () => blankFresh(newKey())) }))
    setErrors(rowErrors)
    setBusy(false)
    const bad = Object.keys(rowErrors).length
    setMsg(
      bad > 0
        ? { text: `${faInt(bad)} ردیف کامل ذخیره نشد — دلیلش زیرِ برگه است.${done ? ` ${faInt(done)} خانه ذخیره شد.` : ''}`, kind: 'err' }
        : { text: `${faInt(done)} خانه‌ی بودجه ذخیره شد.`, kind: 'ok' },
    )
  }

  const savedCount = saved.length
  const nav = useSheetNav<Col>({
    gridRef,
    cols: COLS,
    rowCount: rows.length,
    //: حسابِ ردیفِ ثبت‌شده عوض نمی‌شود (ردیف همان حساب است)؛ فقط ردیفِ تازه حساب می‌گیرد.
    enabled: (row, col) => col !== 'account' || rows[row]?.kind === 'fresh',
    //: همیشه یک ردیفِ خالیِ ته هست — «ردیفِ تازه» یعنی رفتن به همان.
    onAppendRow: () => rows.length - 1,
    onDeleteRow: (row) => {
      const r = rows[row]
      if (!r || (r.kind === 'fresh' && freshIsBlank(r.fresh))) return false
      removeRows(picked.length > 0 ? picked : [r])
      return true
    },
    rowHasContent: (row) => {
      const r = rows[row]
      return Boolean(r && (r.kind === 'saved' || !freshIsBlank(r.fresh)))
    },
  })
  const years = budgetYears(lines ?? [], thisYear)

  return (
    <OpsPage
      canvas
      icon={Target}
      title="بودجه‌بندی"
      description="بودجه‌ی ماهانه‌ی هر حساب در یک سال — مثلِ برگه‌ی اکسل: هر ردیف یک حساب، هر ستون یک ماه. مقایسه با عملکرد در «گزارش‌ها» است."
    >
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          if (!busy) void save()
        }}
        onKeyDown={(e) => {
          if (!(e.ctrlKey || e.metaKey)) return
          if (e.code === 'KeyS') {
            e.preventDefault()
            if (!busy) void save()
          } else if (e.code === 'KeyF') {
            e.preventDefault()
            findRef.current?.focus()
            findRef.current?.select()
          }
        }}
      >
        <SectionCard
          icon={Target}
          title={`بودجه‌ی ${toFaDigits(jy)}`}
          tip="هر خانه مبلغِ برنامه‌ریزی‌شده‌ی یک حساب در یک ماه است. حسابِ تازه را در ردیفِ خالیِ ته انتخاب کنید؛ خانه‌ای را که خالی کنید، بودجه‌ی آن ماه حذف می‌شود. «ذخیره تغییرات» (Ctrl+S) همه را یک‌جا ثبت می‌کند."
          badge={<CountBadge accent>{faInt(savedCount)} حساب</CountBadge>}
          actions={
            <div className="jg-head-actions bg-head">
              <SearchSelect
                className="bg-scope"
                value={String(jy)}
                onChange={(e) => setScope(Number(e.target.value), center)}
                aria-label="سالِ بودجه"
              >
                {years.map((y) => (
                  <option key={y} value={y}>
                    سالِ {toFaDigits(y)}
                  </option>
                ))}
              </SearchSelect>
              {centers.length > 0 && (
                <SearchSelect
                  className="bg-scope"
                  value={center}
                  onChange={(e) => setScope(jy, e.target.value)}
                  aria-label="دامنه‌ی بودجه"
                >
                  <option value="">کلِ کسب‌وکار</option>
                  {centers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code ? `${c.code} — ${c.name}` : c.name}
                    </option>
                  ))}
                </SearchSelect>
              )}
              <div className={`jg-find${find ? ' has-query' : ''}`} role="search">
                <Search size={14} aria-hidden="true" />
                <input
                  ref={findRef}
                  type="search"
                  value={find}
                  onChange={(e) => setFind(e.target.value)}
                  placeholder="کد یا نامِ حساب"
                  aria-label="جست‌وجوی حساب در برگه"
                />
              </div>
              <button type="button" className="ef-btn-secondary" onClick={copyPrevYear} title="بودجه‌ی سالِ قبل در خانه‌های خالیِ همین برگه">
                <History size={14} /> از سالِ قبل
              </button>
              {onNavigate && (
                <button type="button" className="ef-btn-secondary" onClick={() => onNavigate('reports', 'budget')}>
                  <BarChart3 size={14} /> مقایسه با عملکرد
                </button>
              )}
            </div>
          }
        >
          {loadError && <p className="ef-message ef-message--warn ef-block-note">{loadError}</p>}
          {lines === null && !loadError ? (
            <p className="muted">در حال بارگذاری…</p>
          ) : (
            <div className="jg">
              <div
                ref={gridRef}
                className="table-scroll ef-table-wrap jg-wrap"
                onKeyDown={nav.onKeyDown}
                role="grid"
                aria-label={`بودجه‌ی ${toFaDigits(jy)}`}
              >
                <table className="ef-table ef-table--edit jg-table xl-grid table-plain bg-sheet">
                  <colgroup>
                    <col className="bg-c-num" />
                    <col className="bg-c-account" />
                    {JALALI_MONTH_NAMES.map((m) => (
                      <col key={m} className="bg-c-month" />
                    ))}
                    <col className="bg-c-total" />
                    <col className="bg-c-act" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th className="xl-rowhead bg-pin bg-pin--num" data-col="num">
                        ردیف
                      </th>
                      <th className="bg-pin bg-pin--account" data-col="account">
                        حساب
                      </th>
                      {JALALI_MONTH_NAMES.map((m, i) => (
                        <th key={m} data-col={`m${i + 1}`}>
                          {m}
                        </th>
                      ))}
                      <th data-col="total">جمعِ سال</th>
                      <th data-col="actions" aria-label="کنش‌ها" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <SheetRow
                        key={r.key}
                        r={r}
                        i={i}
                        options={accountOptions}
                        selected={selected.has(r.key)}
                        error={errors[r.key]}
                        draft={draft}
                        onPick={(e) => click(order, r.key, modsOf(e))}
                        onCell={(m, v) => setCell(r, m, v)}
                        onAccount={(v) => setAccount(r, v)}
                        onCommitAccount={(how) => nav.commit(i, 'account', how)}
                        onFill={() => fillRow(r)}
                        onRemove={() => removeRows([r])}
                      />
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="bg-total-row">
                      <td className="bg-pin bg-pin--num" />
                      <th scope="row" className="bg-pin bg-pin--account">
                        جمعِ ماه
                      </th>
                      {monthTotals.map((t, m) => (
                        <td key={m} className="num xl-ro">
                          {faAmount(t)}
                        </td>
                      ))}
                      <td className="num xl-ro bg-grand">{faAmount(grand)}</td>
                      <td />
                    </tr>
                  </tfoot>
                </table>
              </div>
              {picked.length > 0 && (
                <SelectionBar count={picked.length} unit="حساب" onClear={clear}>
                  <span>
                    جمعِ سال <b className="num">{fa(picked.reduce((s, r) => s + rowTotal(r.texts), 0))}</b>
                  </span>
                  <button type="button" className="xl-selbar-danger" onClick={() => removeRows(picked)}>
                    <Trash2 size={14} aria-hidden="true" /> حذفِ بودجه‌ی این ردیف‌ها (Ctrl+Delete)
                  </button>
                </SelectionBar>
              )}
            </div>
          )}
          {Object.keys(errors).length > 0 && (
            <ul className="xl-errbar" role="alert">
              {Object.entries(errors).map(([key, text]) => {
                const r = rows.find((x) => x.key === key)
                const name = r ? (r.kind === 'saved' ? `${r.row.code} — ${r.row.name}` : r.fresh.account_id ? labelOf(r.fresh.account_id) : 'ردیفِ تازه') : 'ردیف'
                return (
                  <li key={key}>
                    <b>{name}</b>: {text}
                  </li>
                )
              })}
            </ul>
          )}
        </SectionCard>

        <SheetFooter
          state={state}
          fresh={counts.fresh}
          edited={counts.edited}
          submitting={busy}
          message={msg}
          labels={['خانه‌ی تازه', 'ویرایش/حذف']}
        />
      </form>
    </OpsPage>
  )
}

function SheetRow({
  r,
  i,
  options,
  selected,
  error,
  draft,
  onPick,
  onCell,
  onAccount,
  onCommitAccount,
  onFill,
  onRemove,
}: {
  r: Row
  i: number
  options: ComboOption[]
  selected: boolean
  error?: string
  draft: BudgetDraft
  onPick: (e: MouseEvent) => void
  onCell: (m: number, value: string) => void
  onAccount: (v: string) => void
  onCommitAccount: (how: 'enter' | 'tab') => void
  onFill: () => void
  onRemove: () => void
}) {
  const isBlank = r.kind === 'fresh' && freshIsBlank(r.fresh)
  const changed = (m: number) =>
    r.kind === 'saved'
      ? draft.edits[r.row.account_id]?.[String(m + 1)] !== undefined && cellChanged(r.row.cells[m], r.texts[m])
      : false
  const dirty = r.kind === 'saved' && r.texts.some((_, m) => changed(m))
  const cls = [
    selected && 'is-selected',
    r.kind === 'fresh' && !isBlank && 'xl-row--new',
    dirty && 'xl-row--dirty',
    error && 'xl-row--error',
  ]
    .filter(Boolean)
    .join(' ')
  const label = r.kind === 'saved' ? `${r.row.code} — ${r.row.name}` : 'ردیفِ تازه'
  return (
    <tr className={cls || undefined} title={error}>
      <td className="jg-num xl-rowhead bg-pin bg-pin--num card-title">
        <button
          type="button"
          tabIndex={-1}
          className="xl-rowhead-btn"
          aria-pressed={selected}
          aria-label={`انتخابِ ردیفِ ${fa(i + 1)}`}
          onClick={onPick}
        >
          {fa(i + 1)}
        </button>
      </td>
      {r.kind === 'saved' ? (
        <td className="xl-txt bg-pin bg-pin--account" data-cell={`${i}-0`} title={label}>
          <span className="bg-code">{r.row.code}</span> {r.row.name}
        </td>
      ) : (
        <td className="bg-pin bg-pin--account" data-cell={`${i}-0`}>
          <AccountCombo
            aria-label={`حسابِ ردیفِ ${fa(i + 1)}`}
            value={r.fresh.account_id}
            options={options}
            onChange={onAccount}
            onCommit={onCommitAccount}
          />
        </td>
      )}
      {r.texts.map((t, m) => {
        const note = r.kind === 'saved' ? r.row.cells[m]?.notes : undefined
        return (
          <td
            key={m}
            data-cell={`${i}-${m + 1}`}
            data-label={JALALI_MONTH_NAMES[m]}
            className={changed(m) ? 'is-changed' : undefined}
            title={note || undefined}
          >
            <NumberInput
              aria-label={`${JALALI_MONTH_NAMES[m]} — ${label}`}
              value={t}
              onChange={(v) => onCell(m, v)}
            />
          </td>
        )
      })}
      <td className="num xl-ro" data-label="جمعِ سال">
        {faAmount(rowTotal(r.texts))}
      </td>
      <td className="jg-actions card-actions">
        <div className="row-actions">
          <RowAction
            icon={ChevronsLeft}
            label="تکرار در ماه‌های خالی"
            title="اولین مبلغِ این ردیف در همه‌ی ماه‌های خالی"
            disabled={!r.texts.some((t) => t.trim())}
            onClick={onFill}
          />
          <RowAction
            icon={Trash2}
            label="حذفِ بودجه‌ی این ردیف"
            danger
            disabled={isBlank}
            title="همه‌ی ماه‌های این حساب خالی شود (Ctrl+Delete)"
            onClick={onRemove}
          />
        </div>
      </td>
    </tr>
  )
}
