import { useEffect, useState } from 'react'
import { Menu, Users, BarChart3, CalendarDays } from 'lucide-react'
import {
  fetchAccountsLive,
  fetchBankAccountsLive,
  fetchItemsWithPricingLive,
  fetchWarehousesLive,
  type MeResponse,
} from '../api'
import type { AccountCache, BankAccountCache, ItemCache, WarehouseCache } from '../electron.d'
import { Sidebar, type PageKey } from './Sidebar'
import { NavSectionContext } from './navContext'
import { PayrollPanel } from './PayrollPanel'
import { Reports } from './Reports'
import { PageHeader } from './PageHeader'
import { OverviewPage } from '../pages/OverviewPage'
import { CalendarPage } from '../pages/CalendarPage'
import { ContactsPage } from '../pages/ContactsPage'
import { CrmPage } from '../pages/CrmPage'
import { ManufacturingPage } from '../pages/ManufacturingPage'
import { OnboardingPage } from '../pages/OnboardingPage'
import { InstallmentsPage } from '../pages/InstallmentsPage'
import { SalesPage } from '../pages/SalesPage'
import { PosPage } from '../pages/PosPage'
import { PurchasesPage } from '../pages/PurchasesPage'
import { InventoryPage } from '../pages/InventoryPage'
import { AccountingPage } from '../pages/AccountingPage'
import { BankingPage } from '../pages/BankingPage'
import { HelpPage } from '../pages/HelpPage'
import { ProfilePage } from '../pages/ProfilePage'

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
  payroll: 'حقوق و دستمزد',
  reports: 'گزارش‌ها',
  calendar: 'تقویم و یادآوری',
  profile: 'پروفایل من',
  onboarding: 'راه‌اندازی',
  help: 'راهنما',
}

export function Dashboard({
  token,
  me,
  onLogout,
  onMeUpdated,
}: {
  token: string
  me: MeResponse
  onLogout: () => void
  onMeUpdated: (me: MeResponse) => void
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
  const [accounts, setAccounts] = useState<AccountCache[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseCache[]>([])
  const [items, setItems] = useState<ItemCache[]>([])
  const [bankAccounts, setBankAccounts] = useState<BankAccountCache[]>([])

  // نسخه‌ی محلی: صف/کش آفلاین ندارد؛ داده‌های مرجع (چارت، انبار، کالا، بانک) همیشه
  // مستقیم و زنده از موتورِ محلی خوانده می‌شوند. صفحات با onQueued این را پس از هر
  // تغییر (سند/فاکتور/چارت) دوباره صدا می‌زنند تا مرجع به‌روز بماند.
  async function refreshReferenceData() {
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

  useEffect(() => {
    void refreshReferenceData()
  }, [])

  // دوره‌ی جاری به تقویمِ شمسی — چیپِ آرامِ نوارِ بالا (مثلِ ماکت).
  const period = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { month: 'long', year: 'numeric' }).format(new Date())

  return (
    <NavSectionContext.Provider value={{ activePage: page, section, setSection }}>
    <div className="app-shell">
      <Sidebar
        active={page}
        activeSection={section}
        onNavigate={navigate}
        userName={me.name}
        roleName={me.role_name}
        onLogout={onLogout}
        open={navOpen}
        onClose={() => setNavOpen(false)}
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
            <span className="topbar-chip">
              <CalendarDays size={14} />
              دوره: {period}
            </span>
          </div>
        </header>

        <main className="app-content">
          {page === 'overview' && (
            <OverviewPage token={token} userName={me.name} itemsCount={items.length} />
          )}
          {page === 'sales' && (
            <SalesPage
              token={token}
              me={me}
              warehouses={warehouses}
              items={items}
              onQueued={() => void refreshReferenceData()}
            />
          )}
          {page === 'pos' && <PosPage token={token} />}
          {page === 'purchases' && (
            <PurchasesPage
              token={token}
              me={me}
              warehouses={warehouses}
              items={items}
              onQueued={() => void refreshReferenceData()}
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
              onChanged={() => void refreshReferenceData()}
            />
          )}
          {page === 'manufacturing' && <ManufacturingPage token={token} />}
          {page === 'accounting' && (
            <AccountingPage
              token={token}
              accounts={accounts}
              onQueued={() => void refreshReferenceData()}
            />
          )}
          {page === 'banking' && (
            <BankingPage
              token={token}
              accounts={accounts}
              bankAccounts={bankAccounts}
              onQueued={() => void refreshReferenceData()}
            />
          )}
          {page === 'payroll' && (
            <div className="page">
              <PageHeader
                icon={Users}
                title="حقوق و دستمزد"
                description="پرونده‌ی پرسنل، حکم حقوقی، کارکرد و صدور فیش، مزایا (عیدی/سنوات/مرخصی) و تنظیماتِ بیمه و مالیات."
              />
              <PayrollPanel token={token} />
            </div>
          )}
          {page === 'reports' && (
            <div className="page">
              <PageHeader
                icon={BarChart3}
                title="گزارش‌ها"
                description="تراز آزمایشی، سود و زیان، ترازنامه و دفتر کل — همیشه زنده و مستقیم از دفاتر حسابداری."
              />
              <Reports token={token} accounts={accounts} />
            </div>
          )}
          {page === 'onboarding' && <OnboardingPage token={token} />}
          {page === 'calendar' && <CalendarPage token={token} />}
          {page === 'profile' && <ProfilePage token={token} me={me} onMeUpdated={onMeUpdated} />}
          {page === 'help' && <HelpPage />}
        </main>
      </div>
    </div>
    </NavSectionContext.Provider>
  )
}
