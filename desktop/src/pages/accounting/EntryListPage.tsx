import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { BookOpen, BookOpenCheck, ClipboardCheck, Download, FileStack, Printer, RefreshCw, Search, Trash2 } from 'lucide-react'

import {
  fetchAllJournalEntries,
  fetchFiscalYears,
  fetchJournalEntriesPage,
  fetchJournalEntriesSummary,
  printJournalEntry,
  setEntrySubNumber,
  voidJournalEntry,
  type JournalColumnFilters,
  type JournalEntryRecord,
  type ReportFilters,
} from '../../api'
import { CountBadge, RowAction } from '../../components/form/FormKit'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { CheckChip } from '../../components/ReportViews'
import { SearchSelect } from '../../components/SearchSelect'
import { SectionCard } from '../../components/SectionCard'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { downloadCsv } from '../../lib/csv'
import { normalizeFa } from '../../lib/faText'
import { formatJalali } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { useCursorList } from '../../lib/useCursorList'
import { useDebounced } from '../../lib/useDebounced'
import {
  AsyncBlock,
  Note,
  OpsPage,
  RangeCells,
  SOURCE_LABELS,
  StatusChip,
  fa,
  faAmount,
  faInt,
  sourceText,
  useAsync,
  useRange,
  type Msg,
} from './kit'

/** اسنادِ هر صفحه از سرور؛ «بعدی» صفحه‌ی بعد را می‌آورد. */
const PAGE = 100
/** جابه‌جاییِ PageUp/PageDown. */
const PAGE_STEP = 10

type Status = '' | 'temporary' | 'permanent'
const STATUSES: { key: Status; label: string }[] = [
  { key: '', label: 'همه' },
  { key: 'temporary', label: 'موقت' },
  { key: 'permanent', label: 'دائم' },
]

/** فیلترهای سرستون — متنِ خامِ کادرها؛ تبدیل به پارامترِ سرور پایین‌تر. */
interface ColumnFilters {
  number: string
  atf: string
  sub: string
  desc: string
  source: string
}
const NO_COLUMN_FILTERS: ColumnFilters = { number: '', atf: '', sub: '', desc: '', source: '' }
//: ستون‌بندیِ «جا در قاب»: شماره‌ی ردیف و آیکون‌های کنش ثابت، «شرح» باقی را می‌گیرد. کلیدِ تازه: ستونِ «وضعیت» حالا
//: فیلترِ سرستون ندارد و شناسه‌ها همان‌اند، ولی سهم‌های قدیمی روی عرضِ تازه‌ی کنش‌ها می‌نشستند.
const LIST_LAYOUT = { fixed: ['rowhead', 'actions'], auto: 'desc' } as const
const COL_IDS = ['rowhead', 'number', 'atf', 'sub', 'date', 'desc', 'source', 'status', 'lines', 'amount', 'actions']

const digits = (v: string): number | undefined => {
  const d = normalizeFa(v).replace(/\D/g, '')
  return d ? Number(d) : undefined
}
const entryTotal = (e: JournalEntryRecord) => e.lines.reduce((s, l) => s + Number(l.debit || 0), 0)

/**
 * «اسناد حسابداری» با تمِ اکسلی — دفترِ کاملِ اسناد، دستی و خودکار، موقت و دائم (الگوی «د» از `cubita-excel-theme`).
 *
 * - **سربرگ** (`jh-bar--report`): بازه و سالِ مالی، «وضعیت» (همه/موقت/دائم — روی موبایل هم، که سرستون‌ها پنهان‌اند)، و
 *   «رفتن به».
 * - **برگه:** همان گریدِ اکسلیِ فهرست با فیلترهای سرستون (شماره، عطف، فرعی، شرح، منشأ — همه سمتِ سرور)، ستون‌های کشیدنی،
 *   انتخاب با شماره‌ی ردیف و جمعِ انتخاب. **کلیک روی ردیف خودِ سند را باز می‌کند** (پیش از این هیچ کاری نمی‌کرد).
 * - **صفحه‌بندی از سرور:** پیش از این ۳۰۰ سندِ اول می‌آمد و بقیه بی‌صدا دیده نمی‌شد؛ حالا صفحه‌به‌صفحه با کرسر («سندِ
 *   بعدی») و **«جمعِ بازه»** در پانویس از `/summary`ِ سرور — کلِ دامنه، نه سندهای بارشده — با نشانِ توازن.
 * - خروجیِ CSV کلِ دامنه‌ی فیلترشده است.
 */
