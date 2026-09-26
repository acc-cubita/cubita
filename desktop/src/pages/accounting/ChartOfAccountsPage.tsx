import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent } from 'react'
import {
  BookOpen,
  ChevronDown,
  ChevronLeft,
  ListTree,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
} from 'lucide-react'
import {
  ACCOUNT_NATURE_LABELS,
  ACCOUNT_TRAIT_META,
  changeAccountCode,
  createAccount,
  fetchChartAccounts,
  fetchNextAccountCode,
  fetchTrialBalance,
  updateAccount,
  type AccountTraits,
} from '../../api'
import { AccountEditDrawer } from '../../components/AccountEditDrawer'
import { AccountLedgerDrawer } from '../../components/AccountLedgerDrawer'
import { EmptyState } from '../../components/EmptyState'
import { Amount } from '../../components/ReportViews'
import { useNavSection } from '../../components/navContext'
import { SearchSelect } from '../../components/SearchSelect'
import { SectionCard } from '../../components/SectionCard'
import { SheetFooter, type SheetState } from '../../components/SheetFooter'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { CountBadge, RowAction } from '../../components/form/FormKit'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import {
  NEW_TRAITS,
  buildTree,
  codeOwners,
  createBody,
  isEmptyDraft,
  levelLabel,
  matchingIds,
  nextFreeCode,
  parseDraft,
  patchOf,
  pendingCount,
  problemOf,
  sheetRows,
  visibleNodes,
  type Draft,
  type FreshAccount,
  type Nature,
  type Node,
  type SheetRow,
  type Values,
} from '../../lib/chartSheet'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { tenantKey } from '../../lib/tenantScope'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { useSheetNav } from '../../lib/useSheetNav'
import { AsyncBlock, OpsPage, faInt, useAsync, type Msg } from './kit'

const TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی',
  liability: 'بدهی',
  equity: 'سرمایه',
  income: 'درآمد',
  expense: 'هزینه',
}

/** پرچم‌هایی که روی ردیف نشانه می‌گیرند. «نمایش در گزارشات» برعکس است: پیش‌فرض روشن، پس خاموشش نشان داده می‌شود. */
const TRAIT_TAGS = ACCOUNT_TRAIT_META.filter((t) => t.key !== 'in_management_reports').map((t) => ({
  key: t.key,
  tag: t.key === 'nature_control' ? 'کنترلِ ماهیت' : t.label,
  title: t.hint,
}))

type Col = 'code' | 'name' | 'name2' | 'nature' | 'active'
const COLS: Col[] = ['code', 'name', 'name2', 'nature', 'active']
const LAYOUT = { fixed: ['num', 'actions'], auto: 'name' } as const
const DRAFT_KEY = 'cubita.chart.draft'

/** نوارِ پایین روی برگه: [دکمه] زیرِ ردیف+کد+نام، وضعیت زیرِ عنوانِ دوم+ماهیت، تازه زیرِ نوع+ویژگی، ویرایش‌شده زیرِ مانده+وضعیت. */
const SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [
    w('num') + w('code') + w('name'),
    w('name2') + w('nature'),
    w('kind') + w('traits'),
    w('balance') + w('active'),
    w('actions'),
  ]
}

let seq = 0
const newKey = () => `new-${Date.now().toString(36)}-${++seq}`

function loadDraft(): Draft {
  const key = tenantKey(DRAFT_KEY)
  try {
    return (key ? parseDraft(sessionStorage.getItem(key)) : null) ?? { edits: {}, fresh: [] }
  } catch {
    return { edits: {}, fresh: [] }
  }
}

/**
 * «درختواره حساب‌ها» با تمِ اکسلی — **برگه‌ی ویرایشِ درجا روی درخت** (الگوی «ب» از `cubita-excel-theme`).
 *
 * پیش‌تر درختی فقط‌خواندنی بود و هر تغییر یک فرم می‌خواست: کشوی ویرایش برای نام یا ماهیت، فرمِ جدا برای حسابِ تازه.
 * حالا کد، نام، عنوانِ دوم، ماهیت و وضعیت همان‌جا در خانه ویرایش می‌شوند؛ «+»ِ هر ردیف (یا Ctrl+Enter) حسابِ تازه‌ای
 * زیرِ همان سرفصل با کدِ پیشنهادیِ سرور می‌سازد؛ خانه‌ی عوض‌شده ته‌رنگ می‌گیرد و «ذخیره تغییرات» (Ctrl+S) همه را
 * یک‌جا و پشتِ‌سرِ‌هم می‌فرستد. ویژگی‌های حساب (شش پرچم) در ستونِ خودشان نشان داده می‌شوند و با کلیک باز می‌شوند —
 * کشوی ویرایش برای حسابِ ثبت‌شده، و گزینه‌های درجا برای حسابِ تازه.
 *
 * **حذف این‌جا نیست** (تنظیمات ← کدینگ): دکمه‌ی ویرانگر کنارِ دکمه‌ای که روزی صد بار زده می‌شود، دیر یا زود اشتباه
 * زده می‌شود. غیرفعال‌سازی می‌ماند چون برگشت‌پذیر است. پیش‌نویس در `sessionStorage`ِ همین کسب‌وکار می‌ماند.
 */
