import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent } from 'react'
import { ArrowLeftRight, Folder, FolderTree, ListFilter, Search, Undo2 } from 'lucide-react'
import { fetchChartAccounts, reclassifyAccounts } from '../../api'
import { AccountCombo, type ComboCommit, type ComboOption } from '../../components/AccountCombo'
import { SectionCard } from '../../components/SectionCard'
import { SheetFooter, type SheetState } from '../../components/SheetFooter'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { CountBadge, RowAction } from '../../components/form/FormKit'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import {
  TYPE_LABELS,
  descendantsOf,
  errorAccountId,
  matches,
  parseDraft,
  pendingParent,
  planReclassify,
  treeRows,
  type Acc,
  type Edits,
} from '../../lib/reclassifySheet'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { tenantKey } from '../../lib/tenantScope'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { useSheetNav } from '../../lib/useSheetNav'
import { AsyncBlock, faInt, OpsPage, useAsync, type Msg } from './kit'

/**
 * «انتقال حساب به سرفصل دیگر» — **برگه‌ی اکسلی** (الگوی ب): هر حسابِ قابلِ جابه‌جایی یک ردیف، به ترتیب و
 * تورفتگیِ درختواره، و فقط خانه‌ی «سرفصلِ تازه» ویرایش می‌شود.
 *
 * پیش‌تر جدولی صفحه‌به‌صفحه با یک `<select>` در هر ردیف بود. حالا هم‌سبکِ «سند حسابداری» (خواسته‌ی آرش:
 * صفحه‌ها یکی‌یکی با همان تم): کادرِ جست‌وجوی درجا در خانه (تایپِ کد یا نام، Enter و ردیفِ بعد)، انتخابِ
 * چند ردیف با شماره و بردنِ همه زیرِ یک سرفصل از نوارِ انتخاب، ستونِ «نوع» که **پیش از ذخیره** می‌گوید نوعِ
 * کدام حساب عوض می‌شود (زیرمجموعه‌های سرفصلِ جابه‌جاشده هم)، و حلقه‌ای که همان لحظه قرمز می‌شود.
 * «ذخیره تغییرات» (Ctrl+S) همه را در **یک** درخواست می‌فرستد — سرور دسته را یک‌جا و اتمی اعمال می‌کند.
 *
 * حسابِ نقش‌دار (صندوق، بانک، …) ردیف ندارد: ثبتِ خودکار به آن تکیه دارد و سرور جابه‌جایی‌اش را رد می‌کند.
 * سرفصلِ نقش‌دار اما مقصد می‌شود. پیش‌نویس در `sessionStorage`ِ همین کسب‌وکار می‌ماند.
 */

type Col = 'to'
const COLS: Col[] = ['to']
const LAYOUT = { fixed: ['num', 'actions'], auto: 'name' } as const
const DRAFT_KEY = 'cubita.reclassify.draft'
//: گزینه‌ی «ریشه» در کادرِ ترکیبی — مقدارِ خالیِ کادر آن‌جا یعنی «هنوز چیزی انتخاب نشده»، نه ریشه.
const ROOT = '__root__'
const ROOT_LABEL = '— ریشه (بی‌سرفصل) —'

/** نوارِ پایین روی برگه: [دکمه] زیرِ ردیف+کد+نام، وضعیت زیرِ سرفصلِ فعلی، جابه‌جا زیرِ سرفصلِ تازه، تغییرِ نوع زیرِ نوع. */
const SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('num') + w('code') + w('name'), w('from'), w('to'), w('type'), w('actions')]
}

function loadDraft(): Edits {
  const key = tenantKey(DRAFT_KEY)
  try {
    return (key && parseDraft(sessionStorage.getItem(key))) || {}
  } catch {
    return {}
  }
}

const labelOf = (a: Acc | undefined) => (a ? `${a.code} — ${a.name}` : '—')

