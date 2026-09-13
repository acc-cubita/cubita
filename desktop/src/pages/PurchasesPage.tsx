import { useCallback, useEffect, useRef, useState } from 'react'
import { Inbox, PackagePlus, PackageCheck, Undo2, FileText, TrendingDown, CalendarRange, Receipt } from 'lucide-react'
import {
  fetchPurchaseInvoiceDuplicate,
  fetchPurchaseSummary,
  type MeResponse,
  type PurchaseInvoiceDuplicateDraft,
  type PurchaseInvoiceRecord,
  type PurchaseSummary,
  type ReceiptPaymentContext,
} from '../api'
import type { ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
import { StatCard } from '../components/StatCard'
import { PurchaseInvoiceForm } from '../components/PurchaseInvoiceForm'
import { PurchaseInvoiceWizard } from '../components/wizard/PurchaseInvoiceWizard'
import { PurchaseReturnWizard } from '../components/wizard/PurchaseReturnWizard'
import { useTheme } from '../lib/theme'
import { InvoiceList, type AnyInvoice } from '../components/InvoiceList'
import { PurchaseReturnForm } from '../components/PurchaseReturnForm'
import { WarehouseReceiptsTab } from '../components/WarehouseReceiptsTab'
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
  onCreatePayment,
  onCreateReceiptPayment,
}: {
  token: string
  me: MeResponse
  warehouses: WarehouseCache[]
  items: ItemCache[]
  outbox: OutboxEntry[]
  onQueued: () => void
  onCreatePayment: (invoice: PurchaseInvoiceRecord) => void
  /** میان‌برِ «اعلامیه پرداخت» از روی رسید — فقط زمینه منتقل می‌شود (§۳۹). */
  onCreateReceiptPayment: (context: ReceiptPaymentContext) => void
}) {
  // شاخص‌ها از سرور می‌آیند (قرینه‌ی صفحه‌ی فروش؛ رفعِ دانلودِ کلِ تاریخچه در کلاینت).
  const [summary, setSummary] = useState<PurchaseSummary | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [prefill, setPrefill] = useState<PurchaseInvoiceDuplicateDraft | null>(null)
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
  const handleDuplicate = useCallback(async (inv: AnyInvoice) => {
    try {
      setPrefill(await fetchPurchaseInvoiceDuplicate(token, inv.id))
      formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'پیش‌نویس رونوشت فاکتور خرید بارگذاری نشد.')
    }
  }, [token])
  const fa = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
  const guided = useTheme().theme.content === 'guided'

  return (
    <div className="page panels">
      <PageHeader
        icon={PackagePlus}
        title="خرید"
        description="فاکتور، بدهی خرید را ثبت می‌کند؛ موجودی فقط با رسید انبار مستقل افزایش می‌یابد و تحویل جزئی نیز پشتیبانی می‌شود."
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
                  {guided ? (
                    <PurchaseInvoiceWizard
                      token={token}
                      warehouses={warehouses}
                      items={items}
                      onQueued={handleQueued}
                      prefill={prefill}
                      onPrefillConsumed={() => setPrefill(null)}
                    />
                  ) : (
                    <PurchaseInvoiceForm
                      token={token}
                      warehouses={warehouses}
                      items={items}
                      onQueued={handleQueued}
                      prefill={prefill}
                      onPrefillConsumed={() => setPrefill(null)}
                    />
                  )}
                </div>
                <InvoiceList key={reloadKey} token={token} me={me} kind="purchase" items={items} warehouses={warehouses} onDuplicate={(invoice) => void handleDuplicate(invoice)} onCreatePayment={onCreatePayment} />
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
            //: رسیدِ انبار دیگر فقط از دلِ یک فاکتور ساخته نمی‌شود: رسیدِ مستقیم، حمل،
            //: برگشتِ رسید، چاپ و میان‌برِ پرداخت همه این‌جا هستند — و دفترِ رسیدها
            //: داخلِ همین تب است، طبقِ قراردادِ ماژول‌های تب‌دار.
            key: 'receipts',
            label: 'رسید انبار',
            icon: PackageCheck,
            content: (
              <WarehouseReceiptsTab
                token={token}
                me={me}
                warehouses={warehouses}
                items={items}
                onChanged={handleQueued}
                onCreatePayment={onCreateReceiptPayment}
              />
            ),
          },
          {
            key: 'returns',
            label: 'برگشت از خرید',
            icon: Undo2,
            content: guided ? <PurchaseReturnWizard token={token} /> : <PurchaseReturnForm token={token} />,
          },
        ]}
      />
    </div>
  )
}
