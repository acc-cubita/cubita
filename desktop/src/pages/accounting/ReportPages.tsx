import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  BookOpenCheck,
  Download,
  FileSpreadsheet,
  Landmark,
  Layers,
  Library,
  Percent,
  Printer,
  Scale,
  Search,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import {
  ACCOUNT_NATURE_LABELS,
  fetchAccountBalances,
  fetchChartAccounts,
  fetchAnalyticLedger,
  fetchGeneralLedger,
  fetchJournalEntriesFiltered,
  fetchLegalBook,
  fetchMissingTafsili,
  fetchNatureViolations,
  fetchVatReport,
  type BalanceRow,
  type ChartAccount,
  type GeneralLedger,
  type ReportFilters,
  type VatBreakdown,
} from '../../api'
import { AccountLedgerDrawer } from '../../components/AccountLedgerDrawer'
import { EntryCard } from '../../components/EntryCard'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { ReportFilterBar } from '../../components/ReportFilterBar'
import { SavedViewBar } from '../../components/SavedViewBar'
import { SectionCard } from '../../components/SectionCard'
import { Pager, usePagination } from '../../components/Pager'
import { downloadCsv } from '../../lib/csv'
import { formatJalali, isoToJalali, jalaaliMonthLength, jalaliToIso, todayIso } from '../../lib/jalali'
import {
  AsyncBlock,
  BalanceFooter,
  Metric,
  OpsPage,
  RangeBar,
  StatusChip,
  fa,
  faAmount,
  faInt,
  useAsync,
  useRange,
} from './kit'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * چهار گزارشِ پایه‌ی دفترداری.
 *
 * سه‌تای اولش نمایشِ همان یک دادهٔ گردش‌اند در سه سطحِ ریزشدن — تراز (خلاصه)، دفتر
 * (سندبه‌سند)، دفاترِ قانونی (ردیف‌به‌ردیف با چیدمانِ رسمی). چهارمی مالیات است که
 * دادهٔ خودش را دارد. هر چهار تا خروجیِ CSV می‌دهند چون هر کدامشان دیر یا زود باید
 * جایی بیرون از برنامه تحویل شوند.
 */

const TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی',
  liability: 'بدهی',
  equity: 'سرمایه',
  income: 'درآمد',
  expense: 'هزینه',
}

/** سطحِ حساب در چارت: ۱ = گروه، ۲ = کل، ۳ = معین، ۴+ = تفصیلی. */
function levelOf(account: ChartAccount, byId: Map<string, ChartAccount>): number {
  let level = 1
  let node = account
  const seen = new Set<string>()
  while (node.parent_id && !seen.has(node.id)) {
    seen.add(node.id)
    const parent = byId.get(node.parent_id)
    if (!parent) break
    node = parent
    level += 1
  }
  return level
}

/** جدِ حساب در سطحِ داده‌شده — پایه‌ی تجمیعِ تراز در سطحِ کل/معین. */
function ancestorAtLevel(
  account: ChartAccount,
  byId: Map<string, ChartAccount>,
  level: number,
): ChartAccount {
  let node = account
  const seen = new Set<string>()
  while (levelOf(node, byId) > level && node.parent_id && !seen.has(node.id)) {
    seen.add(node.id)
    const parent = byId.get(node.parent_id)
    if (!parent) break
    node = parent
  }
  return node
}

// ═══════════════════════ ۱) گزارش ترازها ═══════════════════════

type Columns = 2 | 4 | 6 | 8

const COLUMN_OPTIONS: { value: Columns; label: string; hint: string }[] = [
  { value: 2, label: 'دو ستونی', hint: 'فقط مانده‌ی پایانِ دوره' },
  { value: 4, label: 'چهار ستونی', hint: 'گردش و مانده‌ی دوره' },
  { value: 6, label: 'شش ستونی', hint: 'افتتاحیه، گردش، مانده' },
  { value: 8, label: 'هشت ستونی', hint: 'افتتاحیه، گردش، جمع، مانده' },
]

const LEVEL_OPTIONS = [
  { value: 2, label: 'کل' },
  { value: 3, label: 'معین' },
  { value: 0, label: 'تفصیلی (سطحِ آخر)' },
]

/** فیلترِ نوعِ مانده (§۱۷). «بدونِ گردش» عمداً از «مانده صفر» جداست. */
const BALANCE_FILTERS = [
  { value: 'all', label: 'همه' },
  { value: 'debit', label: 'مانده بدهکار' },
  { value: 'credit', label: 'مانده بستانکار' },
  { value: 'zero', label: 'مانده صفر' },
  { value: 'idle', label: 'بدونِ گردش' },
] as const
type BalanceFilter = (typeof BALANCE_FILTERS)[number]['value']

