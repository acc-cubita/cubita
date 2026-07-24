import { Inbox, PackagePlus, Undo2 } from 'lucide-react'
import type { MeResponse } from '../api'
import type { ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
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
  return (
    <div className="page">
      <PageHeader
        icon={PackagePlus}
        title="خرید"
        description="خرید از تأمین‌کننده را اینجا ثبت کنید؛ موجودی انبار افزایش می‌یابد و بهای تمام‌شده‌ی کالا بر اساس آن محاسبه می‌شود."
      />
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
