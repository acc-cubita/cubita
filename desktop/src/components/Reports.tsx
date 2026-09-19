import { useEffect, useMemo, useState } from 'react'
import { BarChart3, Search, Download, CalendarRange } from 'lucide-react'
import { downloadCsv } from '../lib/csv'
import {
  fetchAging,
  fetchBalanceSheet,
  fetchBudgetReport,
  fetchCashFlow,
  fetchEquityStatement,
  fetchContacts,
  fetchContactStatement,
  costCenterKindLabel,
  fetchCostCenterReport,
  fetchInventoryReport,
  fetchItemsLive,
  fetchKardex,
  fetchIncomeStatement,
  fetchSeasonalReport,
  type AgingReport,
  type BalanceSheet,
  type BudgetReport,
  type CashFlow,
  type EquityStatement,
  type ContactRecord,
  type ContactStatement,
  type CostCenterReport,
  type InventoryReport,
  type ItemRecord,
  type KardexReport,
  type IncomeStatement,
  type SeasonalReport,
  type SeasonalSection,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { KardexSummary, KardexTable } from './KardexTable'
import { formatJalali, isoToJalali, jalaliToIso, todayIso, toFaDigits, JALALI_MONTH_NAMES } from '../lib/jalali'
import { SearchSelect } from '../components/SearchSelect'

const ENTITY_LABEL: Record<string, string> = { real: 'حقیقی', legal: 'حقوقی', aggregate: 'تجمیعی' }

/**
 * برچسبِ هر کمبودِ هویتِ مالیاتی. سرور کدِ ماشین‌خوان می‌دهد و فارسی‌اش این‌جاست
 * — همان جایی که `ENTITY_LABEL` هم هست.
 *
 * متنِ هر برچسب می‌گوید **دقیقاً چه چیزی** کم است، نه «ناقص»؛ حسابدار باید
 * از روی همین بداند در صفحه‌ی «اشخاص» سراغِ کدام فیلد برود.
 */
const ISSUE_LABEL: Record<string, string> = {
  national_id_missing: 'کد/شناسه ملی',
  national_id_length: 'طولِ کد ملی',
  economic_code_missing: 'کد اقتصادی',
  postal_code_missing: 'کد پستی',
}

const issueText = (codes: string[]) => codes.map((c) => ISSUE_LABEL[c] ?? c).join('، ')
const QUARTER_OPTIONS = [
  { value: 0, label: 'کل سال' },
  { value: 1, label: 'بهار' },
  { value: 2, label: 'تابستان' },
  { value: 3, label: 'پاییز' },
  { value: 4, label: 'زمستان' },
]

type ReportKind =
  | 'income-statement'
  | 'balance-sheet'
  | 'budget'
  | 'cash-flow'
  | 'equity-statement'
  | 'cost-center'
  | 'receivable-aging'
  | 'payable-aging'
  | 'contact-statement'
  | 'inventory'
  | 'kardex'
  | 'seasonal'

type PeriodPreset = 'all' | 'month' | 'quarter' | 'year' | 'custom'

// گزارش‌هایی که «به تاریخِ مشخص» هستند (نه بازه‌ای) — بازه‌ی تاریخ برایشان بی‌معناست و
// فقط تاریخِ پایان (as_of) اهمیت دارد. «ارزش موجودی انبار» از این فهرست بیرون آمد:
// حالا مانده‌ی اول، ورود و خروجِ بازه را هم دارد.
const POINT_IN_TIME: ReportKind[] = ['balance-sheet', 'receivable-aging', 'payable-aging']

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

// آخرین روزِ یک ماهِ شمسی به ISO: اولِ ماهِ بعد منهای یک روز
function jMonthEndIso(jy: number, jm: number): string {
  const ny = jm === 12 ? jy + 1 : jy
  const nm = jm === 12 ? 1 : jm + 1
  const firstNext = jalaliToIso(ny, nm, 1)
  const d = new Date(firstNext + 'T00:00:00')
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

const Q_LABELS = ['بهار', 'تابستان', 'پاییز', 'زمستان']

function resolvePeriod(preset: PeriodPreset, customFrom: string, customTo: string): { from?: string; to?: string; label: string } {
  const t = isoToJalali(todayIso())
  switch (preset) {
    case 'month':
      return { from: jalaliToIso(t.jy, t.jm, 1), to: jMonthEndIso(t.jy, t.jm), label: `${JALALI_MONTH_NAMES[t.jm - 1]} ${toFaDigits(t.jy)}` }
    case 'quarter': {
      const q = Math.floor((t.jm - 1) / 3)
      const sm = q * 3 + 1
      return { from: jalaliToIso(t.jy, sm, 1), to: jMonthEndIso(t.jy, sm + 2), label: `${Q_LABELS[q]} ${toFaDigits(t.jy)}` }
    }
    case 'year':
      return { from: jalaliToIso(t.jy, 1, 1), to: jMonthEndIso(t.jy, 12), label: `سال ${toFaDigits(t.jy)}` }
    case 'custom':
      return { from: customFrom, to: customTo, label: `${formatJalali(customFrom)} تا ${formatJalali(customTo)}` }
    case 'all':
    default:
      return { label: 'از ابتدا تا امروز' }
  }
}

export function Reports({ token }: { token: string }) {
  const [active, setActive] = useState<ReportKind>('income-statement')
  const [preset, setPreset] = useState<PeriodPreset>('all')
  const [customFrom, setCustomFrom] = useState(todayIso())
  const [customTo, setCustomTo] = useState(todayIso())
  const [incomeStatement, setIncomeStatement] = useState<IncomeStatement | null>(null)
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheet | null>(null)
  const [budgetReport, setBudgetReport] = useState<BudgetReport | null>(null)
  const [cashFlow, setCashFlow] = useState<CashFlow | null>(null)
  const [costCenterReport, setCostCenterReport] = useState<CostCenterReport | null>(null)
  const [aging, setAging] = useState<AgingReport | null>(null)
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [statementContactId, setStatementContactId] = useState('')
  const [contactStatement, setContactStatement] = useState<ContactStatement | null>(null)
  const [inventory, setInventory] = useState<InventoryReport | null>(null)
  const [items, setItems] = useState<ItemRecord[]>([])
  const [kardexItemId, setKardexItemId] = useState('')
  const [kardex, setKardex] = useState<KardexReport | null>(null)
  const [seasonalYear, setSeasonalYear] = useState(() => isoToJalali(todayIso()).jy)
  const [seasonalQuarter, setSeasonalQuarter] = useState(0)
  const [seasonal, setSeasonal] = useState<SeasonalReport | null>(null)
  const [equity, setEquity] = useState<EquityStatement | null>(null)
  const [loading, setLoading] = useState(false)
  //: فیلترِ «فقط ناقص‌ها» سمتِ مرورگر است و این‌جا درست است: گزارشِ فصلی
  //: تجمیعِ محدود به تعدادِ طرف‌حساب است نه کلِ دفتر، و از قبل یک‌جا آمده؛
  //: درخواستِ دوم فقط همان داده را دوباره می‌کشد.
  const [onlyIncomplete, setOnlyIncomplete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const period = useMemo(() => resolvePeriod(preset, customFrom, customTo), [preset, customFrom, customTo])

  // داده‌ی گزارشِ فعال را با بازه‌ی تاریخِ جاری می‌گیرد. گزارش‌های نیازمندِ انتخاب
  // (دفتر کل/کاردکس/صورت‌حساب) فقط وقتی شناسه انتخاب شده باشد بارگذاری می‌شوند.
  async function loadData() {
    setError(null)
    const { from, to } = period
    const asOf = to // برای گزارش‌های «به تاریخِ مشخص» = پایانِ بازه (خالی = امروز)
    setLoading(true)
    try {
      switch (active) {
        case 'income-statement': setIncomeStatement(await fetchIncomeStatement(token, from, to)); break
        case 'balance-sheet': setBalanceSheet(await fetchBalanceSheet(token, asOf)); break
        case 'budget': setBudgetReport(await fetchBudgetReport(token, from, to)); break
        case 'cash-flow': setCashFlow(await fetchCashFlow(token, from, to)); break
        case 'equity-statement': setEquity(await fetchEquityStatement(token, asOf || todayIso(), from)); break
        case 'cost-center': setCostCenterReport(await fetchCostCenterReport(token, from, to)); break
        case 'receivable-aging': setAging(await fetchAging(token, 'receivable', asOf)); break
        case 'payable-aging': setAging(await fetchAging(token, 'payable', asOf)); break
        case 'inventory': setInventory(await fetchInventoryReport(token, to, from)); break
        case 'kardex': if (kardexItemId) setKardex(await fetchKardex(token, kardexItemId, from, to)); break
        case 'contact-statement': if (statementContactId) setContactStatement(await fetchContactStatement(token, statementContactId, from, to)); break
        case 'seasonal': break // فصلی سال/فصلِ خودش را دارد
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  // بارگذاریِ خودکار وقتی گزارشِ فعال یا بازه‌ی تاریخ عوض شود
  useEffect(() => {
    void loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, period.from, period.to])

  async function selectTab(kind: ReportKind) {
    setActive(kind)
    setError(null)
    // فهرست‌های موردنیازِ گزارش‌های انتخابی را زنده می‌گیریم
    try {
      if (kind === 'contact-statement' && contacts.length === 0) setContacts(await fetchContacts(token))
      if (kind === 'kardex' && items.length === 0) setItems((await fetchItemsLive(token)).filter((i) => !i.is_service))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function loadSeasonal() {
    setLoading(true)
    setError(null)
    try {
      setSeasonal(await fetchSeasonalReport(token, seasonalYear, seasonalQuarter))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  // داده‌ی گزارشِ فعال را به سرستون + ردیف‌ها نگاشت می‌کند تا همان چیزی که روی صفحه
  // است در اکسل هم بیاید. null یعنی این گزارش هنوز داده‌ای برای خروجی ندارد.
  function buildExport(): { name: string; headers: string[]; rows: (string | number)[][] } | null {
    switch (active) {
      case 'income-statement':
        return incomeStatement && {
          name: 'سود-و-زیان',
          headers: ['نوع', 'حساب', 'مبلغ'],
          rows: [
            ...incomeStatement.income.map((r) => ['درآمد', r.account_name, r.balance] as (string | number)[]),
            ...incomeStatement.expenses.map((r) => ['هزینه', r.account_name, r.balance] as (string | number)[]),
            ['', 'سود/زیان خالص', incomeStatement.net_profit],
          ],
        }
      case 'balance-sheet':
        return balanceSheet && {
          name: 'ترازنامه',
          headers: ['بخش', 'حساب', 'مانده'],
          rows: [
            ...balanceSheet.assets.map((r) => ['دارایی', r.account_name, r.balance] as (string | number)[]),
            ...balanceSheet.liabilities.map((r) => ['بدهی', r.account_name, r.balance] as (string | number)[]),
            ...balanceSheet.equity.map((r) => ['حقوق صاحبان سرمایه', r.account_name, r.balance] as (string | number)[]),
            ['حقوق صاحبان سرمایه', 'سود/زیان دوره جاری', balanceSheet.current_period_profit],
          ],
        }
      case 'budget':
        return budgetReport && {
          name: 'بودجه-در-برابر-عملکرد',
          headers: ['کد', 'حساب', 'بودجه', 'عملکرد', 'انحراف', 'درصد', 'وضعیت'],
          rows: budgetReport.rows.map((r) => [r.account_code, r.account_name, r.budget, r.actual, r.variance, r.variance_pct ?? '', r.favorable ? 'مطلوب' : 'نامطلوب']),
        }
      case 'equity-statement':
        return equity && {
          name: 'تغییرات-حقوق-صاحبان-سهام',
          headers: ['ردیف', 'مبلغ'],
          rows: [
            ['ماندهٔ اول دوره', equity.opening_equity],
            ['آورده‌ی سرمایه', equity.contributions],
            ['کاهشِ سرمایه', equity.withdrawals],
            ['سایر تغییرات', equity.other_changes],
            ['ماندهٔ پایان دوره', equity.closing_equity],
            ['سود/زیانِ دوره (هنوز منتقل نشده)', equity.net_profit],
          ] as (string | number)[][],
        }
      case 'cash-flow':
        return cashFlow && {
          name: 'جریان-وجوه-نقد',
          headers: ['فعالیت', 'حساب', 'مبلغ'],
          rows: [
            ['', 'مانده ابتدای دوره', cashFlow.opening_cash],
            ...cashFlow.operating.map((l) => ['عملیاتی', `${l.account_code} — ${l.account_name}`, l.amount] as (string | number)[]),
            ...cashFlow.investing.map((l) => ['سرمایه‌گذاری', `${l.account_code} — ${l.account_name}`, l.amount] as (string | number)[]),
            ...cashFlow.financing.map((l) => ['تأمین مالی', `${l.account_code} — ${l.account_name}`, l.amount] as (string | number)[]),
            ['', 'تغییر خالص نقد', cashFlow.net_change],
            ['', 'مانده پایان دوره', cashFlow.closing_cash],
          ],
        }
      case 'cost-center':
        return costCenterReport && {
          name: 'سود-مرکز-هزینه',
          headers: ['کد', 'مرکز/پروژه', 'نوع', 'درآمد', 'هزینه', 'سود مستقیم', 'سود با زیرمجموعه', 'انحراف از بودجه'],
          rows: costCenterReport.rows.map((r) => [r.cost_center_code, r.path || r.cost_center_name, costCenterKindLabel(r.kind), r.income, r.expense, r.profit, r.rollup_profit, r.profit_variance ?? '']),
        }
      case 'receivable-aging':
      case 'payable-aging':
        return aging && {
          name: aging.kind === 'receivable' ? 'سنی-مطالبات' : 'سنی-بدهی‌ها',
          headers: [aging.kind === 'receivable' ? 'مشتری' : 'تأمین‌کننده', 'جاری (۰-۳۰)', '۳۱-۶۰', '۶۱-۹۰', 'بالای ۹۰', 'جمع'],
          rows: aging.rows.map((r) => [r.contact_name, r.current, r.d31_60, r.d61_90, r.over_90, r.total]),
        }
      case 'contact-statement':
        return contactStatement && {
          name: `صورت‌حساب-${contactStatement.contact_name}`,
          headers: ['تاریخ', 'شرح', 'شماره', 'بدهکار', 'بستانکار', 'مانده'],
          rows: [
            ['', 'مانده ابتدای دوره', '', '', '', contactStatement.opening_balance],
            ...contactStatement.lines.map((l) => [formatJalali(l.txn_date), l.description, l.number ?? '', l.debit, l.credit, l.balance] as (string | number)[]),
          ],
        }
      case 'inventory':
        return inventory && {
          name: 'ارزش-موجودی-انبار',
          headers: ['کد', 'کالا', 'واحد', 'اول دوره', 'ارزش اول دوره', 'ورود', 'ارزش ورود', 'خروج', 'ارزش خروج', 'موجودی', 'بهای میانگین', 'ارزش', 'منقضی از'],
          rows: inventory.rows.map((r) => [
            r.sku, r.name, r.unit, r.opening_qty, r.opening_value, r.in_qty, r.in_value,
            r.out_qty, r.out_value, r.qty_on_hand, r.unit_cost, r.stock_value,
            r.stale_from ? formatJalali(r.stale_from) : '',
          ]),
        }
      case 'kardex':
        return kardex && {
          name: `کاردکس-${kardex.item_sku}`,
          headers: ['تاریخ', 'شرح', 'شماره', 'ورود', 'خروج', 'بهای واحد', 'بهای سند', 'مبلغ ورود', 'مبلغ خروج', 'موجودی', 'ارزش مانده', 'میانگین'],
          rows: [
            ['', 'موجودی ابتدای دوره', '', '', '', '', '', '', '', kardex.opening_qty, kardex.opening_value, ''],
            ...kardex.lines.map((l) => [
              formatJalali(l.entry_date), l.source_label, l.source_number ?? '', l.qty_in, l.qty_out,
              l.unit_cost, l.recorded_unit_cost, l.value_in, l.value_out, l.balance_qty, l.balance_value, l.average_cost,
            ] as (string | number)[]),
          ],
        }
      case 'seasonal':
        return seasonal && {
          name: `معاملات-فصلی-${seasonal.year}-${seasonal.quarter_label}`,
          headers: ['نوع معامله', 'طرف حساب', 'شخص', 'کد/شناسه ملی', 'کد اقتصادی', 'کد پستی', 'تعداد فاکتور', 'ناخالص', 'تخفیف', 'خالص', 'مالیات و عوارض', 'مبلغ کل', 'کمبودها'],
          rows: [
            ...seasonal.sales.rows.map((r) => ['فروش', r.contact_name, ENTITY_LABEL[r.entity_type], r.national_id ?? '', r.economic_code ?? '', r.postal_code ?? '', r.invoice_count, r.gross, r.discount, r.net, r.vat, r.total, issueText(r.issues)] as (string | number)[]),
            ...seasonal.purchases.rows.map((r) => ['خرید', r.contact_name, ENTITY_LABEL[r.entity_type], r.national_id ?? '', r.economic_code ?? '', r.postal_code ?? '', r.invoice_count, r.gross, r.discount, r.net, r.vat, r.total, issueText(r.issues)] as (string | number)[]),
          ],
        }
      default:
        return null
    }
  }

  function handleExport() {
    const data = buildExport()
    if (data) downloadCsv(data.name, data.headers, data.rows)
  }

  //: «تراز آزمایشی»، «دفتر کل» و «مالیات بر ارزش افزوده» از این‌جا برداشته شدند و
  //: به ماژولِ حسابداری رفتند («گزارش ترازها»، «گزارش دفتر»، «مالیات بر ارزش
  //: افزوده») — همان‌جا ستون‌های ۲/۴/۶/۸، سطحِ کل/معین/تفصیلی، دفترِ روزنامه و
  //: انتخابِ فصل را هم دارند. ماندنشان این‌جا یعنی دو نسخه با دو رفتار.
  const tabs: { key: ReportKind; label: string }[] = [
    { key: 'income-statement', label: 'سود و زیان' },
    { key: 'balance-sheet', label: 'ترازنامه' },
    { key: 'budget', label: 'بودجه در برابر عملکرد' },
    { key: 'cash-flow', label: 'جریان وجوه نقد' },
    { key: 'equity-statement', label: 'تغییرات حقوق صاحبان سهام' },
    { key: 'cost-center', label: 'سود پروژه/مرکز هزینه' },
    { key: 'receivable-aging', label: 'سنی مطالبات' },
    { key: 'payable-aging', label: 'سنی بدهی‌ها' },
    { key: 'contact-statement', label: 'صورت‌حساب اشخاص' },
    { key: 'inventory', label: 'ارزش موجودی انبار' },
    { key: 'kardex', label: 'کاردکس کالا' },
    { key: 'seasonal', label: 'معاملات فصلی (م۱۶۹)' },
  ]

  const presets: { key: PeriodPreset; label: string }[] = [
    { key: 'all', label: 'از ابتدا' },
    { key: 'month', label: 'این ماه' },
    { key: 'quarter', label: 'این فصل' },
    { key: 'year', label: 'امسال' },
    { key: 'custom', label: 'بازه‌ی دلخواه' },
  ]

  const isPoint = POINT_IN_TIME.includes(active)
  const periodCaption = active === 'seasonal'
    ? null
    : isPoint
      ? `به تاریخِ ${period.to ? formatJalali(period.to) : 'امروز'}`
      : `دوره: ${period.label}`

  return (
    <SectionCard icon={BarChart3} title="گزارش‌های حسابداری">
      <p className="hint">این گزارش‌ها همیشه مستقیم و زنده از سرور خوانده می‌شوند (نیاز به اتصال اینترنت دارند).</p>
      <p className="hint">
        تراز آزمایشی، دفتر کل و مالیات بر ارزش افزوده به ماژولِ «حسابداری» منتقل شده‌اند —
        به‌ترتیب «گزارش ترازها»، «گزارش دفتر» و «مالیات بر ارزش افزوده».
      </p>
      <div className="report-tabs">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={active === t.key ? 'btn-primary' : ''}
            onClick={() => void selectTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {active !== 'seasonal' && (
        <div className="report-period">
          <span className="report-period-icon"><CalendarRange size={15} /> بازه‌ی زمانی</span>
          <div className="report-period-presets">
            {presets.map((p) => (
              <button
                key={p.key}
                type="button"
                className={preset === p.key ? 'chip-active' : ''}
                onClick={() => setPreset(p.key)}
              >
                {p.label}
              </button>
            ))}
          </div>
          {preset === 'custom' && (
            <div className="report-period-custom">
              <label>از<JalaliDatePicker value={customFrom} onChange={setCustomFrom} /></label>
              <label>تا<JalaliDatePicker value={customTo} onChange={setCustomTo} /></label>
            </div>
          )}
          {periodCaption && <span className="report-period-caption">{periodCaption}{isPoint && preset !== 'all' ? ' · بازه بی‌اثر است (گزارشِ لحظه‌ای)' : ''}</span>}
        </div>
      )}

      {loading && <p className="hint">در حال بارگذاری...</p>}
      {error && <div className="error">{error}</div>}

      {buildExport() && (
        <div className="report-export">
          <button type="button" onClick={handleExport}>
            <Download size={13} /> دانلود اکسل (CSV)
          </button>
        </div>
      )}

      {active === 'kardex' && (
        <div className="check-actions">
          <SearchSelect value={kardexItemId} onChange={(e) => setKardexItemId(e.target.value)}>
            <option value="">— انتخاب کالا —</option>
            {items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.sku} — {i.name}
              </option>
            ))}
          </SearchSelect>
          <button type="button" onClick={() => void loadData()}>
            <Search size={13} /> نمایش
          </button>
        </div>
      )}

      {active === 'kardex' && kardex && (
        <div>
          <h3>
            {kardex.item_sku} — {kardex.item_name} ({kardex.unit})
          </h3>
          <KardexSummary data={kardex} />
          <KardexTable data={kardex} className="rep-kardex-table" />
        </div>
      )}

      {active === 'seasonal' && (
        <div className="check-actions">
          <NumberInput
            group={false}
            value={seasonalYear}
            onChange={(v) => setSeasonalYear(Number(v) || seasonalYear)}
            placeholder="سال شمسی"
            style={{ width: 110 }}
          />
          <SearchSelect value={seasonalQuarter} onChange={(e) => setSeasonalQuarter(Number(e.target.value))}>
            {QUARTER_OPTIONS.map((q) => (
              <option key={q.value} value={q.value}>{q.label}</option>
            ))}
          </SearchSelect>
          <button type="button" onClick={() => void loadSeasonal()}>
            <Search size={13} /> نمایش
          </button>
        </div>
      )}

      {active === 'seasonal' && seasonal && (
        <div>
          <h3>
            معاملات {seasonal.quarter_label} سال {fa(seasonal.year)} — {formatJalali(seasonal.date_from)} تا {formatJalali(seasonal.date_to)}
          </h3>
          <p className="hint">
            تجمیعِ خرید و فروش به تفکیکِ طرف حساب، برای سامانه‌ی معاملاتِ فصلیِ سازمانِ امور مالیاتی (ماده ۱۶۹ ق.م.م).
            هویتِ مالیاتیِ هر طرف حساب (کد/شناسه‌ی ملی و کد اقتصادی) در صفحه‌ی «اشخاص» وارد می‌شود.
          </p>
          <label className="rep-only-incomplete">
            <input
              type="checkbox"
              checked={onlyIncomplete}
              onChange={(e) => setOnlyIncomplete(e.target.checked)}
            />
            فقط ناقص‌ها
          </label>
          {([['فروش', seasonal.sales], ['خرید', seasonal.purchases]] as [string, SeasonalSection][]).map(([title, section]) => {
            const visible = onlyIncomplete
              ? section.rows.filter((r) => r.issues.length > 0)
              : section.rows
            return (
            <div key={title} style={{ marginTop: 16 }}>
              <h4>{title}</h4>
              <p className="hint">
                {fa(section.ready_count)} آماده
                {section.incomplete_count > 0 && (
                  <>
                    {' · '}
                    <strong className="rep-incomplete">{fa(section.incomplete_count)} ناقص</strong>
                    {' — هویتِ مالیاتیِ این ردیف‌ها کامل نیست و سامانه ردشان می‌کند.'}
                  </>
                )}
              </p>
              {visible.length === 0 ? (
                <p className="hint">
                  {onlyIncomplete
                    ? 'همه‌ی ردیف‌های این بخش آماده‌اند.'
                    : 'در این فصل معامله‌ای ثبت نشده.'}
                </p>
              ) : (
                <div className="entity-table-wrap">
                  <div className="table-scroll">
                    <table className="entity-table rep-seasonal-table cards-on-mobile">
                      <thead>
                        <tr>
                          <th>طرف حساب</th>
                          <th>شخص</th>
                          <th>کد/شناسه ملی</th>
                          <th>کد اقتصادی</th>
                          <th>تعداد</th>
                          <th>خالص</th>
                          <th>مالیات و عوارض</th>
                          <th>مبلغ کل</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visible.map((r, i) => (
                          <tr key={r.contact_id ?? `agg-${i}`}>
                            <td className="entity-name" data-label="طرف حساب">
                              {r.contact_name}
                              {r.issues.length > 0 && (
                                <span className="field-hint field-hint--warn">
                                  ناقص: {issueText(r.issues)}
                                </span>
                              )}
                            </td>
                            <td data-label="شخص">{ENTITY_LABEL[r.entity_type]}</td>
                            <td data-label="کد/شناسه ملی">{r.national_id ?? '—'}</td>
                            <td data-label="کد اقتصادی">{r.economic_code ?? '—'}</td>
                            <td data-label="تعداد">{fa(r.invoice_count)}</td>
                            <td data-label="خالص" className="money-cell">{fa(r.net)}</td>
                            <td data-label="مالیات و عوارض" className="money-cell">{fa(r.vat)}</td>
                            <td data-label="مبلغ کل" className="money-cell">{fa(r.total)}</td>
                          </tr>
                        ))}
                        <tr className="rep-foot">
                          <td className="entity-name" data-label="طرف حساب">جمع {title}</td>
                          <td data-label="شخص"></td>
                          <td data-label="کد/شناسه ملی"></td>
                          <td data-label="کد اقتصادی"></td>
                          <td data-label="تعداد"></td>
                          <td data-label="خالص" className="invoice-total">{fa(section.total_net)}</td>
                          <td data-label="مالیات و عوارض" className="invoice-total">{fa(section.total_vat)}</td>
                          <td data-label="مبلغ کل" className="invoice-total">{fa(section.total_total)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
            )
          })}
        </div>
      )}

      {active === 'contact-statement' && (
        <div className="check-actions">
          <SearchSelect value={statementContactId} onChange={(e) => setStatementContactId(e.target.value)}>
            <option value="">— انتخاب طرف‌حساب —</option>
            {contacts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </SearchSelect>
          <button type="button" onClick={() => void loadData()}>
            <Search size={13} /> نمایش
          </button>
        </div>
      )}

      {active === 'contact-statement' && contactStatement && (
        <div>
          <h3>{contactStatement.contact_name}</h3>
          <div className="report-kpis">
            <div className="report-kpi"><span>مانده ابتدای دوره</span><strong>{fa(contactStatement.opening_balance)}</strong></div>
            <div className="report-kpi"><span>جمع بدهکار</span><strong>{fa(contactStatement.total_debit)}</strong></div>
            <div className="report-kpi"><span>جمع بستانکار</span><strong>{fa(contactStatement.total_credit)}</strong></div>
            <div className={`report-kpi ${Number(contactStatement.closing_balance) >= 0 ? 'tone-warn' : 'tone-ok'}`}>
              <span>{Number(contactStatement.closing_balance) >= 0 ? 'مانده پایان (بدهکار به ما)' : 'مانده پایان (طلبکار از ما)'}</span>
              <strong>{fa(Math.abs(Number(contactStatement.closing_balance)))}</strong>
            </div>
          </div>
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table rep-stmt-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>تاریخ</th>
                    <th>شرح</th>
                    <th>شماره</th>
                    <th>بدهکار</th>
                    <th>بستانکار</th>
                    <th>مانده</th>
                  </tr>
                </thead>
                <tbody>
                  {contactStatement.lines.map((l, i) => (
                    <tr key={i}>
                      <td data-label="تاریخ">{formatJalali(l.txn_date)}</td>
                      <td className="entity-name" data-label="شرح">{l.description}</td>
                      <td data-label="شماره">{l.number != null ? fa(l.number) : '—'}</td>
                      <td data-label="بدهکار" className="money-cell">{Number(l.debit) ? fa(l.debit) : '—'}</td>
                      <td data-label="بستانکار" className="money-cell">{Number(l.credit) ? fa(l.credit) : '—'}</td>
                      <td data-label="مانده" className="money-cell"><strong>{fa(l.balance)}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {active === 'budget' && budgetReport && (
        <div>
          <p className="hint">
            مبلغِ برنامه‌ریزی‌شده در برابر عملکردِ واقعی، فقط برای حساب‌هایی که بودجه دارند. «مطلوب» یعنی درآمدِ بیشتر
            یا هزینه‌ی کمتر از برنامه.
          </p>
          {budgetReport.rows.length === 0 ? (
            <p className="hint">هنوز بودجه‌ای تعریف نشده. از «حسابداری ← بودجه‌بندی» بودجه اضافه کنید.</p>
          ) : (
            <div className="entity-table-wrap">
              <div className="table-scroll">
                <table className="entity-table rep-budget-table cards-on-mobile">
                  <thead>
                    <tr>
                      <th>کد</th>
                      <th>نام حساب</th>
                      <th>بودجه</th>
                      <th>عملکرد</th>
                      <th>انحراف</th>
                      <th>درصد</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {budgetReport.rows.map((r) => (
                      <tr key={r.account_id}>
                        <td data-label="کد">{r.account_code}</td>
                        <td className="entity-name" data-label="نام حساب">{r.account_name}</td>
                        <td data-label="بودجه" className="money-cell">{fa(r.budget)}</td>
                        <td data-label="عملکرد" className="money-cell">{fa(r.actual)}</td>
                        <td data-label="انحراف" className="money-cell">{fa(r.variance)}</td>
                        <td data-label="درصد">{r.variance_pct != null ? `${fa(r.variance_pct)}٪` : '—'}</td>
                        <td data-label="وضعیت">
                          <span className={`status-badge ${r.favorable ? 'tone-success' : 'tone-danger'}`}>
                            {r.favorable ? 'مطلوب' : 'نامطلوب'}
                          </span>
                        </td>
                      </tr>
                    ))}
                    <tr className="rep-foot">
                      <td className="entity-name" data-label="کد">جمع</td>
                      <td data-label="کد"></td>
                      <td data-label="بودجه" className="invoice-total">{fa(budgetReport.total_budget)}</td>
                      <td data-label="عملکرد" className="invoice-total">{fa(budgetReport.total_actual)}</td>
                      <td data-label="انحراف" className="invoice-total">{fa(budgetReport.total_variance)}</td>
                      <td data-label="درصد"></td>
                      <td data-label="وضعیت"></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {active === 'equity-statement' && equity && (
        <div>
          <p className="hint">
            تغییرِ سرمایه‌ی مالکان در دوره. <strong>سود/زیانِ دوره بیرونِ این تساوی است</strong> — تا سندِ اختتامیه
            زده نشود، در هیچ حسابِ حقوق صاحبان سهامی ننشسته.
          </p>
          <div className="report-kpis">
            <div className="report-kpi"><span>ماندهٔ اول دوره</span><strong>{fa(equity.opening_equity)}</strong></div>
            <div className="report-kpi tone-ok"><span>آورده‌ی سرمایه</span><strong>{fa(equity.contributions)}</strong></div>
            <div className="report-kpi tone-warn"><span>کاهشِ سرمایه</span><strong>{fa(equity.withdrawals)}</strong></div>
            <div className="report-kpi"><span>ماندهٔ پایان دوره</span><strong>{fa(equity.closing_equity)}</strong></div>
          </div>

          <h3>گردشِ دوره</h3>
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table rep-2col-table cards-on-mobile">
                <tbody>
                  <tr><td className="card-title">ماندهٔ اول دوره</td><td className="money-cell" data-label="مبلغ">{fa(equity.opening_equity)}</td></tr>
                  <tr><td className="card-title">آورده‌ی سرمایه</td><td className="money-cell pos-in" data-label="مبلغ">{fa(equity.contributions)}</td></tr>
                  <tr><td className="card-title">کاهشِ سرمایه</td><td className="money-cell pos-out" data-label="مبلغ">{fa(equity.withdrawals)}</td></tr>
                  <tr>
                    <td className="card-title">
                      سایر تغییرات
                      <span className="field-hint">اسنادی که تراکنشِ شریکِ نظیر ندارند: سندِ دستی، اختتامیه، افتتاحیه.</span>
                    </td>
                    <td className="money-cell" data-label="مبلغ">{fa(equity.other_changes)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <p className="invoice-total">ماندهٔ پایان دوره: {fa(equity.closing_equity)}</p>
          <p className="hint">سود/زیانِ دوره (هنوز به حقوق صاحبان سهام منتقل نشده): {fa(equity.net_profit)}</p>

          <h3>اجزای حقوق صاحبان سهام</h3>
          {equity.components.length === 0 ? (
            <p className="hint">هیچ حسابِ حقوق صاحبان سهامی در این بازه حرکتی نداشت.</p>
          ) : (
            <div className="entity-table-wrap">
              <div className="table-scroll">
                <table className="entity-table cards-on-mobile">
                  <thead>
                    <tr><th>حساب</th><th>اول دوره</th><th>تغییر</th><th>پایان دوره</th></tr>
                  </thead>
                  <tbody>
                    {equity.components.map((c) => (
                      <tr key={c.account_id}>
                        <td className="card-title">{c.account_code} — {c.account_name}</td>
                        <td className="money-cell" data-label="اول دوره">{fa(c.opening)}</td>
                        <td className="money-cell" data-label="تغییر">{fa(c.change)}</td>
                        <td className="money-cell" data-label="پایان دوره">{fa(c.closing)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <h3>به تفکیکِ شریک</h3>
          {equity.partner_rows.length === 0 ? (
            <p className="hint">
              آورده یا برداشتی از مسیرِ «تراکنش شریک» ثبت نشده. آورده‌ای که با سندِ دستی ثبت شده در جمع‌های بالا
              هست ولی نامِ شریکش در دفتر نیامده، پس این‌جا دیده نمی‌شود.
            </p>
          ) : (
            <div className="entity-table-wrap">
              <div className="table-scroll">
                <table className="entity-table cards-on-mobile">
                  <thead>
                    <tr><th>شریک</th><th>آورده</th><th>برداشت</th></tr>
                  </thead>
                  <tbody>
                    {equity.partner_rows.map((r) => (
                      <tr key={r.contact_id}>
                        <td className="card-title">{r.contact_name}</td>
                        <td className="money-cell pos-in" data-label="آورده">{fa(r.contributed)}</td>
                        <td className="money-cell pos-out" data-label="برداشت">{fa(r.withdrawn)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {!equity.reconciled && (
            <p className="error">
              تساویِ «اول دوره + تغییرات = پایان دوره» برقرار نیست. این گزارش را مبنا نگیرید و گزارش کنید.
            </p>
          )}
        </div>
      )}

      {active === 'cash-flow' && cashFlow && (() => {
        const groups = [
          { title: 'فعالیت‌های عملیاتی', lines: cashFlow.operating, total: cashFlow.net_operating },
          { title: 'فعالیت‌های سرمایه‌گذاری', lines: cashFlow.investing, total: cashFlow.net_investing },
          { title: 'فعالیت‌های تأمین مالی', lines: cashFlow.financing, total: cashFlow.net_financing },
        ]
        return (
          <div>
            <p className="hint">
              ورود (+) و خروج (−) نقد در دوره‌ی انتخاب‌شده، به تفکیک سه فعالیت. جمعِ سه فعالیت با تغییرِ ماندهٔ نقد
              برابر است.
            </p>
            <div className="report-kpis">
              <div className="report-kpi"><span>ماندهٔ نقد ابتدای دوره</span><strong>{fa(cashFlow.opening_cash)}</strong></div>
              <div className={`report-kpi ${Number(cashFlow.net_change) >= 0 ? 'tone-ok' : 'tone-warn'}`}><span>تغییر خالص نقد</span><strong>{fa(cashFlow.net_change)}</strong></div>
              <div className="report-kpi"><span>ماندهٔ نقد پایان دوره</span><strong>{fa(cashFlow.closing_cash)}</strong></div>
            </div>
            {groups.map((g) => (
              <div key={g.title}>
                <h3>{g.title}</h3>
                {g.lines.length === 0 ? (
                  <p className="hint">موردی در این فعالیت نبود.</p>
                ) : (
                  <div className="entity-table-wrap">
                    <div className="table-scroll">
                      <table className="entity-table rep-2col-table cards-on-mobile">
                        <tbody>
                          {g.lines.map((l) => (
                            <tr key={l.account_id}>
                              <td className="card-title">{l.account_code} — {l.account_name}</td>
                              <td className={`money-cell ${Number(l.amount) >= 0 ? 'pos-in' : 'pos-out'}`} data-label="مبلغ">{fa(l.amount)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                <p className="invoice-total">جمع {g.title}: {fa(g.total)}</p>
              </div>
            ))}
          </div>
        )
      })()}

      {active === 'cost-center' && costCenterReport && (
        <div>
          <p className="hint">
            سود و زیانِ هر مرکز هزینه/پروژه از سندهای برچسب‌خورده. «مستقیم» فقط سندهای خودِ مرکز است و «تجمیعی»
            زیرمجموعه‌ها را هم می‌گیرد. سطرِ «بدون مرکز هزینه» یعنی فعالیتی که به هیچ مرکزی نسبت داده نشده — الان
            {' '}
            <strong>{toFaDigits(costCenterReport.untagged_share_pct)}٪</strong> از کلِ گردش.
          </p>
          {costCenterReport.rows.length === 0 ? (
            <p className="hint">هنوز هیچ سندی به مرکز هزینه‌ای برچسب نخورده. از «شرکت ← مرکز هزینه» شروع کنید.</p>
          ) : (
            <div className="entity-table-wrap">
              <div className="table-scroll">
                <table className="entity-table rep-cc-table cards-on-mobile">
                  <thead>
                    <tr>
                      <th>کد</th>
                      <th>مرکز / پروژه</th>
                      <th>درآمد</th>
                      <th>هزینه</th>
                      <th>سود مستقیم</th>
                      <th>با زیرمجموعه</th>
                      <th>انحراف از بودجه</th>
                    </tr>
                  </thead>
                  <tbody>
                    {costCenterReport.rows.map((r) => (
                      <tr key={r.cost_center_id ?? 'none'}>
                        <td data-label="کد">{r.cost_center_code || '—'}</td>
                        <td className="entity-name" data-label="مرکز / پروژه">
                          <span style={{ paddingInlineStart: r.depth * 14 }}>{r.cost_center_name}</span>
                        </td>
                        <td data-label="درآمد" className="money-cell">{fa(r.income)}</td>
                        <td data-label="هزینه" className="money-cell">{fa(r.expense)}</td>
                        <td data-label="سود مستقیم" className={`money-cell ${Number(r.profit) >= 0 ? 'pos-in' : 'pos-out'}`}>{fa(r.profit)}</td>
                        <td data-label="با زیرمجموعه" className={`money-cell ${Number(r.rollup_profit) >= 0 ? 'pos-in' : 'pos-out'}`}><strong>{fa(r.rollup_profit)}</strong></td>
                        <td data-label="انحراف از بودجه" className="money-cell">
                          {r.profit_variance == null ? (
                            <span className="muted">—</span>
                          ) : (
                            <span className={Number(r.profit_variance) >= 0 ? 'pos-in' : 'pos-out'}>{fa(r.profit_variance)}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                    <tr className="rep-foot">
                      <td className="entity-name card-title">جمع</td>
                      <td data-label="کد"></td>
                      <td data-label="درآمد" className="invoice-total">{fa(costCenterReport.total_income)}</td>
                      <td data-label="هزینه" className="invoice-total">{fa(costCenterReport.total_expense)}</td>
                      <td data-label="سود مستقیم" className="invoice-total">{fa(costCenterReport.total_profit)}</td>
                      <td colSpan={2} />
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {(active === 'receivable-aging' || active === 'payable-aging') && aging && (
        <div>
          <p className="hint">
            {aging.kind === 'receivable'
              ? 'مانده‌ی طلب از هر مشتری، به تفکیک سنِ فاکتورها. تسویه‌ها و برگشت‌ها اول به قدیمی‌ترین فاکتور اعمال می‌شوند.'
              : 'مانده‌ی بدهی به هر تأمین‌کننده، به تفکیک سنِ فاکتورها. پرداخت‌ها و برگشت‌ها اول به قدیمی‌ترین فاکتور اعمال می‌شوند.'}
          </p>
          {aging.rows.length === 0 ? (
            <p className="hint">
              {aging.kind === 'receivable' ? 'مطالبات بازی وجود ندارد.' : 'بدهی بازی وجود ندارد.'}
            </p>
          ) : (
            <div className="entity-table-wrap">
              <div className="table-scroll">
                <table className="entity-table rep-aging-table cards-on-mobile">
                  <thead>
                    <tr>
                      <th>{aging.kind === 'receivable' ? 'مشتری' : 'تأمین‌کننده'}</th>
                      <th>جاری (۰–۳۰)</th>
                      <th>۳۱–۶۰ روز</th>
                      <th>۶۱–۹۰ روز</th>
                      <th>بالای ۹۰ روز</th>
                      <th>جمع</th>
                    </tr>
                  </thead>
                  <tbody>
                    {aging.rows.map((r) => (
                      <tr key={r.contact_id}>
                        <td className="entity-name" data-label={aging.kind === 'receivable' ? 'مشتری' : 'تأمین‌کننده'}>{r.contact_name}</td>
                        <td data-label="جاری (۰–۳۰)" className="money-cell">{fa(r.current)}</td>
                        <td data-label="۳۱–۶۰ روز" className="money-cell">{fa(r.d31_60)}</td>
                        <td data-label="۶۱–۹۰ روز" className="money-cell">{fa(r.d61_90)}</td>
                        <td data-label="بالای ۹۰ روز" className="money-cell">{Number(r.over_90) > 0 ? <span className="status-badge tone-danger">{fa(r.over_90)}</span> : fa(r.over_90)}</td>
                        <td data-label="جمع" className="money-cell"><strong>{fa(r.total)}</strong></td>
                      </tr>
                    ))}
                    <tr className="rep-foot">
                      <td className="entity-name" data-label={aging.kind === 'receivable' ? 'مشتری' : 'تأمین‌کننده'}>جمع</td>
                      <td data-label="جاری (۰–۳۰)" className="money-cell">{fa(aging.total_current)}</td>
                      <td data-label="۳۱–۶۰ روز" className="money-cell">{fa(aging.total_31_60)}</td>
                      <td data-label="۶۱–۹۰ روز" className="money-cell">{fa(aging.total_61_90)}</td>
                      <td data-label="بالای ۹۰ روز" className="money-cell">{fa(aging.total_over_90)}</td>
                      <td data-label="جمع" className="invoice-total">{fa(aging.grand_total)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {active === 'inventory' && inventory && (
        <div>
          <p className="hint">
            مانده‌ی اولِ دوره، ورود، خروج و مانده‌ی پایانِ هر کالا — به تعداد و ریال. ارزش از بازپخشِ دفترِ انبار به ترتیبِ تاریخ می‌آید، پس «تا تاریخ» ارزشِ همان روز است، نه تعدادِ آن روز ضربِ میانگینِ امروز. تطبیقش با مانده‌ی «موجودی کالا» در «بررسی یکپارچگی» است.
          </p>
          {inventory.stale_item_count > 0 && (
            <p className="hint">
              <span className="status-badge tone-warning">منقضی</span>{' '}
              {`ارزش‌گذاریِ ${fa(inventory.stale_item_count)} کالا منقضی است: سندی بعداً با تاریخِ گذشته ثبت یا باطل شده و بهای بعضی خروج‌ها با میانگینِ همان تاریخ نمی‌خواند. کاردکسِ همان کالا حرکت‌ها را نشان می‌دهد.`}
            </p>
          )}
          {inventory.rows.length === 0 ? (
            <p className="hint">در این بازه کالایی مانده یا گردش ندارد.</p>
          ) : (
            <div className="entity-table-wrap">
              <div className="table-scroll">
                <table className="entity-table rep-inv-table cards-on-mobile">
                  <thead>
                    <tr>
                      <th>کد</th>
                      <th>کالا</th>
                      <th>واحد</th>
                      <th>اول دوره</th>
                      <th>ارزش اول دوره</th>
                      <th>ورود</th>
                      <th>ارزش ورود</th>
                      <th>خروج</th>
                      <th>ارزش خروج</th>
                      <th>موجودی</th>
                      <th>بهای میانگین</th>
                      <th>ارزش</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory.rows.map((r) => (
                      <tr key={r.item_id}>
                        <td data-label="کد">{r.sku}</td>
                        <td className="entity-name" data-label="کالا">
                          {r.name}
                          {r.stale_from && <span className="status-badge tone-warning">منقضی از {formatJalali(r.stale_from)}</span>}
                        </td>
                        <td data-label="واحد">{r.unit}</td>
                        <td data-label="اول دوره">{fa(r.opening_qty)}</td>
                        <td data-label="ارزش اول دوره" className="money-cell">{fa(r.opening_value)}</td>
                        <td data-label="ورود" className="pos-in">{fa(r.in_qty)}</td>
                        <td data-label="ارزش ورود" className="money-cell">{fa(r.in_value)}</td>
                        <td data-label="خروج" className="pos-out">{fa(r.out_qty)}</td>
                        <td data-label="ارزش خروج" className="money-cell">{fa(r.out_value)}</td>
                        <td data-label="موجودی">{Number(r.qty_on_hand) < 0 ? <span className="status-badge tone-danger">{fa(r.qty_on_hand)}</span> : fa(r.qty_on_hand)}</td>
                        <td data-label="بهای میانگین" className="money-cell">{fa(Math.round(Number(r.unit_cost)))}</td>
                        <td data-label="ارزش" className="money-cell"><strong>{fa(r.stock_value)}</strong></td>
                      </tr>
                    ))}
                    <tr className="rep-foot">
                      <td className="entity-name" data-label="کد">جمع ({fa(inventory.item_count)} قلم)</td>
                      <td data-label="کالا"></td>
                      <td data-label="واحد"></td>
                      <td data-label="اول دوره"></td>
                      <td data-label="ارزش اول دوره" className="money-cell">{fa(inventory.total_opening_value)}</td>
                      <td data-label="ورود"></td>
                      <td data-label="ارزش ورود" className="money-cell">{fa(inventory.total_in_value)}</td>
                      <td data-label="خروج"></td>
                      <td data-label="ارزش خروج" className="money-cell">{fa(inventory.total_out_value)}</td>
                      <td data-label="موجودی"></td>
                      <td data-label="بهای میانگین"></td>
                      <td data-label="ارزش" className="invoice-total">{fa(inventory.total_value)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {active === 'income-statement' && incomeStatement && (
        <div>
          <div className="report-kpis">
            <div className="report-kpi tone-ok"><span>درآمد کل</span><strong>{fa(incomeStatement.total_income)}</strong></div>
            <div className="report-kpi tone-warn"><span>هزینه کل</span><strong>{fa(incomeStatement.total_expenses)}</strong></div>
            <div className={`report-kpi ${Number(incomeStatement.net_profit) >= 0 ? 'tone-ok' : 'tone-bad'}`}>
              <span>{Number(incomeStatement.net_profit) >= 0 ? 'سود خالص' : 'زیان خالص'}</span>
              <strong>{fa(Math.abs(Number(incomeStatement.net_profit)))}</strong>
            </div>
          </div>
          <h3>درآمدها</h3>
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table rep-2col-table cards-on-mobile">
                <tbody>
                  {incomeStatement.income.map((r) => (
                    <tr key={r.account_id}>
                      <td className="card-title">{r.account_name}</td>
                      <td className="money-cell" data-label="مبلغ">{fa(r.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <h3>هزینه‌ها</h3>
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table rep-2col-table cards-on-mobile">
                <tbody>
                  {incomeStatement.expenses.map((r) => (
                    <tr key={r.account_id}>
                      <td className="card-title">{r.account_name}</td>
                      <td className="money-cell" data-label="مبلغ">{fa(r.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="invoice-total">سود/زیان خالص: {fa(incomeStatement.net_profit)}</p>
        </div>
      )}

      {active === 'balance-sheet' && balanceSheet && (() => {
        const liabPlusEquity = Number(balanceSheet.total_liabilities) + Number(balanceSheet.total_equity) + Number(balanceSheet.current_period_profit)
        const balanced = Math.abs(Number(balanceSheet.total_assets) - liabPlusEquity) < 1
        return (
        <div>
          <div className="report-kpis">
            <div className="report-kpi tone-ok"><span>جمع دارایی‌ها</span><strong>{fa(balanceSheet.total_assets)}</strong></div>
            <div className="report-kpi"><span>بدهی + حقوق صاحبان سرمایه</span><strong>{fa(liabPlusEquity)}</strong></div>
            <div className={`report-kpi ${balanced ? 'tone-ok' : 'tone-bad'}`}>
              <span>توازن</span><strong>{balanced ? 'تراز است ✓' : 'نامتوازن ✕'}</strong>
            </div>
          </div>
          <h3>دارایی‌ها</h3>
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table rep-2col-table cards-on-mobile">
                <tbody>
                  {balanceSheet.assets.map((r) => (
                    <tr key={r.account_id}><td className="card-title">{r.account_name}</td><td className="money-cell" data-label="مبلغ">{fa(r.balance)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="invoice-total">جمع دارایی‌ها: {fa(balanceSheet.total_assets)}</p>

          <h3>بدهی‌ها</h3>
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table rep-2col-table cards-on-mobile">
                <tbody>
                  {balanceSheet.liabilities.map((r) => (
                    <tr key={r.account_id}><td className="card-title">{r.account_name}</td><td className="money-cell" data-label="مبلغ">{fa(r.balance)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="invoice-total">جمع بدهی‌ها: {fa(balanceSheet.total_liabilities)}</p>

          <h3>حقوق صاحبان سرمایه</h3>
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table rep-2col-table cards-on-mobile">
                <tbody>
                  {balanceSheet.equity.map((r) => (
                    <tr key={r.account_id}><td className="card-title">{r.account_name}</td><td className="money-cell" data-label="مبلغ">{fa(r.balance)}</td></tr>
                  ))}
                  <tr>
                    <td className="card-title">سود/زیان دوره جاری</td>
                    <td className="money-cell" data-label="مبلغ">{fa(balanceSheet.current_period_profit)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <p className="invoice-total">جمع حقوق صاحبان سرمایه: {fa(balanceSheet.total_equity)}</p>
        </div>
        )
      })()}
    </SectionCard>
  )
}