export function BalanceReportPage({ token }: { token: string }) {
  const range = useRange('year')
  const [columns, setColumns] = useState<Columns>(6)
  const [level, setLevel] = useState(0)
  const [filters, setFilters] = useState<ReportFilters>({})
  const [balanceFilter, setBalanceFilter] = useState<BalanceFilter>('all')
  const [drill, setDrill] = useState<{ id: string; code: string; name: string } | null>(null)
  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  //: «بدونِ گردش» تنها حالتی است که حساب‌های بی‌ردیف را هم لازم دارد؛ بقیه‌ی
  //: اوقات کشیدنشان یعنی چارتِ چندصدردیفی پر از صفر.
  const wantsIdle = balanceFilter === 'idle' || balanceFilter === 'all'
  const scope: ReportFilters = { ...filters, dateFrom: range.from, dateTo: range.to }
  const balances = useAsync(
    () => fetchAccountBalances(token, scope, wantsIdle),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, JSON.stringify(scope), wantsIdle],
  )

  /** تراز در هر سطحی، جمعِ همان ردیف‌های سطحِ آخر است — پس تجمیع اینجا انجام می‌شود
   *  نه با کوئریِ جدا. یک منبعِ عدد برای هر چهار حالتِ ستونی. */
  const rows = useMemo(() => {
    const list = accounts.data ?? []
    const byId = new Map(list.map((a) => [a.id, a]))
    const source = balances.data ?? []
    if (level === 0) return source
    const totals = new Map<string, BalanceRow>()
    for (const row of source) {
      const leaf = byId.get(row.account_id)
      if (!leaf) continue
      const target = ancestorAtLevel(leaf, byId, level)
      const bucket = totals.get(target.id)
      if (!bucket) {
        totals.set(target.id, {
          ...row,
          account_id: target.id,
          account_code: target.code,
          account_name: target.name,
          account_type: target.type,
          parent_id: target.parent_id,
        })
      } else {
        bucket.opening_debit = String(Number(bucket.opening_debit) + Number(row.opening_debit))
        bucket.opening_credit = String(Number(bucket.opening_credit) + Number(row.opening_credit))
        bucket.period_debit = String(Number(bucket.period_debit) + Number(row.period_debit))
        bucket.period_credit = String(Number(bucket.period_credit) + Number(row.period_credit))
        bucket.closing_debit = String(Number(bucket.closing_debit) + Number(row.closing_debit))
        bucket.closing_credit = String(Number(bucket.closing_credit) + Number(row.closing_credit))
      }
    }
    // مانده‌ی تجمیع‌شده باید *خالص* بشود، وگرنه یک سرفصل هم بدهکار و هم بستانکار
    // نشان می‌داد و جمعِ ستونِ مانده دو برابرِ واقعیت می‌شد.
    return [...totals.values()]
      .map((r) => {
        const net = Number(r.closing_debit) - Number(r.closing_credit)
        const openNet = Number(r.opening_debit) - Number(r.opening_credit)
        return {
          ...r,
          opening_debit: String(openNet > 0 ? openNet : 0),
          opening_credit: String(openNet < 0 ? -openNet : 0),
          closing_debit: String(net > 0 ? net : 0),
          closing_credit: String(net < 0 ? -net : 0),
        }
      })
      .sort((a, b) => a.account_code.localeCompare(b.account_code))
  }, [accounts.data, balances.data, level])


  function exportCsv() {
    const headers = ['کد', 'نام حساب', 'نوع']
    if (columns >= 6) headers.push('افتتاحیه بدهکار', 'افتتاحیه بستانکار')
    if (columns >= 4) headers.push('گردش بدهکار', 'گردش بستانکار')
    if (columns >= 8) headers.push('جمع بدهکار', 'جمع بستانکار')
    headers.push('مانده بدهکار', 'مانده بستانکار')
    downloadCsv(
      `tarazha-${range.from ?? 'all'}`,
      headers,
      visible.map((r) => {
        const cells: (string | number)[] = [r.account_code, r.account_name, TYPE_LABELS[r.account_type] ?? r.account_type]
        if (columns >= 6) cells.push(Number(r.opening_debit), Number(r.opening_credit))
        if (columns >= 4) cells.push(Number(r.period_debit), Number(r.period_credit))
        if (columns >= 8)
          cells.push(
            Number(r.opening_debit) + Number(r.period_debit),
            Number(r.opening_credit) + Number(r.period_credit),
          )
        cells.push(Number(r.closing_debit), Number(r.closing_credit))
        return cells
      }),
    )
  }

  //: در **رابط** اعمال می‌شود نه سرور: ردیف‌ها از قبل در دست‌اند و این فیلتر
  //: دامنه‌ی محاسبه را عوض نمی‌کند، فقط نمایش را — برخلافِ `ReportFilterBar` که
  //: باید سمتِ سرور باشد چون *خودِ عددها* را عوض می‌کند.
  const visible = useMemo(() => {
    if (balanceFilter === 'all') return rows
    return rows.filter((r) => {
      const net = Number(r.closing_debit) - Number(r.closing_credit)
      if (balanceFilter === 'idle') return r.has_activity === false
      if (balanceFilter === 'zero') return net === 0 && r.has_activity !== false
      if (balanceFilter === 'debit') return net > 0
      return net < 0
    })
  }, [rows, balanceFilter])

  //: **این سه خط باید زیرِ `visible` بمانند.**
  //:
  //: `sum` روی `visible` بسته می‌شود و بلافاصله صدا زده می‌شود، پس اگر بالای
  //: تعریفِ `visible` بنشیند در Temporal Dead Zone می‌افتد:
  //: `ReferenceError: Cannot access 'visible' before initialization` — و چون
  //: هیچ ErrorBoundaryای بالادست نبود، کلِ برنامه سفید می‌شد.
  //:
  //: این یک بار واقعاً اتفاق افتاد: نسخه‌ی اولیه `rows.reduce` بود (و `rows`
  //: بالاتر تعریف شده)، و بازآراییِ فیلترها آن را به `visible` عوض کرد بی‌آنکه
  //: جای تعریف را عوض کند. `tsc` نمی‌گیردش چون استفاده *داخلِ* یک تابع است و
  //: تایپ‌چکر فرض می‌کند شاید بعداً صدا زده شود.
  const sum = (key: keyof BalanceRow) => visible.reduce((s, r) => s + Number(r[key] as string), 0)
  const periodDebit = sum('period_debit')
  const periodCredit = sum('period_credit')

  const pg = usePagination(visible, 25)

  return (
    <OpsPage
      icon={Scale}
      title="گزارش ترازها"
      description="تراز آزمایشی در چهار قالبِ استاندارد و سه سطحِ حساب. همان یک داده است؛ ستون‌ها تعیین می‌کنند چقدرش را ببینید."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={
              <>
                <label className="acc-inline-field">
                  ستون‌ها
                  <SearchSelect
                    value={columns}
                    onChange={(e) => setColumns(Number(e.target.value) as Columns)}
                  >
                    {COLUMN_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label} — {o.hint}
                      </option>
                    ))}
                  </SearchSelect>
                </label>
                <label className="acc-inline-field">
                  سطح
                  <SearchSelect value={level} onChange={(e) => setLevel(Number(e.target.value))}>
                    {LEVEL_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </SearchSelect>
                </label>
                <label className="acc-inline-field">
                  نوعِ مانده
                  <SearchSelect
                    value={balanceFilter}
                    onChange={(e) => setBalanceFilter(e.target.value as BalanceFilter)}
                  >
                    {BALANCE_FILTERS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </SearchSelect>
                </label>
                <ReportFilterBar token={token} filters={filters} onChange={setFilters} />
              </>
            }
          />
          <SavedViewBar
            token={token}
            viewKey="accounting.trial_balance"
            filters={filters}
            range={range}
            setFilters={setFilters}
          />
          <div className="cc-summary">
            <Metric icon={<Scale size={14} />} label="ردیف" value={faInt(visible.length)} />
            <Metric icon={<Wallet size={14} />} label="گردشِ بدهکار" value={fa(periodDebit)} tone="in" />
            <Metric icon={<Wallet size={14} />} label="گردشِ بستانکار" value={fa(periodCredit)} tone="out" />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Scale}
        title="تراز"
        description={
          range.from
            ? `${formatJalali(range.from)} تا ${formatJalali(range.to ?? todayIso())} — روی هر حساب کلیک کنید تا دفترش باز شود`
            : 'از ابتدای دفتر — روی هر حساب کلیک کنید تا دفترش باز شود'
        }
        actions={
          <>
            <button type="button" onClick={exportCsv} disabled={visible.length === 0}>
              <Download size={13} /> خروجی CSV
            </button>
            <button type="button" onClick={() => window.print()}>
              <Printer size={13} /> چاپ
            </button>
          </>
        }
      >
        <AsyncBlock
          loading={accounts.loading || balances.loading}
          error={accounts.error ?? balances.error}
          empty={visible.length === 0}
          emptyText="با این فیلترها ردیفی نیست — بازه یا نوعِ مانده را عوض کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table acc-table--wide">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>نامِ حساب</th>
                  {columns >= 6 && (
                    <>
                      <th>افتتاحیه بد</th>
                      <th>افتتاحیه بس</th>
                    </>
                  )}
                  {columns >= 4 && (
                    <>
                      <th>گردش بد</th>
                      <th>گردش بس</th>
                    </>
                  )}
                  {columns >= 8 && (
                    <>
                      <th>جمع بد</th>
                      <th>جمع بس</th>
                    </>
                  )}
                  <th>مانده بد</th>
                  <th>مانده بس</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr
                    key={r.account_id}
                    className={r.has_activity === false ? "acc-row--idle" : "acc-row--clickable"}
                    onClick={() =>
                      r.has_activity === false
                        ? undefined
                        : setDrill({ id: r.account_id, code: r.account_code, name: r.account_name })
                    }
                  >
                    <td className="card-title" data-label="کد" dir="ltr">
                      {r.account_code}
                    </td>
                    <td data-label="نامِ حساب">{r.account_name}</td>
                    {columns >= 6 && (
                      <>
                        <td data-label="افتتاحیه بد" className="num">{faAmount(r.opening_debit)}</td>
                        <td data-label="افتتاحیه بس" className="num">{faAmount(r.opening_credit)}</td>
                      </>
                    )}
                    {columns >= 4 && (
                      <>
                        <td data-label="گردش بد" className="num">{faAmount(r.period_debit)}</td>
                        <td data-label="گردش بس" className="num">{faAmount(r.period_credit)}</td>
                      </>
                    )}
                    {columns >= 8 && (
                      <>
                        <td data-label="جمع بد" className="num">
                          {faAmount(Number(r.opening_debit) + Number(r.period_debit))}
                        </td>
                        <td data-label="جمع بس" className="num">
                          {faAmount(Number(r.opening_credit) + Number(r.period_credit))}
                        </td>
                      </>
                    )}
                    <td data-label="مانده بد" className="num">{faAmount(r.closing_debit)}</td>
                    <td data-label="مانده بس" className="num">{faAmount(r.closing_credit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
          <BalanceFooter debit={periodDebit} credit={periodCredit} />
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
          onClose={() => setDrill(null)}
        />
      )}
    </OpsPage>
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
    >
      <AsyncBlock
        loading={rows.loading}
        error={rows.error}
        empty={list.length === 0}
        emptyText="هر ردیفی که روی حسابِ تفصیلی‌پذیر نشسته، تفصیلی دارد."
      >
        <div className="table-scroll">
          <table className="cards-on-mobile acc-table">
            <thead>
              <tr>
                <th>تاریخ</th>
                <th>سند</th>
                <th>حساب</th>
                <th>شرح</th>
                <th>مبلغ</th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={`${r.entry_id}-${r.account_id}`}>
                  <td data-label="تاریخ">{formatJalali(r.entry_date)}</td>
                  <td data-label="سند">
                    <span className="ltr-cell">{r.entry_number ?? '—'}</span>
                    {!r.is_manual && <span className="chart-trait-tag">خودکار</span>}
                  </td>
                  <td data-label="حساب">
                    <span className="ltr-cell">{r.account_code}</span> {r.account_name}
                  </td>
                  <td data-label="شرح">{r.description || '—'}</td>
                  <td data-label="مبلغ">{fa(Number(r.debit) || Number(r.credit))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncBlock>
    </SectionCard>
  )
}

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
      actions={
        <label className="fy-check">
          <input
            type="checkbox"
            checked={controlledOnly}
            onChange={(e) => setControlledOnly(e.target.checked)}
          />
          فقط حساب‌هایی که «کنترل ماهیت» دارند
        </label>
      }
    >
      <AsyncBlock
        loading={rows.loading}
        error={rows.error}
        empty={list.length === 0}
        emptyText={
          controlledOnly
            ? 'هیچ‌کدام از حساب‌های تحتِ کنترل خلافِ ماهیت نیستند.'
            : 'هیچ حسابی خلافِ ماهیتش نیست.'
        }
      >
        <div className="table-scroll">
          <table className="cards-on-mobile acc-table">
            <thead>
              <tr>
                <th>کد</th>
                <th>حساب</th>
                <th>ماهیتِ انتظاری</th>
                <th>ماندهٔ فعلی</th>
                <th>مبلغ</th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.account_id}>
                  <td data-label="کد" className="ltr-cell">{r.account_code}</td>
                  <td data-label="حساب">
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
                  <td data-label="مبلغ">{fa(Number(r.balance))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncBlock>
    </SectionCard>
  )
}

