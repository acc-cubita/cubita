import { Fragment, useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent, type ReactNode } from 'react'
import { Power, Search, Trash2, type LucideIcon } from 'lucide-react'

import { SectionCard } from './SectionCard'
import { SearchSelect } from './SearchSelect'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { SheetFooter, type SheetState } from './SheetFooter'
import { ColResizer, SelectionBar } from './XlGrid'
import { CountBadge, RowAction } from './form/FormKit'
import { useAlignToGrid, type SlotMap } from '../lib/alignToGrid'
import {
  cellChanged,
  isBlank,
  matches,
  omit,
  parseDraft,
  patchOf,
  pendingCount,
  problemOf,
  withTrailingBlank,
  type DefDraft,
  type DefSpec,
  type DefValues,
  type FreshRow,
} from '../lib/defSheet'
import { modsOf, useRowSelection } from '../lib/rowSelection'
import { tenantKey } from '../lib/tenantScope'
import { useColumnWidths } from '../lib/useColumnWidths'
import { useSheetNav } from '../lib/useSheetNav'

const faInt = (n: number) => n.toLocaleString('fa-IR')

/**
 * «برگه‌ی تعریف» — داده‌ی پایه‌ای که ردیف‌به‌ردیف ساخته و ویرایش می‌شود، به‌صورتِ **برگه‌ی اکسلی با ویرایشِ درجا**
 * (الگوی «ب»ِ تمِ اکسلی؛ مرجع: «تفصیلی سایر»).
 *
 * صفحه فقط ستون‌ها و چهار کارِ سرور (ساخت، ویرایش، حذف، سنجشِ اضافه) را می‌دهد؛ بقیه یکی است و یک‌جاست: ردیفِ
 * خالیِ ته برای رکوردِ تازه، ته‌رنگِ خانه‌ی عوض‌شده، «ذخیره تغییرات» (Ctrl+S) که یکی‌یکی و **پشتِ‌سرِ‌هم** می‌فرستد،
 * ردیفِ ردشده که ورودی‌اش می‌ماند و دلیلش زیرِ برگه می‌آید، پیش‌نویس در نشستِ همین کسب‌وکار، صفحه‌کلیدِ گرید
 * (`useSheetNav`)، انتخابِ ردیف با شماره و نوارِ انتخاب، جست‌وجوی Ctrl+F، و نوارِ پایینِ هم‌خط با ستون‌ها.
 *
 * **آنچه سرور اجازه نمی‌دهد وانمود نمی‌شود:** خانه‌ای که با سابقه‌ی رکورد قفل می‌شود (`lock`) یا فقط روی ردیفِ
 * تازه معنا دارد (`newOnly`) غیرفعال است و دلیلش در `title`؛ حذفِ رکوردِ باسابقه (`removeBlock`) هم.
 *
 * **برگه‌ی پهن** (`wide`): ستون‌ها عرضِ پیکسلی دارند، جدول عرضِ صریح (جمعِ ستون‌ها) و افقی می‌لغزد، و شماره‌ی ردیف
 * و ستونِ نام میخ می‌شوند — همان «ثابت‌کردنِ ستون»ِ اکسل (الگوی بودجه). هم‌خطیِ نوار آن‌جا خاموش است.
 */

export type DefColKind = 'text' | 'number' | 'date' | 'select' | 'toggle' | 'ro'