export function EntryListPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const range = useRange('year')
  const years = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
  const [status, setStatus] = useState<Status>('')
  const [search, setSearch] = useState('')
  const [cols, setCols] = useState<ColumnFilters>(NO_COLUMN_FILTERS)
  const [entryId, setEntryId] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  //: هر حرف یک درخواست نشود.
  const q = useDebounced(search.trim(), 300)
  const colsQ = useDebounced(cols, 350)

  const number = digits(colsQ.number)
  const scope: ReportFilters = {
    dateFrom: range.from,
    dateTo: range.to,
    status: status || undefined,
    sourceType: colsQ.source || undefined,
    //: شماره‌ی سند فیلترِ ستونیِ جدا نمی‌خواهد: «از = تا» همان است.
    entryFrom: number,
    entryTo: number,
  }
  const colFilters: JournalColumnFilters = {
    atf: digits(colsQ.atf),
    sub: colsQ.sub.trim() || undefined,
    desc: colsQ.desc.trim() || undefined,
  }
  const scopeKey = JSON.stringify([scope, colFilters, q])
  const list = useCursorList(
    (cursor) => fetchJournalEntriesPage(token, scope, { q: q || undefined, cursor, limit: PAGE, cols: colFilters }),
    scopeKey,
  )
  const summary = useAsync(
    () => fetchJournalEntriesSummary(token, scope, q || undefined, colFilters),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, scopeKey],
  )
  const rows = list.items
  const total = summary.data

  async function handleEditSub(entry: JournalEntryRecord) {
    const next = window.prompt(
      `شماره فرعیِ سندِ ${entry.number ?? ''} — ارجاعِ خودتان (شماره‌ی پرونده، سندِ سیستمِ قبلی، کدِ دسته).
خالی بگذارید تا پاک شود:`,
      entry.sub_number ?? '',
    )
    if (next === null) return
    try {
      await setEntrySubNumber(token, entry.id, next.trim() || null)
      setMsg({ text: 'شماره فرعی ثبت شد.', kind: 'ok' })
      list.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }
  async function handleVoid(entry: JournalEntryRecord) {
    const reason = window.prompt(
      `ابطالِ سندِ ${entry.number ?? ''} یک سندِ معکوس ثبت می‌کند و اصل سرِ جایش می‌ماند.\nعلتِ ابطال:`,
    )
    if (reason === null) return
    try {
      const out = await voidJournalEntry(token, entry.id, reason)
      setMsg({ text: `سندِ معکوس با شماره ${fa(out.reversal_entry_number ?? 0)} ثبت شد.`, kind: 'ok' })
      list.reload()
      summary.reload()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }
  async function handlePrint(entry: JournalEntryRecord) {
    try {
      await printJournalEntry(token, entry.id)
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const [csvBusy, setCsvBusy] = useState(false)
  async function exportCsv() {
    setCsvBusy(true)
    try {
      //: کلِ دامنه‌ی فیلترشده، نه صفحه‌های بارشده — کسی که «خروجی» می‌زند همه را می‌خواهد.
      const all = await fetchAllJournalEntries(token, scope, q || undefined, colFilters)
      downloadCsv(
        `asnad-${range.from ?? 'all'}`,
        ['شماره', 'عطف', 'فرعی', 'تاریخ', 'شرح', 'منشأ', 'وضعیت', 'ردیف', 'مبلغ'],
        all.map((e) => [
          e.number ?? '',
          e.atf_number ?? '',
          e.sub_number ?? '',
          formatJalali(e.entry_date),
          e.description,
          sourceText(e),
          e.voided_at ? 'باطل' : e.status === 'permanent' ? 'دائم' : 'موقت',
          e.lines.length,
          entryTotal(e),
        ]),
      )
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setCsvBusy(false)
    }
  }

  const findRef = useRef<HTMLInputElement>(null)
  const rangeText = range.from
    ? `${formatJalali(range.from)} تا ${formatJalali(range.to ?? '')}`
    : 'کلِ دفتر'

  return (
    <OpsPage
      canvas
      icon={FileStack}
      title="اسناد حسابداری"
      description="همه‌ی اسنادِ دفتر — دستی و خودکار، موقت و دائم. «عطف» شماره‌ی ثابتِ سند است و با شماره‌گذاری مجدد عوض نمی‌شود؛ «فرعی» ارجاعِ خودِ شماست. سندِ دستی را می‌توان از همین‌جا ابطال کرد."
      head={
        <div className="jh-bar jh-bar--report" role="group" aria-label="بازه و فیلترهای اسناد حسابداری">
          <div className="jh-row rh-row--range">
            <RangeCells range={range} years={years.data ?? []} />
          </div>
          <div className="jh-row jh-row--sub rh-row--tools">
            <div className="jh-field">
              <span className="jh-label">وضعیت</span>
              <div className="cc-presets rh-seg" role="group" aria-label="وضعیتِ سند">
                {STATUSES.map((s) => (
                  <button
                    key={s.key || 'all'}
                    type="button"
                    className={status === s.key ? 'is-active' : ''}
                    aria-pressed={status === s.key}
                    onClick={() => setStatus(s.key)}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
            {onNavigate && (
              <div className="jh-field rh-go">
                <span className="jh-label">رفتن به</span>
                <div className="rh-links">
                  <button type="button" onClick={() => onNavigate('journalentry')}>
                    <BookOpen size={14} aria-hidden="true" /> سند حسابداری
                  </button>
                  <button type="button" onClick={() => onNavigate('entrycartable')}>
                    <ClipboardCheck size={14} aria-hidden="true" /> کارتابل اسناد موقت
                  </button>
                  <button type="button" onClick={() => onNavigate('ledgerreport')}>
                    <BookOpenCheck size={14} aria-hidden="true" /> گزارش دفتر
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      }
    >
      <SectionCard
        icon={FileStack}
        title="اسناد"
        description={total ? `${rangeText} · ${faInt(total.entry_count)} سند · ${faInt(total.line_count)} ردیف` : rangeText}
        tip="روی هر سند کلیک کنید (یا Enter) تا خودش باز شود. فیلترهای زیرِ سرستون‌ها سمتِ سرورند و کلِ دفتر را می‌گردند. با شماره‌ی ردیف (کلیک، Ctrl، Shift) یا Space چند سند را انتخاب کنید تا جمعشان پایین بیاید. «جمعِ بازه» کلِ دامنه است، نه فقط سندهای بارشده."
        badge={total ? <CountBadge accent>{faInt(total.entry_count)} سند</CountBadge> : undefined}
        actions={
          <div className="jg-head-actions">
            <div className={`jg-find${search ? ' has-query' : ''}`} role="search">
              <Search size={14} aria-hidden="true" />
              <input
                ref={findRef}
                type="search"
                value={search}
                placeholder="شماره، عطف، فرعی یا شرح  (Ctrl+F)"
                aria-label="جست‌وجو در اسناد"
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') {
                    e.preventDefault()
                    setSearch('')
                  }
                }}
              />
            </div>
            <button type="button" className="ef-btn-secondary" onClick={() => void exportCsv()} disabled={csvBusy || !total || total.entry_count === 0}>
              <Download size={14} /> {csvBusy ? 'در حال آماده‌سازی…' : 'خروجی CSV'}
            </button>
            <button
              type="button"
              className="ef-btn-secondary"
              onClick={() => {
                list.reload()
                summary.reload()
              }}
              title="دوباره از سرور"
            >
              <RefreshCw size={14} /> به‌روزرسانی
            </button>
          </div>
        }
      >
        <Note msg={msg} />
        {summary.error && <p className="hint acc-note acc-note--err">جمعِ اسناد نیامد: {summary.error}</p>}
        <AsyncBlock loading={list.loading && rows.length === 0 && !list.error} error={rows.length ? null : list.error}>
          <EntryGrid
            entries={rows}
            loading={list.loading}
            filters={cols}
            onFilter={(k, v) => setCols((c) => ({ ...c, [k]: v }))}
            onOpen={setEntryId}
            onVoid={handleVoid}
            onPrint={handlePrint}
            onEditSub={handleEditSub}
            onFind={() => findRef.current?.focus()}
            drawerOpen={entryId !== null}
            foot={
              <tr className="rp-total">
                <td className="xl-rowhead card-hide" />
                <td className="card-title" colSpan={8}>
                  جمعِ بازه
                  {total && <small className="lr-foot-note"> {faInt(total.entry_count)} سند</small>}
                  {total && total.entry_count > 0 && (
                    <CheckChip
                      ok={Math.abs(Number(total.total_debit) - Number(total.total_credit)) < 0.5}
                      okText="تراز است"
                      offText="ناتراز"
                    />
                  )}
                </td>
                <td className="num" data-label="جمعِ مبلغ">
                  {total ? faAmount(total.total_debit) : '…'}
                </td>
                <td className="card-hide" />
              </tr>
            }
          />
          {rows.length > 0 && (
            <div className="daybook-more">
              <span className="hint">
                {total ? `نمایشِ ${faInt(rows.length)} از ${faInt(total.entry_count)} سند` : `${faInt(rows.length)} سند`}
              </span>
              {list.hasMore && (
                <button type="button" className="ef-btn-secondary" onClick={() => void list.loadMore()} disabled={list.moreBusy}>
                  {list.moreBusy ? 'در حال بارگذاری…' : `${faInt(PAGE)} سندِ بعدی`}
                </button>
              )}
            </div>
          )}
          {list.moreError && <p className="hint acc-note acc-note--err">{list.moreError}</p>}
        </AsyncBlock>
      </SectionCard>

      {entryId && (
        <JournalEntryDrawer
          token={token}
          entryId={entryId}
          onClose={() => {
            setEntryId(null)
            //: شاید سند در کشو اصلاح، دائم یا باطل شده باشد.
            list.reload()
            summary.reload()
          }}
        />
      )}
    </OpsPage>
  )
}

/**
 * گریدِ اکسلیِ فهرستِ اسناد: سرستونِ خاکستری با ردیفِ فیلتر (سمتِ سرور)، ردیف‌ها با رنگِ ملایمِ وضعیت (موقت کهربایی،
 * دائم سبز، باطل خط‌خورده)، ستون‌های کشیدنی، انتخاب با شماره‌ی ردیف و جمعِ انتخاب، و کلیک روی ردیف برای بازکردنِ سند.
 */
function EntryGrid({
  entries,
  loading,
  filters,
  onFilter,
  onOpen,
  onVoid,
  onPrint,
  onEditSub,
  onFind,
  drawerOpen,
  foot,
}: {
  entries: JournalEntryRecord[]
  loading: boolean
  filters: ColumnFilters
  onFilter: (key: keyof ColumnFilters, value: string) => void
  onOpen: (id: string) => void
  onVoid: (e: JournalEntryRecord) => void
  onPrint: (e: JournalEntryRecord) => void
  /** اصلاحِ شماره فرعی — فقط سندِ موقتِ باطل‌نشده. */
  onEditSub: (e: JournalEntryRecord) => void
  onFind: () => void
  drawerOpen: boolean
  foot: ReactNode
}) {
  const cw = useColumnWidths('cubita.grid.journalList.v2', LIST_LAYOUT)
  const { selected, click, clear } = useRowSelection()
  const order = useMemo(() => entries.map((e) => e.id), [entries])
  //: دامنه‌ی تازه یعنی فهرستِ دیگر؛ انتخابِ قبلی معنا ندارد. «بعدی» فهرست را فقط بلند می‌کند، پس انتخاب می‌ماند.
  const firstId = entries[0]?.id
  useEffect(() => clear(), [firstId, clear])
  const chosen = entries.filter((e) => selected.has(e.id))

  // ── صفحه‌کلید ──
  const [activeRow, setActiveRow] = useState(0)
  const active = Math.min(activeRow, Math.max(0, entries.length - 1))
  const followActive = useRef(false)
  useEffect(() => {
    if (!followActive.current) return
    followActive.current = false
    document.getElementById(`el-row-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active])
  const moveTo = (i: number) => {
    followActive.current = true
    setActiveRow(Math.max(0, Math.min(entries.length - 1, i)))
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (drawerOpen) return
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
      e.preventDefault()
      onFind()
      return
    }
    //: تایپ در کادرِ فیلترِ سرستون مالِ همان کادر است.
    if ((e.target as HTMLElement).closest('.xl-filter-row')) return
    const last = entries.length - 1
    if (last < 0) return
    switch (e.key) {
      case 'ArrowDown':
      case 'ArrowUp': {
        e.preventDefault()
        const to = active + (e.key === 'ArrowDown' ? 1 : -1)
        if (to < 0 || to > last) break
        moveTo(to)
        if (e.shiftKey) {
          if (selected.size === 0) click(order, order[active], { shift: false, ctrl: true })
          click(order, order[to], { shift: true, ctrl: false })
        }
        break
      }
      case 'PageDown':
      case 'PageUp':
        e.preventDefault()
        moveTo(active + (e.key === 'PageDown' ? PAGE_STEP : -PAGE_STEP))
        break
      case 'Home':
      case 'End':
        e.preventDefault()
        moveTo(e.key === 'Home' ? 0 : last)
        break
      case ' ':
        e.preventDefault()
        click(order, order[active], { shift: false, ctrl: true })
        break
      case 'Enter':
        e.preventDefault()
        onOpen(order[active])
        break
      case 'Escape':
        if (selected.size > 0) {
          e.preventDefault()
          clear()
        }
        break
    }
  }

  const head = (id: string, label: ReactNode, cls?: string) => (
    <th data-col={id} className={cls}>
      {label}
      {/* لبه‌ی کنارِ ستونِ ثابت (آیکون‌ها) کشیدنی نیست. */}
      {cw.canResize(id, COL_IDS[COL_IDS.indexOf(id) + 1]) && <ColResizer onBegin={(ev) => cw.begin(ev, id)} onReset={cw.reset} />}
    </th>
  )
  const textFilter = (key: keyof ColumnFilters, label: string, numeric = false) => (
    <input
      type="search"
      inputMode={numeric ? 'numeric' : undefined}
      value={filters[key]}
      onChange={(ev) => onFilter(key, ev.target.value)}
      placeholder="فیلتر…"
      aria-label={`فیلترِ ${label}`}
    />
  )

  return (
    <>
      <div
        tabIndex={entries.length > 0 ? 0 : -1}
        className={`table-scroll ef-table-wrap rp-scroll lr-scroll el-scroll${loading ? ' is-loading' : ''}`}
        onKeyDown={onKey}
        aria-label="اسناد — ↑↓ حرکت، Enter بازکردنِ سند، Space یا Shift+↑↓ انتخاب، Esc لغوِ انتخاب، Ctrl+F جست‌وجو"
      >
        <table ref={cw.frame} className="cards-on-mobile acc-table ef-table xl-grid xl-grid--list rp-table el-sheet">
          <colgroup>
            {COL_IDS.map((id) => (
              <col key={id} className={`xl-c-${id}`} style={cw.col(id)} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th className="xl-rowhead" data-col="rowhead" aria-label="انتخاب" />
              {head('number', 'شماره')}
              {/* عطف کنارِ شماره می‌نشیند چون کاربر این دو را با هم می‌خواند: یکی جای سند در دفترِ امروز است، دیگری هویتِ ثابتش. */}
              {head('atf', 'عطف')}
              {head('sub', 'فرعی')}
              {head('date', 'تاریخ')}
              {head('desc', 'شرح')}
              {head('source', 'منشأ')}
              {head('status', 'وضعیت')}
              {head('lines', 'ردیف', 'num')}
              {head('amount', 'مبلغ', 'num')}
              <th className="ef-col-min" data-col="actions">
                عملیات
              </th>
            </tr>
            <tr className="xl-filter-row">
              <th className="xl-rowhead" aria-hidden="true" />
              <th>{textFilter('number', 'شماره', true)}</th>
              <th>{textFilter('atf', 'عطف', true)}</th>
              <th>{textFilter('sub', 'فرعی')}</th>
              {/* تاریخ و وضعیت فیلترِ خودشان را در سربرگ دارند. */}
              <th />
              <th>{textFilter('desc', 'شرح')}</th>
              <th>
                <SearchSelect value={filters.source} onChange={(ev) => onFilter('source', ev.target.value)} aria-label="فیلترِ منشأ">
                  <option value="">همه</option>
                  {Object.entries(SOURCE_LABELS).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </SearchSelect>
              </th>
              <th />
              <th />
              <th />
              <th />
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 ? (
              <tr>
                <td className="card-full rp-status" colSpan={COL_IDS.length}>
                  سندی با این شرایط پیدا نشد.
                </td>
              </tr>
            ) : (
              entries.map((e, i) => {
                const on = selected.has(e.id)
                const tone = e.voided_at ? 'acc-row--void' : e.status === 'permanent' ? 'xl-row--perm' : 'xl-row--temp'
                return (
                  <tr
                    key={e.id}
                    id={`el-row-${i}`}
                    className={`${tone} acc-row--clickable${on ? ' is-selected' : ''}${i === active ? ' is-active' : ''}`}
                    title="بازکردنِ سند"
                    onClick={() => {
                      setActiveRow(i)
                      onOpen(e.id)
                    }}
                  >
                    <td className="xl-rowhead card-hide">
                      <button
                        type="button"
                        tabIndex={-1}
                        className="xl-rowhead-btn"
                        aria-pressed={on}
                        aria-label={`انتخابِ سندِ ${fa(e.number ?? 0)}`}
                        onClick={(ev) => {
                          //: شماره‌ی ردیف فقط انتخاب می‌کند؛ کلیکِ بقیه‌ی ردیف سند را باز می‌کند.
                          ev.stopPropagation()
                          setActiveRow(i)
                          click(order, e.id, modsOf(ev))
                        }}
                      >
                        {faInt(i + 1)}
                      </button>
                    </td>
                    <td className="card-title">سند {e.number != null ? fa(e.number) : '—'}</td>
                    <td data-label="عطف" className="num">
                      {e.atf_number === null ? '—' : faInt(e.atf_number)}
                    </td>
                    <td data-label="فرعی">
                      {/* عطف تغییرناپذیر است، ولی فرعی ارجاعِ کاربر است و غلطِ تایپی باید اصلاح شود — تا وقتی سند موقت است. */}
                      {!e.voided_at && e.status === 'temporary' ? (
                        <button
                          type="button"
                          className="link-btn"
                          onClick={(ev) => {
                            ev.stopPropagation()
                            onEditSub(e)
                          }}
                        >
                          {e.sub_number || '＋ افزودن'}
                        </button>
                      ) : (
                        e.sub_number || '—'
                      )}
                    </td>
                    <td data-label="تاریخ">{formatJalali(e.entry_date)}</td>
                    <td data-label="شرح" className="xl-ellipsis card-wide" title={e.description || undefined}>
                      {e.description || '—'}
                    </td>
                    <td data-label="منشأ" className="xl-ellipsis">
                      {sourceText(e)}
                    </td>
                    <td data-label="وضعیت">
                      <StatusChip status={e.status} voided={!!e.voided_at} />
                    </td>
                    <td data-label="ردیف" className="num">
                      {faInt(e.lines.length)}
                    </td>
                    <td data-label="مبلغ" className="num">
                      {faAmount(entryTotal(e))}
                    </td>
                    <td className="card-actions ef-col-min" onClick={(ev) => ev.stopPropagation()}>
                      <div className="row-actions ef-row-actions">
                        {/* چاپ برای **هر** سند، خودکار و باطل هم — خواندن است. */}
                        <RowAction icon={Printer} label="چاپ" onClick={() => onPrint(e)} />
                        {/* فقط سندِ دستی: سندِ خودکار با ابطالِ خودِ فاکتور/فیش برمی‌گردد. */}
                        <RowAction
                          icon={Trash2}
                          label="ابطال"
                          danger
                          onClick={() => onVoid(e)}
                          disabled={!!e.voided_at || e.source_type !== 'manual'}
                          title={
                            e.voided_at
                              ? 'این سند قبلاً باطل شده است.'
                              : e.source_type !== 'manual'
                                ? 'سندِ خودکار با ابطالِ فاکتور، فیش یا عملیاتِ منشأ برمی‌گردد.'
                                : undefined
                          }
                        />
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
          <tfoot>{foot}</tfoot>
        </table>
      </div>
      {chosen.length > 0 && (
        <SelectionBar count={chosen.length} unit="سند" onClear={clear}>
          <span>
            جمع مبلغ <b className="num">{faAmount(chosen.reduce((s, e) => s + entryTotal(e), 0))}</b>
          </span>
          <span>
            ردیف‌ها <b className="num">{faInt(chosen.reduce((s, e) => s + e.lines.length, 0))}</b>
          </span>
        </SelectionBar>
      )}
    </>
  )
}
