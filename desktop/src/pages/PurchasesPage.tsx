import { Inbox, PackagePlus } from 'lucide-react'
import type { ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
import { PurchaseInvoiceForm } from '../components/PurchaseInvoiceForm'
import { PurchaseReturnForm } from '../components/PurchaseReturnForm'
import { OutboxList } from '../components/OutboxList'
import { SectionCard } from '../components/SectionCard'
import { PageHeader } from '../components/PageHeader'
import { isElectron } from '../platform'

export function PurchasesPage({
  token,
  warehouses,
  items,
  outbox,
  onQueued,
}: {
  token: string
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
      <PurchaseInvoiceForm token={token} warehouses={warehouses} items={items} onQueued={onQueued} />
      {isElectron && (
        <SectionCard
          icon={Inbox}
          title="صف فاکتورهای خرید ارسال‌نشده"
          description="فاکتورهایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
        >
          <OutboxList entries={outbox} emptyHint="فاکتوری در صف نیست." />
        </SectionCard>
      )}
      <PurchaseReturnForm token={token} items={items} />
    </div>
  )
}
