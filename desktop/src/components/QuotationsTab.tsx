import { useRef, useState } from 'react'
import type { ItemCache, WarehouseCache } from '../electron.d'
import type { SalesQuotationRecord } from '../api'
import { QuotationForm } from './QuotationForm'
import { QuotationWizard } from './wizard/QuotationWizard'
import { QuotationsList } from './QuotationsList'
import { useTheme } from '../lib/theme'

/**
 * تبِ پیش‌فاکتور: فرمِ ثبت/ویرایش + فهرست را کنارِ هم می‌گذارد و حالتِ ویرایش را نگه می‌دارد.
 * با کلیکِ «ویرایش» در فهرست، همان پیش‌فاکتور در فرمِ بالا بار می‌شود و فرم به دید می‌آید؛
 * پس از ذخیره، فهرست با تغییرِ key دوباره مونت و تازه می‌شود.
 */
export function QuotationsTab({
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
  const [editing, setEditing] = useState<SalesQuotationRecord | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const topRef = useRef<HTMLDivElement>(null)
  const guided = useTheme().theme.content === 'guided'

  function afterChange() {
    onQueued()
    setReloadKey((k) => k + 1)
  }

  function startEdit(quotation: SalesQuotationRecord) {
    setEditing(quotation)
    topRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div ref={topRef}>
      {guided ? (
        <QuotationWizard
          token={token}
          warehouses={warehouses}
          items={items}
          onCreated={afterChange}
          editing={editing}
          onDoneEditing={() => setEditing(null)}
        />
      ) : (
        <QuotationForm
          token={token}
          warehouses={warehouses}
          items={items}
          onCreated={afterChange}
          editing={editing}
          onDoneEditing={() => setEditing(null)}
        />
      )}
      <QuotationsList key={reloadKey} token={token} onConverted={afterChange} onEdit={startEdit} />
    </div>
  )
}
