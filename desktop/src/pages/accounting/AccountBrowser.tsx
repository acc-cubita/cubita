import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type RefObject,
} from 'react'
import {
  AlertTriangle,
  BookOpen,
  BookOpenCheck,
  ChevronDown,
  ChevronLeft,
  FilePlus2,
  FolderTree,
  Layers,
  ListTree,
  LocateFixed,
  Scale,
  Search,
  X,
} from 'lucide-react'
import {
  fetchAnalytics,
  fetchBalanceTree,
  fetchFiscalYears,
  fetchGeneralLedgerPage,
  type BalanceTreeNode,
  type GeneralLedger,
  type ReportFilters,
} from '../../api'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { ReportFilterBar } from '../../components/ReportFilterBar'
import { SavedViewBar } from '../../components/SavedViewBar'
import { SearchSelect } from '../../components/SearchSelect'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { formatJalali, todayIso } from '../../lib/jalali'
import {
  NATURE_LABEL,
  SIDE_LABEL,
  SIDE_SHORT,
  buildTreeIndex,
  isHidden,
  ledgerRaw,
  pathOf,
  revealIn,
  searchAccounts,
  sideOf,
  treeKey,
  visibleRows,
  type SearchHit,
  type TreeIndex,
  type VisibleRow,
} from '../../lib/accountTree'
import type { PageKey } from '../../lib/navModel'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import {
  OpsPage,
  RangeBar,
  fa,
  faAmount,
  faInt,
  jalaliYearStart,
  presetRange,
  useAsync,
  type Preset,
  type RangeState,
} from './kit'
import { tenantKey } from '../../lib/tenantScope'

/**
 * «مرور حساب‌ها» — UI-02: کاوشگرِ حرفه‌ایِ حساب، از سرفصل تا خودِ سند.
 *
 *     درخت (مانده‌ی هر سطح)  →  خلاصه‌ی حساب  →  گردش (دفترِ صفحه‌بندی‌شده)  →  سند
 *
 * **هیچ عددِ مالی در مرورگر ساخته نمی‌شود.** درخت با مانده‌ی تجمیعیِ هر سرفصل از
 * `/api/accounting/balance-tree` می‌آید (همان هسته‌ی تراز، جمع در سرور) و گردش از
 * `/api/reports/general-ledger/{id}` با `limit/offset` — مانده‌ی در حال اجرای هر برش
 * را سرور می‌دهد. پیش‌تر جمعِ سرفصل‌ها این‌جا با `reduce` زده می‌شد؛ حالا نه.
 *
 * **حفظِ زمینه.** سند در کشو روی همین صفحه باز می‌شود، پس بستنش (Esc) کاوشگر را
 * دست‌نخورده برمی‌گرداند. اگر کاربر به صفحه‌ی دیگری برود (ثبتِ سند) و برگردد،
 * گره‌های باز، حسابِ انتخاب‌شده، بازه، فیلترها، اسکرول و صفحه‌ی گردش از
 * `sessionStorage` برمی‌گردند.
 *
 * **چیدمان:** درخت سمتِ راست (شروعِ خواندنِ RTL)، خلاصه و گردش سمتِ چپ.
 */

const LEDGER_PAGE = 100
const STORE_KEY = 'cubita.accountBrowser.v1'

interface Persisted {
  preset: Preset
  custom: { from: string; to: string }
  filters: ReportFilters
  expanded: string[]
  selectedId: string | null
  hideZero: boolean
  activeOnly: boolean
  ledgerOffset: number
  ledgerRow: number
  treeScroll: number
}

//: به‌ازای کسب‌وکار (`tenantKey`). با کلیدِ سراسری، بعد از تعویضِ کسب‌وکار فیلترِ مرکز
//: هزینه یا تفصیلیِ کسب‌وکارِ قبلی به سرور می‌رفت و درخت بی‌صدا خالی می‌آمد.
function loadPersisted(): Partial<Persisted> {
  const key = tenantKey(STORE_KEY)
  if (!key) return {}
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as Partial<Persisted>) : {}
  } catch {
    return {}
  }
}

function savePersisted(p: Persisted) {
  const key = tenantKey(STORE_KEY)
  if (!key) return
  try {
    sessionStorage.setItem(key, JSON.stringify(p))
  } catch {
    /* حافظه‌ی نشست در دسترس نیست — فقط حفظِ زمینه از دست می‌رود. */
  }
}

const nodeDomId = (id: string) => `ab-node-${id}`

/** مبلغ با جهت: «۸۵۰٬۰۰۰ بد». صفر خط تیره است. */
function SideAmount({ raw, long = false }: { raw: number; long?: boolean }) {
  const { amount, side } = sideOf(raw)
  if (!side) return <span className="ab-amt ab-amt--zero">—</span>
  return (
    <span className={`ab-amt ab-amt--${side}`}>
      {fa(amount)} <small>{long ? SIDE_LABEL[side] : SIDE_SHORT[side]}</small>
    </span>
  )
}

// ═══════════════════════════════ ردیفِ درخت ═══════════════════════════════

