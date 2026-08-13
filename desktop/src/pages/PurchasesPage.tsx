import { useCallback, useEffect, useRef, useState } from 'react'
import { Inbox, PackagePlus, Undo2, FileText, TrendingDown, CalendarRange, Receipt } from 'lucide-react'
import { fetchPurchaseSummary, type MeResponse, type PurchaseInvoiceRecord, type PurchaseSummary } from '../api'
import type { ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
import { StatCard } from '../components/StatCard'
import { PurchaseInvoiceForm } from '../components/PurchaseInvoiceForm'
import { InvoiceList, type AnyInvoice } from '../components/InvoiceList'
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
  // شاخص‌ها از سرور می‌آیند (قرینه‌ی صفحه‌ی فروش؛ رفعِ دانلودِ کلِ تاریخچه در کلاینت).
  const [summary, setSummary] = useState<PurchaseSummary | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [prefill, setPrefill] = useState<PurchaseInvoiceRecord | null>(null)
  const formRef = useRef<HTMLDivElement>(null)
  const refresh = useCallback(() => {
    void fetchPurchaseSummary(token).then(setSummary).catch(() => {})
    setReloadKey((k) => k + 1)
  }, [token])
  useEffect(() => {
    refresh()
  }, [refresh])
  const handleQueued = useCallback(() => {
    onQueued()
    refresh()
  }, [onQueued, refresh])
  const handleDuplicate = useCallback((inv: AnyInvoice) => {
    setPrefill(inv as PurchaseInvoiceRecord)
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])
  const fa = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')

  return (
    <div className="page panels">
      <PageHeader
        icon={PackagePlus}
        title="خرید"
        description="خرید از تأمین‌کننده را اینجا ثبت کنید؛ موجودی انبار افزایش می‌یابد و بهای تمام‌شده‌ی کالا بر اساس آن محاسبه می‌شود."
      />

      <div className="stat-grid">
        <StatCard icon={<FileText size={18} />} label="تعداد فاکتور خرید" value={(summary?.invoice_count ?? 0).toLocaleString('fa-IR')} />
        <StatCard icon={<TrendingDown size={18} />} label="مجموع خرید" value={fa(summary?.total_with_tax ?? 0)} hint="ریال (با مالیات)" />
        <StatCard icon={<CalendarRange size={18} />} label="خرید ۳۰ روز اخیر" value={fa(summary?.last_30_with_tax ?? 0)} hint="ریال" />
        <StatCard icon={<Receipt size={18} />} label="میانگین هر فاکتور" value={fa(summary?.avg_invoice ?? 0)} hint="ریال" />
      </div>

      <Tabs
        syncPage="purchases"
        tabs={[
          {
            key: 'invoices',
            label: 'فاکتور خرید',
            icon: PackagePlus,
            content: (
              <>
                <div ref={formRef}>
                  <PurchaseInvoiceForm
                    token={token}
                    warehouses={warehouses}
                    items={items}
                    onQueued={handleQueued}
                    prefill={prefill}
                    onPrefillConsumed={() => setPrefill(null)}
                  />
                </div>
                <InvoiceList key={reloadKey} token={token} me={me} kind="purchase" items={items} onDuplicate={handleDuplicate} />
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
            content: <PurchaseReturnForm token={token} />,
          },
        ]}
      />
    </div>
  )
}
