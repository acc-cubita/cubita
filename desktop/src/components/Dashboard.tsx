import { useEffect, useMemo, useRef, useState } from 'react'
import { RefreshCw, Menu, Users, Store, BarChart3, CreditCard, Link2, Building2 } from 'lucide-react'
import {
  fetchAccountsLive,
  fetchBankAccountsLive,
  fetchItemsWithPricingLive,
  fetchMpUnread,
  fetchWarehousesLive,
  type MeResponse,
} from '../api'
import type { AccountCache, BankAccountCache, ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
import { isElectron } from '../platform'
import { Sidebar, type PageKey } from './Sidebar'
import { buildNav } from '../lib/navModel'
import { TopNav } from './TopNav'
import { useTheme } from '../lib/theme'
import { NavSectionContext } from './navContext'
import { PayrollPanel } from './PayrollPanel'
import { IntegrationPanel } from './IntegrationPanel'
import { NativeStorefrontPanel } from './NativeStorefrontPanel'
import { Tabs } from './Tabs'
import { FeatureUpsell } from './FeatureUpsell'
import { StorefrontGallery } from './StorefrontGallery'
import { PurchasesAdminPanel } from './PurchasesAdminPanel'
import { Reports } from './Reports'
import { FixedAssetsPanel } from './FixedAssetsPanel'
import { FixedAssetWizard } from './wizard/FixedAssetWizard'
import { PageHeader } from './PageHeader'
import { OverviewPage } from '../pages/OverviewPage'
import { GuidedDashboard } from './GuidedDashboard'
import { CommandPalette } from './CommandPalette'
import { CalendarPage } from '../pages/CalendarPage'
import { ContactsPage } from '../pages/ContactsPage'
import { CrmPage } from '../pages/CrmPage'
import { ManufacturingPage } from '../pages/ManufacturingPage'
import { ContractingPage } from '../pages/ContractingPage'
import { MoadianHistoryPage, MoadianModulePage } from '../pages/moadian/MoadianModulePage'
import { FiscalYearPage } from '../pages/FiscalYearPage'
import { ChangePasswordPage } from '../pages/ChangePasswordPage'
import { BackupPage } from '../pages/BackupPage'
import { CodingPage } from '../pages/CodingPage'
import { PersonalizationPage } from '../pages/PersonalizationPage'
import { ContractFormPage } from '../pages/payroll/ContractFormPage'
import { ContractListPage } from '../pages/payroll/ContractListPage'
import { PayslipLedgerPage } from '../pages/payroll/PayslipLedgerPage'
import {
  DeploymentInfoPage,
  EmployeeLoanPage,
  LoanTypePage,
  SettlementPage,
} from '../pages/payroll/PayrollLoanPages'
import {
  JobTitlePage,
  PayrollFactorPage,
  PayrollTaxGroupPage,
  ServiceLocationPage,
} from '../pages/payroll/PayrollRefPages'
import { ContactNewPage } from '../pages/company/ContactFormPage'
import { NumberingPage } from '../pages/NumberingPage'
import { BackupListPage } from '../pages/BackupListPage'
import { UserListPage } from '../pages/UserListPage'
import { FiscalYearListPage } from '../pages/FiscalYearListPage'
import { ModulePanels, hasModulePanels } from './ModulePanels'
import { AccountsAdminPage } from '../pages/AccountsAdminPage'
import { MarketplaceCommissionPage } from '../pages/MarketplaceCommissionPage'
import {
  CommissionCalcPage,
  CommissionPage,
  ContactOverviewPage,
  ContactStatementPage,
  CreditDebitNotePage,
  CustomsPage,
  DiscountGroupPage,
  DiscountPage,
  InvoiceClosePage,
  MarkupPage,
  PriceAnnouncementPage,
  ProductBundlePage,
  SaleTypePage,
  SalesBrowsePage,
  SalesFlowPage,
} from '../pages/sales/SalesOpsPages'
import {
  BundleListPage,
  CommissionRuleListPage,
  CommissionRunListPage,
  CustomsListPage,
  DiscountGroupListPage,
  NoteListPage,
  PriceAnnouncementListPage,
  PricingFactorListPage,
  SaleTypeListPage,
  SalesInvoiceListPage,
  SalesReturnListPage,
} from '../pages/sales/SalesListPages'
import {
  QuotationListPage,
  QuotationPage,
  SalesInvoicePage,
  SalesReturnPage,
} from '../pages/sales/SalesDocumentPages'
import { PosPage } from '../pages/PosPage'
import { PurchasesPage } from '../pages/PurchasesPage'
import { InventoryPage } from '../pages/InventoryPage'
import { DistributorPage } from '../pages/DistributorPage'
import { MarketplacePage } from '../pages/MarketplacePage'
import {
  CashBoxPage,
  ContactSettlementPage,
  PayFlowPage,
  PaymentVoucherPage,
  PettyExpensePage,
  PettyHolderPage,
  ReceiptVoucherPage,
  TreasuryLedgerPage,
} from '../pages/treasury/TreasuryOpsPages'
import {
  CheckPayableClearPage,
  CheckReceivableOpsPage,
  CheckReturnPage,
  CheckSearchPage,
  CheckbooksPage,
} from '../pages/treasury/CheckOpsPages'
import {
  BankAccountListPage,
  CheckbookListPage,
  PettyCashListPage,
  PosSettlementListPage,
  PosTerminalListPage,
  StatementListPage,
} from '../pages/treasury/TreasuryListPages'
import {
  AnalyticListPage,
  CalendarListPage,
  ContactGroupListPage,
  GeoListPage,
  NumberingListPage,
} from '../pages/ledgers/ModuleListPages'
import {
  BankAccountsPage,
  BankLedgerPage,
  BankReconcilePage,
  BankStatementPage,
  PosSettlementPage,
  PosTerminalsPage,
} from '../pages/treasury/BankOpsPages'
import { HelpPage } from '../pages/HelpPage'
import { TeamPage } from '../pages/TeamPage'
import { ModulesPage } from '../pages/ModulesPage'
import { ProfilePage } from '../pages/ProfilePage'
import { ThemeGallery } from './ThemeGallery'
import {
  ContactGroupPage,
  GeoLocationsPage,
  RelatedPeoplePage,
} from '../pages/company/CompanyBasicsPages'
import {
  OpeningOpsPage,
  YearEndOpsPage,
  YearEndReminderPage,
} from '../pages/company/CompanyOpsPages'
import {
  AllInstallmentsPage,
  ContactListPage,
  CostCenterListPage,
  CostCenterPage,
  DataExportPage,
  DataImportPage,
  DayActivityPage,
  InstallmentPlansPage,
  ManagementReportsPage,
  UsageReportPage,
} from '../pages/company/CompanyListPages'
import { DynamicReportsPage, ReportBuilderPage } from '../pages/company/ReportBuilderPages'
import { InstallmentSalesPage } from '../pages/company/InstallmentSalesPage'
import {
  EntryCartablePage,
  EntryListPage,
  FinalizeEntriesPage,
  JournalEntryPage,
  MergeEntriesPage,
  RenumberEntriesPage,
} from '../pages/accounting/JournalPages'
import {
  AccountBrowsePage,
  AccountListPage,
  AnalyticsPage,
  ChartOfAccountsPage,
  NewAccountPage,
  ReclassifyPage,
} from '../pages/accounting/ChartPages'
import { OpeningBalancePage } from '../pages/accounting/OpeningBalancePage'
import {
  ClosePnlPage,
  ClosingOpeningPage,
  BalanceReclassPage,
  FxRevaluationPage,
  GeneralDocumentPage,
} from '../pages/accounting/ClosingPages'
import {
  BalanceReportPage,
  LedgerReportPage,
  LegalBooksPage,
  VatPage,
} from '../pages/accounting/ReportPages'
import {
  BudgetListPage,
  CurrencyListPage,
  PeriodCloseListPage,
  RecurringListPage,
} from '../pages/accounting/AccountingListPages'

const PAGE_TITLES: Record<PageKey, string> = {
  overview: 'داشبورد',
  salesflow: 'فرآیند فروش',
  salesinvoice: 'فاکتور فروش',
  quotations: 'پیش‌فاکتور',
  salesreturn: 'فاکتور برگشتی',
  invoiceclose: 'بستن فاکتور',
  creditnote: 'اعلامیه بدهکار بستانکار',
  contactstatement: 'صورت حساب طرف مقابل',
  commission: 'پورسانت',
  commissioncalc: 'محاسبه پورسانت',
  customs: 'اظهارنامه گمرکی',
  saletype: 'نوع فروش',
  priceannounce: 'اعلامیه قیمت',
  bundle: 'بسته محصول جدید',
  discount: 'تخفیف جدید',
  discountgroup: 'گروه کالای تخفیف جدید',
  markup: 'عامل افزاینده جدید',
  salesbrowse: 'مرور فروش',
  contactoverview: 'مرور جامع طرف حساب',
  saleslist: 'فاکتورهای فروش',
  quotationlist: 'پیش‌فاکتورها',
  returnlist: 'فاکتورهای برگشتی',
  notelist: 'اعلامیه‌های بدهکار و بستانکار',
  commissionrulelist: 'قواعد پورسانت',
  commissionrunlist: 'محاسبه‌های پورسانت',
  customslist: 'اظهارنامه‌های گمرکی',
  saletypelist: 'انواع فروش',
  priceannouncelist: 'اعلامیه‌های قیمت',
  bundlelist: 'بسته‌های محصول',
  pricingfactorlist: 'تخفیف‌ها و عوامل افزاینده',
  discountgrouplist: 'گروه‌های کالای تخفیف',
  installments: 'فروش اقساطی',
  pos: 'صندوق فروشگاهی',
  purchases: 'خرید',
  contacts: 'اشخاص',
  crm: 'باشگاه مشتریان',
  inventory: 'انبار',
  manufacturing: 'تولید و بهای تمام‌شده',
  accounting: 'حسابداری',
  //: `banking` کلیدِ ماژول است، نه صفحه — هجده عملیاتِ زیرش صفحه‌ی خودشان را دارند.
  banking: 'دریافت و پرداخت',
  payflow: 'فرآیند دریافت و پرداخت',
  receiptvoucher: 'رسید دریافت',
  paymentvoucher: 'اعلامیه پرداخت',
  checkops: 'عملیات بانکی چک دریافتنی',
  contactsettle: 'تسویه حساب طرف مقابل',
  checkreturn: 'استرداد چک',
  checkpayclear: 'وصول چک پرداختنی',
  checksearch: 'جستجوی چک',
  possettle: 'تسویه کارت خوان',
  bankstatement: 'صورت حساب بانکی',
  bankreconcile: 'مغایرت بانکی',
  cashbox: 'صندوق',
  bankaccounts: 'حساب بانکی',
  posterminals: 'دستگاه کارت خوان',
  checkbooks: 'دسته چک',
  pettyholder: 'تنخواه دار',
  pettyexpense: 'صورت هزینه تنخواه',
  bankledger: 'مرور عملیات بانکی',
  treasuryledger: 'دریافت‌ها و پرداخت‌ها',
  checkbooklist: 'دسته‌چک‌ها',
  bankaccountlist: 'حساب‌های بانکی',
  posterminallist: 'دستگاه‌های کارتخوان',
  possettlelist: 'تسویه‌های کارتخوان',
  statementlist: 'ردیف‌های صورت‌حساب بانکی',
  pettylist: 'گردش تنخواه',
  analyticlist: 'تفصیلی‌های سایر',
  geolist: 'محل‌های جغرافیایی',
  contactgrouplist: 'گروه‌های طرف حساب',
  calendarlist: 'رویدادهای تقویم',
  numberinglist: 'روش‌های شماره‌گذاری',
  fixedassets: 'دارایی ثابت',
  contracting: 'پیمانکاری',
  moadian: 'سامانه مؤدیان',
  moadianhistory: 'تاریخچه ارسال‌ها',
  distributor: 'پخشِ من',
  marketplace: 'بازارِ خرید',
  payroll: 'حقوق و دستمزد',
  contractnew: 'قرارداد جدید',
  contractlist: 'قراردادها',
  payslipledger: 'مرور حقوق',
  loantype: 'نوع وام جدید',
  employeeloans: 'تقسیط — وام‌های پرسنلی',
  settlement: 'تسویه حساب',
  deploymentinfo: 'اطلاعات استقرار',
  servicelocation: 'محل خدمت جدید',
  jobtitle: 'شغل جدید',
  payrollfactors: 'عوامل حقوق و مزایا',
  payrolltaxgroups: 'گروه مالیاتی و شعب',
  integration: 'اتصال فروشگاه',
  billing: 'خریدهای سایت تجاری',
  accounts: 'مدیریت اکانت‌ها',
  mpcommission: 'کمیسیونِ بازار',
  reports: 'گزارش‌ها',
  calendar: 'تقویم و یادآوری',
  team: 'کاربر جدید',
  modules: 'شخصی‌سازیِ پنل',
  profile: 'پروفایل من',
  // ── ماژولِ «حسابداری» ──
  acctchart: 'درختواره حساب‌ها',
  newaccount: 'سرفصل جدید',
  openingbalance: 'مانده اول دوره',
  journalentry: 'سند حسابداری',
  entrycartable: 'کارتابل صدور سند حسابداری',
  finalizeentries: 'تبدیل اسناد موقت به دائم',
  renumber: 'شماره‌گذاری مجدد اسناد',
  mergeentries: 'ادغام اسناد',
  reclassify: 'جابه‌جایی حساب در درختواره',
  analytics: 'تفصیلی سایر',
  fxrevaluation: 'صدور سند تسعیر ارز',
  balancereclass: 'اصلاح طبقه‌بندی مانده',
  generaldoc: 'صدور سند کل',
  closepnl: 'بستن حساب‌های سود و زیان',
  closingopening: 'صدور سند اختتامیه و افتتاحیه',
  vat: 'مالیات بر ارزش افزوده',
  ebooks: 'دفاتر تجارت الکترونیک',
  accountbrowse: 'مرور حساب‌ها',
  balancereport: 'گزارش ترازها',
  ledgerreport: 'گزارش دفتر',
  entrylist: 'اسناد حسابداری',
  accountlist: 'فهرست حساب‌ها',
  recurringlist: 'اسناد تکرارشونده',
  budgetlist: 'بودجه‌بندی',
  currencylist: 'ارزها و نرخ ارز',
  periodcloselist: 'دوره‌های بسته‌شده',
  theme: 'ظاهر و پوسته',
  fiscalyear: 'سال مالی',
  password: 'تغییر کلمه عبور',
  backup: 'پشتیبان‌گیری خودکار',
  coding: 'کدینگ',
  personalization: 'شخصی‌سازی',
  numbering: 'روش‌های شماره‌گذاری',
  backuplist: 'نسخه‌های پشتیبانی و بازیابی',
  userlist: 'کاربران',
  fiscalyearlist: 'سال‌های مالی',
  help: 'راهنما',
  // ── ماژولِ «شرکت» ──
  contactnew: 'طرف حساب جدید',
  contactgroup: 'گروه جدید',
  geo: 'محل‌های جغرافیایی',
  costcenter: 'مرکز هزینه',
  openingops: 'عملیات اول دوره',
  yearendops: 'عملیات پایان سال',
  yearendreminder: 'یادآوری عملیات پایان سال',
  dataexport: 'ارسال اطلاعات',
  dataimport: 'دریافت اطلاعات',
  reportbuilder: 'گزارش‌ساز',
  dynamicreports: 'گزارش‌های پویا',
  dayactivity: 'فعالیت‌های روز',
  mgmtreports: 'گزارش‌ها و نمودارهای مدیریتی',
  usagereport: 'گزارش استفاده از نرم‌افزار',
  contactlist: 'طرف حساب‌ها',
  relatedpeople: 'افراد مرتبط',
  installmentplans: 'قراردادهای اقساطی',
  allinstallments: 'همه اقساط',
  costcenterlist: 'مراکز هزینه',
}

export function Dashboard({
  token,
  me,
  onLogout,
  onMeUpdated,
  onTokenRenewed,
}: {
  token: string
  me: MeResponse
  onLogout: () => void
  onMeUpdated: (me: MeResponse) => void
  /** توکنِ تازه‌ی سرور (مثلاً پس از تغییرِ رمز) را در نشستِ برنامه می‌نشاند. */
  onTokenRenewed?: (token: string) => void
}) {
  const [page, setPage] = useState<PageKey>('overview')
  // تبِ فعالِ صفحه (زیرمنوی سطح‌سوم). null یعنی تبِ پیش‌فرض (اولین). با NavSectionContext
  // بین سایدبار و نوارِ تبِ داخلِ صفحه دوطرفه هم‌گام می‌شود.
  const [section, setSection] = useState<string | null>(null)
  const navigate = (p: PageKey, s: string | null = null) => {
    setPage(p)
    setSection(s)
  }
  const [navOpen, setNavOpen] = useState(false)
  // شمارِ پیامِ خوانده‌نشده‌ی گفتگوی بازار — نشانِ آن روی منوی «بازارِ خرید»/«پخشِ من».
  // فقط برای حسابِ بازار پول می‌شود؛ هر ~۲۵ ثانیه + با هر جابه‌جاییِ صفحه (تا پس از
  // خواندنِ پیام‌ها زود به‌روز شود). آفلاین/خطا بی‌صدا رد می‌شود.
  const [mpUnread, setMpUnread] = useState(0)
  const [accounts, setAccounts] = useState<AccountCache[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseCache[]>([])
  const [items, setItems] = useState<ItemCache[]>([])
  const [bankAccounts, setBankAccounts] = useState<BankAccountCache[]>([])
  const [journalOutbox, setJournalOutbox] = useState<OutboxEntry[]>([])
  const [invoiceOutbox, setInvoiceOutbox] = useState<OutboxEntry[]>([])
  const [purchaseOutbox, setPurchaseOutbox] = useState<OutboxEntry[]>([])
  const [checkOutbox, setCheckOutbox] = useState<OutboxEntry[]>([])
  const [syncStatus, setSyncStatus] = useState<string>('')
  const [syncing, setSyncing] = useState(false)
  // نگهبانِ اجرای یک‌بارِ همگام‌سازیِ خودکارِ بدو ورود (در برابرِ دوباره‌مانت‌شدن).
  const didAutoSyncRef = useRef(false)

  // نشانِ خوانده‌نشده‌ی گفتگوی بازار: فقط برای حسابِ پخش‌کننده/فروشگاه پول می‌شود.
  // `page` در وابستگی‌ها هست تا با هر جابه‌جایی (مثلاً بعد از خواندنِ پیام‌ها) فوراً به‌روز شود.
  useEffect(() => {
    if (me.tenant_kind !== 'distributor' && me.tenant_kind !== 'retailer') return
    let cancelled = false
    const load = () => {
      fetchMpUnread(token)
        .then((n) => { if (!cancelled) setMpUnread(n) })
        .catch(() => {})
    }
    load()
    const id = window.setInterval(load, 25000)
    return () => { cancelled = true; window.clearInterval(id) }
  }, [token, me.tenant_kind, page])

  async function refreshFromLocalCache() {
    if (isElectron) {
      setAccounts(await window.cubita.listCachedAccounts())
      setWarehouses(await window.cubita.listCachedWarehouses())
      setItems(await window.cubita.listCachedItems())
      setBankAccounts(await window.cubita.listCachedBankAccounts())
      setJournalOutbox(await window.cubita.listOutbox())
      setInvoiceOutbox(await window.cubita.listSalesInvoiceOutbox())
      setPurchaseOutbox(await window.cubita.listPurchaseInvoiceOutbox())
      setCheckOutbox(await window.cubita.listCheckOutbox())
    } else {
      // در وب صف آفلاین/کش محلی وجود ندارد؛ همه‌چیز مستقیم و زنده از API خوانده می‌شود
      const [accs, whs, its, banks] = await Promise.all([
        fetchAccountsLive(token),
        fetchWarehousesLive(token),
        fetchItemsWithPricingLive(token),
        fetchBankAccountsLive(token),
      ])
      setAccounts(accs)
      setWarehouses(whs)
      setItems(its)
      setBankAccounts(banks)
    }
  }

  // silent=true برای همگام‌سازیِ خودکارِ بدو ورود: بی‌سروصدا (بدونِ متنِ خطا/موفقیت)،
  // ولی چرخِ نشانگر همچنان می‌چرخد تا کاربر بداند در حالِ بارگیری است.
  async function handleSync(silent = false) {
    setSyncing(true)
    if (!silent) setSyncStatus('در حال هم‌گام‌سازی...')
    try {
      await window.cubita.pullAll()
      const result = await window.cubita.pushOutbox()
      await refreshFromLocalCache()
      // نسخه‌ی پشتیبانِ محلیِ خودکار پس از هر همگام‌سازیِ موفق (فقط مالک؛ سرور بقیه را ۴۰۳ می‌کند).
      if (me.permissions?.['*']) window.cubita.backupAuto().catch(() => {})
      if (!silent) setSyncStatus(`sync کامل شد — ارسال‌شده: ${result.pushed}, ناموفق: ${result.failed}`)
    } catch (err) {
      if (!silent) setSyncStatus(`خطا در sync: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => {
    void refreshFromLocalCache()
    // در دسکتاپ یک‌بار خودکار همگام‌سازی کن تا کالا/انبار/چارتِ حساب در کش بیاید و
    // فرم‌های ویزارد بدونِ زدنِ دستیِ «همگام‌سازی» آماده باشند. آفلاین → بی‌سروصدا رد می‌شود.
    if (isElectron && !didAutoSyncRef.current) {
      didAutoSyncRef.current = true
      void handleSync(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const pendingOutboxCount = [journalOutbox, invoiceOutbox, purchaseOutbox, checkOutbox]
    .flat()
    .filter((e) => !e.synced).length

  const { theme } = useTheme()

  // محتوای صفحه مستقل از نوعِ چیدمان است؛ فقط کرومِ اطراف (نوارِ کناری یا افقی) عوض می‌شود.
  const pageContent = (
    <>
          {page === 'overview' &&
            (theme.content === 'guided' ? (
              <GuidedDashboard
                token={token}
                userName={me.name}
                pendingOutboxCount={pendingOutboxCount}
                itemsCount={items.length}
                onNavigate={navigate}
              />
            ) : (
              <OverviewPage
                token={token}
                userName={me.name}
                pendingOutboxCount={pendingOutboxCount}
                itemsCount={items.length}
              />
            ))}
          {/* ── ماژولِ فروش: هجده عملیات و دوازده دفتر (قاعده‌ی نظیر) ── */}
          {page === 'salesflow' && <SalesFlowPage />}
          {page === 'salesinvoice' && (
            <SalesInvoicePage
              token={token}
              warehouses={warehouses}
              items={items}
              outbox={invoiceOutbox}
              onQueued={() => void refreshFromLocalCache()}
            />
          )}
          {page === 'quotations' && (
            <QuotationPage
              token={token}
              warehouses={warehouses}
              items={items}
              onQueued={() => void refreshFromLocalCache()}
            />
          )}
          {page === 'salesreturn' && <SalesReturnPage token={token} />}
          {page === 'invoiceclose' && <InvoiceClosePage token={token} />}
          {page === 'creditnote' && <CreditDebitNotePage token={token} />}
          {page === 'contactstatement' && <ContactStatementPage token={token} />}
          {page === 'commission' && <CommissionPage token={token} />}
          {page === 'commissioncalc' && <CommissionCalcPage token={token} />}
          {page === 'customs' && <CustomsPage token={token} />}
          {page === 'saletype' && <SaleTypePage token={token} />}
          {page === 'priceannounce' && <PriceAnnouncementPage token={token} />}
          {page === 'bundle' && <ProductBundlePage token={token} />}
          {page === 'discount' && <DiscountPage token={token} />}
          {page === 'discountgroup' && <DiscountGroupPage token={token} />}
          {page === 'markup' && <MarkupPage token={token} />}
          {page === 'salesbrowse' && <SalesBrowsePage token={token} />}
          {page === 'contactoverview' && <ContactOverviewPage token={token} />}
          {page === 'saleslist' && <SalesInvoiceListPage token={token} />}
          {page === 'quotationlist' && (
            <QuotationListPage token={token} onQueued={() => void refreshFromLocalCache()} />
          )}
          {page === 'returnlist' && <SalesReturnListPage token={token} />}
          {page === 'notelist' && <NoteListPage token={token} />}
          {page === 'commissionrulelist' && <CommissionRuleListPage token={token} />}
          {page === 'commissionrunlist' && <CommissionRunListPage token={token} />}
          {page === 'customslist' && <CustomsListPage token={token} />}
          {page === 'saletypelist' && <SaleTypeListPage token={token} />}
          {page === 'priceannouncelist' && <PriceAnnouncementListPage token={token} />}
          {page === 'bundlelist' && <BundleListPage token={token} />}
          {page === 'pricingfactorlist' && <PricingFactorListPage token={token} />}
          {page === 'discountgrouplist' && <DiscountGroupListPage token={token} />}
          {page === 'pos' && <PosPage token={token} me={me} />}
          {page === 'purchases' && (
            <PurchasesPage
              token={token}
              me={me}
              warehouses={warehouses}
              items={items}
              outbox={purchaseOutbox}
              onQueued={() => void refreshFromLocalCache()}
            />
          )}
          {page === 'installments' && <InstallmentSalesPage token={token} bankAccounts={bankAccounts} />}
          {page === 'contacts' && <ContactsPage token={token} />}
          {page === 'crm' && <CrmPage token={token} />}
          {page === 'inventory' && (
            <InventoryPage
              token={token}
              warehouses={warehouses}
              items={items}
              onChanged={() => void refreshFromLocalCache()}
            />
          )}
          {page === 'manufacturing' && <ManufacturingPage token={token} />}
          {page === 'distributor' && me.tenant_kind === 'distributor' && <DistributorPage token={token} items={items} />}
          {page === 'marketplace' && me.tenant_kind === 'retailer' && <MarketplacePage token={token} />}
          {page === 'fixedassets' && (
            <div className="page panels">
              <PageHeader
                icon={Building2}
                title="دارایی ثابت"
                description="اموال و دارایی‌های سرمایه‌ای را ثبت کنید؛ استهلاکِ دوره‌ای و اسنادِ مرتبط خودکار محاسبه و صادر می‌شود."
              />
              {theme.content === 'guided' ? <FixedAssetWizard token={token} /> : <FixedAssetsPanel token={token} />}
            </div>
          )}
          {/* ── ماژولِ «حسابداری» — هجده عملیات و شش فهرست ── */}
          {page === 'acctchart' && (
            <ChartOfAccountsPage token={token} onChanged={() => void refreshFromLocalCache()} />
          )}
          {page === 'newaccount' && (
            <NewAccountPage token={token} onChanged={() => void refreshFromLocalCache()} />
          )}
          {page === 'openingbalance' && <OpeningBalancePage token={token} />}
          {page === 'journalentry' && (
            <JournalEntryPage
              token={token}
              accounts={accounts}
              outbox={journalOutbox}
              onQueued={() => void refreshFromLocalCache()}
            />
          )}
          {page === 'entrycartable' && <EntryCartablePage token={token} />}
          {page === 'finalizeentries' && <FinalizeEntriesPage token={token} />}
          {page === 'renumber' && <RenumberEntriesPage token={token} />}
          {page === 'mergeentries' && <MergeEntriesPage token={token} />}
          {page === 'reclassify' && (
            <ReclassifyPage token={token} onChanged={() => void refreshFromLocalCache()} />
          )}
          {page === 'analytics' && <AnalyticsPage token={token} />}
          {page === 'fxrevaluation' && <FxRevaluationPage token={token} />}
          {page === 'balancereclass' && <BalanceReclassPage token={token} />}
          {page === 'generaldoc' && <GeneralDocumentPage token={token} />}
          {page === 'closepnl' && <ClosePnlPage token={token} />}
          {page === 'closingopening' && <ClosingOpeningPage token={token} />}
          {page === 'vat' && <VatPage token={token} />}
          {page === 'ebooks' && <LegalBooksPage token={token} />}
          {page === 'accountbrowse' && <AccountBrowsePage token={token} />}
          {page === 'balancereport' && <BalanceReportPage token={token} />}
          {page === 'ledgerreport' && <LedgerReportPage token={token} />}
          {page === 'entrylist' && <EntryListPage token={token} />}
          {page === 'accountlist' && <AccountListPage token={token} />}
          {page === 'recurringlist' && <RecurringListPage token={token} accounts={accounts} />}
          {page === 'budgetlist' && <BudgetListPage token={token} accounts={accounts} />}
          {page === 'currencylist' && <CurrencyListPage token={token} />}
          {page === 'periodcloselist' && <PeriodCloseListPage token={token} />}
          {/* ── ماژولِ «دریافت و پرداخت» — هجده عملیات و یک فهرست ── */}
          {page === 'payflow' && <PayFlowPage token={token} onNavigate={navigate} />}
          {page === 'receiptvoucher' && <ReceiptVoucherPage token={token} />}
          {page === 'paymentvoucher' && <PaymentVoucherPage token={token} />}
          {page === 'checkops' && <CheckReceivableOpsPage token={token} />}
          {page === 'contactsettle' && <ContactSettlementPage token={token} />}
          {page === 'checkreturn' && <CheckReturnPage token={token} />}
          {page === 'checkpayclear' && <CheckPayableClearPage token={token} />}
          {page === 'checksearch' && <CheckSearchPage token={token} />}
          {page === 'possettle' && <PosSettlementPage token={token} />}
          {page === 'bankstatement' && <BankStatementPage token={token} />}
          {page === 'bankreconcile' && <BankReconcilePage token={token} bankAccounts={bankAccounts} />}
          {page === 'cashbox' && <CashBoxPage token={token} onNavigate={navigate} />}
          {page === 'bankaccounts' && <BankAccountsPage token={token} accounts={accounts} />}
          {page === 'posterminals' && <PosTerminalsPage token={token} bankAccounts={bankAccounts} />}
          {page === 'checkbooks' && <CheckbooksPage token={token} />}
          {page === 'pettyholder' && <PettyHolderPage token={token} accounts={accounts} />}
          {page === 'pettyexpense' && <PettyExpensePage token={token} accounts={accounts} />}
          {page === 'bankledger' && <BankLedgerPage token={token} />}
          {page === 'treasuryledger' && <TreasuryLedgerPage token={token} />}
          {/* ── دفترهای نظیر (قاعده‌ی «هر عملیاتِ رکوردساز، یک فهرست») ── */}
          {page === 'checkbooklist' && <CheckbookListPage token={token} />}
          {page === 'bankaccountlist' && <BankAccountListPage token={token} />}
          {page === 'posterminallist' && <PosTerminalListPage token={token} />}
          {page === 'possettlelist' && <PosSettlementListPage token={token} />}
          {page === 'statementlist' && <StatementListPage token={token} />}
          {page === 'pettylist' && <PettyCashListPage token={token} />}
          {page === 'analyticlist' && <AnalyticListPage token={token} />}
          {page === 'geolist' && <GeoListPage token={token} />}
          {page === 'contactgrouplist' && <ContactGroupListPage token={token} />}
          {page === 'calendarlist' && <CalendarListPage token={token} />}
          {page === 'numberinglist' && <NumberingListPage token={token} />}
          {page === 'contractnew' && <ContractFormPage token={token} onNavigate={setPage} />}
          {page === 'contractlist' && <ContractListPage token={token} onNavigate={setPage} />}
          {page === 'payslipledger' && <PayslipLedgerPage token={token} />}
          {page === 'loantype' && <LoanTypePage token={token} />}
          {page === 'employeeloans' && <EmployeeLoanPage token={token} />}
          {page === 'settlement' && <SettlementPage token={token} />}
          {page === 'deploymentinfo' && <DeploymentInfoPage token={token} />}
          {page === 'servicelocation' && <ServiceLocationPage token={token} />}
          {page === 'jobtitle' && <JobTitlePage token={token} />}
          {page === 'payrollfactors' && <PayrollFactorPage token={token} />}
          {page === 'payrolltaxgroups' && <PayrollTaxGroupPage token={token} />}
          {page === 'payroll' && (
            <div className="page panels">
              <PageHeader
                icon={Users}
                title="حقوق و دستمزد"
                description="پرونده‌ی پرسنل، حکم حقوقی، کارکرد و صدور فیش، مزایا (عیدی/سنوات/مرخصی) و تنظیماتِ بیمه و مالیات."
              />
              <PayrollPanel token={token} onNavigate={setPage} />
            </div>
          )}
          {page === 'integration' && (
            <div className="page panels">
              <PageHeader
                icon={Store}
                title="اتصال فروشگاه"
                description="موجودی و قیمت را با سایت فروشگاهی هم‌گام کنید و سفارش‌های ثبت‌شده‌ی آنلاین را خودکار به فاکتور فروش تبدیل کنید."
              />
              {(me.locked_features ?? []).includes('storefront') ? (
                <>
                  <StorefrontGallery locked />
                  <FeatureUpsell feature="storefront" />
                </>
              ) : (
                <Tabs
                  syncPage="integration"
                  tabs={[
                    {
                      key: 'build',
                      label: 'فروشگاهِ کوبیتا (بساز)',
                      icon: Store,
                      content: <NativeStorefrontPanel token={token} />,
                    },
                    {
                      key: 'connect',
                      label: 'اتصال به سایتِ موجود',
                      icon: Link2,
                      content: <IntegrationPanel token={token} />,
                    },
                  ]}
                />
              )}
            </div>
          )}
          {page === 'billing' && me.is_platform_admin && (
            <div className="page panels">
              <PageHeader
                icon={CreditCard}
                title="خریدهای سایت تجاری"
                description="خریدهای پرداخت‌شده از cubita.ir را ببینید و بعد از راه‌اندازی دستی نسخه‌ی اختصاصی مشتری، تحویل را ثبت کنید."
              />
              <PurchasesAdminPanel token={token} />
            </div>
          )}
          {page === 'accounts' && me.is_super_admin && (
            <AccountsAdminPage token={token} me={me} onMeUpdated={onMeUpdated} />
          )}
          {page === 'mpcommission' && me.is_super_admin && <MarketplaceCommissionPage token={token} />}
          {page === 'reports' && (
            <div className="page panels">
              <PageHeader
                icon={BarChart3}
                title="گزارش‌ها"
                description="تراز آزمایشی، سود و زیان، ترازنامه و دفتر کل — همیشه زنده و مستقیم از دفاتر حسابداری."
              />
              <Reports token={token} />
            </div>
          )}
          {page === 'contracting' && <ContractingPage />}
          {page === 'moadian' && <MoadianModulePage token={token} me={me} onNavigate={navigate} />}
          {page === 'moadianhistory' && <MoadianHistoryPage token={token} me={me} />}
          {page === 'calendar' && <CalendarPage token={token} />}
          {page === 'team' && <TeamPage token={token} />}
          {page === 'modules' && <ModulesPage token={token} me={me} onMeUpdated={onMeUpdated} />}
          {page === 'profile' && <ProfilePage token={token} me={me} onMeUpdated={onMeUpdated} />}
          {page === 'fiscalyear' && <FiscalYearPage token={token} />}
          {page === 'backup' && <BackupPage token={token} me={me} />}
          {page === 'coding' && <CodingPage token={token} />}
          {page === 'personalization' && <PersonalizationPage token={token} />}
          {page === 'numbering' && <NumberingPage token={token} />}
          {page === 'backuplist' && <BackupListPage token={token} me={me} />}
          {page === 'userlist' && <UserListPage token={token} />}
          {page === 'fiscalyearlist' && <FiscalYearListPage token={token} />}

          {/* ── ماژولِ «شرکت» ── */}
          {page === 'contactnew' && <ContactNewPage token={token} onNavigate={navigate} />}
          {page === 'contactgroup' && <ContactGroupPage token={token} />}
          {page === 'geo' && <GeoLocationsPage token={token} />}
          {page === 'costcenter' && <CostCenterPage token={token} accounts={accounts} />}
          {page === 'openingops' && <OpeningOpsPage token={token} onNavigate={navigate} />}
          {page === 'yearendops' && <YearEndOpsPage token={token} onNavigate={navigate} />}
          {page === 'yearendreminder' && <YearEndReminderPage token={token} />}
          {page === 'dataexport' && <DataExportPage token={token} me={me} />}
          {page === 'dataimport' && <DataImportPage token={token} me={me} />}
          {page === 'reportbuilder' && <ReportBuilderPage token={token} />}
          {page === 'dynamicreports' && <DynamicReportsPage token={token} onNavigate={navigate} />}
          {page === 'dayactivity' && <DayActivityPage token={token} />}
          {page === 'mgmtreports' && <ManagementReportsPage token={token} />}
          {page === 'usagereport' && <UsageReportPage token={token} />}
          {page === 'contactlist' && <ContactListPage token={token} onNavigate={navigate} />}
          {page === 'relatedpeople' && <RelatedPeoplePage token={token} />}
          {page === 'installmentplans' && <InstallmentPlansPage token={token} />}
          {page === 'allinstallments' && <AllInstallmentsPage token={token} />}
          {page === 'costcenterlist' && <CostCenterListPage token={token} onNavigate={navigate} />}
          {page === 'password' && (
            <ChangePasswordPage token={token} me={me} onTokenRenewed={onTokenRenewed} />
          )}
          {page === 'theme' && <ThemeGallery />}
          {page === 'help' && <HelpPage />}
    </>
  )

  // همان مدلِ ناوبریِ نوار/سایدبار — کارتِ «عملیات» هم صفحه‌های هم‌گروه را از این‌جا
  // می‌گیرد، پس دقیقاً همان چیزی را نشان می‌دهد که منو نشان می‌داد.
  const navGroups = useMemo(
    () =>
      buildNav({
        isPlatformAdmin: me.is_platform_admin,
        isSuperAdmin: me.is_super_admin,
        tenantKind: me.tenant_kind,
        enabledModules: me.enabled_modules,
        allowedModules: me.allowed_modules,
        isOwner: me.role_key === 'owner',
      }).groups,
    [me.is_platform_admin, me.is_super_admin, me.tenant_kind, me.enabled_modules, me.allowed_modules, me.role_key],
  )

  // نوارِ تبِ داخلِ صفحه فقط وقتی پنهان می‌شود که کارتِ «عملیات» جایش را گرفته باشد.
  const panelsClass = hasModulePanels(page, navGroups) ? ' app-shell--panels' : ''

  return (
    <NavSectionContext.Provider value={{ activePage: page, section, setSection }}>
      {theme.shell === 'topnav' ? (
        <div className={`app-shell app-shell--topnav${panelsClass}`}>
          <TopNav
            active={page}
            onNavigate={navigate}
            userName={me.name}
            roleName={me.role_name}
            businessName={me.tenant_name}
            isPlatformAdmin={me.is_platform_admin}
            isSuperAdmin={me.is_super_admin}
            tenantKind={me.tenant_kind}
            enabledModules={me.enabled_modules}
            allowedModules={me.allowed_modules}
            isOwner={me.role_key === 'owner'}
            mpUnread={mpUnread}
            onLogout={onLogout}
            onSync={isElectron ? () => handleSync() : undefined}
            syncing={syncing}
            syncStatus={syncStatus}
          />
          {/* دو کارت باید کنارِ محتوا بنشینند، نه زیرِ نوار؛ پس یک ردیفِ افقی زیرِ نوار. */}
          <div className="app-body">
            <ModulePanels
              page={page}
              section={section}
              onSelectSection={(key) => setSection(key)}
              onNavigate={navigate}
              groups={navGroups}
              token={token}
            />
            <main className="app-content">{pageContent}</main>
          </div>
          {theme.content === 'guided' && <CommandPalette me={me} onNavigate={navigate} />}
        </div>
      ) : (
        <div className={`app-shell${panelsClass}`}>
          <Sidebar
            active={page}
            activeSection={section}
            onNavigate={navigate}
            userName={me.name}
            roleName={me.role_name}
            isPlatformAdmin={me.is_platform_admin}
            isSuperAdmin={me.is_super_admin}
            tenantKind={me.tenant_kind}
            enabledModules={me.enabled_modules}
            allowedModules={me.allowed_modules}
            isOwner={me.role_key === 'owner'}
            onLogout={onLogout}
            open={navOpen}
            onClose={() => setNavOpen(false)}
          />
          <ModulePanels
            page={page}
            section={section}
            onSelectSection={(key) => setSection(key)}
            onNavigate={navigate}
            groups={navGroups}
            token={token}
          />
          <div className="app-main">
            <header className="topbar">
              <div className="topbar-start">
                <button
                  type="button"
                  className="nav-toggle"
                  onClick={() => setNavOpen(true)}
                  aria-label="باز کردن منو"
                >
                  <Menu size={20} />
                </button>
                <h1 className="topbar-title">{PAGE_TITLES[page]}</h1>
              </div>
              <div className="topbar-actions">
                {syncStatus && <span className="sync-status">{syncStatus}</span>}
                {isElectron && (
                  <button className="btn-primary" onClick={() => handleSync()} disabled={syncing}>
                    <RefreshCw size={15} className={syncing ? 'spin' : ''} />
                    هم‌گام‌سازی
                  </button>
                )}
              </div>
            </header>
            <main className="app-content">{pageContent}</main>
          </div>
        </div>
      )}
    </NavSectionContext.Provider>
  )
}