// ═══════════════════════ ۲) گزارش دفتر ═══════════════════════

/** سه دفترِ حسابداری، به همان ترتیبی که در عمل خوانده می‌شوند. */
type Book = 'journal' | 'general' | 'ledger' | 'analytic'

export function LedgerReportPage({ token }: { token: string }) {
  const range = useRange('month')
  const [book, setBook] = useState<Book>('journal')
  const [filters, setFilters] = useState<ReportFilters>({})
  const [accountId, setAccountId] = useState('')
  //: انتخابِ دفترِ کل جداست، وگرنه جابه‌جا شدن بینِ دو تب یک شناسه‌ی نامعتبر را
  //: به انتخابگرِ دیگر می‌برد و کاربر یک `select`ِ خالی می‌بیند بی‌آنکه بداند چرا.
  const [generalId, setGeneralId] = useState('')
  const [search, setSearch] = useState('')

  const accounts = useAsync(() => fetchChartAccounts(token), [token])
  const postable = useMemo(
    () =>
      (accounts.data ?? [])
        .filter((a) => !a.is_group)
        .sort((a, b) => a.code.localeCompare(b.code)),
    [accounts.data],
  )
  //: حساب‌های سطحِ «کل» — همان عددی که `LEVEL_OPTIONS`ِ گزارش ترازها به کار می‌برد،
  //: با همان `levelOf`. سطح از عمقِ درخت می‌آید نه طولِ کد، چون چارت یکدست نیست:
  //: دارایی‌ها ۱ ← ۱۱ ← ۱۱۰۱ دارند و هزینه‌ها ۵ ← ۵۱۰۱.
  const generalAccounts = useMemo(() => {
    const list = accounts.data ?? []
    const byId = new Map(list.map((a) => [a.id, a]))
    return list
      .filter((a) => levelOf(a, byId) === 2)
      .sort((a, b) => a.code.localeCompare(b.code))
  }, [accounts.data])
  //: بازه و فیلترها یک دامنه‌اند و با هم به سرور می‌روند — همان چیزی که تراز هم
  //: می‌فرستد، تا دو گزارش نتوانند از هم جدا بیفتند.
  const scope: ReportFilters = { ...filters, dateFrom: range.from, dateTo: range.to }

  //: ردیفِ سند فقط شناسه‌ی حساب دارد؛ نام از چارت می‌آید تا دفتر خوانا باشد.
  const accountNames = useMemo(
    () => new Map((accounts.data ?? []).map((a) => [a.id, `${a.code} — ${a.name}`])),
    [accounts.data],
  )

  return (
    <OpsPage
      icon={BookOpenCheck}
      title="گزارش دفتر"
      description="سه دفترِ حسابداری: روزنامه (همه‌ی اسناد به‌ترتیبِ تاریخ)، کل (گردشِ یک سرفصل با همه‌ی زیرحساب‌هایش) و معین (گردشِ یک حساب با مانده‌ی دوره‌ای)."
      head={
        <div className="cc-head">
          <div className="cc-tabs">
            <button
              type="button"
              className={book === 'journal' ? 'is-active' : ''}
              onClick={() => setBook('journal')}
            >
              <BookOpenCheck size={14} /> دفتر روزنامه
            </button>
            <button
              type="button"
              className={book === 'general' ? 'is-active' : ''}
              onClick={() => setBook('general')}
            >
              <Library size={14} /> دفتر کل
            </button>
            <button
              type="button"
              className={book === 'ledger' ? 'is-active' : ''}
              onClick={() => setBook('ledger')}
            >
              <Landmark size={14} /> دفتر معین
            </button>
            <button
              type="button"
              className={book === 'analytic' ? 'is-active' : ''}
              onClick={() => setBook('analytic')}
            >
              <Layers size={14} /> دفتر تفصیلی
            </button>
          </div>
          <RangeBar
            range={range}
            extra={
              book === 'journal' ? (
                <label className="acc-search">
                  <Search size={14} />
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="شماره یا شرحِ سند"
                  />
                </label>
              ) : book === 'general' ? (
                <>
                  <label className="acc-inline-field">
                    حسابِ کل
                    <SearchSelect value={generalId} onChange={(e) => setGeneralId(e.target.value)}>
                      <option value="">— انتخابِ حسابِ کل —</option>
                      {generalAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} — {a.name}
                        </option>
                      ))}
                    </SearchSelect>
                  </label>
                  <ReportFilterBar token={token} filters={filters} onChange={setFilters} />
                </>
              ) : book === 'ledger' ? (
                <>
                  <label className="acc-inline-field">
                    حساب
                    <SearchSelect value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                      <option value="">— انتخابِ حساب —</option>
                      {postable.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} — {a.name}
                        </option>
                      ))}
                    </SearchSelect>
                  </label>
                  <ReportFilterBar token={token} filters={filters} onChange={setFilters} />
                </>
              ) : (
                <ReportFilterBar token={token} filters={filters} onChange={setFilters} />
              )
            }
          />
          <SavedViewBar
            token={token}
            viewKey="accounting.ledger"
            filters={filters}
            range={range}
            setFilters={setFilters}
          />
        </div>
      }
    >
      {book === 'journal' ? (
        <DaybookCard
          token={token}
          from={range.from}
          to={range.to}
          search={search}
          accountNames={accountNames}
        />
      ) : book === 'general' ? (
        <SubsidiaryCard token={token} accountId={generalId} filters={scope} rollup />
      ) : book === 'analytic' ? (
        <SubsidiaryCard token={token} accountId="" filters={scope} analytic />
      ) : (
        <SubsidiaryCard token={token} accountId={accountId} filters={scope} />
      )}
    </OpsPage>
  )
}

