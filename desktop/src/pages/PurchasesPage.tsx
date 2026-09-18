import { useCallback, useEffect, useRef, useState } from 'react'
import { ClipboardList, Inbox, PackagePlus, PackageCheck, Undo2, FileText, TrendingDown, CalendarRange, Receipt, Briefcase, Percent } from 'lucide-react'
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
import { ServicePurchaseTab } from '../components/ServicePurchaseTab'
import { PurchaseDeductionTypesPanel } from '../components/PurchaseDeductionTypesPanel'
import { OutboxList } from '../components/OutboxList'
import { SectionCard } from '../components/SectionCard'
import { PageHeader } from '../components/PageHeader'
import { Tabs } from '../components/Tabs'
import { useNavSection } from '../components/navContext'
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
  //: فرم و دفترِ فاکتورها حالا دو تب‌اند (عملیات/فهرست). «رونوشت» از دفتر پیش‌نویس را
  //: می‌گذارد و کاربر را به تبِ فرم می‌برد؛ فرم با mount شدن مصرفش می‌کند.
  const nav = useNavSection()
  const [serviceDup, setServiceDup] = useState<AnyInvoice | null>(null)
  const clearServiceDup = useCallback(() => setServiceDup(null), [])
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
      nav?.setSection('invoices')
      formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'پیش‌نویس رونوشت فاکتور خرید بارگذاری نشد.')
    }
  }, [token, nav])
  const fa = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
  const guided = useTheme().theme.content === 'guided'

  return (
    <div className="page panels">
      <PageHeader
        icon={PackagePlus}
        title="خرید"
        description="فاکتور خرید بدهی را ثبت می‌کند و کالا با رسید انبار وارد می‌شود؛ خرید خدمت هزینه و کسوراتش را همان لحظه ثبت می‌کند."
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
            //: فاکتور خرید خدمات سندِ مستقل است (سریِ شماره، چاپ و دفترِ خودش) ولی
            //: موتورش همان فاکتور خرید است؛ فرم و دفترش هر دو داخلِ همین تب‌اند.
            key: 'services',
            label: 'فاکتور خرید خدمات',
            icon: Briefcase,
            content: (
              <ServicePurchaseTab
                token={token}
                me={me}
                items={items}
                onChanged={handleQueued}
                onCreatePayment={onCreatePayment}
                view="form"
                duplicateOf={serviceDup}
                onDuplicateTaken={clearServiceDup}
              />
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
                view="form"
              />
            ),
          },
          {
            key: 'returns',
            label: 'برگشت از خرید',
            icon: Undo2,
            content: guided ? <PurchaseReturnWizard token={token} /> : <PurchaseReturnForm token={token} />,
          },
          {
            key: 'deductions',
            label: 'انواع کسورات',
            icon: Percent,
            content: <PurchaseDeductionTypesPanel token={token} me={me} />,
          },
          {
            //: دفترِ فاکتورهای خرید — پیش‌تر زیرِ فرمِ «فاکتور خرید» بود.
            key: 'invoice-list',
            label: 'فاکتورهای خرید',
            icon: ClipboardList,
            content: (
              <InvoiceList key={reloadKey} token={token} me={me} kind="purchase" purchaseKind="goods" items={items} warehouses={warehouses} onDuplicate={(invoice) => void handleDuplicate(invoice)} onCreatePayment={onCreatePayment} />
            ),
          },
          {
            key: 'service-list',
            label: 'فاکتورهای خرید خدمات',
            icon: FileText,
            content: (
              <ServicePurchaseTab
                token={token}
                me={me}
                items={items}
                onChanged={handleQueued}
                onCreatePayment={onCreatePayment}
                view="ledger"
                onDuplicate={(invoice) => {
                  setServiceDup(invoice)
                  nav?.setSection('services')
                }}
              />
            ),
          },
        ]}
      />
    </div>
  )
}
