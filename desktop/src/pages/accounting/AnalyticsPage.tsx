import { useEffect, useId, useMemo, useRef, useState, type MouseEvent } from 'react'
import { Layers, Power, Search, Tag, Trash2, Wallet } from 'lucide-react'
import { createAnalytic, deleteAnalytic, fetchAnalytics, updateAnalytic, type AnalyticAccount } from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { SheetFooter, type SheetState } from '../../components/SheetFooter'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { CountBadge, RowAction } from '../../components/form/FormKit'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import {
  blankFresh,
  isBlank,
  matches,
  parseDraft,
  patchOf,
  pendingCount,
  problemOf,
  sortRows,
  withTrailingBlank,
  type Draft,
  type Field,
  type FreshRow,
  type Values,
} from '../../lib/analyticsSheet'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { tenantKey } from '../../lib/tenantScope'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { useSheetNav } from '../../lib/useSheetNav'
import { AsyncBlock, faInt, Metric, OpsPage, useAsync, type Msg } from './kit'

/**
 * «تفصیلی سایر» — بُعدِ تحلیلیِ آزادِ ردیفِ سند، به‌صورتِ **برگه‌ی اکسلی با ویرایشِ درجا**.
 *
 * پیش‌تر فرمی بالا (کد، نام، دسته، توضیح) و فهرستی دسته‌دسته پایین بود: برای هر تفصیلی یک‌بار فرم را
 * پر کن، ثبت بزن، و برای اصلاح دکمه‌ی ویرایش. حالا هم‌سبکِ «سند حسابداری» (خواسته‌ی آرش: صفحه‌ها یکی‌یکی
 * با همان تم): هر تفصیلی یک ردیف است و هر خانه همان‌جا ویرایش می‌شود؛ ردیفِ خالیِ ته برای تفصیلیِ تازه؛
 * خانه‌ی عوض‌شده ته‌رنگ می‌گیرد و «ذخیره تغییرات (Ctrl+S)» همه را یک‌جا می‌فرستد. همان صفحه‌کلیدِ گرید
 * (`useSheetNav`)، همان جست‌وجوی Ctrl+F، همان انتخابِ ردیف با شماره، و نوارِ پایینِ هم‌خط با ستون‌ها.
 *
 * **تغییرِ ذخیره‌نشده گم نمی‌شود:** پیش‌نویس در `sessionStorage`ِ همین کسب‌وکار می‌ماند و با برگشتن به
 * صفحه برمی‌گردد. ردیفی که سرور نپذیرفت (کدِ تکراری) با ویرایش‌هایش می‌ماند و قرمز می‌شود، و دلیلش زیرِ برگه.
 * حذف فوری است (با تأیید) — تفصیلیِ استفاده‌شده حذف نمی‌شود، غیرفعال می‌شود.
 */

type Col = 'code' | 'name' | 'group' | 'description' | 'active'
const COLS: Col[] = ['code', 'name', 'group', 'description', 'active']
const FIELD: Record<Exclude<Col, 'active'>, Exclude<Field, 'is_active'>> = {
  code: 'code',
  name: 'name',
  group: 'group_name',
  description: 'description',
}
const LAYOUT = { fixed: ['num', 'actions'], auto: 'name' } as const
const DRAFT_KEY = 'cubita.analytics.draft'

/** نوارِ پایین روی برگه: [دکمه] زیرِ ردیف+کد+نام، وضعیت زیرِ دسته، تازه زیرِ توضیح، ویرایش‌شده زیرِ ردیفِ سند+وضعیت. */
const SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('num') + w('code') + w('name'), w('group'), w('description'), w('lines') + w('active'), w('actions')]
}

type Row =
  | { kind: 'saved'; key: string; row: AnalyticAccount; values: Values }
  | { kind: 'new'; key: string; fresh: FreshRow; values: Values }

let seq = 0
const newKey = () => `new-${Date.now().toString(36)}-${++seq}`
const emptyDraft = (): Draft => ({ edits: {}, fresh: [blankFresh(newKey())] })

function loadDraft(): Draft {
  const key = tenantKey(DRAFT_KEY)
  let d: Draft | null = null
  try {
    d = key ? parseDraft(sessionStorage.getItem(key)) : null
  } catch {
    d = null
  }
  return d ? { ...d, fresh: withTrailingBlank(d.fresh, newKey) } : emptyDraft()
}

