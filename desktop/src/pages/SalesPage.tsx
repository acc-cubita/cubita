import { Inbox, ShoppingCart } from 'lucide-react'
import type { ItemCache, OutboxEntry, WarehouseCache } from '../electron.d'
import { SalesInvoiceForm } from '../components/SalesInvoiceForm'
import { QuotationForm } from '../components/QuotationForm'
import { QuotationsList } from '../components/QuotationsList'
import { SalesReturnForm } from '../components/SalesReturnForm'
import { OutboxList } from '../components/OutboxList'
import { SectionCard } from '../components/SectionCard'
import { PageHeader } from '../components/PageHeader'
import { isElectron } from '../platform'

export function SalesPage({
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
        icon={ShoppingCart}
        title="فروش"
        description="برای هر فروش یک فاکتور بزنید — موجودی انبار و سند حسابداری آن به‌طور خودکار ثبت می‌شود. بدون اینترنت هم می‌توانید فاکتور بزنید؛ بعداً با «هم‌گام‌سازی» ارسال می‌شود."
      />
      <SalesInvoiceForm token={token} warehouses={warehouses} items={items} onQueued={onQueued} />
      {isElectron && (
        <SectionCard
          icon={Inbox}
          title="صف فاکتورهای فروش ارسال‌نشده"
          description="فاکتورهایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
        >
          <OutboxList entries={outbox} emptyHint="فاکتوری در صف نیست." />
        </SectionCard>
      )}
      <QuotationForm token={token} warehouses={warehouses} items={items} onCreated={onQueued} />
      <QuotationsList token={token} onConverted={onQueued} />
      <SalesReturnForm token={token} items={items} />
    </div>
  )
}
