import { useCallback, useRef, useState } from 'react'
import { FileText, Inbox, ShoppingCart, Undo2 } from 'lucide-react'
import type { ItemCache, OutboxEntry, WarehouseCache } from '../../electron.d'
import type { SalesInvoiceRecord, SalesQuotationRecord } from '../../api'
import { SalesInvoiceForm } from '../../components/SalesInvoiceForm'
import { SalesInvoiceWizard } from '../../components/wizard/SalesInvoiceWizard'
import { SalesReturnForm } from '../../components/SalesReturnForm'
import { SalesReturnWizard } from '../../components/wizard/SalesReturnWizard'
import { QuotationForm } from '../../components/QuotationForm'
import { QuotationWizard } from '../../components/wizard/QuotationWizard'
import { QuotationsList } from '../../components/QuotationsList'
import { OutboxList } from '../../components/OutboxList'
import { SectionCard } from '../../components/SectionCard'
import { OpsPage } from '../accounting/kit'
import { useTheme } from '../../lib/theme'
import { isElectron } from '../../platform'

/**
 * سه سندِ فروش و دفترِ پیش‌فاکتور.
 *
 * **این‌ها فرمِ تازه نیستند** — همان فرم‌های آزموده‌ی صفحه‌ی تب‌دارِ قبلی‌اند که حالا
 * هرکدام صفحه‌ی خودشان را دارند. بازنویسی‌شان یعنی دور ریختنِ ویزاردها، مدیریتِ صفِ
 * آفلاین و منطقِ رونوشت که همه کار می‌کردند.
 *
 * تقسیمِ پیش‌فاکتور به دو صفحه (فرم اینجا، دفتر در کارتِ فهرست) همان کاری است که
 * برای «سند حسابداری» شد: یک نمای داده، نه دو تا.
 */

// ═══════════════════ فاکتور فروش ═══════════════════

export function SalesInvoicePage({
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
  const guided = useTheme().theme.content === 'guided'
  const [prefill, setPrefill] = useState<SalesInvoiceRecord | null>(null)
  const formRef = useRef<HTMLDivElement>(null)

  return (
    <OpsPage
      icon={ShoppingCart}
      title="فاکتور فروش"
      description="صدورِ فاکتور. موجودیِ انبار و سند حسابداری همان لحظه خودکار ثبت می‌شوند. دفترِ کاملِ فاکتورها زیرِ کارتِ «فهرست» است."
    >
      <div ref={formRef}>
        {guided ? (
          <SalesInvoiceWizard
            token={token}
            warehouses={warehouses}
            items={items}
            onQueued={onQueued}
            prefill={prefill}
            onPrefillConsumed={() => setPrefill(null)}
          />
        ) : (
          <SalesInvoiceForm
            token={token}
            warehouses={warehouses}
            items={items}
            onQueued={onQueued}
            prefill={prefill}
            onPrefillConsumed={() => setPrefill(null)}
          />
        )}
      </div>

      {isElectron && (
        <SectionCard
          icon={Inbox}
          title="صف فاکتورهای ارسال‌نشده"
          description="فاکتورهایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
        >
          <OutboxList entries={outbox} emptyHint="فاکتوری در صف نیست." />
        </SectionCard>
      )}
    </OpsPage>
  )
}

// ═══════════════════ پیش‌فاکتور ═══════════════════

export function QuotationPage({
  token,
  warehouses,
  items,
  onQueued,
}: {
  token: string
  warehouses: WarehouseCache[]
  items: ItemCache[]
  onQueued: () => void
}) {
  const guided = useTheme().theme.content === 'guided'
  return (
    <OpsPage
      icon={FileText}
      title="پیش‌فاکتور"
      description="صدورِ پیش‌فاکتور برای مشتری. تبدیلش به فاکتور از دفترِ «پیش‌فاکتورها» در کارتِ فهرست انجام می‌شود."
    >
      {guided ? (
        <QuotationWizard
          token={token}
          warehouses={warehouses}
          items={items}
          onCreated={onQueued}
          editing={null}
          onDoneEditing={() => {}}
        />
      ) : (
        <QuotationForm
          token={token}
          warehouses={warehouses}
          items={items}
          onCreated={onQueued}
          editing={null}
          onDoneEditing={() => {}}
        />
      )}
    </OpsPage>
  )
}

/** دفترِ پیش‌فاکتورها — با کنشِ تبدیل به فاکتور، چون همان‌جا لازم می‌شود. */
export function QuotationListPage({ token, onQueued }: { token: string; onQueued: () => void }) {
  const [reloadKey, setReloadKey] = useState(0)
  const afterChange = useCallback(() => {
    onQueued()
    setReloadKey((k) => k + 1)
  }, [onQueued])

  return (
    <OpsPage
      icon={FileText}
      title="پیش‌فاکتورها"
      description="دفترِ پیش‌فاکتورهای صادرشده. از همین‌جا می‌توان یکی را به فاکتورِ فروش تبدیل کرد."
    >
      <QuotationsList
        key={reloadKey}
        token={token}
        onConverted={afterChange}
        //: ویرایش در صفحه‌ی عملیات انجام می‌شود؛ اینجا فقط مرور و تبدیل.
        onEdit={(_q: SalesQuotationRecord) => {}}
      />
    </OpsPage>
  )
}

// ═══════════════════ فاکتور برگشتی ═══════════════════

export function SalesReturnPage({ token }: { token: string }) {
  const guided = useTheme().theme.content === 'guided'
  return (
    <OpsPage
      icon={Undo2}
      title="فاکتور برگشتی"
      description="برگشت از فروش. موجودی برمی‌گردد و سندِ معکوس ثبت می‌شود. دفترِ برگشتی‌ها زیرِ کارتِ «فهرست» است."
    >
      {guided ? <SalesReturnWizard token={token} /> : <SalesReturnForm token={token} />}
    </OpsPage>
  )
}
