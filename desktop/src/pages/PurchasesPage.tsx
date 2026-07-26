import { useEffect, useMemo, useState } from 'react'
import { Inbox, PackagePlus, Undo2, FileText, TrendingDown, CalendarRange, Receipt } from 'lucide-react'
import { fetchPurchaseInvoices, type MeResponse, type PurchaseInvoiceRecord } from '../api'
import type { ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
import { StatCard } from '../components/StatCard'
import { PurchaseInvoiceForm } from '../components/PurchaseInvoiceForm'
import { InvoiceList } from '../components/InvoiceList'
import { PurchaseReturnForm } from '../components/PurchaseReturnForm'
import { OutboxList } from '../components/OutboxList'
import { SectionCard } from '../components/SectionCard'
import { PageHeader } from '../components/PageHeader'
import { Tabs } from '../components/Tabs'
import { isElectron } from '../platform'

export function PurchasesPage({
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
  const [invoices, setInvoices] = useState<PurchaseInvoiceRecord[]>([])
  useEffect(() => {
    void fetchPurchaseInvoices(token).then(setInvoices).catch(() => {})
  }, [])
  const kpis = useMemo(() => {
    const live = invoices.filter((i) => !i.voided_at)
    const withTax = (i: PurchaseInvoiceRecord) => Number(i.total_amount) + Number(i.tax_amount)
    const total = live.reduce((s, i) => s + withTax(i), 0)
    const cutoff = new Date(Date.now() - 30 * 86_400_000).toISOString().slice(0, 10)
    const last30 = live.filter((i) => i.invoice_date >= cutoff).reduce((s, i) => s + withTax(i), 0)
    const avg = live.length ? Math.round(total / live.length) : 0
    return { count: live.length, total, last30, avg }
  }, [invoices])

  return (
    <div className="page">
      <PageHeader
        icon={PackagePlus}
        title="خرید"
        description="خرید از تأمین‌کننده را اینجا ثبت کنید؛ موجودی انبار افزایش می‌یابد و بهای تمام‌شده‌ی کالا بر اساس آن محاسبه می‌شود."
      />

      <div className="stat-grid">
        <StatCard icon={<FileText size={18} />} label="تعداد فاکتور خرید" value={kpis.count.toLocaleString('fa-IR')} />
        <StatCard icon={<TrendingDown size={18} />} label="مجموع خرید" value={kpis.total.toLocaleString('fa-IR')} hint="تومان (با مالیات)" />
        <StatCard icon={<CalendarRange size={18} />} label="خرید ۳۰ روز اخیر" value={kpis.last30.toLocaleString('fa-IR')} hint="تومان" />
        <StatCard icon={<Receipt size={18} />} label="میانگین هر فاکتور" value={kpis.avg.toLocaleString('fa-IR')} hint="تومان" />
      </div>

      <Tabs
        tabs={[
          {
            key: 'invoices',
            label: 'فاکتور خرید',
            icon: PackagePlus,
            content: (
              <>
                <PurchaseInvoiceForm token={token} warehouses={warehouses} items={items} onQueued={onQueued} />
                <InvoiceList token={token} me={me} kind="purchase" />
                {isElectron && (
                  <SectionCard
                    icon={Inbox}
                    title="صف فاکتورهای خرید ارسال‌نشده"
                    description="فاکتورهایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
                  >
                    <OutboxList entries={outbox} emptyHint="فاکتوری در صف نیست." />
                  </SectionCard>
                )}
              </>
            ),
          },
          {
            key: 'returns',
            label: 'برگشت از خرید',
            icon: Undo2,
            content: <PurchaseReturnForm token={token} items={items} />,
          },
        ]}
      />
    </div>
  )
}
