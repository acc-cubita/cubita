import { useEffect, useState } from 'react'
import { BarChart3, Download, Printer } from 'lucide-react'
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
  fetchFiscalYears,
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
  type ReportFilters,
  type SeasonalReport,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { KardexSummary, KardexTable } from './KardexTable'
import { AccountLedgerDrawer } from './AccountLedgerDrawer'
import {
  AgingGrid,
  BudgetGrid,
  CheckChip,
  ContactStatementGrid,
  CostCenterGrid,
  EquityView,
  InventoryGrid,
  SeasonalGrid,
  StatementGrid,
  type OpenAccount,
} from './ReportViews'
import { formatJalali, isoToJalali, todayIso, toFaDigits } from '../lib/jalali'
import { SearchSelect } from '../components/SearchSelect'
import { useNavSection } from './navContext'
import { REPORT_TABS, REPORT_TAB_GROUPS, isReportKind, type ReportKind } from '../lib/reportCatalog'
import {
  balanceSheetCheck,
  balanceSheetRows,
  cashFlowRows,
  equityRows,
  incomeStatementRows,
  seasonalCsvRow,
  statementCsv,
} from '../lib/reportSheets'
import { RangeCells, useAsync, useRange } from '../pages/accounting/kit'

const QUARTER_OPTIONS = [
  { value: 0, label: 'کل سال' },
  { value: 1, label: 'بهار' },
  { value: 2, label: 'تابستان' },
  { value: 3, label: 'پاییز' },
  { value: 4, label: 'زمستان' },
]

// گزارش‌هایی که «به تاریخِ مشخص» هستند (نه بازه‌ای) — بازه‌ی تاریخ برایشان بی‌معناست و
// فقط تاریخِ پایان (as_of) اهمیت دارد. «ارزش موجودی انبار» از این فهرست بیرون آمد:
// حالا مانده‌ی اول، ورود و خروجِ بازه را هم دارد.
const POINT_IN_TIME: ReportKind[] = ['balance-sheet', 'receivable-aging', 'payable-aging']

/** توضیحِ هر گزارش — «؟» کنارِ عنوان، به‌جای پاراگرافِ ثابت بالای گرید. */
const TIPS: Record<ReportKind, string> = {
  'income-statement': 'درآمد و هزینه‌ی دوره، هر حساب با مانده‌ی بازه؛ روی هر قلم کلیک کنید تا دفترش باز شود.',
  'balance-sheet':
    'مانده‌ی دارایی‌ها، بدهی‌ها و حقوق صاحبان سرمایه در پایانِ روزِ انتخاب‌شده. سود/زیانِ دوره تا سندِ اختتامیه قلمی از حقوق صاحبان سرمایه است.',
  budget:
    'مبلغِ برنامه‌ریزی‌شده در برابر عملکردِ واقعی، فقط برای حساب‌هایی که بودجه دارند. «مطلوب» یعنی درآمدِ بیشتر یا هزینه‌ی کمتر از برنامه.',
  'cash-flow':
    'ورود (+) و خروج (−) نقد در دوره، به تفکیکِ سه فعالیت. جمعِ سه فعالیت با تغییرِ مانده‌ی نقد برابر است.',
  'equity-statement':
    'تغییرِ سرمایه‌ی مالکان در دوره. سود/زیانِ دوره بیرونِ این تساوی است — تا سندِ اختتامیه زده نشود، در هیچ حسابِ حقوق صاحبان سهامی ننشسته.',
  'cost-center':
    'سود و زیانِ هر مرکز هزینه/پروژه از سندهای برچسب‌خورده. «مستقیم» فقط سندهای خودِ مرکز است و «با زیرمجموعه» زیرمجموعه‌ها را هم می‌گیرد.',
  'receivable-aging':
    'مانده‌ی طلب از هر مشتری، به تفکیکِ سنِ فاکتورها. تسویه‌ها و برگشت‌ها اول به قدیمی‌ترین فاکتور اعمال می‌شوند.',
  'payable-aging':
    'مانده‌ی بدهی به هر تأمین‌کننده، به تفکیکِ سنِ فاکتورها. پرداخت‌ها و برگشت‌ها اول به قدیمی‌ترین فاکتور اعمال می‌شوند.',
  'contact-statement': 'گردش و مانده‌ی یک طرف‌حساب در بازه. مانده‌ی مثبت یعنی بدهکار به ما، منفی یعنی طلبکار از ما.',
  inventory:
    'مانده‌ی اولِ دوره، ورود، خروج و مانده‌ی پایانِ هر کالا — به تعداد و ریال. ارزش از بازپخشِ دفترِ انبار به ترتیبِ تاریخ می‌آید، پس «تا تاریخ» ارزشِ همان روز است. تطبیقش با مانده‌ی «موجودی کالا» در «بررسی یکپارچگی» است.',
  kardex: 'ورود و خروجِ یک کالا به ترتیبِ تاریخ، با بهای میانگینِ هر لحظه.',
  seasonal:
    'تجمیعِ خرید و فروش به تفکیکِ طرف حساب، برای سامانه‌ی معاملاتِ فصلیِ سازمانِ امور مالیاتی (ماده ۱۶۹ ق.م.م). هویتِ مالیاتیِ هر طرف حساب در صفحه‌ی «اشخاص» وارد می‌شود.',
}