export interface DefCol<R> {
  id: string
  label: string
  /** راهنمای سرستون. */
  title?: string
  kind: DefColKind
  /** فیلدِ ویرایشی (همه جز `ro`). */
  field?: string
  /** عرضِ پیش‌فرض: درصد در برگه‌ی جا-در-قاب، پیکسل (عدد) در برگه‌ی پهن. ستونِ کشسان ندارد. */
  w?: string | number
  ltr?: boolean
  numeric?: boolean
  /** گزینه‌های انتخاب‌گر (مقدارِ خالی با `emptyOption`). */
  options?: (values: DefValues) => { value: string; label: string }[]
  emptyOption?: string
  placeholder?: string
  /** نمایشِ خانه‌ی فقط‌خواندنی. ردیفِ تازه `null` می‌گیرد. */
  ro?: (row: R | null, values: DefValues) => ReactNode
  /** خانه‌ی ثبت‌شده قفل است؟ دلیلِ قفل (برای `title`) یا `null`. */
  lock?: (row: R) => string | null
  /** فقط روی ردیفِ تازه ویرایشی — متن دلیلِ قفل روی ردیفِ ثبت‌شده است. */
  newOnly?: string
  /** Enter رویش می‌ایستد (پیش‌فرض: نه). */
  enter?: boolean
  /** زیرِ ۷۶۰px پنهان — برگه‌ی ویرایشی کارت نمی‌شود، پس ستون‌های کم‌اهمیت کنار می‌روند. */
  mhide?: boolean
  /** وقتی **قابِ خودِ برگه** باریک‌تر از ۸۶۰px است پنهان (`@container`، نه پنجره) — در ۱۲۰۰ با کارت‌های کناری
   *  ستونِ کشسان وگرنه به چند پیکسل می‌رسید. */
  narrow?: boolean
  /** کلیدِ روشن/خاموش روی ردیفِ تازه: مقدارِ نمایشی (پیش‌فرضِ سرور) و دلیلِ غیرفعال بودنش. */
  newValue?: boolean
  newLock?: string
}

export interface DefSheetProps<R extends { id: string }> {
  /** شناسه‌ی برگه: کلیدِ پیش‌نویس (`cubita.<id>.draft`) و عرضِ ستون‌ها (`cubita.grid.<id>.shares`). */
  sheetId: string
  spec: DefSpec
  cols: DefCol<R>[]
  /** ستونِ کشسان (معمولاً نام). */
  autoCol: string
  /** پنج خانه‌ی نوارِ پایین: شناسه‌ی ستون‌های زیرِ هر خانه — [دکمه] [وضعیت] [تازه] [ویرایش‌شده] [باقی]. */
  slots: [string[], string[], string[], string[], string[]]
  /** برگه‌ی پهن با عرضِ پیکسلیِ ستون‌ها (نگاه به توضیحِ بالا). */
  wide?: boolean
  rows: R[] | null
  error: string | null
  reload: () => void
  valuesOf: (r: R) => DefValues
  create: (values: DefValues) => Promise<unknown>
  update: (r: R, patch: Partial<DefValues>) => Promise<unknown>
  remove: (r: R) => Promise<unknown>
  /** چرا این رکورد حذف نمی‌شود (سابقه دارد)؛ `null` یعنی می‌شود. */
  removeBlock?: (r: R) => string | null
  /** سنجشِ پیش از ارسالِ بیش از فیلدهای لازم (مثلاً «صندوقِ دوم تفصیلی می‌خواهد»). */
  check?: (values: DefValues, ctx: { isNew: boolean; saved: readonly R[] }) => string | null
  /** کنش‌های اضافه‌ی ردیفِ ثبت‌شده (کارتِ حساب، آزمایشِ اتصال، …) — کنارِ حذف. */
  rowActions?: (r: R) => ReactNode
  /** ردیفِ جزئیاتِ باز زیرِ یک رکورد (برگ‌های دسته‌چک). */
  detail?: (r: R) => ReactNode | null
  /** نامِ خوانای ردیف برای تأیید و فهرستِ خطا. */
  labelOf: (values: DefValues) => string
  icon: LucideIcon
  title: string
  tip: string
  /** واحدِ شمارش: «۳ صندوق». */
  unit: string
  newPlaceholder: string
  findPlaceholder: string
  /** فیلدِ وضعیت (پیش‌فرض `is_active`)؛ `null` یعنی این برگه وضعیت ندارد. */
  activeField?: string | null
  /** بعد از هر ذخیره/حذفِ موفق — صفحه‌ی میزبان شمارشِ سربرگش را تازه کند. */
  onSaved?: () => void
}

type Row<R> =
  | { kind: 'saved'; key: string; row: R; orig: DefValues; values: DefValues }
  | { kind: 'new'; key: string; fresh: FreshRow; values: DefValues }

