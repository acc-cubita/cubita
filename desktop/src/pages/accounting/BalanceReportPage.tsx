import { Fragment, useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  Download,
  FilePlus2,
  Layers,
  Printer,
  Scale,
  Search,
} from 'lucide-react'
import {
  ACCOUNT_NATURE_LABELS,
  fetchAccountBalances,
  fetchChartAccounts,
  fetchFiscalYears,
  fetchMissingTafsili,
  fetchNatureViolations,
  type BalanceRow,
  type ReportFilters,
} from '../../api'
import { AccountLedgerDrawer } from '../../components/AccountLedgerDrawer'
import { CountBadge } from '../../components/form/FormKit'
import { useNavSection } from '../../components/navContext'
import { ReportFilterBar } from '../../components/ReportFilterBar'
import { SavedViewBar } from '../../components/SavedViewBar'
import { SearchSelect } from '../../components/SearchSelect'
import { SectionCard } from '../../components/SectionCard'
import { SelectionBar } from '../../components/XlGrid'
import {
  GROUP_LABELS,
  aggregateBalances,
  balanceCheck,
  balanceGroups,
  balanceTotals,
  filterBalances,
  pairOf,
  type BalanceColumns,
  type BalanceFilter,
} from '../../lib/balanceReport'
import { downloadCsv } from '../../lib/csv'
import { formatJalali, todayIso } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { AsyncBlock, OpsPage, RangeCells, fa, faAmount, faInt, useAsync, useRange } from './kit'

const TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی',
  liability: 'بدهی',
  equity: 'سرمایه',
  income: 'درآمد',
  expense: 'هزینه',
}

const COLUMN_OPTIONS: { value: BalanceColumns; label: string; hint: string }[] = [
  { value: 2, label: 'دو', hint: 'دو ستونی — فقط مانده‌ی پایانِ دوره' },
  { value: 4, label: 'چهار', hint: 'چهار ستونی — گردش و مانده‌ی دوره' },
  { value: 6, label: 'شش', hint: 'شش ستونی — افتتاحیه، گردش، مانده' },
  { value: 8, label: 'هشت', hint: 'هشت ستونی — افتتاحیه، گردش، جمع، مانده' },
]

const LEVEL_OPTIONS = [
  { value: 2, label: 'کل' },
  { value: 3, label: 'معین' },
  { value: 0, label: 'تفصیلی', hint: 'سطحِ آخرِ هر شاخه' },
]

const BALANCE_FILTERS: { value: BalanceFilter; label: string }[] = [
  { value: 'all', label: 'همه' },
  { value: 'debit', label: 'مانده بدهکار' },
  { value: 'credit', label: 'مانده بستانکار' },
  { value: 'zero', label: 'مانده صفر' },
  { value: 'idle', label: 'بدونِ گردش' },
]

/** جابه‌جاییِ PageUp/PageDown در گرید. */
const PAGE_STEP = 10

/**
 * دو قالبِ یک داده: **تراز آزمایشی** (ستون‌ها و سطحِ دلخواه) و **سند کل** — خلاصه‌ی گردشِ بازه در سطحِ
 * حسابِ کل، همان برگه‌ای که پایانِ ماه چاپ و بایگانی می‌شود. «سند کل» پیش‌تر منوی جدای «صدور سند کل»
 * بود که سندی صادر نمی‌کرد و همین تجمیع را دوباره حساب می‌کرد؛ در بازچینیِ ۱۴۰۵/۰۷/۰۳ قالبی از همین
 * صفحه شد (بخشِ `general`).
 */
type BalanceView = 'trial' | 'general'