export function AnalyticsPage({ token }: { token: string }) {
  const list = useAsync(() => fetchAnalytics(token), [token])
  const [draft, setDraft] = useState<Draft>(loadDraft)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [find, setFind] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(() => {
    const d = loadDraft()
    return Object.keys(d.edits).length > 0 || d.fresh.some((f) => !isBlank(f))
      ? { text: 'تغییرهای ذخیره‌نشده‌ی دفعه‌ی قبل برگشت — «ذخیره تغییرات» بزنید.', kind: 'ok' }
      : null
  })
  const formRef = useRef<HTMLFormElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const findRef = useRef<HTMLInputElement>(null)
  const groupsId = useId()
  const cw = useColumnWidths('cubita.grid.analytics.shares', LAYOUT)
  const { selected, click, clear } = useRowSelection()
  useAlignToGrid(formRef, '.jf-foot--cols', { table: '.an-sheet', slots: SLOTS })

  //: پیش‌نویس با هر تغییر در نشستِ همین کسب‌وکار؛ خالی = پاک.
  useEffect(() => {
    const key = tenantKey(DRAFT_KEY)
    if (!key) return
    try {
      const empty = Object.keys(draft.edits).length === 0 && draft.fresh.every(isBlank)
      if (empty) sessionStorage.removeItem(key)
      else sessionStorage.setItem(key, JSON.stringify(draft))
    } catch {
      //: ذخیره‌نشدنِ پیش‌نویس فقط یعنی با بستنِ صفحه می‌رود؛ برگه باید کار کند.
    }
  }, [draft])

  const saved = useMemo(() => sortRows(list.data ?? []), [list.data])
  const groups = useMemo(() => new Set(saved.map((r) => r.group_name).filter(Boolean)), [saved])
  const counts = pendingCount(draft, saved)

  //: ردیف‌های روی صفحه: ثبت‌شده‌هایی که با جست‌وجو می‌خوانند، و همه‌ی تازه‌ها (جست‌وجو آن‌ها را پنهان
  //: نمی‌کند — تفصیلیِ نیمه‌کاره نباید با تایپ در کادرِ جست‌وجو گم شود).
  const rows: Row[] = useMemo(
    () => [
      ...saved
        .map((r): Row => ({ kind: 'saved', key: r.id, row: r, values: { ...r, ...draft.edits[r.id] } }))
        .filter((r) => matches(r.values, find)),
      ...draft.fresh.map((f): Row => ({ kind: 'new', key: f.key, fresh: f, values: { ...f, is_active: true } })),
    ],
    [saved, draft, find],
  )
  const order = rows.map((r) => r.key)
  const picked = rows.filter((r) => selected.has(r.key))
  //: افزودن/حذفِ ردیف یا جست‌وجوی تازه یعنی برگه‌ی دیگری؛ انتخابِ قبلی معنا ندارد.
  useEffect(() => clear(), [rows.length, clear])

  function edit(r: Row, field: Exclude<Field, 'is_active'>, value: string) {
    setErrors((e) => (e[r.key] ? omit(e, [r.key]) : e))
    setDraft((d) => {
      if (r.kind === 'saved') return { ...d, edits: { ...d.edits, [r.key]: { ...d.edits[r.key], [field]: value } } }
      const fresh = d.fresh.map((f) => (f.key === r.key ? { ...f, [field]: value } : f))
      return { ...d, fresh: withTrailingBlank(fresh, newKey) }
    })
  }

  function setActive(targets: Row[], active: boolean) {
    setDraft((d) => {
      const edits = { ...d.edits }
      for (const r of targets) if (r.kind === 'saved') edits[r.key] = { ...edits[r.key], is_active: active }
      return { ...d, edits }
    })
  }

  async function remove(targets: Row[]) {
    const local = targets.filter((r) => r.kind === 'new').map((r) => r.key)
    const savedRows = targets.flatMap((r) => (r.kind === 'saved' ? [r.row] : []))
    const used = savedRows.filter((r) => r.line_count > 0)
    const deletable = savedRows.filter((r) => r.line_count === 0)
    if (local.length > 0) {
      setDraft((d) => ({ ...d, fresh: withTrailingBlank(d.fresh.filter((f) => !local.includes(f.key)), newKey) }))
    }
    if (deletable.length > 0) {
      const names = deletable.length === 1 ? `«${deletable[0].name}»` : `${faInt(deletable.length)} تفصیلی`
      if (!window.confirm(`${names} حذف شود؟`)) return
      const failed: string[] = []
      for (const r of deletable) {
        try {
          await deleteAnalytic(token, r.id)
        } catch (err) {
          failed.push(`«${r.name}»: ${err instanceof Error ? err.message : 'خطای ناشناخته'}`)
        }
      }
      setDraft((d) => ({ ...d, edits: omit(d.edits, deletable.map((r) => r.id)) }))
      list.reload()
      if (failed.length > 0) {
        setMsg({ text: `حذف نشد — ${failed.join('؛ ')}`, kind: 'err' })
        return
      }
    }
    if (used.length > 0) {
      setMsg({
        text: `${used.map((r) => `«${r.name}»`).join('، ')} در سند به کار رفته و حذف نمی‌شود — به‌جایش غیرفعالش کنید.`,
        kind: 'err',
      })
    } else if (deletable.length > 0) {
      setMsg({ text: `${faInt(deletable.length)} تفصیلی حذف شد.`, kind: 'ok' })
    }
  }

  async function save() {
    const byId = new Map(saved.map((r) => [r.id, r]))
    const problems: Record<string, string> = {}
    const jobs: { key: string; label: string; run: () => Promise<unknown> }[] = []
    for (const [id, e] of Object.entries(draft.edits)) {
      const r = byId.get(id)
      const patch = r ? patchOf(r, e) : null
      if (!r || !patch) continue
      const p = problemOf({ ...r, ...e })
      if (p) problems[id] = p
      else jobs.push({ key: id, label: r.name, run: () => updateAnalytic(token, id, patch) })
    }
    for (const f of draft.fresh) {
      if (isBlank(f)) continue
      const p = problemOf(f)
      if (p) problems[f.key] = p
      else
        jobs.push({
          key: f.key,
          label: f.name.trim(),
          run: () =>
            createAnalytic(token, {
              code: f.code.trim(),
              name: f.name.trim(),
              group_name: f.group_name.trim(),
              description: f.description.trim(),
            }),
        })
    }
    if (jobs.length === 0 && Object.keys(problems).length === 0) {
      setMsg({ text: 'تغییری برای ذخیره نیست.', kind: 'ok' })
      return
    }
    setBusy(true)
    setMsg(null)
    //: یکی‌یکی و نه موازی: خطای هر ردیف مالِ همان ردیف است، و دو کدِ تکراری در یک دسته نباید هر دو بنشینند.
    const done: string[] = []
    for (const j of jobs) {
      try {
        await j.run()
        done.push(j.key)
      } catch (err) {
        problems[j.key] = err instanceof Error ? err.message : 'خطای ناشناخته'
      }
    }
    setDraft((d) => ({
      edits: omit(d.edits, done),
      fresh: withTrailingBlank(
        d.fresh.filter((f) => !done.includes(f.key)),
        newKey,
      ),
    }))
    setErrors(problems)
    list.reload()
    setBusy(false)
    const bad = Object.keys(problems).length
    setMsg(
      bad > 0
        ? { text: `${faInt(bad)} ردیف ذخیره نشد — دلیلش زیرِ برگه است.${done.length ? ` ${faInt(done.length)} ردیف ذخیره شد.` : ''}`, kind: 'err' }
        : { text: `${faInt(done.length)} ردیف ذخیره شد.`, kind: 'ok' },
    )
  }

  const nav = useSheetNav<Col>({
    gridRef,
    cols: COLS,
    rowCount: rows.length,
    //: وضعیتِ ردیفِ تازه همیشه «فعال» است و قابلِ‌تغییر نیست.
    enabled: (row, col) => col !== 'active' || rows[row]?.kind === 'saved',
    //: Enter: کد → نام → دسته → ردیفِ بعد. توضیح و وضعیت اختیاری‌اند؛ Tab و موس به آن‌ها می‌رسند.
    enterPath: (row, col) => col !== 'description' && col !== 'active' && rows[row] !== undefined,
    //: ته برگه همیشه یک ردیفِ خالی هست — «ردیفِ تازه» یعنی رفتن به همان.
    onAppendRow: () => rows.length - 1,
    onDeleteRow: (row) => {
      const targets = picked.length > 0 ? picked : rows[row] ? [rows[row]] : []
      if (targets.every((r) => r.kind === 'new' && isBlank(r.fresh))) return false
      void remove(targets)
      return true
    },
    rowHasContent: () => false,
  })

  const head = (id: string, label: string, next: string, title?: string) => (
    <th data-col={id} title={title}>
      {label}
      {cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  const errorList = rows.filter((r) => errors[r.key])
  const state: SheetState = errorList.length > 0 ? 'err' : counts.fresh + counts.edited > 0 ? 'dirty' : 'clean'

  return (
    <OpsPage
      canvas
      icon={Tag}
      title="تفصیلی سایر"
      description="بُعدِ تحلیلیِ آزادِ ردیفِ سند — برای هرچه نه طرف‌حساب است نه مرکزِ هزینه: خودرو، قرارداد، دستگاه، پرونده."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Tag size={14} />} label="تفصیلی‌ها" value={faInt(saved.length)} />
            <Metric icon={<Layers size={14} />} label="دسته‌ها" value={faInt(groups.size)} />
            <Metric
              icon={<Wallet size={14} />}
              label="ردیف‌های برچسب‌خورده"
              value={faInt(saved.reduce((s, r) => s + r.line_count, 0))}
            />
          </div>
        </div>
      }
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
          icon={Tag}
          title="تفصیلی‌ها"
          tip="هر خانه را همان‌جا ویرایش کنید؛ تفصیلیِ تازه را در ردیفِ خالیِ ته بنویسید. خانه‌ی عوض‌شده ته‌رنگ می‌گیرد و «ذخیره تغییرات» (Ctrl+S) همه را یک‌جا می‌فرستد. کد یکتاست و در گزارش‌ها به‌جای نام می‌آید."
          badge={<CountBadge accent>{faInt(saved.length)} تفصیلی</CountBadge>}
          actions={
            <div className="jg-head-actions">
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
                  placeholder="جست‌وجو: کد، نام، دسته"
                  aria-label="جست‌وجو در تفصیلی‌ها — کد، نام، دسته یا توضیح"
                  aria-keyshortcuts="Control+F"
                  title="Ctrl+F — Esc: پاک‌کردن"
                />
                {find && (
                  <span className="jg-find-count" aria-live="polite">
                    {faInt(rows.filter((r) => r.kind === 'saved').length)} مورد
                  </span>
                )}
              </div>
            </div>
          }
        >
          <AsyncBlock loading={list.loading && !list.data} error={list.data ? null : list.error}>
            <div className="jg">
              <div
                ref={gridRef}
                className="table-scroll ef-table-wrap jg-wrap"
                onKeyDown={nav.onKeyDown}
                role="grid"
                aria-label="برگه‌ی تفصیلی‌ها"
              >
                <table ref={cw.frame} className="ef-table ef-table--edit jg-table xl-grid table-plain an-sheet">
                  <colgroup>
                    <col className="jg-c-num" style={cw.col('num')} />
                    <col className="jg-c-code" style={cw.col('code')} />
                    <col className="jg-c-account" style={cw.col('name')} />
                    <col className="jg-c-group" style={cw.col('group')} />
                    <col className="jg-c-note" style={cw.col('description')} />
                    <col className="jg-c-lines" style={cw.col('lines')} />
                    <col className="jg-c-state" style={cw.col('active')} />
                    <col className="jg-c-act1" style={cw.col('actions')} />
                  </colgroup>
                  <thead>
                    <tr>
                      <th className="ef-col-min xl-rowhead" data-col="num">
                        ردیف
                      </th>
                      {head('code', 'کد', 'name')}
                      {head('name', 'نام', 'group')}
                      {head('group', 'دسته', 'description', 'تفصیلی‌های هم‌دسته در گزارش‌ها کنارِ هم می‌آیند.')}
                      {head('description', 'توضیح', 'lines')}
                      {head('lines', 'ردیفِ سند', 'active', 'چند ردیفِ سند این تفصیلی را دارند.')}
                      {head('active', 'وضعیت', 'actions')}
                      <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <SheetRow
                        key={r.key}
                        r={r}
                        i={i}
                        last={i === rows.length - 1}
                        selected={selected.has(r.key)}
                        error={errors[r.key]}
                        groupsId={groupsId}
                        onPick={(e) => click(order, r.key, modsOf(e))}
                        onEdit={edit}
                        onToggle={() => setActive([r], !r.values.is_active)}
                        onRemove={() => void remove([r])}
                      />
                    ))}
                  </tbody>
                </table>
                <datalist id={groupsId}>
                  {[...groups].map((g) => (
                    <option key={g} value={g} />
                  ))}
                </datalist>
              </div>
              {picked.length > 0 && (
                <SelectionBar count={picked.length} unit="ردیف" onClear={clear}>
                  <button type="button" onClick={() => setActive(picked, true)}>
                    <Power size={14} aria-hidden="true" /> فعال‌کردن
                  </button>
                  <button type="button" onClick={() => setActive(picked, false)}>
                    <Power size={14} aria-hidden="true" /> غیرفعال‌کردن
                  </button>
                  <button type="button" className="xl-selbar-danger" onClick={() => void remove(picked)}>
                    <Trash2 size={14} aria-hidden="true" /> حذف (Ctrl+Delete)
                  </button>
                </SelectionBar>
              )}
            </div>
            {errorList.length > 0 && (
              <ul className="xl-errbar" role="alert">
                {errorList.map((r) => (
                  <li key={r.key}>
                    <b>{r.values.name.trim() || r.values.code.trim() || 'ردیفِ تازه'}</b> — {errors[r.key]}
                  </li>
                ))}
              </ul>
            )}
          </AsyncBlock>
        </SectionCard>

        <SheetFooter
          state={state}
          fresh={counts.fresh}
          edited={counts.edited}
          submitting={busy}
          message={msg}
          columns
        />
      </form>
    </OpsPage>
  )
}