export function ChartOfAccountsPage({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const nav = useNavSection()
  //: «سرفصل جدید» و «فهرست حساب‌ها»ی قدیمی با بخشِ `new`/`flat` به همین‌جا می‌رسند.
  const startAdding = nav?.activePage === 'acctchart' && nav.section === 'new'
  const startFlat = nav?.activePage === 'acctchart' && nav.section === 'flat'

  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  //: مانده‌ها اختیاری‌اند: اگر نیامدند، برگه بی ستونِ مانده کار می‌کند.
  const trial = useAsync(() => fetchTrialBalance(token).catch(() => []), [token])
  const [draft, setDraft] = useState<Draft>(loadDraft)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [find, setFind] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [showInactive, setShowInactive] = useState(true)
  const [flat, setFlat] = useState(startFlat)
  //: درخت پیش‌فرض **بسته** است: با ۶۰+ حساب، بازبودنِ همه دیواری از ردیف است که ساختاری نشان نمی‌دهد.
  const [collapsed, setCollapsed] = useState<Set<string> | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(() =>
    isEmptyDraft(loadDraft()) ? null : { text: 'تغییرهای ذخیره‌نشده‌ی دفعه‌ی قبل برگشت — «ذخیره تغییرات» بزنید.', kind: 'ok' },
  )
  const [ledger, setLedger] = useState<{ id: string; code: string; name: string } | null>(null)
  const [editing, setEditing] = useState<Node | null>(null)
  const [menu, setMenu] = useState<{ row: SheetRow; x: number; y: number } | null>(null)
  const [traitsOpen, setTraitsOpen] = useState<string | null>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const findRef = useRef<HTMLInputElement>(null)
  const focusedRow = useRef(0)
  const pendingFocus = useRef<string | null>(null)
  const cw = useColumnWidths('cubita.grid.chart.shares', LAYOUT)
  const { selected, click, clear } = useRowSelection()
  useAlignToGrid(formRef, '.jf-foot--cols', { table: '.ca-sheet', slots: SLOTS })

  //: پیش‌نویس با هر تغییر در نشستِ همین کسب‌وکار؛ خالی = پاک.
  useEffect(() => {
    const key = tenantKey(DRAFT_KEY)
    if (!key) return
    try {
      if (isEmptyDraft(draft)) sessionStorage.removeItem(key)
      else sessionStorage.setItem(key, JSON.stringify(draft))
    } catch {
      //: ذخیره‌نشدنِ پیش‌نویس فقط یعنی با بستنِ صفحه می‌رود؛ برگه باید کار کند.
    }
  }, [draft])

  const list = useMemo(() => accounts.data ?? [], [accounts.data])
  const balances = useMemo(
    () => new Map((trial.data ?? []).map((r) => [r.account_id, Number(r.balance) || 0])),
    [trial.data],
  )
  const roots = useMemo(() => buildTree(list, balances), [list, balances])
  const byId = useMemo(() => {
    const m = new Map<string, Node>()
    const walk = (ns: Node[]) => ns.forEach((n) => (m.set(n.id, n), walk(n.children)))
    walk(roots)
    return m
  }, [roots])
  const groupIds = useMemo(() => [...byId.values()].filter((n) => n.children.length > 0).map((n) => n.id), [byId])
  //: فقط بارِ اول جمع می‌شود؛ به‌روزرسانی‌های بعدی نباید آنچه کاربر باز کرده را ببندند.
  useEffect(() => {
    if (collapsed === null && accounts.data) setCollapsed(new Set(groupIds))
  }, [collapsed, accounts.data, groupIds])

  const visible = useMemo(() => matchingIds(roots, find), [roots, find])
  const nodes = useMemo(
    () =>
      visibleNodes(roots, { collapsed: collapsed ?? new Set(), visible, type: typeFilter, showInactive, flat }),
    [roots, collapsed, visible, typeFilter, showInactive, flat],
  )
  const rows = useMemo(() => sheetRows(nodes, draft, byId), [nodes, draft, byId])
  const owners = useMemo(() => codeOwners(list, draft), [list, draft])
  const counts = pendingCount(draft, list)
  const order = rows.map((r) => r.key)
  const picked = rows.filter((r) => selected.has(r.key))
  const stats = useMemo(
    () => ({
      total: list.length,
      groups: list.filter((a) => a.is_group).length,
      leaves: list.filter((a) => !a.is_group).length,
      inactive: list.filter((a) => !a.is_active).length,
    }),
    [list],
  )

  // ── ویرایش ──
  function edit(r: SheetRow, patch: Partial<Values>) {
    setErrors((e) => (e[r.key] ? omit(e, [r.key]) : e))
    setDraft((d) =>
      r.kind === 'saved'
        ? { ...d, edits: { ...d.edits, [r.key]: { ...d.edits[r.key], ...patch } } }
        : { ...d, fresh: d.fresh.map((f) => (f.key === r.key ? { ...f, ...patch } : f)) },
    )
  }
  function editFresh(key: string, patch: Partial<FreshAccount>) {
    setDraft((d) => ({ ...d, fresh: d.fresh.map((f) => (f.key === key ? { ...f, ...patch } : f)) }))
  }
  function setActive(targets: SheetRow[], active: boolean) {
    setDraft((d) => {
      const edits = { ...d.edits }
      for (const r of targets) if (r.kind === 'saved') edits[r.key] = { ...edits[r.key], is_active: active }
      return { ...d, edits }
    })
  }

  /** حسابِ تازه زیرِ `parent` (یا ریشه). مادر باز می‌شود و کدِ پیشنهادی از سرور می‌آید (قاعده‌ی کدینگ آن‌جاست). */
  function addUnder(parent: Node | null) {
    const key = newKey()
    const fresh: FreshAccount = {
      key,
      parentId: parent?.id ?? null,
      code: '',
      name: '',
      name2: '',
      nature: '',
      isGroup: false,
      type: parent?.type ?? 'expense',
      traits: NEW_TRAITS,
    }
    setDraft((d) => ({ ...d, fresh: [...d.fresh, fresh] }))
    if (parent) setCollapsed((c) => new Set([...(c ?? [])].filter((id) => id !== parent.id)))
    pendingFocus.current = key
    void fetchNextAccountCode(token, parent?.id ?? null)
      .then((r) =>
        setDraft((d) => {
          const taken = codeOwners(list, d)
          return {
            ...d,
            fresh: d.fresh.map((f) => (f.key === key && !f.code ? { ...f, code: nextFreeCode(r.code, taken) } : f)),
          }
        }),
      )
      .catch(() => setMsg({ text: 'کدِ پیشنهادی خوانده نشد؛ کد را دستی وارد کنید.', kind: 'err' }))
  }
  /** Ctrl+Enter روی یک ردیف: زیرِ سرفصل فرزند، کنارِ حساب هم‌سطح (زیرِ همان مادر). */
  function addFromRow(r: SheetRow | undefined) {
    if (!r) return addUnder(null)
    if (r.kind === 'new') return addUnder(r.fresh.parentId ? (byId.get(r.fresh.parentId) ?? null) : null)
    if (r.node.is_group) return addUnder(r.node)
    return addUnder(r.node.parent_id ? (byId.get(r.node.parent_id) ?? null) : null)
  }
  function dropRows(targets: SheetRow[]) {
    const fresh = targets.filter((r) => r.kind === 'new').map((r) => r.key)
    const saved = targets.filter((r) => r.kind === 'saved').map((r) => r.key)
    setDraft((d) => ({ edits: omit(d.edits, saved), fresh: d.fresh.filter((f) => !fresh.includes(f.key)) }))
    setErrors((e) => omit(e, [...fresh, ...saved]))
  }

  // ── ذخیره ──
  async function save() {
    const accountsById = new Map(list.map((a) => [a.id, a]))
    const problems: Record<string, string> = {}
    const jobs: { key: string; run: () => Promise<unknown> }[] = []
    for (const [id, e] of Object.entries(draft.edits)) {
      const a = accountsById.get(id)
      const patch = a ? patchOf(a, e) : null
      if (!a || !patch) continue
      const p = problemOf({ code: e.code ?? a.code, name: e.name ?? a.name }, id, owners)
      if (p) problems[id] = p
      else
        jobs.push({
          key: id,
          run: async () => {
            if (patch.fields) await updateAccount(token, id, patch.fields)
            if (patch.code) await changeAccountCode(token, id, patch.code)
          },
        })
    }
    for (const f of draft.fresh) {
      const parent = f.parentId ? accountsById.get(f.parentId) : undefined
      const p = f.parentId && !parent ? 'سرفصلِ مادر دیگر نیست.' : problemOf(f, f.key, owners)
      if (p) problems[f.key] = p
      else jobs.push({ key: f.key, run: () => createAccount(token, createBody(f, parent)) })
    }
    if (jobs.length === 0 && Object.keys(problems).length === 0) {
      setMsg({ text: 'تغییری برای ذخیره نیست.', kind: 'ok' })
      return
    }
    setBusy(true)
    setMsg(null)
    //: یکی‌یکی و نه موازی: خطای هر ردیف مالِ همان ردیف است، و دو کدِ تکراری نباید هر دو بنشینند.
    const done: string[] = []
    for (const j of jobs) {
      try {
        await j.run()
        done.push(j.key)
      } catch (err) {
        problems[j.key] = err instanceof Error ? err.message : 'خطای ناشناخته'
      }
    }
    setDraft((d) => ({ edits: omit(d.edits, done), fresh: d.fresh.filter((f) => !done.includes(f.key)) }))
    setErrors(problems)
    accounts.reload()
    trial.reload()
    if (done.length > 0) onChanged?.()
    setBusy(false)
    const bad = Object.keys(problems).length
    setMsg(
      bad > 0
        ? {
            text: `${faInt(bad)} ردیف ذخیره نشد — دلیلش زیرِ برگه است.${done.length ? ` ${faInt(done.length)} ردیف ذخیره شد.` : ''}`,
            kind: 'err',
          }
        : { text: `${faInt(done.length)} ردیف ذخیره شد.`, kind: 'ok' },
    )
  }

  const sheetNav = useSheetNav<Col>({
    gridRef,
    cols: COLS,
    rowCount: rows.length,
    enabled: (row, col) => {
      const r = rows[row]
      if (!r) return false
      if (col === 'nature') return !(r.kind === 'saved' ? r.node.is_group : r.fresh.isGroup)
      if (col === 'active') return r.kind === 'saved'
      return true
    },
    //: Enter: کد → نام → ردیفِ بعد. عنوانِ دوم، ماهیت و وضعیت اختیاری‌اند؛ Tab و موس به آن‌ها می‌رسند.
    enterPath: (row, col) => (col === 'code' || col === 'name') && rows[row] !== undefined,
    onAppendRow: () => addFromRow(rows[focusedRow.current]),
    onDeleteRow: (row) => {
      const targets = picked.length > 0 ? picked : rows[row] ? [rows[row]] : []
      const touched = targets.filter((r) => r.kind === 'new' || draft.edits[r.key])
      if (touched.length === 0) return false
      dropRows(touched)
      return true
    },
    rowHasContent: () => false,
  })
  //: ردیفِ تازه‌ای که همین حالا ساخته شد، بعد از رندر فوکوس می‌گیرد (خانه‌ی نام).
  useEffect(() => {
    const key = pendingFocus.current
    if (!key) return
    const i = rows.findIndex((r) => r.key === key)
    if (i < 0) return
    pendingFocus.current = null
    sheetNav.focusCell(i, 1)
  })

  //: «سرفصل جدید»ِ قدیمی: بارِ اول یک حسابِ ریشه‌ی تازه با کدِ پیشنهادی.
  const didStartAdd = useRef(false)
  useEffect(() => {
    if (!startAdding || didStartAdd.current || !accounts.data) return
    didStartAdd.current = true
    if (draft.fresh.length === 0) addUnder(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startAdding, accounts.data])

  const head = (id: string, label: string, next: string, title?: string, className?: string) => (
    <th data-col={id} title={title} className={className}>
      {label}
      {cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  const errorList = rows.filter((r) => errors[r.key])
  const state: SheetState = errorList.length > 0 ? 'err' : counts.fresh + counts.edited > 0 ? 'dirty' : 'clean'
  const loading = (accounts.loading && !accounts.data) || collapsed === null

  return (
    <OpsPage
      canvas
      icon={ListTree}
      title="درختواره حساب‌ها"
      description="ساختارِ کاملِ چارت با مانده‌ی هر حساب — کد، نام، ماهیت و وضعیت همان‌جا در خانه ویرایش می‌شوند و «+» زیرِ هر سرفصل حسابِ تازه می‌سازد. قالب‌های صنفی و حذفِ حساب در تنظیمات ← کدینگ است."
      head={
        <div className="jh-bar jh-bar--report" role="group" aria-label="نمای درختواره">
          <div className="jh-row ca-row--view">
            <div className="jh-field">
              <span className="jh-label">نوع</span>
              <div className="cc-presets rh-seg" role="group" aria-label="نوعِ حساب">
                {[['', 'همه'], ...Object.entries(TYPE_LABELS)].map(([k, v]) => (
                  <button
                    key={k}
                    type="button"
                    className={typeFilter === k ? 'is-active' : ''}
                    aria-pressed={typeFilter === k}
                    onClick={() => setTypeFilter(k)}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
            <div className="jh-field">
              <span className="jh-label">نما</span>
              <div className="cc-presets rh-seg" role="group" aria-label="نمای درختواره">
                <button
                  type="button"
                  className={flat ? '' : 'is-active'}
                  aria-pressed={!flat}
                  title="با تورفتگی و جمع‌شدنِ سرفصل‌ها"
                  onClick={() => setFlat(false)}
                >
                  درختی
                </button>
                <button
                  type="button"
                  className={flat ? 'is-active' : ''}
                  aria-pressed={flat}
                  title="همه‌ی حساب‌ها بی‌تورفتگی، به ترتیبِ کد"
                  onClick={() => setFlat(true)}
                >
                  تخت
                </button>
              </div>
            </div>
            <div className="jh-field">
              <span className="jh-label">سرفصل‌ها</span>
              <div className="rh-links">
                <button type="button" disabled={flat} onClick={() => setCollapsed(new Set())}>
                  بازکردنِ همه
                </button>
                <button type="button" disabled={flat} onClick={() => setCollapsed(new Set(groupIds))}>
                  بستنِ همه
                </button>
              </div>
            </div>
            <div className="jh-field">
              <span className="jh-label">غیرفعال‌ها</span>
              <button
                type="button"
                className={`xl-toggle${showInactive ? ' is-on' : ''}`}
                aria-pressed={showInactive}
                title="حسابِ غیرفعال از فهرست‌های انتخاب پنهان است، نه از دفتر."
                onClick={() => setShowInactive(!showInactive)}
              >
                {showInactive ? 'نمایش' : 'پنهان'}
              </button>
            </div>
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
          icon={ListTree}
          title="حساب‌ها"
          description={
            accounts.data
              ? `${faInt(stats.total)} حساب — ${faInt(stats.groups)} سرفصل، ${faInt(stats.leaves)} حسابِ قابلِ ثبت${stats.inactive ? `، ${faInt(stats.inactive)} غیرفعال` : ''}`
              : undefined
          }
          tip="هر خانه را همان‌جا ویرایش کنید؛ «+»ِ هر ردیف (یا Ctrl+Enter) حسابِ تازه‌ای زیرِ همان سرفصل با کدِ پیشنهادی می‌سازد. خانه‌ی عوض‌شده ته‌رنگ می‌گیرد و «ذخیره تغییرات» (Ctrl+S) همه را یک‌جا می‌فرستد؛ Ctrl+Delete تغییرِ ردیف را برمی‌گرداند. ویژگی‌ها (ارزی، پیگیری، …) با کلیک روی ستونِ «ویژگی‌ها». نوعِ هر حساب از سرفصلش می‌آید؛ فقط سرفصلِ ریشه نوعِ دستی می‌گیرد."
          badge={<CountBadge accent>{faInt(stats.total)} حساب</CountBadge>}
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
                      sheetNav.focusCell(0, 1)
                    }
                  }}
                  placeholder="جست‌وجو: کد یا نام"
                  aria-label="جست‌وجو در حساب‌ها — کد، نام یا عنوانِ دوم"
                  aria-keyshortcuts="Control+F"
                  title="Ctrl+F — Esc: پاک‌کردن"
                />
              </div>
              <button type="button" className="ef-btn-secondary" onClick={() => addUnder(null)} disabled={busy}>
                <Plus size={14} /> سرفصلِ ریشه
              </button>
              <button
                type="button"
                className="ef-btn-secondary"
                title="به‌روزرسانی از سرور"
                aria-label="به‌روزرسانی"
                onClick={() => {
                  accounts.reload()
                  trial.reload()
                }}
              >
                <RefreshCw size={14} />
              </button>
            </div>
          }
        >
          <AsyncBlock loading={loading} error={accounts.data ? null : accounts.error}>
            {list.length === 0 && draft.fresh.length === 0 ? (
              <EmptyState
                icon={ListTree}
                //: کاربرِ تازه نمی‌داند قالب‌های آماده وجود دارند. «حسابی وجود ندارد» بن‌بست بود.
                text="حسابی وجود ندارد. برای شروع، از تنظیمات ← کدینگ یکی از قالب‌های آماده را درج کنید، یا «سرفصلِ ریشه» بزنید."
              />
            ) : (
              <div className="jg">
                <div
                  ref={gridRef}
                  className="table-scroll ef-table-wrap jg-wrap"
                  onKeyDown={sheetNav.onKeyDown}
                  onFocus={(e) => {
                    const cell = (e.target as HTMLElement).closest<HTMLElement>('[data-cell]')
                    if (cell?.dataset.cell) focusedRow.current = Number(cell.dataset.cell.split('-')[0])
                  }}
                  role="grid"
                  aria-label="برگه‌ی حساب‌ها"
                >
                  <table ref={cw.frame} className="ef-table ef-table--edit jg-table xl-grid table-plain ca-sheet">
                    <colgroup>
                      <col className="jg-c-num" style={cw.col('num')} />
                      <col className="ca-c-code" style={cw.col('code')} />
                      <col className="jg-c-account" style={cw.col('name')} />
                      <col className="ca-c-name2 ca-mhide" style={cw.col('name2')} />
                      <col className="ca-c-nature" style={cw.col('nature')} />
                      <col className="ca-c-kind ca-mhide" style={cw.col('kind')} />
                      <col className="ca-c-traits ca-mhide" style={cw.col('traits')} />
                      <col className="ca-c-bal" style={cw.col('balance')} />
                      <col className="ca-c-state" style={cw.col('active')} />
                      <col className="ca-c-act" style={cw.col('actions')} />
                    </colgroup>
                    <thead>
                      <tr>
                        <th className="ef-col-min xl-rowhead" data-col="num">
                          ردیف
                        </th>
                        {head('code', 'کد', 'name', 'تغییرِ کد امن است: ثبتِ خودکار حساب را با نقشش پیدا می‌کند، نه با کد.')}
                        {head('name', 'نامِ حساب', 'name2')}
                        {head('name2', 'عنوانِ دوم', 'nature', 'برای گزارشِ دوزبانه (معمولاً انگلیسی).', 'ca-mhide')}
                        {head('nature', 'ماهیت', 'kind', 'فقط معیارِ گزارشِ «خلافِ ماهیت»؛ جلوی ثبت را نمی‌گیرد.')}
                        {head('kind', 'نوع و سطح', 'traits', undefined, 'ca-mhide')}
                        {head('traits', 'ویژگی‌ها', 'balance', 'کلیک: ویرایشِ ویژگی‌های حساب', 'ca-mhide')}
                        {head('balance', 'مانده', 'active')}
                        {head('active', 'وضعیت', 'actions')}
                        <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r, i) => (
                        <ChartRow
                          key={r.key}
                          r={r}
                          i={i}
                          flat={flat}
                          open={!(collapsed ?? new Set()).has(r.key) || find.trim() !== ''}
                          selected={selected.has(r.key)}
                          error={errors[r.key]}
                          traitsOpen={traitsOpen === r.key}
                          busy={busy}
                          parentOf={(id) => (id ? byId.get(id) : undefined)}
                          onPick={(e) => click(order, r.key, modsOf(e))}
                          onEdit={(patch) => edit(r, patch)}
                          onFresh={(patch) => r.kind === 'new' && editFresh(r.key, patch)}
                          onToggleOpen={() =>
                            setCollapsed((c) => {
                              const next = new Set(c ?? [])
                              if (next.has(r.key)) next.delete(r.key)
                              else next.add(r.key)
                              return next
                            })
                          }
                          onToggleActive={() => setActive([r], !r.values.is_active)}
                          onAdd={() => r.kind === 'saved' && addUnder(r.node)}
                          onTraits={() =>
                            r.kind === 'saved' ? setEditing(r.node) : setTraitsOpen(traitsOpen === r.key ? null : r.key)
                          }
                          onLedger={() =>
                            r.kind === 'saved' && setLedger({ id: r.node.id, code: r.node.code, name: r.node.name })
                          }
                          onDrop={() => dropRows([r])}
                          onMenu={(e) => {
                            e.preventDefault()
                            setMenu({ row: r, x: e.clientX, y: e.clientY })
                          }}
                        />
                      ))}
                      {rows.length === 0 && (
                        <tr>
                          <td className="ca-empty" colSpan={10}>
                            حسابی با این جست‌وجو یا فیلتر نیست.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                {picked.length > 0 && (
                  <SelectionBar count={picked.length} unit="ردیف" onClear={clear}>
                    <button type="button" onClick={() => setActive(picked, true)}>
                      فعال‌کردن
                    </button>
                    <button type="button" onClick={() => setActive(picked, false)}>
                      غیرفعال‌کردن
                    </button>
                    <button type="button" onClick={() => dropRows(picked)}>
                      <RotateCcw size={14} aria-hidden="true" /> برگرداندنِ تغییرها
                    </button>
                  </SelectionBar>
                )}
              </div>
            )}
            {errorList.length > 0 && (
              <ul className="xl-errbar" role="alert">
                {errorList.map((r) => (
                  <li key={r.key}>
                    <b>{r.values.name.trim() || r.values.code.trim() || 'حسابِ تازه'}</b> — {errors[r.key]}
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
          labels={['حسابِ تازه', 'ویرایش‌شده']}
          columns
        />
      </form>

      {menu && (
        <ContextMenu
          menu={menu}
          onClose={() => setMenu(null)}
          onAdd={() => menu.row.kind === 'saved' && addUnder(menu.row.node)}
          onEdit={() => menu.row.kind === 'saved' && setEditing(menu.row.node)}
          onLedger={() =>
            menu.row.kind === 'saved' &&
            setLedger({ id: menu.row.node.id, code: menu.row.node.code, name: menu.row.node.name })
          }
        />
      )}

      {ledger && <AccountLedgerDrawer token={token} account={ledger} onClose={() => setLedger(null)} />}

      {editing && (
        <AccountEditDrawer
          token={token}
          account={editing}
          levelLabel={levelLabel(editing.depth)}
          //: مسیرِ کامل منهای خودِ حساب — همان «حساب سرشاخه»، ولی با کلِ مسیر.
          parentName={editing.fullName.split(' › ').slice(0, -1).join(' › ')}
          typeLabel={TYPE_LABELS[editing.type] ?? editing.type}
          onClose={() => setEditing(null)}
          onSaved={(text) => {
            setEditing(null)
            setMsg({ text, kind: 'ok' })
            accounts.reload()
            onChanged?.()
          }}
        />
      )}
    </OpsPage>
  )
}

/** یک ردیفِ برگه — ثبت‌شده یا تازه. خانه‌ی عوض‌شده `is-changed` می‌گیرد (ته‌رنگِ اکسلیِ «ویرایش‌شده»). */
function ChartRow({
  r,
  i,
  flat,
  open,
  selected,
  error,
  traitsOpen,
  busy,
  parentOf,
  onPick,
  onEdit,
  onFresh,
  onToggleOpen,
  onToggleActive,
  onAdd,
  onTraits,
  onLedger,
  onDrop,
  onMenu,
}: {
  r: SheetRow
  i: number
  flat: boolean
  open: boolean
  selected: boolean
  error?: string
  traitsOpen: boolean
  busy: boolean
  parentOf: (id: string | null) => Node | undefined
  onPick: (e: MouseEvent) => void
  onEdit: (patch: Partial<Values>) => void
  onFresh: (patch: Partial<FreshAccount>) => void
  onToggleOpen: () => void
  onToggleActive: () => void
  onAdd: () => void
  onTraits: () => void
  onLedger: () => void
  onDrop: () => void
  onMenu: (e: MouseEvent) => void
}) {
  const saved = r.kind === 'saved' ? r.node : null
  const isGroup = saved ? saved.is_group : r.kind === 'new' && r.fresh.isGroup
  const depth = saved ? saved.depth : r.kind === 'new' ? r.depth : 0
  const hasChildren = Boolean(saved && saved.children.length > 0)
  const orig: Values | null = saved
    ? { code: saved.code, name: saved.name, name2: saved.name2 ?? '', nature: (saved.nature ?? '') as Nature, is_active: saved.is_active }
    : null
  const changed = (f: keyof Values) => Boolean(orig && String(r.values[f]).trim() !== String(orig[f]).trim())
  const dirty = Boolean(orig && (['code', 'name', 'name2', 'nature', 'is_active'] as (keyof Values)[]).some(changed))
  const cls = [
    selected && 'is-selected',
    r.kind === 'new' && 'xl-row--new',
    dirty && 'xl-row--dirty',
    error && 'xl-row--error',
    !r.values.is_active && 'xl-row--off',
    isGroup && 'ca-group',
  ]
    .filter(Boolean)
    .join(' ')
  const text = (f: 'code' | 'name' | 'name2', label: string, extra: { dir?: 'ltr'; placeholder?: string } = {}) => (
    <input
      type="text"
      aria-label={`${label}ِ ردیفِ ${faInt(i + 1)}`}
      value={r.values[f]}
      onChange={(e) => onEdit({ [f]: e.target.value })}
      {...extra}
    />
  )
  const parent = r.kind === 'new' ? parentOf(r.fresh.parentId) : undefined
  const type = saved ? saved.type : r.kind === 'new' ? (parent?.type ?? r.fresh.type) : ''
  const traits: AccountTraits | null = saved ?? (r.kind === 'new' ? r.fresh.traits : null)

  return (
    <tr className={cls || undefined} title={error} onContextMenu={saved ? onMenu : undefined}>
      <td className="ef-col-min jg-num xl-rowhead card-title">
        <button
          type="button"
          tabIndex={-1}
          className="xl-rowhead-btn"
          aria-pressed={selected}
          aria-label={`انتخابِ ردیفِ ${faInt(i + 1)}`}
          onClick={onPick}
        >
          {r.kind === 'new' ? '+' : faInt(i + 1)}
        </button>
      </td>
      <td data-cell={`${i}-0`} className={changed('code') ? 'is-changed' : undefined}>
        {text('code', 'کد', { dir: 'ltr' })}
      </td>
      <td
        data-label="نام"
        data-cell={`${i}-1`}
        className={`ca-name${changed('name') ? ' is-changed' : ''}`}
        style={{ '--ca-depth': flat ? 0 : depth } as CSSProperties}
      >
        <div className="ca-name-in">
          {!flat &&
            (hasChildren ? (
              <button
                type="button"
                tabIndex={-1}
                className="ca-toggle"
                aria-expanded={open}
                aria-label={open ? 'بستنِ سرفصل' : 'بازکردنِ سرفصل'}
                onClick={onToggleOpen}
              >
                {open ? <ChevronDown size={14} /> : <ChevronLeft size={14} />}
              </button>
            ) : (
              <span className="ca-toggle ca-toggle--leaf" aria-hidden="true" />
            ))}
          {text('name', 'نام', r.kind === 'new' ? { placeholder: 'نامِ حسابِ تازه…' } : {})}
          {saved?.system_role && <span className="chart-sys-tag">سیستمی</span>}
        </div>
      </td>
      <td data-cell={`${i}-2`} className={`ca-mhide${changed('name2') ? ' is-changed' : ''}`}>
        {text('name2', 'عنوانِ دوم', { dir: 'ltr' })}
      </td>
      <td data-cell={`${i}-3`} className={isGroup ? 'xl-ro' : changed('nature') ? 'is-changed' : undefined}>
        {isGroup ? (
          <span className="ca-muted">—</span>
        ) : (
          <SearchSelect
            aria-label={`ماهیتِ ردیفِ ${faInt(i + 1)}`}
            value={r.values.nature}
            onChange={(e) => onEdit({ nature: e.target.value as Nature })}
          >
            <option value="">
              {saved ? `خودکار: ${ACCOUNT_NATURE_LABELS[saved.effective_nature] ?? saved.effective_nature}` : 'خودکار (از نوع)'}
            </option>
            <option value="debit">بدهکار</option>
            <option value="credit">بستانکار</option>
            <option value="any">مهم نیست</option>
          </SearchSelect>
        )}
      </td>
      <td className="xl-txt ca-kind ca-mhide" data-label="نوع و سطح">
        <div className="ca-kind-in">
        {r.kind === 'new' && !parent ? (
          <SearchSelect aria-label="نوعِ سرفصلِ ریشه" value={r.fresh.type} onChange={(e) => onFresh({ type: e.target.value })}>
            {Object.entries(TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </SearchSelect>
        ) : r.kind === 'new' ? (
          //: حسابِ تازه‌ی زیرِ سرفصل: نوع از مادر است؛ سطح را کلیدِ «حساب/سرفصل» کنارش می‌گوید.
          <span>{TYPE_LABELS[type] ?? type}</span>
        ) : (
          <span>
            {TYPE_LABELS[type] ?? type} · <span className={`tree-level tree-level--l${Math.min(depth, 3)}`}>{levelLabel(depth)}</span>
          </span>
        )}
        {r.kind === 'new' && (
          <button
            type="button"
            className={`xl-toggle ca-isgroup${r.fresh.isGroup ? ' is-on' : ''}`}
            aria-pressed={r.fresh.isGroup}
            title="سرفصل زیرحساب می‌گیرد و خودش سند نمی‌خورد."
            onClick={() => onFresh({ isGroup: !r.fresh.isGroup })}
          >
            {r.fresh.isGroup ? 'سرفصل' : 'حساب'}
          </button>
        )}
        </div>
      </td>
      <td className="ca-traits ca-mhide" data-label="ویژگی‌ها">
        <button
          type="button"
          className="ca-traits-btn"
          title={saved ? 'ویرایشِ ویژگی‌های حساب' : 'ویژگی‌های حسابِ تازه'}
          aria-expanded={r.kind === 'new' ? traitsOpen : undefined}
          onClick={onTraits}
        >
          {traits && TRAIT_TAGS.some(({ key }) => traits[key]) ? (
            TRAIT_TAGS.map(({ key, tag, title }) =>
              traits[key] ? (
                <span key={key} className="chart-trait-tag" title={title}>
                  {tag}
                </span>
              ) : null,
            )
          ) : (
            <span className="ca-muted">—</span>
          )}
          {traits && !traits.in_management_reports && (
            <span className="chart-trait-tag chart-trait-tag--off" title="از گزارش‌های مدیریتی کنار گذاشته شده">
              بی گزارشِ مدیریتی
            </span>
          )}
          {saved && <Pencil size={12} className="ca-traits-edit" aria-hidden="true" />}
        </button>
        {r.kind === 'new' && traitsOpen && (
          <div className="ca-traits-pop" role="dialog" aria-label="ویژگی‌های حسابِ تازه">
            {ACCOUNT_TRAIT_META.map((t) => {
              const locked = t.key === 'fx_revaluable' && !r.fresh.traits.is_fx
              return (
                <label key={t.key} className="fy-check" title={locked ? 'اول «ارزی» را روشن کنید.' : t.hint}>
                  <input
                    type="checkbox"
                    checked={r.fresh.traits[t.key]}
                    disabled={locked}
                    onChange={(e) => {
                      const next = { ...r.fresh.traits, [t.key]: e.target.checked }
                      if (t.key === 'is_fx' && !e.target.checked) next.fx_revaluable = false
                      onFresh({ traits: next })
                    }}
                  />
                  {t.label}
                </label>
              )
            })}
          </div>
        )}
      </td>
      <td className="num xl-ro" data-label="مانده">
        {saved ? <Amount value={saved.balance} /> : '—'}
      </td>
      <td data-cell={`${i}-4`} className={changed('is_active') ? 'is-changed' : undefined}>
        <button
          type="button"
          className={`xl-toggle${r.values.is_active ? ' is-on' : ''}`}
          aria-pressed={r.values.is_active}
          aria-label={`وضعیتِ ردیفِ ${faInt(i + 1)}: ${r.values.is_active ? 'فعال' : 'غیرفعال'}`}
          disabled={r.kind === 'new'}
          title={
            r.kind === 'new'
              ? 'حسابِ تازه فعال ساخته می‌شود.'
              : r.values.is_active
                ? 'از فهرست‌های انتخاب پنهان شود'
                : 'دوباره در فهرست‌ها دیده شود'
          }
          onClick={onToggleActive}
        >
          {r.values.is_active ? 'فعال' : 'غیرفعال'}
        </button>
      </td>
      <td className="ef-col-min jg-actions card-actions">
        <div className="row-actions">
          {saved ? (
            <>
              <RowAction
                icon={Plus}
                label={saved.is_group ? 'زیرحسابِ تازه' : 'تفصیلیِ تازه'}
                disabled={busy}
                //: روی معین هم هست، چون تفصیلی زیرِ معین می‌نشیند. اگر آن حساب سندِ مستقیم خورده باشد سرور با
                //: پیامِ روشن ردش می‌کند — بهتر از پنهان کردنِ دکمه.
                title={
                  saved.is_group
                    ? 'افزودنِ زیرحساب (Ctrl+Enter)'
                    : saved.accepts_tafsili || hasChildren
                      ? 'افزودنِ تفصیلی زیرِ این حساب'
                      : 'برای افزودنِ تفصیلی، اول در ویژگی‌ها «تفصیلی پذیر» را روشن کنید'
                }
                onClick={onAdd}
              />
              {!saved.is_group && <RowAction icon={BookOpen} label="کارتِ حساب" onClick={onLedger} />}
              {dirty && <RowAction icon={RotateCcw} label="برگرداندنِ تغییرها (Ctrl+Delete)" onClick={onDrop} />}
            </>
          ) : (
            <RowAction icon={Trash2} label="حذفِ ردیفِ تازه (Ctrl+Delete)" danger onClick={onDrop} />
          )}
        </div>
      </td>
    </tr>
  )
}

/** منوی راست‌کلیک — همان کارهای دکمه‌های ردیف. **افزوده است، نه جایگزین**: روی موبایل و وب کشف نمی‌شود. */
function ContextMenu({
  menu,
  onClose,
  onAdd,
  onEdit,
  onLedger,
}: {
  menu: { row: SheetRow; x: number; y: number }
  onClose: () => void
  onAdd: () => void
  onEdit: () => void
  onLedger: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    //: `capture` تا کلیک روی خودِ آیتم‌ها هم اول منو را ببندد و بعد کارش را بکند.
    window.addEventListener('click', onClose)
    window.addEventListener('scroll', onClose, true)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('click', onClose)
      window.removeEventListener('scroll', onClose, true)
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])
  if (menu.row.kind !== 'saved') return null
  const node = menu.row.node
  return (
    <div className="tree-menu" style={{ left: menu.x, top: menu.y }} role="menu">
      <div className="tree-menu-head">
        {node.code} — {node.name}
      </div>
      <button type="button" onClick={onAdd}>
        <Plus size={13} /> {node.is_group ? 'زیرحسابِ تازه' : 'تفصیلیِ تازه'}
      </button>
      <button type="button" onClick={onEdit}>
        <Pencil size={13} /> ویژگی‌ها و ویرایشِ کامل
      </button>
      {!node.is_group && (
        <button type="button" onClick={onLedger}>
          <BookOpen size={13} /> کارتِ حساب
        </button>
      )}
    </div>
  )
}

function omit<T>(o: Record<string, T>, keys: readonly string[]): Record<string, T> {
  const out = { ...o }
  for (const k of keys) delete out[k]
  return out
}