/**
 * «گزارش ترازها» با تمِ اکسلی (الگوی «د» از `cubita-excel-theme`: گریدِ فقط‌خواندنی).
 *
 * - سربرگِ فیلتر همان `jh-bar--report`ِ «مرور حساب‌ها» است، به‌اضافه‌ی سطرِ «قالب»: نوعِ برگه، شمارِ ستون، سطح و
 *   نوعِ مانده.
 * - سرستونِ دوطبقه مثلِ ترازِ چاپی: «افتتاحیه / گردش / جمع / مانده» هر کدام بالای جفتِ بدهکار و بستانکار.
 * - جمع‌ها در `tfoot`ِ چسبنده به تهِ قاب، با نشانِ توازن — نه کارتِ خلاصه بالای صفحه.
 * - ستون‌های «ردیف، کد، نام» سمتِ راستِ قاب میخ‌اند؛ در قالبِ هشت‌ستونی که گرید از قاب پهن‌تر است، فقط مبلغ‌ها
 *   می‌لغزند و حساب همیشه دیده می‌شود.
 * - انتخاب با شماره‌ی ردیف (کلیک، Ctrl، Shift، Space، Shift+↑↓) و جمعِ انتخاب در `SelectionBar`؛ کلیکِ بقیه‌ی
 *   ردیف یا Enter دفترِ حساب را باز می‌کند.
 */