/**
 * گزارش‌های صفحه‌ی «گزارش‌ها» با تمِ اکسلی (الگوی «د» از `cubita-excel-theme`).
 *
 * - **سربرگ** (`jh-bar--report`): دوازده گزارش به‌شکلِ خانه‌های یک جدول، دسته‌بندی‌شده به همان دسته‌های کاتالوگِ
 *   بالای صفحه؛ بعد بازه (یا «به تاریخ» برای گزارشِ لحظه‌ای، یا سال و فصل برای معاملاتِ فصلی) و انتخابِ کالا/شخص.
 * - **بدنه:** هر گزارش یک گریدِ `xl-grid` با جمع‌ها در `tfoot`؛ صورت‌های مالی برگه‌ی بخش/قلم/جمع‌اند
 *   (`lib/reportSheets.ts`) و هر قلمِ حساب دفترش را باز می‌کند.
 * - انتخابِ کالا، شخص، سال یا فصل خودش گزارش را می‌آورد؛ دکمه‌ی «نمایش» لازم نیست.
 */
export function Reports({
  token,
  picker = true,
}: {
  token: string
  /** خانه‌های انتخابِ دوازده گزارش در سربرگ. صفحه‌ی «گزارش‌ها» خاموشش می‌کند: «همه‌ی گزارش‌ها»ی بالای همان صفحه
   *  انتخاب‌گر است و دو انتخاب‌گرِ هم‌معنا زیرِ هم فقط شلوغی بود. */
  picker?: boolean
}) {
  //: `reports/balance-sheet` گزارش را مستقیم باز می‌کند — از «همه‌ی گزارش‌ها» یا هر
  //: پیوندِ دیگری. بی‌بخش یعنی پیش‌فرض، سود و زیان.
  const nav = useNavSection()
  const wanted = nav?.activePage === 'reports' && isReportKind(nav.section) ? nav.section : null
  const [active, setActive] = useState<ReportKind>(wanted ?? 'income-statement')
  const range = useRange('all')
  const years = useAsync(() => fetchFiscalYears(token).catch(() => []), [token])
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
  const [drill, setDrill] = useState<OpenAccount | null>(null)

  const isPoint = POINT_IN_TIME.includes(active)
  //: سالِ نیمه‌تایپ‌شده («۱۴۰») درخواست نمی‌فرستد.
  const seasonalYearOk = seasonalYear >= 1300 && seasonalYear <= 1500

  // داده‌ی گزارشِ فعال را با بازه‌ی جاری می‌گیرد. کاردکس و صورت‌حساب فقط وقتی کالا یا شخص
  // انتخاب شده باشد؛ فصلی سال و فصلِ خودش را دارد.
  async function loadData() {
    setError(null)
    const { from, to } = range
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
        case 'seasonal': if (seasonalYearOk) setSeasonal(await fetchSeasonalReport(token, seasonalYear, seasonalQuarter)); break
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  // بارگذاریِ خودکار وقتی گزارش، بازه یا پارامترِ گزارش عوض شود
  useEffect(() => {
    void loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, range.from, range.to, kardexItemId, statementContactId, seasonalYear, seasonalQuarter])

  //: روی mount هم صدا زده می‌شود، نه فقط با تغییر: `selectTab` فهرستِ اشخاص و کالاها
  //: را برای صورت‌حساب و کاردکس می‌گیرد، و گزارشی که مستقیم باز شده بی آن فهرست
  //: انتخاب‌گرِ خالی نشان می‌داد.
  useEffect(() => {
    if (wanted) void selectTab(wanted)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wanted])

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

  //: روی صفحه‌ی «گزارش‌ها» بخشِ ناوبری عوض می‌شود و افکتِ بالا تب را باز می‌کند — تا «همه‌ی گزارش‌ها» هم
  //: بداند کدام باز است. در میزبانِ دیگر («گزارش‌های مدیریتی») مستقیم.
  const pick = (kind: ReportKind) => (nav?.activePage === 'reports' ? nav.setSection(kind) : void selectTab(kind))

  // داده‌ی گزارشِ فعال را به سرستون + ردیف‌ها نگاشت می‌کند تا همان چیزی که روی صفحه
  // است در اکسل هم بیاید. null یعنی این گزارش هنوز داده‌ای برای خروجی ندارد.
  function buildExport(): { name: string; headers: string[]; rows: (string | number)[][] } | null {
    const statement = ['شرح', 'کد', 'مبلغ']
    switch (active) {
      case 'income-statement':
        return incomeStatement && { name: 'سود-و-زیان', headers: statement, rows: statementCsv(incomeStatementRows(incomeStatement)) }
      case 'balance-sheet':
        return balanceSheet && { name: 'ترازنامه', headers: statement, rows: statementCsv(balanceSheetRows(balanceSheet)) }
      case 'cash-flow':
        return cashFlow && { name: 'جریان-وجوه-نقد', headers: statement, rows: statementCsv(cashFlowRows(cashFlow)) }
      case 'equity-statement':
        return equity && { name: 'تغییرات-حقوق-صاحبان-سهام', headers: statement, rows: statementCsv(equityRows(equity)) }
      case 'budget':
        return budgetReport && {
          name: 'بودجه-در-برابر-عملکرد',
          headers: ['کد', 'حساب', 'بودجه', 'عملکرد', 'انحراف', 'درصد', 'وضعیت'],
          rows: budgetReport.rows.map((r) => [r.account_code, r.account_name, r.budget, r.actual, r.variance, r.variance_pct ?? '', r.favorable ? 'مطلوب' : 'نامطلوب']),
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
            ...seasonal.sales.rows.map((r) => seasonalCsvRow('فروش', r)),
            ...seasonal.purchases.rows.map((r) => seasonalCsvRow('خرید', r)),
          ],
        }
      default:
        return null
    }
  }

  const exportData = buildExport()
  const tab = REPORT_TABS.find((t) => t.key === active)!
  const toText = range.to ? formatJalali(range.to) : 'امروز'
  const caption =
    active === 'seasonal'
      ? seasonal
        ? `${seasonal.quarter_label} ${toFaDigits(seasonal.year)} — ${formatJalali(seasonal.date_from)} تا ${formatJalali(seasonal.date_to)}`
        : `${QUARTER_OPTIONS.find((q) => q.value === seasonalQuarter)?.label} ${toFaDigits(seasonalYear)}`
      : isPoint
        ? `به تاریخِ ${toText}`
        : `${range.from ? formatJalali(range.from) : 'از ابتدا'} تا ${toText}`
  //: دامنه‌ی دفترِ حسابی که از گزارش باز می‌شود همان دامنه‌ی گزارش است.
  const drillScope: ReportFilters = isPoint ? { dateTo: range.to } : { dateFrom: range.from, dateTo: range.to }
  const openAccount = (a: OpenAccount) => setDrill(a)

  function body() {
    switch (active) {
      case 'income-statement':
        return incomeStatement && <StatementGrid rows={incomeStatementRows(incomeStatement)} onOpen={openAccount} />
      case 'balance-sheet': {
        if (!balanceSheet) return null
        const c = balanceSheetCheck(balanceSheet)
        return (
          <StatementGrid
            rows={balanceSheetRows(balanceSheet)}
            label="مانده"
            onOpen={openAccount}
            check={
              <CheckChip
                ok={c.ok}
                okText="تراز است"
                offText={`نامتوازن — اختلاف ${Math.abs(c.diff).toLocaleString('fa-IR')}`}
              />
            }
          />
        )
      }
      case 'cash-flow':
        return cashFlow && <StatementGrid rows={cashFlowRows(cashFlow)} onOpen={openAccount} />
      case 'equity-statement':
        return equity && <EquityView data={equity} onOpen={openAccount} />
      case 'budget':
        return (
          budgetReport &&
          (budgetReport.rows.length === 0 ? (
            <p className="hint">هنوز بودجه‌ای تعریف نشده. از «حسابداری ← بودجه‌بندی» بودجه اضافه کنید.</p>
          ) : (
            <BudgetGrid data={budgetReport} onOpen={openAccount} />
          ))
        )
      case 'cost-center':
        return (
          costCenterReport &&
          (costCenterReport.rows.length === 0 ? (
            <p className="hint">هنوز هیچ سندی به مرکز هزینه‌ای برچسب نخورده. از «شرکت ← مرکز هزینه» شروع کنید.</p>
          ) : (
            <>
              <p className="hint rp-before">
                ردیفِ «بدون مرکز هزینه» فعالیتی است که به هیچ مرکزی نسبت داده نشده — الان{' '}
                <b>{toFaDigits(costCenterReport.untagged_share_pct)}٪</b> از کلِ گردش.
              </p>
              <CostCenterGrid data={costCenterReport} />
            </>
          ))
        )
      case 'receivable-aging':
      case 'payable-aging':
        return (
          aging &&
          (aging.rows.length === 0 ? (
            <p className="hint">{aging.kind === 'receivable' ? 'مطالبات بازی وجود ندارد.' : 'بدهی بازی وجود ندارد.'}</p>
          ) : (
            <AgingGrid data={aging} />
          ))
        )
      case 'contact-statement':
        if (!statementContactId) return <p className="hint">یک طرف‌حساب در سربرگ انتخاب کنید تا صورت‌حسابش بیاید.</p>
        return contactStatement && <ContactStatementGrid data={contactStatement} />
      case 'inventory':
        return (
          inventory && (
            <>
              {inventory.stale_item_count > 0 && (
                <p className="hint rp-before">
                  <span className="status-badge tone-warning">منقضی</span>{' '}
                  {`ارزش‌گذاریِ ${inventory.stale_item_count.toLocaleString('fa-IR')} کالا منقضی است: سندی بعداً با تاریخِ گذشته ثبت یا باطل شده و بهای بعضی خروج‌ها با میانگینِ همان تاریخ نمی‌خواند. کاردکسِ همان کالا حرکت‌ها را نشان می‌دهد.`}
                </p>
              )}
              {inventory.rows.length === 0 ? (
                <p className="hint">در این بازه کالایی مانده یا گردش ندارد.</p>
              ) : (
                <InventoryGrid data={inventory} />
              )}
            </>
          )
        )
      case 'kardex':
        if (!kardexItemId) return <p className="hint">یک کالا در سربرگ انتخاب کنید تا کاردکسش بیاید.</p>
        return (
          kardex && (
            <>
              <KardexSummary data={kardex} />
              <KardexTable data={kardex} grid className="rp-kardex" />
            </>
          )
        )
      case 'seasonal':
        return (
          seasonal && (
            <>
              <SeasonalGrid title="فروش" section={seasonal.sales} onlyIncomplete={onlyIncomplete} />
              <SeasonalGrid title="خرید" section={seasonal.purchases} onlyIncomplete={onlyIncomplete} />
            </>
          )
        )
    }
  }

  const content = body()
  const firstLoad = loading && !content

  return (
    <>
      <section className="ef-head">
        <div className="jh-bar jh-bar--report rp-head" role="group" aria-label="گزارش، بازه و پارامترها">
          {/* دوازده گزارش به دسته‌های کاتالوگ: صورت‌های مالی یک سطر، بقیه کنارِ هم. */}
          {(picker
            ? [
                REPORT_TAB_GROUPS.filter((g) => g.key === 'statements'),
                REPORT_TAB_GROUPS.filter((g) => g.key !== 'statements'),
              ]
            : []
          ).map((groups, row) => (
            <div key={row} className={`jh-row${row ? ' jh-row--sub' : ''} rp-row--pick rp-row--pick${row + 1}`}>
              {groups.map((g) => (
                <div key={g.key} className="jh-field rp-group">
                  <span className="jh-label">{g.heading}</span>
                  <div className="rp-seg" role="group" aria-label={g.heading}>
                    {g.tabs.map((t) => (
                      <button
                        key={t.key}
                        type="button"
                        className={`rp-tab${active === t.key ? ' is-active' : ''}`}
                        aria-pressed={active === t.key}
                        onClick={() => pick(t.key)}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ))}

          {active === 'seasonal' ? (
            <div className="jh-row jh-row--sub rp-row--season">
              <label className="jh-field">
                <span className="jh-label">سال</span>
                <NumberInput
                  group={false}
                  value={seasonalYear}
                  onChange={(v) => setSeasonalYear(Number(v) || seasonalYear)}
                  placeholder="سال شمسی"
                  aria-label="سالِ شمسی"
                />
              </label>
              <div className="jh-field">
                <span className="jh-label">فصل</span>
                <div className="cc-presets rh-seg" role="group" aria-label="فصل">
                  {QUARTER_OPTIONS.map((q) => (
                    <button
                      key={q.value}
                      type="button"
                      className={seasonalQuarter === q.value ? 'is-active' : ''}
                      aria-pressed={seasonalQuarter === q.value}
                      onClick={() => setSeasonalQuarter(q.value)}
                    >
                      {q.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="jh-field">
                <span className="jh-label">ردیف‌ها</span>
                <button
                  type="button"
                  className={`xl-toggle${onlyIncomplete ? ' is-on' : ''}`}
                  aria-pressed={onlyIncomplete}
                  title="فقط طرف‌حساب‌هایی که هویتِ مالیاتی‌شان کامل نیست"
                  onClick={() => setOnlyIncomplete(!onlyIncomplete)}
                >
                  {onlyIncomplete ? 'فقط ناقص‌ها' : 'همه'}
                </button>
              </div>
            </div>
          ) : isPoint ? (
            <div className="jh-row jh-row--sub rp-row--asof">
              <div className="jh-field">
                <span className="jh-label">به تاریخ</span>
                <JalaliDatePicker
                  value={range.to ?? ''}
                  onChange={(iso) => {
                    range.setCustom({ from: range.from ?? '', to: iso })
                    range.setPreset('custom')
                  }}
                  placeholder="امروز"
                  clearLabel="امروز"
                />
              </div>
              <div className="jh-field rp-hint-cell">
                <span className="jh-label">بازه</span>
                <p>گزارشِ لحظه‌ای است: مانده‌ها در پایانِ همین روز؛ «از تاریخ» اثری ندارد.</p>
              </div>
            </div>
          ) : (
            <div className="jh-row jh-row--sub rh-row--range">
              <RangeCells range={range} years={years.data ?? []} />
            </div>
          )}

          {(active === 'kardex' || active === 'contact-statement') && (
            <div className="jh-row jh-row--sub rp-row--param">
              {active === 'kardex' ? (
                <label className="jh-field">
                  <span className="jh-label">کالا</span>
                  <SearchSelect aria-label="کالا" value={kardexItemId} onChange={(e) => setKardexItemId(e.target.value)}>
                    <option value="">— انتخاب کالا —</option>
                    {items.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.sku} — {i.name}
                      </option>
                    ))}
                  </SearchSelect>
                </label>
              ) : (
                <label className="jh-field">
                  <span className="jh-label">طرف‌حساب</span>
                  <SearchSelect
                    aria-label="طرف‌حساب"
                    value={statementContactId}
                    onChange={(e) => setStatementContactId(e.target.value)}
                  >
                    <option value="">— انتخاب طرف‌حساب —</option>
                    {contacts.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </SearchSelect>
                </label>
              )}
            </div>
          )}
        </div>
      </section>

      <SectionCard
        icon={BarChart3}
        title={tab.label}
        description={caption}
        tip={TIPS[active]}
        actions={
          <div className="jg-head-actions">
            <button type="button" className="ef-btn-secondary" onClick={() => exportData && downloadCsv(exportData.name, exportData.headers, exportData.rows)} disabled={!exportData}>
              <Download size={14} /> خروجی CSV
            </button>
            <button type="button" className="ef-btn-secondary" onClick={() => window.print()} disabled={!content}>
              <Printer size={14} /> چاپ
            </button>
          </div>
        }
      >
        {error && <p className="hint acc-note acc-note--err">{error}</p>}
        {firstLoad ? (
          <p className="hint">در حال بارگذاری…</p>
        ) : (
          <div className={`rp-body${loading ? ' is-loading' : ''}`} aria-busy={loading}>
            {content}
          </div>
        )}
      </SectionCard>

      {drill && (
        <AccountLedgerDrawer token={token} account={drill} filters={drillScope} onClose={() => setDrill(null)} />
      )}
    </>
  )
}
