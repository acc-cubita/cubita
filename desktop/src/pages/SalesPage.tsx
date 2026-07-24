import { Inbox, ShoppingCart, FileText, Undo2 } from 'lucide-react'
import type { MeResponse } from '../api'
import type { ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
import { SalesInvoiceForm } from '../components/SalesInvoiceForm'
import { InvoiceList } from '../components/InvoiceList'
import { QuotationForm } from '../components/QuotationForm'
import { QuotationsList } from '../components/QuotationsList'
import { SalesReturnForm } from '../components/SalesReturnForm'
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
  return (
    <div className="page">
      <PageHeader
        icon={ShoppingCart}
        title="فروش"
        description="برای هر فروش یک فاکتور بزنید — موجودی انبار و سند حسابداری آن به‌طور خودکار ثبت می‌شود. بدون اینترنت هم می‌توانید فاکتور بزنید؛ بعداً با «هم‌گام‌سازی» ارسال می‌شود."
      />
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
        ]}
      />
    </div>
  )
}