export function BalanceReportPage({ token, onNavigate }: { token: string; onNavigate?: (page: PageKey) => void }) {
  const nav = useNavSection()
  const askedGeneral = nav?.activePage === 'balancereport' && nav.section === 'general'
  const [view, setView] = useState<BalanceView>(askedGeneral ? 'general' : 'trial')
  const general = view === 'general'
  //: سند کل برگه‌ی ماهانه است؛ تراز معمولاً کلِ سال.
  const range = useRange(askedGeneral ? 'month' : 'year')
  const [columns, setColumns] = useState<BalanceColumns>(6)
  const [level, setLevel] = useState(0)
  const [filters, setFilters] = useState<ReportFilters>({})
  const [balanceFilter, setBalanceFilter] = useState<BalanceFilter>('all')
  const [query, setQuery] = useState('')
  const [drill, setDrill] = useState<{ id: string; code: string; name: string } | null>(null)
  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const fiscalYears = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
  //: کاتالوگِ گزارش‌ها «سند کل» را روی همین صفحه‌ی باز هم می‌تواند بخواهد.
  useEffect(() => {
    if (askedGeneral) setView('general')
  }, [askedGeneral])
  //: سند کل: فقط گردش، سطحِ کل. بقیه‌ی گزینه‌ها مالِ تراز است.
  const shownColumns: BalanceColumns = general ? 4 : columns
  const shownLevel = general ? 2 : level
  const groups = useMemo(() => balanceGroups(columns, general), [columns, general])
  //: «بدونِ گردش» تنها حالتی است که حساب‌های بی‌ردیف را هم لازم دارد؛ بقیه‌ی
  //: اوقات کشیدنشان یعنی چارتِ چندصدردیفی پر از صفر.
  const wantsIdle = !general && (balanceFilter === 'idle' || balanceFilter === 'all')
  const scope: ReportFilters = { ...filters, dateFrom: range.from, dateTo: range.to }
  const scopeKey = JSON.stringify(scope)
  const balances = useAsync(
    () => fetchAccountBalances(token, scope, wantsIdle),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, scopeKey, wantsIdle],
  )

  const rows = useMemo(
    () => aggregateBalances(balances.data ?? [], accounts.data ?? [], shownLevel),
    [accounts.data, balances.data, shownLevel],
  )
  const visible = useMemo(
    () => filterBalances(rows, { general, filter: balanceFilter, query }),
    [rows, balanceFilter, general, query],
  )
  const totals = useMemo(() => balanceTotals(visible, groups), [visible, groups])
  //: جمعِ بخشی از دفتر لازم نیست تراز باشد — «مانده بدهکار» به‌تعریف ناتراز است.
  const check = balanceCheck(totals, (general || balanceFilter === 'all') && !query.trim())

  // ── گرید: ردیفِ فعال، انتخاب، کیبورد ──
  const gridRef = useRef<HTMLDivElement>(null)
  const findRef = useRef<HTMLInputElement>(null)
  const [activeRow, setActiveRow] = useState(0)
  const { selected, click, clear } = useRowSelection()
  const active = Math.min(activeRow, Math.max(0, visible.length - 1))
  const order = visible.map((r) => r.account_id)
  const picked = visible.filter((r) => selected.has(r.account_id))
  //: بازه، سطح یا فیلترِ دیگر یعنی ردیف‌های دیگر؛ انتخابِ قبلی معنا ندارد.
  useEffect(() => {
    clear()
    setActiveRow(0)
  }, [scopeKey, shownLevel, balanceFilter, general, query, clear])
  //: فقط حرکتِ کیبورد ردیف را به دید می‌آورد — نه بارگذاری، که صفحه را بی‌خبر می‌پراند.
  const followActive = useRef(false)
  useEffect(() => {
    if (!followActive.current) return
    followActive.current = false
    document.getElementById(`br-row-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [active])

  const openDrill = (r: BalanceRow) => {
    if (r.has_activity === false) return
    setDrill({ id: r.account_id, code: r.account_code, name: r.account_name })
  }
  const moveTo = (i: number) => {
    followActive.current = true
    setActiveRow(Math.max(0, Math.min(visible.length - 1, i)))
  }
  /** Shift+↑↓: انتخاب از ردیفِ فعلی تا مقصد — اگر لنگری نیست، همین ردیف لنگر می‌شود. */
  const extendTo = (to: number) => {
    if (selected.size === 0) click(order, order[active], { shift: false, ctrl: true })
    click(order, order[to], { shift: true, ctrl: false })
  }
  const onGridKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (drill) return
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
      e.preventDefault()
      findRef.current?.focus()
      return
    }
    const last = visible.length - 1
    if (last < 0) return
    switch (e.key) {
      case 'ArrowDown':
      case 'ArrowUp': {
        e.preventDefault()
        const to = active + (e.key === 'ArrowDown' ? 1 : -1)
        if (to < 0 || to > last) break
        moveTo(to)
        if (e.shiftKey) extendTo(to)
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
        openDrill(visible[active])
        break
      case 'Escape':
        if (selected.size > 0) {
          e.preventDefault()
          clear()
        }
        break
    }
  }

  function exportCsv() {
    const headers = ['کد', 'نام حساب', 'نوع']
    for (const g of groups) headers.push(`${GROUP_LABELS[g]} بدهکار`, `${GROUP_LABELS[g]} بستانکار`)
    downloadCsv(
      `${general ? 'sanad-kol' : 'tarazha'}-${range.from ?? 'all'}`,
      headers,
      visible.map((r) => [
        r.account_code,
        r.account_name,
        TYPE_LABELS[r.account_type] ?? r.account_type,
        ...groups.flatMap((g) => pairOf(r, g)),
      ]),
    )
  }

  const pickedSum = (key: 'period' | 'closing') =>
    picked.reduce(
      (s, r) => {
        const [d, c] = pairOf(r, key)
        return [s[0] + d, s[1] + c]
      },
      [0, 0],
    )
  const [selPd, selPc] = pickedSum('period')
  const [selCd, selCc] = pickedSum('closing')
  const selNet = selCd - selCc

  const rangeText = range.from
    ? `${formatJalali(range.from)} تا ${formatJalali(range.to ?? todayIso())}`
    : `از ابتدای دفتر تا ${formatJalali(range.to ?? todayIso())}`
  const loadingFirst = !balances.data && !balances.error
  const levelLabel = LEVEL_OPTIONS.find((o) => o.value === shownLevel)?.label ?? ''

  return (
    <OpsPage
      canvas
      icon={Scale}
      title="گزارش ترازها"
      description="تراز آزمایشی در چهار قالبِ استاندارد و سه سطحِ حساب، و «سند کل»ِ پایانِ ماه (گردشِ هر حسابِ کل). همان یک داده است؛ قالب و ستون‌ها تعیین می‌کنند چقدرش را ببینید."
      head={
        //: سربرگِ اکسلی (همان «مرور حساب‌ها»): بازه و سالِ مالی؛ قالبِ برگه؛ فیلترهای دفتر؛ نماها و میان‌برها.
        <div className="jh-bar jh-bar--report" role="group" aria-label="بازه، قالب و فیلترهای گزارش ترازها">
          <div className="jh-row rh-row--range">
            <RangeCells range={range} years={fiscalYears.data ?? []} />
          </div>
          <div className="jh-row jh-row--sub rh-row--shape">
            <div className="jh-field br-view">
              <span className="jh-label">قالب</span>
              <div className="cc-presets rh-seg" role="group" aria-label="قالبِ گزارش">
                <button
                  type="button"
                  className={general ? '' : 'is-active'}
                  aria-pressed={!general}
                  onClick={() => setView('trial')}
                >
                  تراز آزمایشی
                </button>
                <button
                  type="button"
                  className={general ? 'is-active' : ''}
                  aria-pressed={general}
                  title="گردشِ بدهکار و بستانکارِ هر حسابِ کل در بازه — برگه‌ی بایگانیِ پایانِ ماه"
                  onClick={() => {
                    setView('general')
                    if (range.preset === 'year') range.setPreset('month')
                  }}
                >
                  سند کل
                </button>
              </div>
            </div>
            <div className="jh-field br-cols">
              <span className="jh-label">ستون‌ها</span>
              <div className="cc-presets rh-seg" role="group" aria-label="شمارِ ستون‌های مبلغ">
                {COLUMN_OPTIONS.map((o) => (
                  <button
                    key={o.value}
                    type="button"
                    title={general ? 'سند کل فقط گردش دارد' : o.hint}
                    disabled={general}
                    className={shownColumns === o.value ? 'is-active' : ''}
                    aria-pressed={shownColumns === o.value}
                    onClick={() => setColumns(o.value)}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="jh-field br-level">
              <span className="jh-label">سطح</span>
              <div className="cc-presets rh-seg" role="group" aria-label="سطحِ حساب">
                {LEVEL_OPTIONS.map((o) => (
                  <button
                    key={o.value}
                    type="button"
                    title={general ? 'سند کل در سطحِ حسابِ کل است' : o.hint}
                    disabled={general}
                    className={shownLevel === o.value ? 'is-active' : ''}
                    aria-pressed={shownLevel === o.value}
                    onClick={() => setLevel(o.value)}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <label className="jh-field br-balance">
              <span className="jh-label">نوعِ مانده</span>
              <SearchSelect
                aria-label="نوعِ مانده"
                value={general ? 'all' : balanceFilter}
                disabled={general}
                onChange={(e) => setBalanceFilter(e.target.value as BalanceFilter)}
              >
                {BALANCE_FILTERS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </SearchSelect>
            </label>
          </div>
          <div className="jh-row jh-row--sub rh-row--filters">
            <ReportFilterBar token={token} filters={filters} onChange={setFilters} variant="cells" />
          </div>
          <div className="jh-row jh-row--sub rh-row--tools">
            <div className="jh-field rh-views">
              <span className="jh-label">نماهای ذخیره‌شده</span>
              <SavedViewBar
                token={token}
                viewKey="accounting.trial_balance"
                filters={filters}
                range={range}
                setFilters={setFilters}
              />
            </div>
            {onNavigate && (
              <div className="jh-field rh-go">
                <span className="jh-label">رفتن به</span>
                <div className="rh-links">
                  <button type="button" onClick={() => onNavigate('journalentry')}>
                    <FilePlus2 size={14} aria-hidden="true" /> ثبت سند جدید
                  </button>
                  <button type="button" onClick={() => onNavigate('accountbrowse')}>
                    <Layers size={14} aria-hidden="true" /> مرور حساب‌ها
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
        icon={Scale}
        title={general ? 'سند کل' : 'تراز آزمایشی'}
        description={`${rangeText} — ${general ? 'گردشِ هر حسابِ کل' : `سطحِ ${levelLabel}، ${faInt(shownColumns)} ستونی`}`}
        badge={
          balances.data ? (
            <CountBadge accent>
              {faInt(visible.length)} حساب
            </CountBadge>
          ) : undefined
        }
        actions={
          <div className="jg-head-actions">
            <div className={`jg-find${query ? ' has-query' : ''}`} role="search">
              <Search size={14} aria-hidden="true" />
              <input
                ref={findRef}
                type="search"
                value={query}
                placeholder="جست‌وجوی کد یا نام  (Ctrl+F)"
                aria-label="جست‌وجوی حساب در تراز"
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') {
                    e.preventDefault()
                    setQuery('')
                    gridRef.current?.focus()
                  } else if (e.key === 'ArrowDown' || e.key === 'Enter') {
                    e.preventDefault()
                    gridRef.current?.focus()
                  }
                }}
              />
            </div>
            <button type="button" className="ef-btn-secondary" onClick={exportCsv} disabled={visible.length === 0}>
              <Download size={14} /> خروجی CSV
            </button>
            <button type="button" className="ef-btn-secondary" onClick={() => window.print()}>
              <Printer size={14} /> چاپ
            </button>
          </div>
        }
      >
        <AsyncBlock
          loading={loadingFirst || (accounts.loading && !accounts.data)}
          error={balances.data ? null : (balances.error ?? accounts.error)}
        >
          {balances.error && <p className="hint acc-note acc-note--err">{balances.error}</p>}
          <div
            ref={gridRef}
            tabIndex={visible.length > 0 ? 0 : -1}
            className={`table-scroll ef-table-wrap br-scroll${balances.loading ? ' is-loading' : ''}`}
            onKeyDown={onGridKey}
            aria-label="تراز — ↑↓ حرکت، Enter دفترِ حساب، Space یا Shift+↑↓ انتخاب، Esc لغوِ انتخاب"
          >
            {/* کفِ عرض با هر جفت ستونِ مبلغ بزرگ می‌شود؛ جا نشد، مبلغ‌ها زیرِ ستون‌های میخ‌شده‌ی حساب می‌لغزند. */}
            <table
              className="cards-on-mobile ef-table xl-grid br-table"
              style={{ '--br-pairs': groups.length } as CSSProperties}
            >
              <colgroup>
                <col className="br-c-rowhead" />
                <col className="br-c-code" />
                <col className="br-c-name" />
                {groups.map((g) => (
                  <Fragment key={g}>
                    <col className="br-c-amt" />
                    <col className="br-c-amt" />
                  </Fragment>
                ))}
              </colgroup>
              <thead>
                <tr>
                  <th className="xl-rowhead br-pin br-pin--row" rowSpan={2} aria-label="انتخاب" />
                  <th className="br-pin br-pin--code" rowSpan={2}>
                    کد
                  </th>
                  <th className="br-pin br-pin--name" rowSpan={2}>
                    نامِ حساب
                  </th>
                  {groups.map((g) => (
                    <th key={g} colSpan={2} className="br-group br-gs" scope="colgroup">
                      {GROUP_LABELS[g]}
                    </th>
                  ))}
                </tr>
                <tr>
                  {groups.map((g) => (
                    <Fragment key={g}>
                      <th className="num br-gs">بدهکار</th>
                      <th className="num">بستانکار</th>
                    </Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 ? (
                  <tr>
                    <td className="card-full br-status" colSpan={3 + groups.length * 2}>
                      {general
                        ? 'در این بازه هیچ حسابی گردش نخورده — بازه را عوض کنید.'
                        : query.trim()
                          ? 'حسابی با این کد یا نام در تراز نیست.'
                          : 'با این فیلترها ردیفی نیست — بازه یا نوعِ مانده را عوض کنید.'}
                    </td>
                  </tr>
                ) : (
                  visible.map((r, i) => {
                    const on = selected.has(r.account_id)
                    const idle = r.has_activity === false
                    return (
                      <tr
                        key={r.account_id}
                        id={`br-row-${i}`}
                        className={`${idle ? 'acc-row--idle' : 'acc-row--clickable'}${i === active ? ' is-active' : ''}${on ? ' is-selected' : ''}`}
                        title={idle ? 'این حساب در این دامنه گردشی ندارد' : undefined}
                        onClick={() => {
                          setActiveRow(i)
                          openDrill(r)
                        }}
                      >
                        <td className="xl-rowhead card-hide br-pin br-pin--row">
                          <button
                            type="button"
                            tabIndex={-1}
                            className="xl-rowhead-btn"
                            aria-pressed={on}
                            aria-label={`انتخابِ ردیفِ ${faInt(i + 1)}`}
                            onClick={(ev) => {
                              //: شماره‌ی ردیف فقط انتخاب می‌کند؛ کلیکِ بقیه‌ی ردیف دفترِ حساب را باز می‌کند.
                              ev.stopPropagation()
                              setActiveRow(i)
                              click(order, r.account_id, modsOf(ev))
                            }}
                          >
                            {faInt(i + 1)}
                          </button>
                        </td>
                        <td className="card-hide br-code br-pin br-pin--code">
                          <span className="ltr-cell">{r.account_code}</span>
                        </td>
                        <td className="card-title br-name br-pin br-pin--name" title={r.account_name}>
                          <span className="br-code-inline">{r.account_code}</span>
                          {r.account_name}
                        </td>
                        {groups.map((g) => {
                          const [d, c] = pairOf(r, g)
                          return (
                            <Fragment key={g}>
                              <td
                                className={`num br-gs${d === 0 ? ' br-zero' : ''}`}
                                data-label={`${GROUP_LABELS[g]} بدهکار`}
                              >
                                {faAmount(d)}
                              </td>
                              <td className={`num${c === 0 ? ' br-zero' : ''}`} data-label={`${GROUP_LABELS[g]} بستانکار`}>
                                {faAmount(c)}
                              </td>
                            </Fragment>
                          )
                        })}
                      </tr>
                    )
                  })
                )}
              </tbody>
              <tfoot>
                <tr className="br-total">
                  <td className="xl-rowhead card-hide br-pin br-pin--row" />
                  <td className="card-title br-pin br-pin--code" colSpan={2}>
                    <span className="br-total-label">جمع</span>
                    {check.kind === 'ok' ? (
                      <span className="br-check br-check--ok">
                        <CheckCircle2 size={13} aria-hidden="true" /> تراز است
                      </span>
                    ) : check.kind === 'off' ? (
                      <span
                        className="br-check br-check--off"
                        role="alert"
                        title={check.off.map((o) => `اختلافِ ${GROUP_LABELS[o.group]}: ${fa(Math.abs(o.diff))}`).join('، ')}
                      >
                        <AlertTriangle size={13} aria-hidden="true" />
                        {check.off.length === 1
                          ? `ناتراز — اختلافِ ${GROUP_LABELS[check.off[0].group]} ${fa(Math.abs(check.off[0].diff))}`
                          : `ناتراز در ${check.off.map((o) => GROUP_LABELS[o.group]).join(' و ')}`}
                      </span>
                    ) : (
                      <small>ردیف‌های فیلترشده</small>
                    )}
                  </td>
                  {groups.map((g) => {
                    const [d, c] = totals.get(g) ?? [0, 0]
                    const off = check.kind === 'off' && check.off.some((o) => o.group === g) ? ' br-off' : ''
                    return (
                      <Fragment key={g}>
                        <td className={`num br-gs${off}${d === 0 ? ' br-zero' : ''}`} data-label={`جمعِ ${GROUP_LABELS[g]} بدهکار`}>
                          {faAmount(d)}
                        </td>
                        <td className={`num${off}${c === 0 ? ' br-zero' : ''}`} data-label={`جمعِ ${GROUP_LABELS[g]} بستانکار`}>
                          {faAmount(c)}
                        </td>
                      </Fragment>
                    )
                  })}
                </tr>
              </tfoot>
            </table>
          </div>
          {picked.length > 0 && (
            <SelectionBar count={picked.length} unit="حساب" onClear={clear}>
              {groups.includes('period') && (
                <>
                  <span>
                    گردش بدهکار <b className="num">{faAmount(selPd)}</b>
                  </span>
                  <span>
                    گردش بستانکار <b className="num">{faAmount(selPc)}</b>
                  </span>
                </>
              )}
              {groups.includes('closing') && (
                <span>
                  مانده{' '}
                  <b className="num">
                    {selNet === 0 ? '—' : `${fa(Math.abs(selNet))} ${selNet > 0 ? 'بدهکار' : 'بستانکار'}`}
                  </b>
                </span>
              )}
            </SelectionBar>
          )}
          {visible.length > 0 && (
            <p className="ab-keys br-keys">
              <kbd>↑</kbd>
              <kbd>↓</kbd> ردیف · <kbd>Enter</kbd> یا کلیک دفترِ حساب · <kbd>Space</kbd> یا <kbd>Shift+↑↓</kbd> یا
              شماره‌ی ردیف انتخاب · <kbd>Ctrl+F</kbd> جست‌وجو · <kbd>Esc</kbd> لغوِ انتخاب
            </p>
          )}
        </AsyncBlock>
      </SectionCard>

      <NatureViolationsCard token={token} />
      <MissingTafsiliCard token={token} />

      {/* §۱۱ و §۲۸ — هیچ عددی بن‌بست نیست. دامنه‌ی دفتر همان دامنه‌ی تراز است،
          وگرنه کاربر عددی را باز می‌کرد و توضیحی می‌دید که با آن نمی‌خواند. */}
      {drill && (
        <AccountLedgerDrawer
          token={token}
          account={drill}
          filters={scope}
          onClose={() => {
            setDrill(null)
            gridRef.current?.focus({ preventScroll: true })
          }}
        />
      )}
    </OpsPage>
  )
}

/**
 * ردیف‌هایی که روی حسابِ «تفصیلی پذیر» نشسته‌اند ولی تفصیلی ندارند.
 *
 * **در هر سه سطحِ اجبار کار می‌کند.** سطحِ اجبار (تنظیمات ← شخصی‌سازی) تعیین می‌کند
 * چه چیزی *مسدود* شود، نه چه چیزی *دیده* شود — پس حتی در «شناور» هم این سوراخ
 * نامرئی نمی‌ماند. در «ترکیبی» تقریباً همه‌ی ردیف‌های این فهرست از ماژول‌ها می‌آیند،
 * که دقیقاً همان چیزی است که باید دیده شود.
 */
function MissingTafsiliCard({ token }: { token: string }) {
  const rows = useAsync(() => fetchMissingTafsili(token), [token])
  const list = rows.data ?? []

  return (
    <SectionCard
      icon={AlertTriangle}
      title="ردیف‌های بدونِ تفصیلی"
      description="این ردیف‌ها روی حسابِ تفصیلی‌پذیر نشسته‌اند ولی تفصیلی ندارند. جمعِ حساب درست است؛ تفکیکش ناقص."
      badge={list.length > 0 ? <CountBadge>{faInt(list.length)} ردیف</CountBadge> : undefined}
    >
      <AsyncBlock
        loading={rows.loading}
        error={rows.error}
        empty={list.length === 0}
        emptyText="هر ردیفی که روی حسابِ تفصیلی‌پذیر نشسته، تفصیلی دارد."
      >
        <div className="table-scroll ef-table-wrap">
          <table className="ef-table xl-grid cards-on-mobile acc-table br-check-table">
            <thead>
              <tr>
                <th>تاریخ</th>
                <th>سند</th>
                <th>حساب</th>
                <th>شرح</th>
                <th className="num">مبلغ</th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={`${r.entry_id}-${r.account_id}`}>
                  <td data-label="تاریخ">{formatJalali(r.entry_date)}</td>
                  <td className="card-title" data-label="سند">
                    <span className="ltr-cell">{r.entry_number ?? '—'}</span>
                    {!r.is_manual && <span className="chart-trait-tag">خودکار</span>}
                  </td>
                  <td data-label="حساب">
                    <span className="ltr-cell">{r.account_code}</span> {r.account_name}
                  </td>
                  <td className="card-wide" data-label="شرح">
                    {r.description || '—'}
                  </td>
                  <td className="num" data-label="مبلغ">
                    {fa(Number(r.debit) || Number(r.credit))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncBlock>
    </SectionCard>
  )
}

/**
 * حساب‌هایی که مانده‌شان خلافِ ماهیتشان است.
 *
 * **گزارش است، نه گارد.** خلافِ ماهیت شدن گاهی واقعاً درست است — اضافه‌برداشتِ
 * بانکی، پیش‌دریافتِ مشتری — پس مسدود کردنِ ثبت یعنی جلوگیری از ضبطِ رویدادی که
 * اتفاق افتاده. این‌جا فقط نشان داده می‌شود تا حسابدار خودش قضاوت کند.
 *
 * زیرِ ترازها نشسته چون همان دادهٔ مانده را از زاویه‌ی دیگری می‌خواند: تراز
 * می‌گوید مانده چقدر است، این می‌گوید کدام مانده سرِ جایش نیست.
 */
function NatureViolationsCard({ token }: { token: string }) {
  //: تیکِ «کنترل ماهیت طی دوره»ی فرمِ حساب. پیش‌فرض خاموش است تا گزارش کامل بیاید؛
  //: در چارتِ بزرگ حسابدار فقط چند حسابِ حساس را رصد می‌کند و آن‌وقت روشنش می‌کند.
  const [controlledOnly, setControlledOnly] = useState(false)
  const rows = useAsync(() => fetchNatureViolations(token, controlledOnly), [token, controlledOnly])
  const list = rows.data ?? []

  return (
    <SectionCard
      icon={AlertTriangle}
      title="حساب‌های خلافِ ماهیت"
      description="ماندهٔ این حساب‌ها در سمتی است که انتظار نمی‌رفت. لزوماً غلط نیست — اضافه‌برداشتِ بانکی و پیش‌دریافتِ مشتری هم همین شکل‌اند."
      badge={list.length > 0 ? <CountBadge>{faInt(list.length)} حساب</CountBadge> : undefined}
      actions={
        <label className="fy-check">
          <input type="checkbox" checked={controlledOnly} onChange={(e) => setControlledOnly(e.target.checked)} />
          فقط حساب‌هایی که «کنترل ماهیت» دارند
        </label>
      }
    >
      <AsyncBlock
        loading={rows.loading}
        error={rows.error}
        empty={list.length === 0}
        emptyText={
          controlledOnly ? 'هیچ‌کدام از حساب‌های تحتِ کنترل خلافِ ماهیت نیستند.' : 'هیچ حسابی خلافِ ماهیتش نیست.'
        }
      >
        <div className="table-scroll ef-table-wrap">
          <table className="ef-table xl-grid cards-on-mobile acc-table br-check-table">
            <thead>
              <tr>
                <th>کد</th>
                <th>حساب</th>
                <th>ماهیتِ انتظاری</th>
                <th>ماندهٔ فعلی</th>
                <th className="num">مبلغ</th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.account_id}>
                  <td data-label="کد">
                    <span className="ltr-cell">{r.account_code}</span>
                  </td>
                  <td className="card-title" data-label="حساب">
                    {r.account_name}
                    {r.nature_control && <span className="chart-trait-tag">کنترلِ ماهیت</span>}
                  </td>
                  <td data-label="ماهیتِ انتظاری">
                    <span className={`nature-badge nature-badge--${r.nature}`}>
                      {ACCOUNT_NATURE_LABELS[r.nature] ?? r.nature}
                      {!r.nature_is_explicit && <span className="nature-badge__auto">خودکار</span>}
                    </span>
                  </td>
                  <td data-label="ماندهٔ فعلی">
                    <span className={`nature-badge nature-badge--${r.balance_side}`}>
                      {ACCOUNT_NATURE_LABELS[r.balance_side] ?? r.balance_side}
                    </span>
                  </td>
                  <td className="num" data-label="مبلغ">
                    {fa(Number(r.balance))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncBlock>
    </SectionCard>
  )
}
