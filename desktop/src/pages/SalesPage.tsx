import { useCallback, useEffect, useRef, useState } from 'react'
import { Inbox, ShoppingCart, FileText, Undo2, Landmark, TrendingUp, CalendarRange, Receipt, Coins } from 'lucide-react'
import { fetchSalesSummary, type MeResponse, type SalesInvoiceRecord, type SalesSummary } from '../api'
import type { ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
import { StatCard } from '../components/StatCard'
import { SalesInvoiceForm } from '../components/SalesInvoiceForm'
import { InvoiceList } from '../components/InvoiceList'
import { QuotationForm } from '../components/QuotationForm'
import { QuotationsList } from '../components/QuotationsList'
import { SalesReturnForm } from '../components/SalesReturnForm'
import { MoadianPanel } from '../components/MoadianPanel'
import { OutboxList } from '../components/OutboxList'
import { SectionCard } from '../components/SectionCard'
import { PageHeader } from '../components/PageHeader'
import { Tabs } from '../components/Tabs'
import { isElectron } from '../platform'

export function SalesPage({
  token,
  me,
  warehouses,
  items,
  outbox,
  onQueued,
}: {
  token: string
  me: MeResponse
  warehouses: WarehouseCache[]
  items: ItemCache[]
  outbox: OutboxEntry[]
  onQueued: () => void
}) {
  // شاخص‌ها از سرور می‌آیند (نه با دانلودِ کلِ فاکتورها در کلاینت که کند است و از
  // سقفِ صفحه‌بندی فراتر می‌رود). reloadKey فهرستِ فاکتورها را هم دوباره مونت می‌کند.
  const [summary, setSummary] = useState<SalesSummary | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [prefill, setPrefill] = useState<SalesInvoiceRecord | null>(null)
  const formRef = useRef<HTMLDivElement>(null)
  const refresh = useCallback(() => {
    void fetchSalesSummary(token).then(setSummary).catch(() => {})
    setReloadKey((k) => k + 1)
  }, [token])
  useEffect(() => {
    refresh()
  }, [refresh])
  const handleQueued = useCallback(() => {
    onQueued()
    refresh()
  }, [onQueued, refresh])
  // رونوشت: فاکتور را در فرمِ بالای صفحه پیش‌پر کن و فرم را به دید بیاور.
  const handleDuplicate = useCallback((inv: SalesInvoiceRecord) => {
    setPrefill(inv)
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])
  const fa = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')

  return (
    <div className="page">
      <PageHeader
        icon={ShoppingCart}
        title="فروش"
        description="برای هر فروش یک فاکتور بزنید — موجودی انبار و سند حسابداری آن به‌طور خودکار ثبت می‌شود. بدون اینترنت هم می‌توانید فاکتور بزنید؛ بعداً با «هم‌گام‌سازی» ارسال می‌شود."
      />

      <div className="stat-grid">
        <StatCard icon={<FileText size={18} />} label="تعداد فاکتور فروش" value={(summary?.invoice_count ?? 0).toLocaleString('fa-IR')} />
        <StatCard icon={<TrendingUp size={18} />} label="مجموع فروش" value={fa(summary?.total_with_tax ?? 0)} tone="success" hint="ریال (با مالیات)" />
        <StatCard icon={<Coins size={18} />} label="سود ناخالص" value={fa(summary?.gross_profit ?? 0)} tone="success" hint={`ریال — حاشیه ${Number(summary?.margin_pct ?? 0).toLocaleString('fa-IR')}٪`} />
        <StatCard icon={<CalendarRange size={18} />} label="فروش ۳۰ روز اخیر" value={fa(summary?.last_30_with_tax ?? 0)} hint="ریال" />
        <StatCard icon={<Receipt size={18} />} label="میانگین هر فاکتور" value={fa(summary?.avg_invoice ?? 0)} hint="ریال" />
      </div>

      <Tabs
        tabs={[
          {
            key: 'invoices',
            label: 'فاکتور فروش',
            icon: ShoppingCart,
            content: (
              <>
                <div ref={formRef}>
                  <SalesInvoiceForm
                    token={token}
                    warehouses={warehouses}
                    items={items}
                    onQueued={handleQueued}
                    prefill={prefill}
                    onPrefillConsumed={() => setPrefill(null)}
                  />
                </div>
                <InvoiceList key={reloadKey} token={token} me={me} kind="sales" items={items} onDuplicate={handleDuplicate} />
                {isElectron && (
                  <SectionCard
                    icon={Inbox}
                    title="صف فاکتورهای فروش ارسال‌نشده"
                    description="فاکتورهایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
                  >
                    <OutboxList entries={outbox} emptyHint="فاکتوری در صف نیست." />
                  </SectionCard>
                )}
              </>
            ),
          },
          {
            key: 'quotations',
            label: 'پیش‌فاکتور',
            icon: FileText,
            content: (
              <>
                <QuotationForm token={token} warehouses={warehouses} items={items} onCreated={onQueued} />
                <QuotationsList token={token} onConverted={handleQueued} />
              </>
            ),
          },
          {
            key: 'returns',
            label: 'برگشت از فروش',
            icon: Undo2,
            content: <SalesReturnForm token={token} />,
          },
          {
            key: 'moadian',
            label: 'سامانه مؤدیان',
            icon: Landmark,
            content: <MoadianPanel token={token} />,
          },
        ]}
      />
    </div>
  )
}