const TreeRowView = memo(function TreeRowView({
  row,
  expanded,
  selected,
  onSelect,
  onToggle,
  onOpen,
}: {
  row: VisibleRow
  expanded: boolean
  selected: boolean
  onSelect: (id: string) => void
  onToggle: (id: string) => void
  onOpen: (id: string) => void
}) {
  const n = row.node
  //: ردیفِ گریدِ درخت (تمِ اکسلی): کد ستونِ خودش را دارد و تورفتگی فقط در ستونِ نام است، پس کدها
  //: زیرِ هم می‌مانند. نقش‌ها (`treeitem`) و شناسه‌ها همان‌اند — کیبورد و فوکوس دست نخورده‌اند.
  return (
    <tr
      id={nodeDomId(n.account_id)}
      role="treeitem"
      aria-level={row.level + 1}
      aria-expanded={row.expandable ? expanded : undefined}
      aria-selected={selected}
      className={`ab-row${selected ? ' is-selected' : ''}${n.is_active ? '' : ' is-inactive'}${n.is_group ? ' is-group' : ''}`}
      onClick={() => onSelect(n.account_id)}
      onDoubleClick={() => onOpen(n.account_id)}
    >
      <td className="ab-code-cell ab-codecol" data-label="کد">
        <span className="ab-code" dir="ltr">
          {n.account_code}
        </span>
      </td>
      <td className="ab-name-cell" data-label="نام حساب" style={{ '--ab-depth': row.level } as CSSProperties}>
        <span className="ab-name">
          <span
            className="ab-twisty"
            onClick={(e) => {
              if (!row.expandable) return
              e.stopPropagation()
              onSelect(n.account_id)
              onToggle(n.account_id)
            }}
          >
            {row.expandable ? expanded ? <ChevronDown size={14} /> : <ChevronLeft size={14} /> : null}
          </span>
          {/* قابِ باریک (موبایل): ستونِ کد پنهان است و کد جلوی نام می‌آید. */}
          <span className="ab-code ab-code-inline" dir="ltr">
            {n.account_code}
          </span>
          <span className="ab-name-text">{n.account_name}</span>
          {!n.is_active && <span className="ab-badge ab-badge--muted">غیرفعال</span>}
          {n.nature_violation && (
            <span className="ab-badge ab-badge--warn" title="مانده‌ی پایانِ دوره خلافِ ماهیتِ حساب است">
              هشدار ماهیت
            </span>
          )}
          {n.has_direct_lines && (
            <span className="ab-badge ab-badge--warn" title="این سرفصل خودش ردیفِ سند دارد؛ بررسی یکپارچگی را ببینید">
              ردیف روی سرفصل
            </span>
          )}
        </span>
      </td>
      <td className="num ab-turn" data-label="گردش بدهکار">
        {faAmount(n.period_debit)}
      </td>
      <td className="num ab-turn" data-label="گردش بستانکار">
        {faAmount(n.period_credit)}
      </td>
      <td className="num ab-bal" data-label="مانده">
        <SideAmount raw={Number(n.closing)} />
      </td>
    </tr>
  )
})

// ═══════════════════════════════ صفحه ═══════════════════════════════

