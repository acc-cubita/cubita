import { useEffect, useState } from 'react'
import { RefreshCw, Menu, Users, Store, BarChart3, CreditCard } from 'lucide-react'
import {
  fetchAccountsLive,
  fetchBankAccountsLive,
  fetchItemsWithPricingLive,
  fetchWarehousesLive,
  type MeResponse,
} from '../api'
import type { AccountCache, BankAccountCache, ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
import { isElectron } from '../platform'
import { Sidebar, type PageKey } from './Sidebar'
import { PayrollPanel } from './PayrollPanel'
import { BenefitsPanel } from './BenefitsPanel'
import { IntegrationPanel } from './IntegrationPanel'
import { PurchasesAdminPanel } from './PurchasesAdminPanel'
import { Reports } from './Reports'
import { PageHeader } from './PageHeader'
import { OverviewPage } from '../pages/OverviewPage'
import { CalendarPage } from '../pages/CalendarPage'
import { ContactsPage } from '../pages/ContactsPage'
import { CrmPage } from '../pages/CrmPage'
import { SalesPage } from '../pages/SalesPage'
import { PosPage } from '../pages/PosPage'
import { PurchasesPage } from '../pages/PurchasesPage'
import { InventoryPage } from '../pages/InventoryPage'
import { AccountingPage } from '../pages/AccountingPage'
import { BankingPage } from '../pages/BankingPage'
import { HelpPage } from '../pages/HelpPage'
import { TeamPage } from '../pages/TeamPage'
import { ProfilePage } from '../pages/ProfilePage'

const PAGE_TITLES: Record<PageKey, string> = {
  overview: 'داشبورد',
  sales: 'فروش',
  pos: 'صندوق فروشگاهی',
  purchases: 'خرید',
  contacts: 'اشخاص',
  crm: 'باشگاه مشتریان',
  inventory: 'انبار',
  accounting: 'حسابداری',
  banking: 'چک و بانک',
  payroll: 'حقوق و دستمزد',
  integration: 'اتصال فروشگاه',
  billing: 'خریدهای سایت تجاری',
  reports: 'گزارش‌ها',
  calendar: 'تقویم و یادآوری',
  team: 'کاربران',
  profile: 'پروفایل من',
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
  const [navOpen, setNavOpen] = useState(false)
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

  async function handleSync() {
    setSyncing(true)
    setSyncStatus('در حال هم‌گام‌سازی...')
    try {
      await window.cubita.pullAll()
      const result = await window.cubita.pushOutbox()
      await refreshFromLocalCache()
      setSyncStatus(`sync کامل شد — ارسال‌شده: ${result.pushed}, ناموفق: ${result.failed}`)
    } catch (err) {
      setSyncStatus(`خطا در sync: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => {
    void refreshFromLocalCache()
  }, [])

  const pendingOutboxCount = [journalOutbox, invoiceOutbox, purchaseOutbox, checkOutbox]
    .flat()
    .filter((e) => !e.synced).length

  return (
    <div className="app-shell">
      <Sidebar
        active={page}
        onNavigate={setPage}
        userName={me.name}
        roleName={me.role_name}
        isPlatformAdmin={me.is_platform_admin}
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
            {syncStatus && <span className="sync-status">{syncStatus}</span>}
            {isElectron && (
              <button className="btn-primary" onClick={handleSync} disabled={syncing}>
                <RefreshCw size={15} className={syncing ? 'spin' : ''} />
                هم‌گام‌سازی
              </button>
            )}
          </div>
        </header>

        <main className="app-content">
          {page === 'overview' && (
            <OverviewPage
              token={token}
              userName={me.name}
              pendingOutboxCount={pendingOutboxCount}
              itemsCount={items.length}
            />
          )}
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
          {page === 'pos' && <PosPage token={token} />}
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
            <div className="page">
              <PageHeader
                icon={Users}
                title="حقوق و دستمزد"
                description="پرونده‌ی پرسنل، حکم حقوقی، کارکرد ماهانه و صدور فیش حقوقی برای هر دوره."
              />
              <PayrollPanel token={token} />
              <BenefitsPanel token={token} />
            </div>
          )}
          {page === 'integration' && (
            <div className="page">
              <PageHeader
                icon={Store}
                title="اتصال فروشگاه"
                description="موجودی و قیمت را با سایت فروشگاهی هم‌گام کنید و سفارش‌های ثبت‌شده‌ی آنلاین را خودکار به فاکتور فروش تبدیل کنید."
              />
              <IntegrationPanel token={token} />
            </div>
          )}
          {page === 'billing' && me.is_platform_admin && (
            <div className="page">
              <PageHeader
                icon={CreditCard}
                title="خریدهای سایت تجاری"
                description="خریدهای پرداخت‌شده از cubita.ir را ببینید و بعد از راه‌اندازی دستی نسخه‌ی اختصاصی مشتری، تحویل را ثبت کنید."
              />
              <PurchasesAdminPanel token={token} />
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
          {page === 'calendar' && <CalendarPage token={token} />}
          {page === 'team' && <TeamPage token={token} />}
          {page === 'profile' && <ProfilePage token={token} me={me} onMeUpdated={onMeUpdated} />}
          {page === 'help' && <HelpPage />}
        </main>
      </div>
    </div>
  )
}
