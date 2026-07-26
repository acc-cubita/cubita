import { useEffect, useMemo, useState } from 'react'
import { Inbox, ShoppingCart, FileText, Undo2, Landmark, TrendingUp, CalendarRange, Receipt } from 'lucide-react'
import { fetchSalesInvoices, type MeResponse, type SalesInvoiceRecord } from '../api'
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
  const [invoices, setInvoices] = useState<SalesInvoiceRecord[]>([])
  useEffect(() => {
    void fetchSalesInvoices(token).then(setInvoices).catch(() => {})
  }, [])
  const kpis = useMemo(() => {
    const live = invoices.filter((i) => !i.voided_at)
    const withTax = (i: SalesInvoiceRecord) => Number(i.total_amount) + Number(i.tax_amount)
    const total = live.reduce((s, i) => s + withTax(i), 0)
    const cutoff = new Date(Date.now() - 30 * 86_400_000).toISOString().slice(0, 10)
    const last30 = live.filter((i) => i.invoice_date >= cutoff).reduce((s, i) => s + withTax(i), 0)
    const avg = live.length ? Math.round(total / live.length) : 0
    return { count: live.length, total, last30, avg }
  }, [invoices])

  return (
    <div className="page">
      <PageHeader
        icon={ShoppingCart}
        title="فروش"
        description="برای هر فروش یک فاکتور بزنید — موجودی انبار و سند حسابداری آن به‌طور خودکار ثبت می‌شود. بدون اینترنت هم می‌توانید فاکتور بزنید؛ بعداً با «هم‌گام‌سازی» ارسال می‌شود."
      />

      <div className="stat-grid">
        <StatCard icon={<FileText size={18} />} label="تعداد فاکتور فروش" value={kpis.count.toLocaleString('fa-IR')} />
        <StatCard icon={<TrendingUp size={18} />} label="مجموع فروش" value={kpis.total.toLocaleString('fa-IR')} tone="success" hint="تومان (با مالیات)" />
        <StatCard icon={<CalendarRange size={18} />} label="فروش ۳۰ روز اخیر" value={kpis.last30.toLocaleString('fa-IR')} hint="تومان" />
        <StatCard icon={<Receipt size={18} />} label="میانگین هر فاکتور" value={kpis.avg.toLocaleString('fa-IR')} hint="تومان" />
      </div>

      <Tabs
        tabs={[
          {
            key: 'invoices',
            label: 'فاکتور فروش',
            icon: ShoppingCart,
            content: (
              <>
                <SalesInvoiceForm token={token} warehouses={warehouses} items={items} onQueued={onQueued} />
                <InvoiceList token={token} me={me} kind="sales" />
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
                <QuotationsList token={token} onConverted={onQueued} />
              </>
            ),
          },
          {
            key: 'returns',
            label: 'برگشت از فروش',
            icon: Undo2,
            content: <SalesReturnForm token={token} items={items} />,
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