let seq = 0
const newKey = () => `n-${Date.now().toString(36)}-${++seq}`
/** کلاسِ پنهان‌شدنِ ستون — `col`، سرستون و خانه‌ها با هم، تا در `table-layout: fixed` ستون‌ها جابه‌جا نشوند. */
const hideCls = (c: { mhide?: boolean; narrow?: boolean }) =>
  [c.mhide && 'ds-mhide', c.narrow && 'ds-nhide'].filter(Boolean).join(' ')

export function DefSheet<R extends { id: string }>(props: DefSheetProps<R>) {
  const {
    sheetId, spec, cols, autoCol, slots, wide = false, rows: savedRows, error: loadError, reload, valuesOf,
    create, update, remove: removeOne, removeBlock, check, rowActions, detail, labelOf, icon, title, tip, unit,
    newPlaceholder, findPlaceholder, activeField = 'is_active', onSaved,
  } = props
  const draftKey = `cubita.${sheetId}.draft`
  const fresh = (list: FreshRow[]) => withTrailingBlank(spec, list, newKey)
  const loadDraft = (): DefDraft => {
    const key = tenantKey(draftKey)
    let d: DefDraft | null = null
    try {
      d = key ? parseDraft(spec, sessionStorage.getItem(key)) : null
    } catch {
      d = null
    }
    return { edits: d?.edits ?? {}, fresh: fresh(d?.fresh ?? []) }
  }

  const [draft, setDraft] = useState<DefDraft>(loadDraft)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [find, setFind] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(() => {
    const d = loadDraft()
    return Object.keys(d.edits).length > 0 || d.fresh.some((f) => !isBlank(spec, f))
      ? { text: 'تغییرهای ذخیره‌نشده‌ی دفعه‌ی قبل برگشت — «ذخیره تغییرات» بزنید.', kind: 'ok' }
      : null
  })
  const formRef = useRef<HTMLFormElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const findRef = useRef<HTMLInputElement>(null)
  const layout = useMemo(() => ({ fixed: ['num', 'actions'], auto: autoCol }), [autoCol])
  const cw = useColumnWidths(`cubita.grid.${sheetId}.shares`, layout)
  const { selected, click, clear } = useRowSelection()
  const slotMap: SlotMap = useMemo(
    () => (measured) => {
      const w = (id: string) => measured.find((c) => c.id === id)?.w ?? 0
      return slots.map((ids) => ids.reduce((s, id) => s + w(id), 0))
    },
    [slots],
  )
  const tableCls = `ds-${sheetId}`
  useAlignToGrid(formRef, '.jf-foot--cols', { table: `.${tableCls}`, slots: slotMap })

  //: پیش‌نویس با هر تغییر در نشستِ همین کسب‌وکار؛ خالی = پاک.
  useEffect(() => {
    const key = tenantKey(draftKey)
    if (!key) return
    try {
      const empty = Object.keys(draft.edits).length === 0 && draft.fresh.every((f) => isBlank(spec, f))
      if (empty) sessionStorage.removeItem(key)
      else sessionStorage.setItem(key, JSON.stringify(draft))
    } catch {
      //: ذخیره‌نشدنِ پیش‌نویس فقط یعنی با بستنِ صفحه می‌رود؛ برگه باید کار کند.
    }
  }, [draft, draftKey, spec])

  const saved = useMemo(() => savedRows ?? [], [savedRows])
  const origById = useMemo(() => new Map(saved.map((r) => [r.id, valuesOf(r)])), [saved, valuesOf])
  const counts = pendingCount(spec, draft, origById)

  //: جست‌وجو ثبت‌شده‌ها را فیلتر می‌کند نه تازه‌ها — رکوردِ نیمه‌کاره نباید با تایپ در کادرِ جست‌وجو گم شود.
  const rows: Row<R>[] = useMemo(
    () => [
      ...saved
        .map((r): Row<R> => {
          const orig = origById.get(r.id)!
          return { kind: 'saved', key: r.id, row: r, orig, values: { ...orig, ...draft.edits[r.id] } }
        })
        .filter((r) => matches(spec, r.values, find)),
      ...draft.fresh.map((f): Row<R> => ({ kind: 'new', key: f.key, fresh: f, values: { ...f } })),
    ],
    [saved, origById, draft, find, spec],
  )
  const order = rows.map((r) => r.key)
  const picked = rows.filter((r) => selected.has(r.key))
  useEffect(() => clear(), [rows.length, clear])

  //: ستون‌های ویرایشی به ترتیبِ صفحه — `data-cell`ِ هر خانه جایش در همین فهرست است.
  const navCols = cols.filter((c) => c.kind !== 'ro' && c.field)
  const navIndex = new Map(navCols.map((c, i) => [c.id, i]))

  /** قفلِ یک خانه روی این ردیف (دلیل) یا `null`. */
  function lockOf(r: Row<R>, c: DefCol<R>): string | null {
    if (r.kind === 'new') return c.kind === 'toggle' ? (c.newLock ?? 'رکوردِ تازه فعال ساخته می‌شود.') : null
    if (c.newOnly) return c.newOnly
    return c.lock?.(r.row) ?? null
  }

  function edit(r: Row<R>, field: string, value: string | boolean) {
    setErrors((e) => (e[r.key] ? omit(e, [r.key]) : e))
    setDraft((d) => {
      if (r.kind === 'saved') return { ...d, edits: { ...d.edits, [r.key]: { ...d.edits[r.key], [field]: value } } }
      const list = d.fresh.map((f) => (f.key === r.key ? { ...f, [field]: String(value) } : f))
      return { ...d, fresh: fresh(list) }
    })
  }

  function setActive(targets: Row<R>[], on: boolean) {
    if (!activeField) return
    setDraft((d) => {
      const edits = { ...d.edits }
      for (const r of targets) if (r.kind === 'saved') edits[r.key] = { ...edits[r.key], [activeField]: on }
      return { ...d, edits }
    })
  }

  async function remove(targets: Row<R>[]) {
    const local = targets.filter((r) => r.kind === 'new').map((r) => r.key)
    const savedT = targets.flatMap((r) => (r.kind === 'saved' ? [r] : []))
    const blocked = savedT.filter((r) => removeBlock?.(r.row))
    const deletable = savedT.filter((r) => !removeBlock?.(r.row))
    if (local.length > 0) setDraft((d) => ({ ...d, fresh: fresh(d.fresh.filter((f) => !local.includes(f.key))) }))
    if (deletable.length > 0) {
      const names = deletable.length === 1 ? `«${labelOf(deletable[0].values)}»` : `${faInt(deletable.length)} ${unit}`
      if (!window.confirm(`${names} حذف شود؟`)) return
      const failed: string[] = []
      for (const r of deletable) {
        try {
          await removeOne(r.row)
        } catch (err) {
          failed.push(`«${labelOf(r.values)}»: ${err instanceof Error ? err.message : 'خطای ناشناخته'}`)
        }
      }
      setDraft((d) => ({ ...d, edits: omit(d.edits, deletable.map((r) => r.key)) }))
      reload()
      onSaved?.()
      if (failed.length > 0) {
        setMsg({ text: `حذف نشد — ${failed.join('؛ ')}`, kind: 'err' })
        return
      }
    }
    if (blocked.length > 0) {
      setMsg({
        text: blocked.map((r) => `«${labelOf(r.values)}»: ${removeBlock!(r.row)}`).join('؛ '),
        kind: 'err',
      })
    } else if (deletable.length > 0) {
      setMsg({ text: `${faInt(deletable.length)} ${unit} حذف شد.`, kind: 'ok' })
    }
  }

  async function save() {
    const problems: Record<string, string> = {}
    const jobs: { key: string; run: () => Promise<unknown> }[] = []
    for (const [id, e] of Object.entries(draft.edits)) {
      const r = saved.find((s) => s.id === id)
      const orig = origById.get(id)
      const patch = r && orig ? patchOf(spec, orig, e) : null
      if (!r || !orig || !patch) continue
      const values = { ...orig, ...e }
      const p = problemOf(spec, values) ?? check?.(values, { isNew: false, saved })
      if (p) problems[id] = p
      else jobs.push({ key: id, run: () => update(r, patch) })
    }
    for (const f of draft.fresh) {
      if (isBlank(spec, f)) continue
      const values: DefValues = { ...f }
      const p = problemOf(spec, values) ?? check?.(values, { isNew: true, saved })
      if (p) problems[f.key] = p
      else jobs.push({ key: f.key, run: () => create(values) })
    }
    if (jobs.length === 0 && Object.keys(problems).length === 0) {
      setMsg({ text: 'تغییری برای ذخیره نیست.', kind: 'ok' })
      return
    }
    setBusy(true)
    setMsg(null)
    //: یکی‌یکی و نه موازی: خطای هر ردیف مالِ همان ردیف است، و دو رکوردِ ناسازگار در یک دسته نباید هر دو بنشینند.
    const done: string[] = []
    for (const j of jobs) {
      try {
        await j.run()
        done.push(j.key)
      } catch (err) {
        problems[j.key] = err instanceof Error ? err.message : 'خطای ناشناخته'
      }
    }
    setDraft((d) => ({ edits: omit(d.edits, done), fresh: fresh(d.fresh.filter((f) => !done.includes(f.key))) }))
    setErrors(problems)
    reload()
    if (done.length > 0) onSaved?.()
    setBusy(false)
    const bad = Object.keys(problems).length
    setMsg(
      bad > 0
        ? { text: `${faInt(bad)} ردیف ذخیره نشد — دلیلش زیرِ برگه است.${done.length ? ` ${faInt(done.length)} ردیف ذخیره شد.` : ''}`, kind: 'err' }
        : { text: `${faInt(done.length)} ردیف ذخیره شد.`, kind: 'ok' },
    )
  }

  const nav = useSheetNav<string>({
    gridRef,
    cols: navCols.map((c) => c.id),
    rowCount: rows.length,
    enabled: (row, col) => {
      const r = rows[row]
      const c = navCols.find((x) => x.id === col)
      return Boolean(r && c && !lockOf(r, c))
    },
    enterPath: (row, col) => {
      const r = rows[row]
      const c = navCols.find((x) => x.id === col)
      return Boolean(r && c?.enter && !lockOf(r, c))
    },
    //: ته برگه همیشه یک ردیفِ خالی هست — «ردیفِ تازه» یعنی رفتن به همان.
    onAppendRow: () => rows.length - 1,
    onDeleteRow: (row) => {
      const targets = picked.length > 0 ? picked : rows[row] ? [rows[row]] : []
      if (targets.every((r) => r.kind === 'new' && isBlank(spec, r.fresh))) return false
      void remove(targets)
      return true
    },
    rowHasContent: () => false,
  })

  const colStyle = (c: DefCol<R>): CSSProperties | undefined => {
    if (wide) return typeof c.w === 'number' ? { width: `${c.w}px` } : undefined
    if (c.id === autoCol) return cw.col(c.id)
    return cw.col(c.id) ?? (c.w !== undefined ? { width: typeof c.w === 'number' ? `${c.w}px` : c.w } : undefined)
  }
  const tableWidth = wide ? 44 + 96 + cols.reduce((s, c) => s + (typeof c.w === 'number' ? c.w : 0), 0) : undefined
  const errorList = rows.filter((r) => errors[r.key])
  const state: SheetState = errorList.length > 0 ? 'err' : counts.fresh + counts.edited > 0 ? 'dirty' : 'clean'
  const colSpan = cols.length + 2

  return (
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
        icon={icon}
        title={title}
        tip={tip}
        badge={<CountBadge accent>{`${faInt(saved.length)} ${unit}`}</CountBadge>}
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
                placeholder={findPlaceholder}
                aria-label={`جست‌وجو در ${title}`}
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
        {loadError && !savedRows ? (
          <p className="form-error" role="alert">{loadError}</p>
        ) : !savedRows ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : (
          <>
            <div className="jg">
              <div
                ref={gridRef}
                className={`table-scroll ef-table-wrap jg-wrap ds-wrap${wide ? ' ds-wrap--wide' : ''}`}
                onKeyDown={nav.onKeyDown}
                role="grid"
                aria-label={`برگه‌ی ${title}`}
              >
                <table
                  ref={wide ? undefined : cw.frame}
                  className={`ef-table ef-table--edit jg-table xl-grid table-plain ds-sheet ${tableCls}${wide ? ' ds-sheet--wide' : ''}`}
                  style={tableWidth ? { inlineSize: `${tableWidth}px` } : undefined}
                >
                  <colgroup>
                    <col className="jg-c-num" />
                    {cols.map((c) => (
                      <col key={c.id} className={hideCls(c) || undefined} style={colStyle(c)} />
                    ))}
                    <col className="ds-c-actions" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th className={`ef-col-min xl-rowhead${wide ? ' ds-pin ds-pin--num' : ''}`} data-col="num">
                        ردیف
                      </th>
                      {cols.map((c, i) => {
                        const next = cols[i + 1]?.id
                        return (
                          <th
                            key={c.id}
                            data-col={c.id}
                            title={c.title}
                            className={[wide && i === 0 && 'ds-pin ds-pin--lead', hideCls(c)].filter(Boolean).join(' ') || undefined}
                          >
                            {c.label}
                            {!wide && cw.canResize(c.id, next) && <ColResizer onBegin={(e) => cw.begin(e, c.id)} onReset={cw.reset} />}
                          </th>
                        )
                      })}
                      <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => {
                      const extra = r.kind === 'saved' ? detail?.(r.row) : null
                      return (
                        <Fragment key={r.key}>
                          <SheetRow
                            r={r}
                            i={i}
                            last={i === rows.length - 1}
                            spec={spec}
                            cols={cols}
                            wide={wide}
                            navIndex={navIndex}
                            selected={selected.has(r.key)}
                            error={errors[r.key]}
                            activeField={activeField}
                            newPlaceholder={newPlaceholder}
                            lockOf={lockOf}
                            removeBlock={r.kind === 'saved' ? (removeBlock?.(r.row) ?? null) : null}
                            actions={r.kind === 'saved' ? rowActions?.(r.row) : null}
                            onPick={(e) => click(order, r.key, modsOf(e))}
                            onEdit={edit}
                            onRemove={() => void remove([r])}
                          />
                          {extra && (
                            <tr className="ds-detail">
                              <td colSpan={colSpan}>{extra}</td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {picked.length > 0 && (
                <SelectionBar count={picked.length} unit="ردیف" onClear={clear}>
                  {activeField && (
                    <>
                      <button type="button" onClick={() => setActive(picked, true)}>
                        <Power size={14} aria-hidden="true" /> فعال‌کردن
                      </button>
                      <button type="button" onClick={() => setActive(picked, false)}>
                        <Power size={14} aria-hidden="true" /> غیرفعال‌کردن
                      </button>
                    </>
                  )}
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
                    <b>{labelOf(r.values) || 'ردیفِ تازه'}</b> — {errors[r.key]}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </SectionCard>

      <SheetFooter
        state={state}
        fresh={counts.fresh}
        edited={counts.edited}
        submitting={busy}
        message={msg}
        columns={!wide}
      />
    </form>
  )
}

/** یک ردیفِ برگه — ثبت‌شده یا تازه. خانه‌ی عوض‌شده `is-changed` می‌گیرد (ته‌رنگِ اکسلیِ «ویرایش‌شده»). */
function SheetRow<R extends { id: string }>({
  r,
  i,
  last,
  spec,
  cols,
  wide,
  navIndex,
  selected,
  error,
  activeField,
  newPlaceholder,
  lockOf,
  removeBlock,
  actions,
  onPick,
  onEdit,
  onRemove,
}: {
  r: Row<R>
  i: number
  last: boolean
  spec: DefSpec
  cols: DefCol<R>[]
  wide: boolean
  navIndex: Map<string, number>
  selected: boolean
  error?: string
  activeField: string | null
  newPlaceholder: string
  lockOf: (r: Row<R>, c: DefCol<R>) => string | null
  removeBlock: string | null
  actions: ReactNode
  onPick: (e: MouseEvent) => void
  onEdit: (r: Row<R>, field: string, value: string | boolean) => void
  onRemove: () => void
}) {
  const blank = r.kind === 'new' && isBlank(spec, r.fresh)
  const changed = (field: string) => r.kind === 'saved' && cellChanged(spec, field, r.orig, r.values)
  const dirty = r.kind === 'saved' && [...spec.text, ...(spec.bools ?? [])].some(changed)
  const off = activeField !== null && r.kind === 'saved' && !r.values[activeField]
  const cls = [
    selected && 'is-selected',
    r.kind === 'new' && !blank && 'xl-row--new',
    dirty && 'xl-row--dirty',
    error && 'xl-row--error',
    off && 'xl-row--off',
  ]
    .filter(Boolean)
    .join(' ')
  const rowName = `ردیفِ ${faInt(i + 1)}`

  function cell(c: DefCol<R>, idx: number) {
    const pin = wide && idx === 0 ? 'ds-pin ds-pin--lead' : ''
    const hide = hideCls(c)
    if (c.kind === 'ro' || !c.field) {
      return (
        <td key={c.id} className={['xl-ro', c.numeric && 'num', pin, hide].filter(Boolean).join(' ')} data-label={c.label}>
          {c.ro ? c.ro(r.kind === 'saved' ? r.row : null, r.values) : '—'}
        </td>
      )
    }
    const field = c.field
    const lock = lockOf(r, c)
    const value = r.values[field]
    const label = `${c.label}ِ ${rowName}`
    const tdCls = [changed(field) && 'is-changed', lock && 'ds-locked', pin, hide].filter(Boolean).join(' ') || undefined
    let editor: ReactNode
    if (c.kind === 'toggle') {
      const on = r.kind === 'new' ? (c.newValue ?? true) : Boolean(value)
      editor = (
        <button
          type="button"
          className={`xl-toggle${on ? ' is-on' : ''}`}
          aria-pressed={on}
          aria-label={`${label}: ${on ? 'فعال' : 'غیرفعال'}`}
          disabled={Boolean(lock)}
          title={lock ?? 'Space: فعال/غیرفعال'}
          onClick={() => onEdit(r, field, !on)}
        >
          {on ? 'فعال' : 'غیرفعال'}
        </button>
      )
    } else if (c.kind === 'select') {
      editor = (
        <SearchSelect
          value={String(value ?? '')}
          aria-label={label}
          disabled={Boolean(lock)}
          title={lock ?? undefined}
          onChange={(e) => onEdit(r, field, e.target.value)}
        >
          {c.emptyOption !== undefined && <option value="">{c.emptyOption}</option>}
          {(c.options?.(r.values) ?? []).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </SearchSelect>
      )
    } else if (c.kind === 'date') {
      editor = lock ? (
        <input type="text" value={String(value ?? '')} aria-label={label} disabled title={lock} readOnly />
      ) : (
        <JalaliDatePicker value={String(value ?? '')} onChange={(v) => onEdit(r, field, v)} />
      )
    } else if (c.kind === 'number') {
      editor = (
        <NumberInput
          value={String(value ?? '')}
          onChange={(v) => onEdit(r, field, v)}
          aria-label={label}
          disabled={Boolean(lock)}
        />
      )
    } else {
      editor = (
        <input
          type="text"
          aria-label={label}
          value={String(value ?? '')}
          dir={c.ltr ? 'ltr' : undefined}
          inputMode={c.numeric ? 'numeric' : undefined}
          disabled={Boolean(lock)}
          title={lock ?? undefined}
          placeholder={idx === 0 && last && blank ? newPlaceholder : c.placeholder}
          onChange={(e) => onEdit(r, field, e.target.value)}
        />
      )
    }
    return (
      <td key={c.id} data-cell={`${i}-${navIndex.get(c.id)}`} className={tdCls} title={lock ?? undefined}>
        {editor}
      </td>
    )
  }

  return (
    <tr className={cls || undefined} title={error}>
      <td className={`ef-col-min jg-num xl-rowhead card-title${wide ? ' ds-pin ds-pin--num' : ''}`}>
        <button
          type="button"
          tabIndex={-1}
          className="xl-rowhead-btn"
          aria-pressed={selected}
          aria-label={`انتخابِ ${rowName}`}
          onClick={onPick}
        >
          {last && blank ? '+' : faInt(i + 1)}
        </button>
      </td>
      {cols.map((c, idx) => cell(c, idx))}
      <td className="ef-col-min jg-actions card-actions">
        <div className="row-actions">
          {actions}
          <RowAction
            icon={Trash2}
            label="حذف ردیف"
            danger
            disabled={blank || Boolean(removeBlock)}
            title={removeBlock ?? 'حذف (Ctrl+Delete)'}
            onClick={onRemove}
          />
        </div>
      </td>
    </tr>
  )
}