export function ReclassifyPage({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const list = useAsync(() => fetchChartAccounts(token), [token])
  const [edits, setEdits] = useState<Edits>(loadDraft)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [find, setFind] = useState('')
  const [onlyChanged, setOnlyChanged] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(() =>
    Object.keys(loadDraft()).length > 0
      ? { text: 'جابه‌جایی‌های ذخیره‌نشده‌ی دفعه‌ی قبل برگشت — «ذخیره تغییرات» بزنید.', kind: 'ok' }
      : null,
  )
  const formRef = useRef<HTMLFormElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const findRef = useRef<HTMLInputElement>(null)
  const cw = useColumnWidths('cubita.grid.reclassify.shares', LAYOUT)
  const { selected, click, clear } = useRowSelection()
  useAlignToGrid(formRef, '.jf-foot--cols', { table: '.rx-sheet', slots: SLOTS })

  //: پیش‌نویس با هر تغییر در نشستِ همین کسب‌وکار؛ خالی = پاک.
  useEffect(() => {
    const key = tenantKey(DRAFT_KEY)
    if (!key) return
    try {
      if (Object.keys(edits).length === 0) sessionStorage.removeItem(key)
      else sessionStorage.setItem(key, JSON.stringify(edits))
    } catch {
      //: ذخیره‌نشدنِ پیش‌نویس فقط یعنی با بستنِ صفحه می‌رود؛ برگه باید کار کند.
    }
  }, [edits])

  const all: Acc[] = useMemo(() => list.data ?? [], [list.data])
  const byId = useMemo(() => new Map(all.map((a) => [a.id, a])), [all])
  const tree = useMemo(() => treeRows(all), [all])
  const movable = useMemo(() => tree.filter((r) => !r.acc.system_role), [tree])
  const options: ComboOption[] = useMemo(
    () => [
      { value: ROOT, label: ROOT_LABEL },
      ...tree.filter((r) => r.acc.is_group).map((r) => ({ value: r.acc.id, label: labelOf(r.acc) })),
    ],
    [tree],
  )
  //: سرفصل زیرِ خودش یا زیرمجموعه‌اش نمی‌رود — هر سرفصل فهرستِ خودش را دارد، حسابِ ساده همان فهرستِ مشترک.
  const groupOptions = useMemo(() => {
    const m = new Map<string, ComboOption[]>()
    for (const r of movable) {
      if (!r.acc.is_group) continue
      const bad = descendantsOf(all, r.acc.id).add(r.acc.id)
      m.set(r.acc.id, options.filter((o) => !bad.has(o.value)))
    }
    return m
  }, [all, movable, options])

  //: پیش‌نویسِ کهنه: حسابی که دیگر نیست یا حالا نقش‌دار است ردیفی ندارد که درستش کنی — کنار می‌رود.
  const live = useMemo(() => {
    if (!list.data) return edits
    const out: Edits = {}
    for (const [id, p] of Object.entries(edits)) if (byId.get(id) && !byId.get(id)!.system_role) out[id] = p
    return out
  }, [edits, byId, list.data])
  const plan = useMemo(() => planReclassify(all, live), [all, live])
  const moved = plan.moves.size
  const showOnly = onlyChanged && moved > 0
  const rows = useMemo(
    () =>
      movable.filter(
        ({ acc }) =>
          (!showOnly || plan.moves.has(acc.id) || plan.typeChanged.has(acc.id)) &&
          matches(acc, acc.parent_id ? (byId.get(acc.parent_id)?.name ?? '') : '', find),
      ),
    [movable, showOnly, plan, byId, find],
  )
  const order = rows.map((r) => r.acc.id)
  const picked = rows.filter((r) => selected.has(r.acc.id)).map((r) => r.acc)
  //: جست‌وجو یا فیلترِ تازه یعنی برگه‌ی دیگری؛ انتخابِ قبلی معنا ندارد.
  useEffect(() => clear(), [rows.length, clear])

  //: مشکل‌های پیش از ارسال (حلقه، سرفصلِ ناپیدا) زنده‌اند؛ خطای سرور تا ویرایشِ بعدیِ همان ردیف می‌ماند.
  const problems = { ...errors, ...plan.problems }
  const problemIds = Object.keys(problems)
  const state: SheetState = problemIds.length > 0 ? 'err' : moved > 0 ? 'dirty' : 'clean'

  function setParents(targets: readonly Acc[], parent: string) {
    setErrors((e) => omit(e, targets.map((a) => a.id)))
    setEdits((d) => {
      const next = { ...d }
      for (const a of targets) {
        if ((parent || null) === a.parent_id) delete next[a.id]
        else next[a.id] = parent
      }
      return next
    })
  }

  function choose(acc: Acc, value: string) {
    setParents([acc], value === ROOT ? '' : value)
  }

  /** بردنِ همه‌ی انتخاب‌شده‌ها زیرِ یک سرفصل؛ خودِ مقصد و سرفصل‌هایی که مقصد زیرشان است کنار می‌روند. */
  function moveMany(targets: readonly Acc[], value: string) {
    const parent = value === ROOT ? '' : value
    const ok = targets.filter((a) => !parent || (a.id !== parent && !descendantsOf(all, a.id).has(parent)))
    setParents(ok, parent)
    const where = parent ? `«${byId.get(parent)?.name ?? ''}»` : 'ریشه'
    const skipped = targets.length - ok.length
    setMsg({
      text:
        `${faInt(ok.length)} حساب زیرِ ${where} رفت — با «ذخیره تغییرات» ثبت می‌شود.` +
        (skipped > 0 ? ` ${faInt(skipped)} سرفصل کنار ماند، چون مقصد خودش یا زیرمجموعه‌اش است.` : ''),
      kind: 'ok',
    })
  }

  function revert(targets: readonly Acc[]) {
    const ids = targets.map((a) => a.id)
    setErrors((e) => omit(e, ids))
    setEdits((d) => omit(d, ids))
  }

  async function save() {
    if (moved === 0) {
      setMsg({ text: 'هیچ حسابی سرفصلِ تازه نگرفته است.', kind: 'ok' })
      return
    }
    if (Object.keys(plan.problems).length > 0) {
      setMsg({ text: 'ردیفِ قرمز را درست کنید — تا وقتی درخت حلقه دارد یا مقصدی نیست، چیزی فرستاده نمی‌شود.', kind: 'err' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const out = await reclassifyAccounts(token, plan.items)
      const types = plan.typeChanged.size
      setEdits({})
      setErrors({})
      list.reload()
      onChanged?.()
      setMsg({
        text: `${faInt(out.count)} حساب جابه‌جا شد.${types > 0 ? ` نوعِ ${faInt(types)} حساب هم عوض شد.` : ''}`,
        kind: 'ok',
      })
    } catch (err) {
      const text = err instanceof Error ? err.message : 'خطای ناشناخته'
      //: سرور دسته را اتمی رد می‌کند — هیچ‌چیز ننشسته. ردیفی که نامش در پیام است قرمز می‌شود.
      const id = errorAccountId(
        text,
        [...plan.moves.keys()].flatMap((k) => byId.get(k) ?? []),
      )
      setErrors(id ? { [id]: text } : {})
      setMsg({ text: id ? 'ذخیره نشد و چیزی جابه‌جا نشد — دلیلش زیرِ برگه است.' : `ذخیره نشد — ${text}`, kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const nav = useSheetNav<Col>({
    gridRef,
    cols: COLS,
    rowCount: rows.length,
    //: برگه ردیفِ تازه ندارد (حساب در درختواره ساخته می‌شود)؛ «ردیفِ تازه» همان ردیفِ آخر است.
    onAppendRow: () => rows.length - 1,
    //: Ctrl+Delete = برگرداندنِ همین ردیف (یا انتخاب‌شده‌ها) به سرفصلِ فعلی. `false` تا فوکوس سرِ جایش بماند.
    onDeleteRow: (row) => {
      const targets = picked.length > 0 ? picked : rows[row] ? [rows[row].acc] : []
      revert(targets.filter((a) => a.id in live))
      return false
    },
    rowHasContent: () => false,
  })

  const head = (id: string, label: string, next: string, title?: string, className?: string) => (
    <th data-col={id} title={title} className={className}>
      {label}
      {cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )

  return (
    <OpsPage
      canvas
      icon={ArrowLeftRight}
      title="انتقال حساب به سرفصل دیگر"
      description="خودِ حساب‌ها را زیرِ سرفصلِ درست می‌برد و نوعشان را از سرفصلِ مقصد می‌گیرد. سندی صادر نمی‌شود و گزارش‌های گذشته هم از این پس با طبقه‌بندیِ تازه دیده می‌شوند — برای بردنِ مانده به حسابِ دیگر، «انتقال مانده به حساب دیگر» را باز کنید."
    >
      <form
        ref={formRef}
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          if (!busy) void save()
        }}
        onKeyDown={(e) => {
          if (!(e.ctrlKey || e.metaKey)) return
          //: Ctrl+F «یافتنِ» مرورگر را کنار می‌زند و به جست‌وجوی همین برگه می‌رود.
          if (e.code === 'KeyF') {
            e.preventDefault()
            findRef.current?.focus()
            findRef.current?.select()
          } else if (e.code === 'KeyS') {
            e.preventDefault()
            if (!busy) void save()
          }
        }}
      >
        <SectionCard
          icon={FolderTree}
          title="حساب‌ها و سرفصل‌ها"
          tip="در ستونِ «سرفصلِ تازه» کد یا نامِ سرفصل را تایپ کنید و Enter بزنید. برای بردنِ چند حساب با هم، شماره‌ی ردیف‌ها را انتخاب کنید (Ctrl و Shift). ستونِ «نوع» پیش از ذخیره می‌گوید نوعِ کدام حساب عوض می‌شود. حساب‌های نقش‌دار (صندوق، بانک، …) این‌جا نیستند؛ ثبتِ خودکار به آن‌ها گره خورده."
          badge={<CountBadge accent>{faInt(movable.length)} حساب</CountBadge>}
          actions={
            <div className="jg-head-actions">
              {moved > 0 && (
                <button
                  type="button"
                  className="rx-only"
                  aria-pressed={showOnly}
                  onClick={() => setOnlyChanged((v) => !v)}
                  title="فقط حساب‌هایی که جابه‌جا می‌شوند یا نوعشان عوض می‌شود"
                >
                  <ListFilter size={14} aria-hidden="true" /> فقط تغییرها ({faInt(moved)})
                </button>
              )}
              <div className={`jg-find${find ? ' has-query' : ''}`} role="search">
                <Search size={14} aria-hidden="true" />
                <input
                  ref={findRef}
                  type="search"
                  value={find}
                  onChange={(e) => setFind(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') e.preventDefault()
                    else if (e.key === 'Escape') {
                      e.preventDefault()
                      setFind('')
                      nav.focusCell(0, 0)
                    }
                  }}
                  placeholder="جست‌وجو: کد، نام، سرفصل"
                  aria-label="جست‌وجو در حساب‌ها — کد، نام یا سرفصلِ فعلی"
                  aria-keyshortcuts="Control+F"
                  title="Ctrl+F — Esc: پاک‌کردن"
                />
                {find && (
                  <span className="jg-find-count" aria-live="polite">
                    {faInt(rows.length)} مورد
                  </span>
                )}
              </div>
            </div>
          }
        >
          <AsyncBlock
            loading={list.loading && !list.data}
            error={list.data ? null : list.error}
            empty={movable.length === 0}
            emptyText="حسابِ قابلِ جابه‌جایی نیست — حساب‌ها را در «درختواره حساب‌ها» بسازید."
          >
            <div className="jg">
              <div
                ref={gridRef}
                className="table-scroll ef-table-wrap jg-wrap"
                onKeyDown={nav.onKeyDown}
                role="grid"
                aria-label="برگه‌ی حساب‌ها و سرفصل‌ها"
              >
                <table ref={cw.frame} className="ef-table ef-table--edit jg-table xl-grid table-plain rx-sheet">
                  <colgroup>
                    <col className="jg-c-num" style={cw.col('num')} />
                    <col className="jg-c-code rx-mhide" style={cw.col('code')} />
                    <col className="jg-c-account" style={cw.col('name')} />
                    <col className="jg-c-parent rx-mhide" style={cw.col('from')} />
                    <col className="jg-c-parent" style={cw.col('to')} />
                    <col className="jg-c-kind" style={cw.col('type')} />
                    <col className="jg-c-act1" style={cw.col('actions')} />
                  </colgroup>
                  <thead>
                    <tr>
                      <th className="ef-col-min xl-rowhead" data-col="num">
                        ردیف
                      </th>
                      {head('code', 'کد', 'name', undefined, 'rx-mhide')}
                      {head('name', 'نامِ حساب', 'from')}
                      {head('from', 'سرفصلِ فعلی', 'to', undefined, 'rx-mhide')}
                      {head('to', 'سرفصلِ تازه', 'type', 'کد یا نام را تایپ کنید؛ Enter انتخاب می‌کند و به ردیفِ بعد می‌رود.')}
                      {head('type', 'نوع', 'actions', 'نوعِ حساب از سرفصلِ مقصد می‌آید؛ زیرمجموعه‌های سرفصلِ جابه‌جاشده هم هم‌نوعش می‌شوند.')}
                      <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="rx-empty card-full">
                          {showOnly ? 'تغییری با این جست‌وجو نیست.' : 'حسابی با این جست‌وجو پیدا نشد.'}
                        </td>
                      </tr>
                    ) : (
                      rows.map(({ acc, depth }, i) => (
                        <SheetRow
                          key={acc.id}
                          acc={acc}
                          depth={depth}
                          i={i}
                          selected={selected.has(acc.id)}
                          error={problems[acc.id]}
                          to={pendingParent(acc, live)}
                          from={acc.parent_id ? labelOf(byId.get(acc.parent_id)) : ROOT_LABEL}
                          finalType={plan.finalType.get(acc.id) ?? acc.type}
                          options={groupOptions.get(acc.id) ?? options}
                          onPick={(e) => click(order, acc.id, modsOf(e))}
                          onChoose={(v) => choose(acc, v)}
                          onCommit={(how) => nav.commit(i, 'to', how)}
                          onRevert={() => revert([acc])}
                        />
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              {picked.length > 0 && (
                <SelectionBar count={picked.length} unit="حساب" onClear={clear}>
                  <div className="rx-bulk">
                    <AccountCombo
                      aria-label="بردنِ حساب‌های انتخاب‌شده زیرِ سرفصل"
                      placeholder="بردنِ همه زیرِ سرفصلِ…"
                      emptyText="سرفصلی با این کد یا نام پیدا نشد."
                      value=""
                      options={options}
                      onChange={(v) => moveMany(picked, v)}
                    />
                  </div>
                  <button type="button" onClick={() => revert(picked)} disabled={!picked.some((a) => a.id in live)}>
                    <Undo2 size={14} aria-hidden="true" /> برگرداندن (Ctrl+Delete)
                  </button>
                </SelectionBar>
              )}
            </div>
            {problemIds.length > 0 && (
              <ul className="xl-errbar" role="alert">
                {problemIds.map((id) => (
                  <li key={id}>
                    <b>{labelOf(byId.get(id))}</b> — {problems[id]}
                  </li>
                ))}
              </ul>
            )}
          </AsyncBlock>
        </SectionCard>

        <SheetFooter
          state={state}
          fresh={moved}
          edited={plan.typeChanged.size}
          pending={moved}
          labels={['حسابِ جابه‌جا', 'تغییرِ نوع']}
          submitting={busy}
          message={msg}
          columns
        />
      </form>
    </OpsPage>
  )
}

/** یک ردیفِ برگه. خانه‌ی سرفصلِ عوض‌شده و نوعِ عوض‌شده `is-changed` می‌گیرند (ته‌رنگِ اکسلیِ «ویرایش‌شده»). */
function SheetRow({
  acc,
  depth,
  i,
  selected,
  error,
  to,
  from,
  finalType,
  options,
  onPick,
  onChoose,
  onCommit,
  onRevert,
}: {
  acc: Acc
  depth: number
  i: number
  selected: boolean
  error?: string
  /** سرفصلِ تازه؛ `undefined` = بی‌تغییر، `null` = ریشه. */
  to: string | null | undefined
  from: string
  finalType: string
  options: ComboOption[]
  onPick: (e: MouseEvent) => void
  onChoose: (value: string) => void
  onCommit: (how: ComboCommit) => void
  onRevert: () => void
}) {
  const moved = to !== undefined
  const current = moved ? (to ?? ROOT) : (acc.parent_id ?? ROOT)
  const retyped = finalType !== acc.type
  const cls = [selected && 'is-selected', moved && 'xl-row--dirty', error && 'xl-row--error'].filter(Boolean).join(' ')
  return (
    <tr className={cls || undefined} title={error}>
      <td className="ef-col-min jg-num xl-rowhead card-title">
        <button
          type="button"
          tabIndex={-1}
          className="xl-rowhead-btn"
          aria-pressed={selected}
          aria-label={`انتخابِ ردیفِ ${faInt(i + 1)}`}
          onClick={onPick}
        >
          {faInt(i + 1)}
        </button>
      </td>
      <td className="xl-txt rx-mhide" dir="ltr" data-label="کد">
        {acc.code}
      </td>
      {/* تورفتگی = عمق در درختواره (`--rx-depth`؛ در موبایل کم‌عمق‌تر)؛ سرفصل پررنگ با نشانه‌ی پوشه. در موبایل
          ستونِ کد پنهان است و کد جلوی نام می‌آید. */}
      <td
        className={`xl-txt rx-name${acc.is_group ? ' rx-name--group' : ''}`}
        style={{ '--rx-depth': depth } as CSSProperties}
        title={`${acc.code} — ${acc.name}`}
        data-label="نامِ حساب"
      >
        <span className="rx-code-inline">{acc.code}</span>
        {acc.is_group && <Folder size={14} aria-hidden="true" />}
        {acc.name}
      </td>
      <td className="xl-txt rx-from rx-mhide" title={from} data-label="سرفصلِ فعلی">
        {from}
      </td>
      <td data-cell={`${i}-0`} className={moved ? 'is-changed' : undefined} data-label="سرفصلِ تازه">
        <AccountCombo
          aria-label={`سرفصلِ تازه‌ی «${acc.name}»`}
          placeholder="کد یا نامِ سرفصل…"
          emptyText="سرفصلی با این کد یا نام پیدا نشد."
          value={current}
          options={options}
          onChange={onChoose}
          onCommit={onCommit}
        />
      </td>
      <td className={`xl-txt rx-kind${retyped ? ' is-changed' : ''}`} data-label="نوع">
        {retyped ? (
          <>
            <s>{TYPE_LABELS[acc.type] ?? acc.type}</s> ← <b>{TYPE_LABELS[finalType] ?? finalType}</b>
          </>
        ) : (
          (TYPE_LABELS[acc.type] ?? acc.type)
        )}
      </td>
      <td className="ef-col-min jg-actions card-actions">
        <div className="row-actions">
          <RowAction
            icon={Undo2}
            label={`برگرداندنِ سرفصلِ «${acc.name}»`}
            disabled={!moved}
            title="سرفصلِ فعلی بماند (Ctrl+Delete)"
            onClick={onRevert}
          />
        </div>
      </td>
    </tr>
  )
}

function omit<T>(o: Record<string, T>, keys: readonly string[]): Record<string, T> {
  const out = { ...o }
  for (const k of keys) delete out[k]
  return out
}