function DaybookCard({
  token,
  from,
  to,
  search,
  accountNames,
}: {
  token: string
  from?: string
  to?: string
  search: string
  accountNames: Map<string, string>
}) {
  const list = useAsync(
    () =>
      fetchJournalEntriesFiltered(token, {
        dateFrom: from,
        dateTo: to,
        q: search || undefined,
        limit: 200,
      }),
    [token, from, to, search],
  )
  const entries = list.data ?? []
  const pg = usePagination(entries, 12)

  function exportCsv() {
    downloadCsv(
      `daftar-rooznameh-${from ?? 'all'}`,
      ['شماره سند', 'تاریخ', 'شرح سند', 'حساب', 'شرح ردیف', 'بدهکار', 'بستانکار'],
      entries.flatMap((e) =>
        e.lines.map((l) => [
          e.number ?? '',
          formatJalali(e.entry_date),
          e.description,
          accountNames.get(l.account_id) ?? '',
          l.description,
          Number(l.debit),
          Number(l.credit),
        ]),
      ),
    )
  }

  const debit = entries.reduce(
    (s, e) => s + e.lines.reduce((t, l) => t + Number(l.debit), 0),
    0,
  )

  return (
    <SectionCard
      icon={BookOpenCheck}
      title="دفتر روزنامه"
      description={`${faInt(entries.length)} سند — هر سند با ردیف‌هایش`}
      actions={
        <button type="button" onClick={exportCsv} disabled={entries.length === 0}>
          <Download size={13} /> خروجی CSV
        </button>
      }
    >
      <AsyncBlock
        loading={list.loading}
        error={list.error}
        empty={entries.length === 0}
        emptyText="در این بازه سندی نیست."
      >
        {/* همان `EntryCard`ی که درایوِ drill-down رندر می‌کند — یک نمای یک داده.
            پیش از این این جدول فقط این‌جا بود و وقتی «ردیفِ دفتر → سند» لازم شد،
            وسوسه‌ی نوشتنِ نسخه‌ی دومش پیش آمد. */}
        {pg.pageItems.map((e) => (
          <EntryCard key={e.id} entry={e} accountNames={accountNames} />
        ))}
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        <p className="hint">جمعِ گردشِ بازه: {fa(debit)}</p>
      </AsyncBlock>
    </SectionCard>
  )
}