export function AccountBrowsePage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate?: (page: PageKey) => void
}) {
  const initial = useRef(loadPersisted()).current

  // ── بازه — همان `RangeState`ِ kit، با مقدارِ اولیه از نشست ──
  const [preset, setPreset] = useState<Preset>(initial.preset ?? 'year')
  const [custom, setCustom] = useState(initial.custom ?? { from: jalaliYearStart(), to: todayIso() })
  const span = preset === 'custom' ? custom : presetRange(preset)
  const range: RangeState = { preset, setPreset, custom, setCustom, from: span.from, to: span.to }

  const [filters, setFilters] = useState<ReportFilters>(initial.filters ?? {})
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(initial.expanded ?? []))
  const [selectedId, setSelectedId] = useState<string | null>(initial.selectedId ?? null)
  const [hideZero, setHideZero] = useState(initial.hideZero ?? false)
  const [activeOnly, setActiveOnly] = useState(initial.activeOnly ?? false)
  const [ledgerOffset, setLedgerOffset] = useState(initial.ledgerOffset ?? 0)
  const [ledgerRow, setLedgerRow] = useState(initial.ledgerRow ?? 0)
  const [query, setQuery] = useState('')
  const [hitIndex, setHitIndex] = useState(0)
  const [entryId, setEntryId] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  //: درخواستِ فوکوس روی گردش. جدولِ گردش پس از رسیدنِ داده ساخته می‌شود، پس
  //: `focus()`ِ مستقیم به عنصری می‌خورد که هنوز نیست؛ شمارنده درخواست را نگه می‌دارد.
  const [ledgerFocus, setLedgerFocus] = useState(0)

  const treeRef = useRef<HTMLDivElement>(null)
  const ledgerRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const treeScroll = useRef(initial.treeScroll ?? 0)
  const restoredScroll = useRef(false)

  const scope: ReportFilters = useMemo(
    () => ({ ...filters, dateFrom: range.from, dateTo: range.to }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(filters), range.from, range.to],
  )
  const scopeKey = JSON.stringify(scope)

  const tree = useAsync(() => fetchBalanceTree(token, scope), [token, scopeKey])
  const fiscalYears = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
  const analytics = useAsync(() => fetchAnalytics(token).catch(() => []), [token])

  const index: TreeIndex = useMemo(() => buildTreeIndex(tree.data ?? []), [tree.data])
  const flags = useMemo(() => ({ hideZero, activeOnly }), [hideZero, activeOnly])
  const rows = useMemo(() => visibleRows(index, expanded, flags), [index, expanded, flags])
  const hits: SearchHit[] = useMemo(() => searchAccounts(index, query), [index, query])
  const selected = selectedId ? index.byId.get(selectedId) ?? null : null
  const selectedPath = useMemo(() => (selectedId ? pathOf(index, selectedId) : []), [index, selectedId])

  // اولین بار: ریشه‌ها باز تا سطحِ دوم دیده شود — درخت با یک خطِ «دارایی/بدهی/…» شروع نشود.
  const seeded = useRef(initial.expanded !== undefined)
  useEffect(() => {
    if (seeded.current || index.roots.length === 0) return
    seeded.current = true
    setExpanded(new Set(index.roots.map((r) => r.account_id)))
  }, [index])

  // ── حفظِ زمینه در نشست ──
  useEffect(() => {
    savePersisted({
      preset,
      custom,
      filters,
      expanded: [...expanded],
      selectedId,
      hideZero,
      activeOnly,
      ledgerOffset,
      ledgerRow,
      treeScroll: treeScroll.current,
    })
  }, [preset, custom, filters, expanded, selectedId, hideZero, activeOnly, ledgerOffset, ledgerRow])

  useEffect(
    () => () => {
      const saved = loadPersisted() as Persisted
      savePersisted({ ...saved, treeScroll: treeScroll.current })
    },
    [],
  )

  //: درخواستِ فوکوس روی درخت. وقتی جست‌وجو باز است درخت اصلاً ساخته نشده، پس
  //: `focus()`ِ مستقیم به هیچ می‌خورد و `requestAnimationFrame` روی رانرِ کُند دیر
  //: می‌رسد — کلیدِ بعدی به کادرِ جست‌وجو می‌رفت. این پس از همان رندر اجرا می‌شود.
  const wantTreeFocus = useRef(false)
  useLayoutEffect(() => {
    if (wantTreeFocus.current && treeRef.current) {
      wantTreeFocus.current = false
      treeRef.current.focus({ preventScroll: true })
    }
  })

  // اسکرولِ درخت فقط یک بار، وقتی ردیف‌ها رسیدند، برمی‌گردد.
  useLayoutEffect(() => {
    if (restoredScroll.current || rows.length === 0 || !treeRef.current) return
    restoredScroll.current = true
    treeRef.current.scrollTop = treeScroll.current
    //: کیبوردمحور: اگر فوکوس جای دیگری نیست (از فرمان‌یاب آمده‌ایم)، درخت آماده‌ی
    //: ↑↓ و «/» است — بی‌آن‌که اول کلیک لازم باشد.
    if (!document.activeElement || document.activeElement === document.body) {
      treeRef.current.focus({ preventScroll: true })
    }
  }, [rows.length])

  const selectedRef = useRef(selectedId)
  selectedRef.current = selectedId
  const focusRow = useCallback((id: string) => {
    //: حسابِ تازه از صفحه‌ی اولِ گردشش شروع می‌شود؛ همان حساب صفحه‌اش را نگه می‌دارد.
    if (selectedRef.current !== id) {
      setLedgerOffset(0)
      setLedgerRow(0)
    }
    setSelectedId(id)
    requestAnimationFrame(() => document.getElementById(nodeDomId(id))?.scrollIntoView({ block: 'nearest' }))
  }, [])

  const selectFromClick = useCallback(
    (id: string) => {
      focusRow(id)
      treeRef.current?.focus({ preventScroll: true })
    },
    [focusRow],
  )

  const toggle = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const openLedger = useCallback(
    (id: string) => {
      focusRow(id)
      setLedgerFocus((n) => n + 1)
    },
    [focusRow],
  )

  /** «نمایش در درخت»: نیاکان باز می‌شوند و حساب انتخاب و دیده می‌شود. */
  const reveal = useCallback(
    (id: string) => {
      const path = pathOf(index, id)
      if (path.some((n) => isHidden(n, flags))) {
        //: فیلترِ «صفر/بی‌گردش» گره را پنهان کرده بود — حساب حذف نشده، فقط دیده نمی‌شد.
        setHideZero(false)
        setActiveOnly(false)
        setNotice('برای نمایشِ این حساب، فیلترِ پنهان‌کردنِ حساب‌های صفر/بی‌گردش برداشته شد.')
      }
      setExpanded((prev) => revealIn(index, prev, id))
      setQuery('')
      focusRow(id)
      wantTreeFocus.current = true
    },
    [index, flags, focusRow],
  )

  // ── کیبوردِ درخت ──
  const onTreeKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === '/' || (e.key === 'f' && (e.ctrlKey || e.metaKey))) {
      e.preventDefault()
      searchRef.current?.focus()
      return
    }
    if (e.key === ' ' && selectedId) {
      e.preventDefault()
      toggle(selectedId)
      return
    }
    const r = treeKey(e.key, rows, selectedId, expanded)
    if (r.kind === 'none') return
    e.preventDefault()
    if (r.kind === 'focus') focusRow(r.id)
    else if (r.kind === 'expand' || r.kind === 'collapse') toggle(r.id)
    else if (r.kind === 'open') openLedger(r.id)
  }

  // ── کیبوردِ جست‌وجو ──
  const onSearchKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHitIndex((i) => Math.min(hits.length - 1, i + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHitIndex((i) => Math.max(0, i - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const hit = hits[hitIndex]
      if (hit) reveal(hit.node.account_id)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setQuery('')
      wantTreeFocus.current = true
    }
  }

  useEffect(() => {
    document.getElementById(`ab-hit-${hitIndex}`)?.scrollIntoView({ block: 'nearest' })
  }, [hitIndex])

  const setFiscalYear = (id: string) => {
    const fy = (fiscalYears.data ?? []).find((y) => y.id === id)
    if (!fy) return
    setCustom({ from: fy.start_date, to: fy.end_date })
    setPreset('custom')
  }
  const activeFy = (fiscalYears.data ?? []).find(
    (y) => preset === 'custom' && y.start_date === custom.from && y.end_date === custom.to,
  )

  const loadingFirst = tree.loading && !tree.data

  return (
    <OpsPage
      canvas
      icon={Layers}
      title="مرور حساب‌ها"
      description="از سرفصل تا سند: درختِ کدینگ با مانده‌ی هر سطح، گردشِ حساب و خودِ سند — بی‌ترکِ صفحه."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={
              <>
                {(fiscalYears.data ?? []).length > 0 && (
                  <label className="acc-inline-field">
                    سال مالی
                    <SearchSelect value={activeFy?.id ?? ''} onChange={(e) => setFiscalYear(e.target.value)}>
                      <option value="">—</option>
                      {(fiscalYears.data ?? []).map((y) => (
                        <option key={y.id} value={y.id}>
                          {y.title}
                        </option>
                      ))}
                    </SearchSelect>
                  </label>
                )}
                <ReportFilterBar token={token} filters={filters} onChange={setFilters} />
              </>
            }
          />
          <SavedViewBar
            token={token}
            viewKey="accounting.account_browse"
            filters={filters}
            range={range}
            setFilters={setFilters}
          />
          {onNavigate && (
            <div className="ab-quick" aria-label="دسترسی سریع">
              <button type="button" className="ef-btn-secondary" onClick={() => onNavigate('journalentry')}>
                <FilePlus2 size={14} /> ثبت سند جدید
              </button>
              <button type="button" className="ef-btn-secondary" onClick={() => onNavigate('ledgerreport')}>
                <BookOpenCheck size={14} /> دفتر کل
              </button>
              <button type="button" className="ef-btn-secondary" onClick={() => onNavigate('balancereport')}>
                <Scale size={14} /> تراز آزمایشی
              </button>
              <button type="button" className="ef-btn-secondary" onClick={() => onNavigate('acctchart')}>
                <ListTree size={14} /> کدینگ حساب‌ها
              </button>
            </div>
          )}
        </div>
      }
    >
      <section className="ab-split">
        {/* ─────────── درخت ─────────── */}
        <div className="ab-pane ab-pane--tree">
          <div className="ab-search">
            <Search size={15} />
            <input
              ref={searchRef}
              type="search"
              value={query}
              placeholder="جست‌وجوی کد یا نامِ حساب  ( / )"
              aria-label="جست‌وجوی حساب"
              aria-controls="ab-hits"
              aria-activedescendant={query && hits.length ? `ab-hit-${hitIndex}` : undefined}
              onChange={(e) => {
                setQuery(e.target.value)
                setHitIndex(0)
              }}
              onKeyDown={onSearchKey}
            />
            {query && (
              <button type="button" className="ab-icon-btn" aria-label="پاک‌کردنِ جست‌وجو" onClick={() => setQuery('')}>
                <X size={14} />
              </button>
            )}
          </div>
          <div className="ab-toggles">
            <label>
              <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
              فقط حساب‌های دارای گردش
            </label>
            <label>
              <input type="checkbox" checked={hideZero} onChange={(e) => setHideZero(e.target.checked)} />
              مخفی‌کردنِ حساب‌های با مانده‌ی صفر
            </label>
            {tree.loading && tree.data && <span className="muted">در حال به‌روزرسانی…</span>}
          </div>
          {notice && (
            <p className="hint ab-notice">
              {notice}
              <button type="button" className="ab-icon-btn" aria-label="بستن" onClick={() => setNotice(null)}>
                <X size={12} />
              </button>
            </p>
          )}

          {query ? (
            <div id="ab-hits" role="listbox" className="ab-hits" aria-label="نتیجه‌ی جست‌وجو">
              {hits.length === 0 && <p className="muted ab-empty">حسابی با این کد یا نام پیدا نشد.</p>}
              {hits.map((hit, i) => (
                <div
                  key={hit.node.account_id}
                  id={`ab-hit-${i}`}
                  role="option"
                  aria-selected={i === hitIndex}
                  className={`ab-hit${i === hitIndex ? ' is-active' : ''}${hit.node.is_active ? '' : ' is-inactive'}`}
                  onMouseEnter={() => setHitIndex(i)}
                  onClick={() => reveal(hit.node.account_id)}
                >
                  <div className="ab-hit-main">
                    <span className="ab-code" dir="ltr">
                      {hit.node.account_code}
                    </span>
                    <span className="ab-name-text">{hit.node.account_name}</span>
                    {!hit.node.is_active && <span className="ab-badge ab-badge--muted">غیرفعال</span>}
                    <span className="ab-bal num">
                      <SideAmount raw={Number(hit.node.closing)} />
                    </span>
                  </div>
                  <div className="ab-hit-path">
                    {hit.path.slice(0, -1).map((p) => p.account_name).join(' / ') || 'ریشه'}
                  </div>
                  <button
                    type="button"
                    className="ab-link"
                    onClick={(e) => {
                      e.stopPropagation()
                      reveal(hit.node.account_id)
                    }}
                  >
                    <LocateFixed size={12} /> نمایش در درخت
                  </button>
                </div>
              ))}
            </div>
          ) : loadingFirst ? (
            <p className="muted ab-empty">در حال بارگذاری…</p>
          ) : tree.error ? (
            <div className="error">{tree.error}</div>
          ) : rows.length === 0 ? (
            <p className="muted ab-empty">
              {index.roots.length === 0
                ? 'هنوز حسابی در کدینگ نیست — از «درختواره حساب‌ها» بسازید.'
                : 'با این فیلترها حسابی نمانده؛ تیکِ «فقط دارای گردش» یا «مخفی‌کردنِ صفر» را بردارید.'}
            </p>
          ) : (
            <div
              ref={treeRef}
              role="tree"
              aria-label="درختِ حساب‌ها"
              tabIndex={0}
              className="table-scroll ef-table-wrap ab-tree"
              aria-activedescendant={selectedId ? nodeDomId(selectedId) : undefined}
              onKeyDown={onTreeKey}
              onScroll={(e) => (treeScroll.current = e.currentTarget.scrollTop)}
            >
              {/* گریدِ اکسلی با نقشِ درخت: جدول فقط چیدمان است (`presentation`)؛ ردیف‌ها `treeitem`اند. */}
              {/* عرضِ ستون‌ها از CSS است و کشیدنی نیست: دو ستونِ گردش در قابِ باریک پنهان می‌شوند
                  (کوئریِ ظرف) و لبه‌ی کنارِ ستونِ پنهان کشیدنی نمی‌ماند. */}
              <table role="presentation" className="ef-table xl-grid table-plain ab-treegrid">
                <colgroup>
                  <col className="ab-c-code ab-codecol" />
                  <col className="ab-c-name" />
                  <col className="ab-c-turn ab-turn" />
                  <col className="ab-c-turn ab-turn" />
                  <col className="ab-c-bal" />
                </colgroup>
                <thead aria-hidden="true">
                  <tr>
                    <th className="ab-codecol">کد</th>
                    <th>نام حساب</th>
                    <th className="num ab-turn">گردش بدهکار</th>
                    <th className="num ab-turn">گردش بستانکار</th>
                    <th className="num">مانده</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <TreeRowView
                      key={row.node.account_id}
                      row={row}
                      expanded={expanded.has(row.node.account_id)}
                      selected={row.node.account_id === selectedId}
                      onSelect={selectFromClick}
                      onToggle={toggle}
                      onOpen={openLedger}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="ab-keys">
            <kbd>↑</kbd>
            <kbd>↓</kbd> حرکت · <kbd>←</kbd> باز · <kbd>→</kbd> بستن/والد · <kbd>Enter</kbd> گردش ·{' '}
            <kbd>Esc</kbd> سطحِ بالا · <kbd>/</kbd> جست‌وجو
          </p>
        </div>

        {/* ─────────── خلاصه و گردش ─────────── */}
        <div className="ab-pane ab-pane--detail">
          {!selected ? (
            <div className="ab-placeholder">
              <FolderTree size={28} />
              <p>یک حساب را در درخت انتخاب کنید تا خلاصه و گردشش این‌جا بیاید.</p>
            </div>
          ) : (
            <>
              <AccountSummary
                node={selected}
                path={selectedPath}
                onPathClick={(id) => {
                  setExpanded((prev) => revealIn(index, prev, id))
                  focusRow(id)
                  treeRef.current?.focus({ preventScroll: true })
                }}
                analytics={analytics.data ?? []}
                analyticId={filters.analyticId}
                onAnalytic={(id) => setFilters({ ...filters, analyticId: id || undefined })}
                onShowLedger={() => setLedgerFocus((n) => n + 1)}
                onNewEntry={onNavigate ? () => onNavigate('journalentry') : undefined}
              />
              <LedgerPanel
                token={token}
                node={selected}
                scope={scope}
                scopeKey={scopeKey}
                offset={ledgerOffset}
                onOffset={(o) => {
                  setLedgerOffset(o)
                  setLedgerRow(0)
                }}
                row={ledgerRow}
                onRow={setLedgerRow}
                entryOpen={entryId !== null}
                onOpenEntry={setEntryId}
                onBack={() => treeRef.current?.focus()}
                tableRef={ledgerRef}
                focusRequest={ledgerFocus}
              />
            </>
          )}
        </div>
      </section>

      {entryId && (
        <JournalEntryDrawer
          token={token}
          entryId={entryId}
          onClose={() => {
            setEntryId(null)
            //: برگشت از سند به همان ردیفِ گردش — نه به ابتدای صفحه.
            setLedgerFocus((n) => n + 1)
          }}
        />
      )}
    </OpsPage>
  )
}

// ═══════════════════════════════ خلاصه‌ی حساب ═══════════════════════════════

const TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی',
  liability: 'بدهی',
  equity: 'سرمایه',
  income: 'درآمد',
  expense: 'هزینه',
}

function AccountSummary({
  node,
  path,
  onPathClick,
  analytics,
  analyticId,
  onAnalytic,
  onShowLedger,
  onNewEntry,
}: {
  node: BalanceTreeNode
  path: BalanceTreeNode[]
  onPathClick: (id: string) => void
  analytics: { id: string; code: string; name: string; is_active: boolean }[]
  analyticId?: string
  onAnalytic: (id: string) => void
  onShowLedger: () => void
  onNewEntry?: () => void
}) {
  return (
    <div className="ab-summary">
      <nav className="acc-trail ab-trail" aria-label="مسیرِ حساب">
        {path.map((p, i) => (
          <span key={p.account_id}>
            {i > 0 && <ChevronLeft size={12} />}
            <button
              type="button"
              className={i === path.length - 1 ? 'is-active' : ''}
              onClick={() => onPathClick(p.account_id)}
            >
              {p.account_name}
            </button>
          </span>
        ))}
      </nav>
      <div className="ab-summary-title">
        <strong>{node.account_name}</strong>
        <span className="ab-code" dir="ltr">
          {node.account_code}
        </span>
        <span className="ab-badge">{node.is_group ? `سرفصل · ${faInt(node.child_count)} زیرحساب` : 'حسابِ سطحِ آخر'}</span>
        <span className="ab-badge">{TYPE_LABELS[node.account_type] ?? node.account_type}</span>
        <span className="ab-badge">ماهیت: {NATURE_LABEL[node.nature] ?? node.nature}</span>
        {!node.is_active && <span className="ab-badge ab-badge--muted">غیرفعال</span>}
        {node.nature_violation && (
          <span className="ab-badge ab-badge--warn">
            <AlertTriangle size={11} /> هشدار ماهیت
          </span>
        )}
      </div>
      {node.has_direct_lines && (
        <p className="hint ab-warn">
          <AlertTriangle size={13} /> این سرفصل خودش ردیفِ سند دارد؛ مبلغش در مانده شمرده شده ولی در تراز (که فقط
          برگ‌ها را می‌آورد) نیست. «بررسی یکپارچگی» جزئیاتش را دارد.
        </p>
      )}
      <div className="ab-actions">
        <button type="button" className="ef-btn-secondary" onClick={onShowLedger}>
          <BookOpen size={14} /> مشاهده گردش
        </button>
        {node.accepts_tafsili && analytics.length > 0 && (
          <label className="acc-inline-field">
            گردش تفصیلی
            <SearchSelect value={analyticId ?? ''} onChange={(e) => onAnalytic(e.target.value)}>
              <option value="">همه‌ی تفصیلی‌ها</option>
              {analytics.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} — {a.name}
                  {a.is_active ? '' : ' (غیرفعال)'}
                </option>
              ))}
            </SearchSelect>
          </label>
        )}
        {onNewEntry && (
          <button type="button" className="ef-btn-secondary" onClick={onNewEntry}>
            <FilePlus2 size={14} /> ثبت سند جدید
          </button>
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════ گردشِ حساب ═══════════════════════════════

//: «شرح» کشسان است و باقیِ عرض را می‌گیرد. شماره‌ی ردیف و سه ستونِ مبلغ ثابت‌اند — مبلغ‌ها سمتِ چپِ قاب
//: میخ شده‌اند (`ab-pin`) و جایشان باید پیکسلیِ پایدار بماند. تاریخ، سند و ستون‌های اختیاری (حساب، تفصیلی،
//: مرکز) کشیدنی‌اند؛ اختیاری‌ها تا وقتی درصدی ندارند همان پیش‌فرضِ CSS.
const LEDGER_LAYOUT = { fixed: ['rowhead', 'debit', 'credit', 'bal'], auto: 'desc' } as const

/**
 * گردشِ حساب — گریدِ اکسلیِ فقط‌خواندنی (الگوی «د»): شماره‌ی ردیف برای انتخاب و جمعِ انتخاب در نوارِ پایین
 * (مثلِ نوارِ وضعیتِ اکسل)، ردیفِ «مانده‌ی اول دوره» بالا و «جمعِ بازه» چسبیده به پایین. گرید از لحظه‌ی
 * انتخابِ حساب ساخته می‌شود — ارقامِ بالا و پایین از گره‌ی درخت (سرور) می‌آیند و منتظرِ دفتر نمی‌مانند.
 */
function LedgerPanel({
  token,
  node,
  scope,
  scopeKey,
  offset,
  onOffset,
  row,
  onRow,
  entryOpen,
  onOpenEntry,
  onBack,
  tableRef,
  focusRequest,
}: {
  token: string
  node: BalanceTreeNode
  scope: ReportFilters
  scopeKey: string
  offset: number
  onOffset: (o: number) => void
  row: number
  onRow: (r: number) => void
  entryOpen: boolean
  onOpenEntry: (id: string) => void
  onBack: () => void
  tableRef: RefObject<HTMLDivElement | null>
  focusRequest: number
}) {
  const [data, setData] = useState<GeneralLedger | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const cw = useColumnWidths('cubita.grid.accountLedger.shares', LEDGER_LAYOUT)
  const { selected, click, clear } = useRowSelection()

  //: مکثِ کوتاه: حرکت با ↓ در درخت نباید برای هر حسابی که از رویش رد می‌شویم
  //: یک درخواستِ دفتر بفرستد.
  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    const t = setTimeout(() => {
      fetchGeneralLedgerPage(token, node.account_id, scope, LEDGER_PAGE, offset)
        .then((r) => {
          if (alive) {
            setData(r)
            setLoading(false)
          }
        })
        .catch((e) => {
          if (alive) {
            setError(e instanceof Error ? e.message : 'خطای ناشناخته')
            setLoading(false)
          }
        })
    }, 180)
    return () => {
      alive = false
      clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, node.account_id, scopeKey, offset])

  //: حساب، صفحه یا بازه‌ی دیگر یعنی ردیف‌های دیگر؛ انتخابِ قبلی معنا ندارد.
  useEffect(() => clear(), [node.account_id, offset, scopeKey, clear])

  const current = data && data.account_id === node.account_id ? data : null
  const lines = current?.lines ?? []
  const total = current?.total_lines ?? 0

  //: درخواستِ فوکوس به *همان حسابی* بسته است که برایش داده شد: اگر گردشِ آن حساب
  //: خالی بود یا کاربر پیش از رسیدنِ داده جای دیگری رفت، درخواست دور ریخته می‌شود —
  //: وگرنه حسابِ بعدی که با ↓ از رویش رد می‌شویم فوکوس را از درخت می‌دزدید. گرید همیشه
  //: ساخته شده است، پس «خالی» را خودمان می‌سنجیم نه نبودنِ عنصر.
  const pendingFocus = useRef<string | null>(null)
  useEffect(() => {
    if (focusRequest > 0) pendingFocus.current = node.account_id
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusRequest])
  useEffect(() => {
    const want = pendingFocus.current
    if (!want) return
    if (want !== node.account_id) {
      pendingFocus.current = null
      return
    }
    if (!current) return // هنوز در راه است
    pendingFocus.current = null
    if (total > 0) tableRef.current?.focus({ preventScroll: true })
  })
  const showAccount = node.is_group
  const showAnalytic = lines.some((l) => l.analytic_name)
  const showCenter = lines.some((l) => l.cost_center_name)
  const active = Math.min(row, Math.max(0, lines.length - 1))
  const order = lines.map((l) => l.line_id)
  const picked = lines.filter((l) => selected.has(l.line_id))
  const colIds = [
    'rowhead',
    'date',
    'doc',
    'desc',
    ...(showAccount ? ['account'] : []),
    ...(showAnalytic ? ['analytic'] : []),
    ...(showCenter ? ['center'] : []),
    'debit',
    'credit',
    'bal',
  ]
  //: ستون‌های متنی (بی شماره‌ی ردیف و سه ستونِ مبلغ) — برچسبِ ردیفِ بالا و پایین رویشان پهن می‌شود.
  const labelSpan = colIds.length - 4

  useEffect(() => {
    document.getElementById(`ab-line-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active])

  /** Shift+↑↓: انتخاب از ردیفِ فعلی تا مقصد — اگر لنگری نیست، همین ردیف لنگر می‌شود. */
  const extendTo = (to: number) => {
    if (selected.size === 0) click(order, order[active], { shift: false, ctrl: true })
    click(order, order[to], { shift: true, ctrl: false })
  }

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    //: کشوی سند کیبوردِ خودش را دارد (Esc)؛ این‌جا نباید همان کلید را دوباره بخورد.
    if (entryOpen) return
    const last = lines.length - 1
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        if (active < last) {
          onRow(active + 1)
          if (e.shiftKey) extendTo(active + 1)
        } else if (!e.shiftKey && offset + LEDGER_PAGE < total) onOffset(offset + LEDGER_PAGE)
        break
      case 'ArrowUp':
        e.preventDefault()
        if (active > 0) {
          onRow(active - 1)
          if (e.shiftKey) extendTo(active - 1)
        }
        break
      case ' ':
        e.preventDefault()
        if (lines[active]) click(order, order[active], { shift: false, ctrl: true })
        break
      case 'Home':
        e.preventDefault()
        onRow(0)
        break
      case 'End':
        e.preventDefault()
        onRow(last)
        break
      case 'PageDown':
        e.preventDefault()
        if (offset + LEDGER_PAGE < total) onOffset(offset + LEDGER_PAGE)
        break
      case 'PageUp':
        e.preventDefault()
        if (offset > 0) onOffset(Math.max(0, offset - LEDGER_PAGE))
        break
      case 'Enter':
        e.preventDefault()
        if (lines[active]) onOpenEntry(lines[active].entry_id)
        break
      case 'Escape':
        e.preventDefault()
        if (selected.size > 0) clear()
        else onBack()
        break
    }
  }

  const head = (id: string, label: string, className?: string) => (
    <th data-col={id} className={className}>
      {label}
      {cw.canResize(id, colIds[colIds.indexOf(id) + 1]) && (
        <ColResizer onBegin={(ev) => cw.begin(ev, id)} onReset={cw.reset} />
      )}
    </th>
  )
  const status = (text: string, err = false) => (
    <tr>
      <td className={`card-full ab-ledger-status${err ? ' ab-ledger-status--err' : ''}`} colSpan={colIds.length}>
        {text}
      </td>
    </tr>
  )
  const sumDebit = picked.reduce((s, l) => s + Number(l.debit || 0), 0)
  const sumCredit = picked.reduce((s, l) => s + Number(l.credit || 0), 0)

  return (
    <div className="ab-ledger">
      <div className="ab-ledger-head">
        <strong>
          <BookOpen size={14} /> گردشِ حساب
          {node.is_group && <small className="muted"> — همه‌ی زیرحساب‌ها (دفتر کل)</small>}
        </strong>
        {current && total > 0 && (
          <span className="ab-pager">
            <button
              type="button"
              className="ab-icon-btn"
              disabled={offset === 0}
              onClick={() => onOffset(Math.max(0, offset - LEDGER_PAGE))}
            >
              قبلی
            </button>
            ردیفِ {faInt(offset + 1)} تا {faInt(Math.min(offset + LEDGER_PAGE, total))} از {faInt(total)}
            <button
              type="button"
              className="ab-icon-btn"
              disabled={offset + LEDGER_PAGE >= total}
              onClick={() => onOffset(offset + LEDGER_PAGE)}
            >
              بعدی
            </button>
          </span>
        )}
      </div>
      <div
        ref={tableRef}
        tabIndex={total > 0 ? 0 : -1}
        className={`table-scroll ef-table-wrap ab-ledger-scroll${loading && current ? ' is-loading' : ''}`}
        onKeyDown={onKey}
        aria-label="گردشِ حساب — ↑↓ حرکت، Shift+↑↓ یا Space انتخاب، Enter بازکردنِ سند، Esc برگشت به درخت"
      >
        {/* کفِ عرض با هر ستونِ اختیاری بزرگ می‌شود تا «شرح» له نشود؛ جا نشد، گرید درونِ قاب می‌لغزد. */}
        <table
          ref={cw.frame}
          className="cards-on-mobile ef-table xl-grid ab-ledger-table"
          style={{ '--ab-opt': colIds.length - 7 } as CSSProperties}
        >
          <colgroup>
            {colIds.map((id) => (
              <col key={id} className={`ab-lc-${id}`} style={cw.col(id)} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th className="xl-rowhead" data-col="rowhead" aria-label="انتخاب" />
              {head('date', 'تاریخ')}
              {head('doc', 'سند')}
              {head('desc', 'شرح')}
              {showAccount && head('account', 'حساب')}
              {showAnalytic && head('analytic', 'تفصیلی')}
              {showCenter && head('center', 'مرکز هزینه')}
              {head('debit', 'بدهکار', 'num ab-pin ab-pin--debit')}
              {head('credit', 'بستانکار', 'num ab-pin ab-pin--credit')}
              {head('bal', 'مانده', 'num ab-pin ab-pin--bal')}
            </tr>
          </thead>
          <tbody>
            {offset === 0 && (
              <tr className="ab-carry">
                <td className="xl-rowhead card-hide" />
                <td className="card-title" colSpan={labelSpan}>
                  مانده‌ی اول دوره
                </td>
                <td className="card-hide ab-pin ab-pin--debit" />
                <td className="card-hide ab-pin ab-pin--credit" />
                <td className="num ab-pin ab-pin--bal" data-label="مانده">
                  <SideAmount
                    raw={current ? ledgerRaw(Number(current.opening_balance), node.account_type) : Number(node.opening)}
                    long
                  />
                </td>
              </tr>
            )}
            {error
              ? status(error, true)
              : !current
                ? status('در حال بارگذاری…')
                : total === 0
                  ? status('این حساب در این دامنه گردشی ندارد.')
                  : lines.map((l, i) => {
                      const on = selected.has(l.line_id)
                      return (
                        <tr
                          key={l.line_id}
                          id={`ab-line-${i}`}
                          className={`acc-row--clickable${i === active ? ' is-active' : ''}${on ? ' is-selected' : ''}`}
                          onClick={() => {
                            onRow(i)
                            onOpenEntry(l.entry_id)
                          }}
                        >
                          <td className="xl-rowhead card-hide">
                            <button
                              type="button"
                              tabIndex={-1}
                              className="xl-rowhead-btn"
                              aria-pressed={on}
                              aria-label={`انتخابِ ردیفِ ${faInt(offset + i + 1)}`}
                              onClick={(ev) => {
                                //: شماره‌ی ردیف فقط انتخاب می‌کند؛ کلیکِ بقیه‌ی ردیف سند را باز می‌کند.
                                ev.stopPropagation()
                                onRow(i)
                                click(order, l.line_id, modsOf(ev))
                              }}
                            >
                              {faInt(offset + i + 1)}
                            </button>
                          </td>
                          <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                          <td className="card-title" data-label="سند">
                            {l.entry_number != null ? faInt(l.entry_number) : '—'}
                            {l.entry_status === 'temporary' && <span className="ab-badge ab-badge--muted">موقت</span>}
                          </td>
                          <td data-label="شرح" className="card-wide" title={l.description || undefined}>
                            {l.description || '—'}
                          </td>
                          {showAccount && (
                            <td data-label="حساب" title={`${l.account_code} ${l.account_name}`}>
                              <span dir="ltr">{l.account_code}</span> {l.account_name}
                            </td>
                          )}
                          {showAnalytic && <td data-label="تفصیلی">{l.analytic_name ?? '—'}</td>}
                          {showCenter && <td data-label="مرکز هزینه">{l.cost_center_name ?? '—'}</td>}
                          <td data-label="بدهکار" className="num ab-pin ab-pin--debit">
                            {faAmount(l.debit)}
                          </td>
                          <td data-label="بستانکار" className="num ab-pin ab-pin--credit">
                            {faAmount(l.credit)}
                          </td>
                          <td data-label="مانده" className="num ab-pin ab-pin--bal">
                            <SideAmount raw={ledgerRaw(Number(l.balance), node.account_type)} />
                          </td>
                        </tr>
                      )
                    })}
          </tbody>
          <tfoot>
            <tr className="ab-total">
              <td className="xl-rowhead card-hide" />
              <td className="card-title" colSpan={labelSpan} title="گردشِ کلِ بازه‌ی انتخاب‌شده — نه فقط همین صفحه">
                جمعِ بازه {total > LEDGER_PAGE && <small>(همه‌ی {faInt(total)} ردیف)</small>}
              </td>
              <td className="num ab-pin ab-pin--debit" data-label="گردش بدهکار">
                {faAmount(node.period_debit)}
              </td>
              <td className="num ab-pin ab-pin--credit" data-label="گردش بستانکار">
                {faAmount(node.period_credit)}
              </td>
              <td className="num ab-pin ab-pin--bal" data-label="مانده‌ی پایان دوره">
                <SideAmount raw={Number(node.closing)} long />
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      {picked.length > 0 && (
        <SelectionBar count={picked.length} unit="ردیف" onClear={clear}>
          <span>
            بدهکار <b className="num">{faAmount(sumDebit)}</b>
          </span>
          <span>
            بستانکار <b className="num">{faAmount(sumCredit)}</b>
          </span>
          <span>
            خالص <SideAmount raw={sumDebit - sumCredit} long />
          </span>
        </SelectionBar>
      )}
      {current && total > 0 && (
        <p className="ab-keys">
          <kbd>↑</kbd>
          <kbd>↓</kbd> ردیف · <kbd>Shift+↑↓</kbd> یا <kbd>Space</kbd> انتخاب · <kbd>Enter</kbd> سند · <kbd>PgUp</kbd>
          <kbd>PgDn</kbd> صفحه · <kbd>Esc</kbd> برگشت به درخت
        </p>
      )}
    </div>
  )
}
