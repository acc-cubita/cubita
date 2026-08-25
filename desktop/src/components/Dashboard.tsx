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
import { OnboardingPage } from '../pages/OnboardingPage'
import { ContractingPage } from '../pages/ContractingPage'
import { MoadianPage } from '../pages/MoadianPage'
import { FiscalYearPage } from '../pages/FiscalYearPage'
import { ChangePasswordPage } from '../pages/ChangePasswordPage'
import { BackupPage } from '../pages/BackupPage'
import { ModulePanels, hasModulePanels } from './ModulePanels'
import { InstallmentsPage } from '../pages/InstallmentsPage'
import { AccountsAdminPage } from '../pages/AccountsAdminPage'
import { MarketplaceCommissionPage } from '../pages/MarketplaceCommissionPage'
import { SalesPage } from '../pages/SalesPage'
import { PosPage } from '../pages/PosPage'
import { PurchasesPage } from '../pages/PurchasesPage'
import { InventoryPage } from '../pages/InventoryPage'
import { DistributorPage } from '../pages/DistributorPage'
import { MarketplacePage } from '../pages/MarketplacePage'
import { AccountingPage } from '../pages/AccountingPage'
import { BankingPage } from '../pages/BankingPage'
import { HelpPage } from '../pages/HelpPage'
import { TeamPage } from '../pages/TeamPage'
import { ModulesPage } from '../pages/ModulesPage'
import { ProfilePage } from '../pages/ProfilePage'
import { ThemeGallery } from './ThemeGallery'

const PAGE_TITLES: Record<PageKey, string> = {
  overview: 'داشبورد',
  sales: 'فروش',
  installments: 'فروش اقساطی',
  pos: 'صندوق فروشگاهی',
  purchases: 'خرید',
  contacts: 'اشخاص',
  crm: 'باشگاه مشتریان',
  inventory: 'انبار',
  manufacturing: 'تولید و بهای تمام‌شده',
  accounting: 'حسابداری',
  banking: 'چک و بانک',
  fixedassets: 'دارایی ثابت',
  contracting: 'پیمانکاری',
  moadian: 'سامانه مؤدیان',
  distributor: 'پخشِ من',
  marketplace: 'بازارِ خرید',
  payroll: 'حقوق و دستمزد',
  integration: 'اتصال فروشگاه',
  billing: 'خریدهای سایت تجاری',
  accounts: 'مدیریت اکانت‌ها',
  mpcommission: 'کمیسیونِ بازار',
  reports: 'گزارش‌ها',
  calendar: 'تقویم و یادآوری',
  team: 'کاربران',
  modules: 'شخصی‌سازیِ پنل',
  profile: 'پروفایل من',
  onboarding: 'راه‌اندازی',
  theme: 'ظاهر و پوسته',
  fiscalyear: 'سال مالی',
  password: 'تغییر کلمه عبور',
  backup: 'پشتیبان‌گیری خودکار',
  help: 'راهنما',
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
          {page === 'sales' && (
            <SalesPage
              token={token}
              me={me}
              warehouses={warehouses}
              items={items}
              outbox={invoiceOutbox}
              onQueued={() => void refreshFromLocalCache()}
            />
          )}
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
          {page === 'installments' && <InstallmentsPage token={token} bankAccounts={bankAccounts} />}
          {page === 'contacts' && <ContactsPage token={token} bankAccounts={bankAccounts} />}
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
          {page === 'accounting' && (
            <AccountingPage
              token={token}
              accounts={accounts}
              outbox={journalOutbox}
              onQueued={() => void refreshFromLocalCache()}
            />
          )}
          {page === 'banking' && (
            <BankingPage
              token={token}
              accounts={accounts}
              bankAccounts={bankAccounts}
              outbox={checkOutbox}
              onQueued={() => void refreshFromLocalCache()}
            />
          )}
          {page === 'payroll' && (
            <div className="page panels">
              <PageHeader
                icon={Users}
                title="حقوق و دستمزد"
                description="پرونده‌ی پرسنل، حکم حقوقی، کارکرد و صدور فیش، مزایا (عیدی/سنوات/مرخصی) و تنظیماتِ بیمه و مالیات."
              />
              <PayrollPanel token={token} />
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
          {page === 'accounts' && me.is_super_admin && <AccountsAdminPage token={token} />}
          {page === 'mpcommission' && me.is_super_admin && <MarketplaceCommissionPage token={token} />}
          {page === 'reports' && (
            <div className="page panels">
              <PageHeader
                icon={BarChart3}
                title="گزارش‌ها"
                description="تراز آزمایشی، سود و زیان، ترازنامه و دفتر کل — همیشه زنده و مستقیم از دفاتر حسابداری."
              />
              <Reports token={token} accounts={accounts} />
            </div>
          )}
          {page === 'contracting' && <ContractingPage />}
          {page === 'moadian' && <MoadianPage token={token} />}
          {page === 'onboarding' && <OnboardingPage token={token} />}
          {page === 'calendar' && <CalendarPage token={token} />}
          {page === 'team' && <TeamPage token={token} />}
          {page === 'modules' && <ModulesPage token={token} me={me} onMeUpdated={onMeUpdated} />}
          {page === 'profile' && <ProfilePage token={token} me={me} onMeUpdated={onMeUpdated} />}
          {page === 'fiscalyear' && <FiscalYearPage token={token} />}
          {page === 'backup' && <BackupPage token={token} me={me} />}
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