/**
 * دفترِ یک حساب. با `rollup` همان حساب به‌علاوه‌ی همه‌ی زیرحساب‌هایش را می‌آورد —
 * یعنی «دفتر کل». سرور هر دو حالت را از یک نقطه می‌دهد، پس این‌جا هم یک کارت
 * می‌ماند نه دو: دو نمای یک داده ساخته نمی‌شود.
 */
function SubsidiaryCard({
  token,
  accountId,
  filters,
  rollup = false,
  analytic = false,
}: {
  token: string
  accountId: string
  filters: ReportFilters
  rollup?: boolean
  /** دفترِ تفصیلی: حساب اختیاری است و دامنه را `filters.analyticId` تعیین می‌کند. */
  analytic?: boolean
}) {
  const [entryId, setEntryId] = useState<string | null>(null)
  const ready = analytic ? !!filters.analyticId : !!accountId
  const ledger = useAsync<GeneralLedger | null>(
    () =>
      !ready
        ? Promise.resolve(null)
        : analytic
          ? fetchAnalyticLedger(token, filters)
          : fetchGeneralLedger(token, accountId, filters),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, accountId, analytic, ready, JSON.stringify(filters)],
  )
  const data = ledger.data
  const pg = usePagination(data?.lines ?? [], 20)
  const bookName = analytic ? 'دفتر تفصیلی' : rollup ? 'دفتر کل' : 'دفتر معین'
  const Icon = analytic ? Layers : rollup ? Library : Landmark

  //: ستون فقط وقتی می‌آید که ردیفی مقدار داشته باشد — جدولِ همیشه‌هشت‌ستونه‌ای که
  //: نیمش خط تیره است، خواندن را سخت می‌کند نه آسان.
  const hasFx = (data?.lines ?? []).some((l) => l.currency_code)
  const hasTracking = (data?.lines ?? []).some((l) => l.tracking_no)
  //: در دفترِ تفصیلی ردیف‌ها از حساب‌های مختلف‌اند، پس ستونِ حساب لازم است.
  const showAccount = rollup || analytic

  if (!ready)
    return (
      <SectionCard icon={Icon} title={bookName}>
        <p className="hint">
          {analytic
            ? 'برای دیدنِ دفترِ تفصیلی، از نوارِ فیلتر یک تفصیلی انتخاب کنید؛ گردشش در همه‌ی حساب‌ها می‌آید.'
            : rollup
              ? 'برای دیدنِ دفترِ کل، یک حسابِ کل انتخاب کنید؛ گردشِ همه‌ی زیرحساب‌هایش با هم می‌آید.'
              : 'برای دیدنِ دفترِ معین، یک حساب انتخاب کنید.'}
        </p>
      </SectionCard>
    )

  const title = data?.account_code ? `${data.account_code} — ${data.account_name}` : bookName

  return (
    <SectionCard
      icon={Icon}
      title={title}
      description={
        data
          ? `مانده‌ی ابتدای دوره ${fa(data.opening_balance)} · مانده‌ی پایان ${fa(data.closing_balance)}` +
            (data.fx_totals.length
              ? ` · ${data.fx_totals.map((t) => `${fa(t.amount)} ${t.currency_code}`).join(' · ')}`
              : '')
          : undefined
      }
      actions={
        <button
          type="button"
          disabled={!data || data.lines.length === 0}
          onClick={() =>
            data &&
            downloadCsv(
              `${analytic ? 'daftar-tafsili' : rollup ? 'daftar-kol' : 'daftar-moein'}-${data.account_code ?? 'all'}`,
              [
                'شماره سند',
                'تاریخ',
                ...(showAccount ? ['حساب'] : []),
                'شرح',
                ...(hasFx ? ['ارز', 'مبلغ ارزی'] : []),
                ...(hasTracking ? ['شماره پیگیری', 'تاریخ پیگیری'] : []),
                'بدهکار',
                'بستانکار',
                'مانده',
              ],
              data.lines.map((l) => [
                l.entry_number ?? '',
                formatJalali(l.entry_date),
                ...(showAccount ? [`${l.account_code} — ${l.account_name}`] : []),
                l.description,
                ...(hasFx ? [l.currency_code ?? '', l.fx_amount ? Number(l.fx_amount) : ''] : []),
                ...(hasTracking
                  ? [l.tracking_no ?? '', l.tracking_date ? formatJalali(l.tracking_date) : '']
                  : []),
                Number(l.debit),
                Number(l.credit),
                Number(l.balance),
              ]),
            )
          }
        >
          <Download size={13} /> خروجی CSV
        </button>
      }
    >
      <AsyncBlock
        loading={ledger.loading}
        error={ledger.error}
        empty={(data?.lines.length ?? 0) === 0}
        emptyText={
          analytic
            ? 'این تفصیلی در این دامنه هیچ گردشی ندارد.'
            : rollup
              ? 'هیچ‌کدام از زیرحساب‌های این سرفصل در بازه‌ی انتخابی گردشی ندارند.'
              : 'این حساب در بازه‌ی انتخابی گردشی ندارد.'
        }
      >
        <p className="hint">روی هر ردیف کلیک کنید تا سندش باز شود.</p>
        <div className="table-scroll">
          <table className="cards-on-mobile acc-table">
            <thead>
              <tr>
                <th>سند</th>
                <th>تاریخ</th>
                {/* در دفترِ معین همه‌ی ردیف‌ها یک حساب‌اند و این ستون فقط تکرار است. */}
                {showAccount && <th>حساب</th>}
                <th>شرح</th>
                {hasFx && <th>ارز</th>}
                {hasTracking && <th>پیگیری</th>}
                <th>بدهکار</th>
                <th>بستانکار</th>
                <th>مانده</th>
              </tr>
            </thead>
            <tbody>
              {pg.pageItems.map((l) => (
                <tr
                  key={l.line_id}
                  className="acc-row--clickable"
                  onClick={() => setEntryId(l.entry_id)}
                >
                  <td className="card-title" data-label="سند">
                    {fa(l.entry_number ?? 0)}
                  </td>
                  <td data-label="تاریخ">{formatJalali(l.entry_date)}</td>
                  {showAccount && (
                    <td data-label="حساب">
                      <span dir="ltr">{l.account_code}</span> — {l.account_name}
                    </td>
                  )}
                  <td data-label="شرح">{l.description || '—'}</td>
                  {hasFx && (
                    <td data-label="ارز" className="num">
                      {l.currency_code ? `${fa(l.fx_amount ?? 0)} ${l.currency_code}` : '—'}
                    </td>
                  )}
                  {hasTracking && (
                    <td data-label="پیگیری">
                      {l.tracking_no ? (
                        <>
                          <span dir="ltr">{l.tracking_no}</span>
                          {l.tracking_date ? ` — ${formatJalali(l.tracking_date)}` : ''}
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                  )}
                  <td data-label="بدهکار" className="num">
                    {faAmount(l.debit)}
                  </td>
                  <td data-label="بستانکار" className="num">
                    {faAmount(l.credit)}
                  </td>
                  <td data-label="مانده" className="num">
                    {fa(l.balance)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      </AsyncBlock>

      {entryId && (
        <JournalEntryDrawer token={token} entryId={entryId} onClose={() => setEntryId(null)} />
      )}
    </SectionCard>
  )
}

// ═════════════ ۳) مالیات بر ارزش افزوده ═════════════

const QUARTERS = [
  { value: 1, label: 'بهار (فروردین—خرداد)' },
  { value: 2, label: 'تابستان (تیر—شهریور)' },
  { value: 3, label: 'پاییز (مهر—آذر)' },
  { value: 4, label: 'زمستان (دی—اسفند)' },
]

export function VatPage({ token }: { token: string }) {
  const now = isoToJalali(todayIso())
  const [year, setYear] = useState(now.jy)
  const [quarter, setQuarter] = useState(Math.ceil(now.jm / 3))

  // بازه‌ی فصل به تقویمِ شمسی — اظهارنامه فصلی است، نه سه‌ماهه‌ی میلادی.
  const { from, to } = useMemo(() => {
    const startMonth = (quarter - 1) * 3 + 1
    const endMonth = startMonth + 2
    return {
      from: jalaliToIso(year, startMonth, 1),
      to: jalaliToIso(year, endMonth, jalaaliMonthLength(year, endMonth)),
    }
  }, [year, quarter])

  const report = useAsync(() => fetchVatReport(token, from, to), [token, from, to])
  const data = report.data
  const net = Number(data?.net_vat ?? 0)

  //: فروش و خرید در یک فهرست با برچسبِ نوع — کاربر دنبالِ «کدام فاکتور» است، نه
  //: دنبالِ دو جدولِ جدا که باید بینشان چشم بچرخاند.
  const mixed = [
    ...(data?.mixed_sales_invoices ?? []).map((m) => ({ ...m, kind: 'فروش' })),
    ...(data?.mixed_purchase_invoices ?? []).map((m) => ({ ...m, kind: 'خرید' })),
  ]

  const rows = data
    ? [
        //: پیش‌تر «فروشِ مشمول» نوشته بود، ولی این جمعِ کل است نه بخشِ مشمول؛
        //: تفکیکِ مشمول/معاف در کارتِ «ترکیبِ پایه» است.
        { label: 'فروش', net: data.sales_net, vat: data.output_vat, sign: 1 },
        { label: 'برگشت از فروش', net: data.sales_returns_net, vat: data.sales_returns_vat, sign: -1 },
        { label: 'خرید', net: data.purchase_net, vat: data.input_vat, sign: -1 },
        {
          label: 'برگشت از خرید',
          net: data.purchase_returns_net,
          vat: data.purchase_returns_vat,
          sign: 1,
        },
      ]
    : []

  return (
    <OpsPage
      icon={Percent}
      title="مالیات بر ارزش افزوده"
      description="مالیاتِ فروش منهای اعتبارِ مالیاتیِ خرید در یک فصل — همان عددی که در اظهارنامه‌ی فصلی می‌رود."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              سالِ مالی
              <SearchSelect value={year} onChange={(e) => setYear(Number(e.target.value))}>
                {[now.jy + 1, now.jy, now.jy - 1, now.jy - 2].map((y) => (
                  <option key={y} value={y}>
                    {fa(y)}
                  </option>
                ))}
              </SearchSelect>
            </label>
            <label className="acc-inline-field">
              فصل
              <SearchSelect value={quarter} onChange={(e) => setQuarter(Number(e.target.value))}>
                {QUARTERS.map((q) => (
                  <option key={q.value} value={q.value}>
                    {q.label}
                  </option>
                ))}
              </SearchSelect>
            </label>
          </div>
          <div className="cc-summary">
            <Metric
              icon={<TrendingUp size={14} />}
              label="مالیاتِ فروش"
              value={data ? fa(data.output_vat) : '—'}
              tone="in"
            />
            <Metric
              icon={<TrendingDown size={14} />}
              label="اعتبارِ خرید"
              value={data ? fa(data.input_vat) : '—'}
              tone="out"
            />
            <Metric
              icon={<Percent size={14} />}
              label={net >= 0 ? 'قابلِ پرداخت' : 'قابلِ استرداد'}
              value={data ? fa(Math.abs(net)) : '—'}
              tone={net >= 0 ? 'out' : 'in'}
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Percent}
        title="ریزِ محاسبه"
        description={`${formatJalali(from)} تا ${formatJalali(to)}`}
        actions={
          <button
            type="button"
            disabled={!data}
            onClick={() =>
              data &&
              downloadCsv(
                `vat-${year}-q${quarter}`,
                ['شرح', 'مبلغ خالص', 'مالیات'],
                rows.map((r) => [r.label, Number(r.net), Number(r.vat)]),
              )
            }
          >
            <Download size={13} /> خروجی CSV
          </button>
        }
      >
        <AsyncBlock loading={report.loading} error={report.error}>
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شرح</th>
                  <th>مبلغِ خالص</th>
                  <th>مالیات</th>
                  <th>اثر</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.label}>
                    <td className="card-title" data-label="شرح">
                      {r.label}
                    </td>
                    <td data-label="مبلغِ خالص" className="num">
                      {faAmount(r.net)}
                    </td>
                    <td data-label="مالیات" className="num">
                      {faAmount(r.vat)}
                    </td>
                    <td data-label="اثر" className={r.sign > 0 ? 'pos-out' : 'pos-in'}>
                      {r.sign > 0 ? 'افزاینده‌ی بدهی' : 'کاهنده‌ی بدهی'}
                    </td>
                  </tr>
                ))}
                <tr className="acc-row--total">
                  <td className="card-title" data-label="شرح">مالیاتِ خالصِ فصل</td>
                  <td className="num" data-label="مبلغِ خالص">—</td>
                  <td className="num" data-label="مالیات">{fa(net)}</td>
                  <td data-label="اثر">{net >= 0 ? 'پرداختنی' : 'استردادی'}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>

      <SectionCard
        icon={Percent}
        title="ترکیبِ پایه"
        description="چقدر از فروش و خریدِ دوره مشمول بوده و چقدر معاف. وضعیت از لحظه‌ی معامله می‌آید، نه از وضعیتِ امروزِ کالا. برگشت‌ها در این جدول نمی‌آیند."
      >
        <AsyncBlock loading={report.loading} error={report.error}>
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>طبقه</th>
                  <th>فروش</th>
                  <th>خرید</th>
                </tr>
              </thead>
              <tbody>
                {([
                  ['کالای مشمول', 'taxable_goods'],
                  ['خدمتِ مشمول', 'taxable_services'],
                  ['کالای معاف', 'exempt_goods'],
                  ['خدمتِ معاف', 'exempt_services'],
                ] as [string, keyof VatBreakdown][]).map(([label, key]) => (
                  <tr key={key}>
                    <td className="card-title" data-label="طبقه">{label}</td>
                    <td data-label="فروش" className="num">
                      {faAmount(data?.sales_breakdown[key] ?? 0)}
                    </td>
                    <td data-label="خرید" className="num">
                      {faAmount(data?.purchase_breakdown[key] ?? 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {mixed.length > 0 && (
            <>
              <p className="fy-note fy-note--warn">
                <AlertTriangle size={14} />{' '}
                {fa(mixed.length)} فاکتور ردیفِ معاف و مشمول را با هم دارند و نرخِ سربرگشان غیرصفر
                است — یعنی روی ردیفِ معاف هم مالیات گرفته شده.
              </p>
              <div className="table-scroll">
                <table className="cards-on-mobile acc-table">
                  <thead>
                    <tr>
                      <th>فاکتور</th>
                      <th>تاریخ</th>
                      <th>خالصِ معاف</th>
                      <th>مالیاتِ فاکتور</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mixed.map((m) => (
                      <tr key={m.invoice_id}>
                        <td className="card-title" data-label="فاکتور">
                          {m.kind} {fa(m.number ?? 0)}
                        </td>
                        <td data-label="تاریخ">{formatJalali(m.invoice_date)}</td>
                        <td data-label="خالصِ معاف" className="num">{faAmount(m.exempt_net)}</td>
                        <td data-label="مالیاتِ فاکتور" className="num">{faAmount(m.tax_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════ ۴) دفاتر تجارت الکترونیک ═════════════

export function LegalBooksPage({ token }: { token: string }) {
  const range = useRange('year')
  const book = useAsync(
    () =>
      range.from && range.to
        ? fetchLegalBook(token, range.from, range.to)
        : fetchLegalBook(token, '1900-01-01', todayIso()),
    [token, range.from, range.to],
  )
  const data = book.data
  const rows = data?.rows ?? []
  const pg = usePagination(rows, 40)

  function exportCsv() {
    downloadCsv(
      `dafater-${range.from ?? 'all'}`,
      ['ردیف', 'شماره سند', 'تاریخ', 'کد حساب', 'نام حساب', 'شرح', 'بدهکار', 'بستانکار', 'وضعیت'],
      rows.map((r, i) => [
        i + 1,
        r.entry_number ?? '',
        formatJalali(r.entry_date),
        r.account_code,
        r.account_name,
        r.description,
        Number(r.debit),
        Number(r.credit),
        r.voided ? 'باطل' : r.status === 'permanent' ? 'دائم' : 'موقت',
      ]),
    )
  }

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="دفاتر تجارت الکترونیک"
      description="ردیف‌های دفترِ روزنامه با چیدمانِ دفاترِ قانونی — آماده‌ی خروجی و بارگذاری در سامانه. اسنادِ باطل و معکوسشان هر دو می‌آیند، چون دفترِ قانونی باید اصلاح را هم نشان دهد."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<FileSpreadsheet size={14} />} label="ردیفِ دفتر" value={faInt(rows.length)} />
            <Metric
              icon={<Wallet size={14} />}
              label="جمعِ بدهکار"
              value={data ? fa(data.total_debit) : '—'}
              tone="in"
            />
            <Metric
              icon={<Wallet size={14} />}
              label="جمعِ بستانکار"
              value={data ? fa(data.total_credit) : '—'}
              tone="out"
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={FileSpreadsheet}
        title="دفترِ روزنامه (قانونی)"
        description="یک ردیف به‌ازای هر ردیفِ سند، به‌ترتیبِ تاریخ و شماره."
        actions={
          <>
            <button type="button" onClick={exportCsv} disabled={rows.length === 0}>
              <Download size={13} /> خروجی CSV
            </button>
            <button type="button" onClick={() => window.print()}>
              <Printer size={13} /> چاپ
            </button>
          </>
        }
      >
        <AsyncBlock
          loading={book.loading}
          error={book.error}
          empty={rows.length === 0}
          emptyText="در این بازه ردیفی ثبت نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table acc-table--wide">
              <thead>
                <tr>
                  <th>سند</th>
                  <th>تاریخ</th>
                  <th>کدِ حساب</th>
                  <th>نامِ حساب</th>
                  <th>شرح</th>
                  <th>بدهکار</th>
                  <th>بستانکار</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r, i) => (
                  <tr key={`${r.entry_id}-${i}`} className={r.voided ? 'acc-row--void' : ''}>
                    <td className="card-title" data-label="سند">
                      {fa(r.entry_number ?? 0)}
                    </td>
                    <td data-label="تاریخ">{formatJalali(r.entry_date)}</td>
                    <td data-label="کدِ حساب" dir="ltr">
                      {r.account_code}
                    </td>
                    <td data-label="نامِ حساب">{r.account_name}</td>
                    <td data-label="شرح">{r.description || '—'}</td>
                    <td data-label="بدهکار" className="num">
                      {faAmount(r.debit)}
                    </td>
                    <td data-label="بستانکار" className="num">
                      {faAmount(r.credit)}
                    </td>
                    <td data-label="وضعیت">
                      <StatusChip status={r.status} voided={r.voided} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
          {data && (
            <BalanceFooter debit={Number(data.total_debit)} credit={Number(data.total_credit)} />
          )}
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