/** یک ردیفِ برگه — ثبت‌شده یا تازه. خانه‌ی عوض‌شده `is-changed` می‌گیرد (ته‌رنگِ اکسلیِ «ویرایش‌شده»). */
function SheetRow({
  r,
  i,
  last,
  selected,
  error,
  groupsId,
  onPick,
  onEdit,
  onToggle,
  onRemove,
}: {
  r: Row
  i: number
  last: boolean
  selected: boolean
  error?: string
  groupsId: string
  onPick: (e: MouseEvent) => void
  onEdit: (r: Row, field: Exclude<Field, 'is_active'>, value: string) => void
  onToggle: () => void
  onRemove: () => void
}) {
  const orig = r.kind === 'saved' ? r.row : null
  const changed = (f: Field) => Boolean(orig && r.values[f] !== orig[f] && String(r.values[f]).trim() !== String(orig[f]).trim())
  const blank = r.kind === 'new' && isBlank(r.fresh)
  const dirty = r.kind === 'saved' && (['code', 'name', 'group_name', 'description', 'is_active'] as Field[]).some(changed)
  const cls = [
    selected && 'is-selected',
    r.kind === 'new' && !blank && 'xl-row--new',
    dirty && 'xl-row--dirty',
    error && 'xl-row--error',
    !r.values.is_active && 'xl-row--off',
  ]
    .filter(Boolean)
    .join(' ')
  const text = (col: Exclude<Col, 'active'>, c: number, extra: { dir?: 'ltr'; list?: string; placeholder?: string } = {}) => {
    const f = FIELD[col]
    return (
      <td data-cell={`${i}-${c}`} className={changed(f) ? 'is-changed' : undefined}>
        <input
          type="text"
          aria-label={`${LABEL[col]}ِ ردیفِ ${faInt(i + 1)}`}
          value={r.values[f]}
          onChange={(e) => onEdit(r, f, e.target.value)}
          {...extra}
        />
      </td>
    )
  }
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
          {last && blank ? '+' : faInt(i + 1)}
        </button>
      </td>
      {text('code', 0, { dir: 'ltr' })}
      {text('name', 1, last && blank ? { placeholder: 'تفصیلیِ تازه: کد و نام را بنویسید…' } : {})}
      {text('group', 2, { list: groupsId })}
      {text('description', 3)}
      <td className="num xl-ro" data-label="ردیفِ سند">
        {r.kind === 'saved' ? faInt(r.row.line_count) : '—'}
      </td>
      <td data-cell={`${i}-4`} className={changed('is_active') ? 'is-changed' : undefined}>
        <button
          type="button"
          className={`xl-toggle${r.values.is_active ? ' is-on' : ''}`}
          aria-pressed={r.values.is_active}
          aria-label={`وضعیتِ ردیفِ ${faInt(i + 1)}: ${r.values.is_active ? 'فعال' : 'غیرفعال'}`}
          disabled={r.kind === 'new'}
          title={r.kind === 'new' ? 'تفصیلیِ تازه فعال ساخته می‌شود.' : 'Space: فعال/غیرفعال'}
          onClick={onToggle}
        >
          {r.values.is_active ? 'فعال' : 'غیرفعال'}
        </button>
      </td>
      <td className="ef-col-min jg-actions card-actions">
        <div className="row-actions">
          <RowAction
            icon={Trash2}
            label="حذف ردیف"
            danger
            disabled={blank || (r.kind === 'saved' && r.row.line_count > 0)}
            title={
              r.kind === 'saved' && r.row.line_count > 0
                ? 'ردیف‌های سند به این تفصیلی اشاره کرده‌اند؛ به‌جای حذف غیرفعالش کنید.'
                : 'حذف (Ctrl+Delete)'
            }
            onClick={onRemove}
          />
        </div>
      </td>
    </tr>
  )
}

const LABEL: Record<Exclude<Col, 'active'>, string> = { code: 'کد', name: 'نام', group: 'دسته', description: 'توضیح' }

function omit<T>(o: Record<string, T>, keys: readonly string[]): Record<string, T> {
  const out = { ...o }
  for (const k of keys) delete out[k]
  return out
}
