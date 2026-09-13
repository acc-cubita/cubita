import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X, History } from 'lucide-react'
import { fetchKardex, type KardexReport } from '../api'
import { KardexSummary, KardexTable } from './KardexTable'

/**
 * کاردکسِ یک کالا — تاریخچه‌ی همه‌ی ورود/خروج به ترتیبِ تاریخ، با موجودی و ارزشِ در حال
 * اجرا و بهای هر حرکت. درجا از دفترِ موجودی خوانده می‌شود (همان اندپوینتِ گزارش‌ها) و
 * روی موبایل به‌صورتِ کارت نمایش داده می‌شود تا جدولِ افقی فشرده نشود.
 */
export function KardexDrawer({
  token,
  item,
  onClose,
}: {
  token: string
  item: { id: string; name: string; sku: string }
  onClose: () => void
}) {
  const [data, setData] = useState<KardexReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchKardex(token, item.id)
      .then((r) => { if (alive) setData(r) })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : 'خطای ناشناخته') })
    return () => { alive = false }
  }, [token, item.id])

  // بستن با Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <History size={17} />
            <div>
              <div className="drawer-title-main">کاردکس: {item.name}</div>
              <div className="drawer-title-sub ltr-cell">{item.sku}{data ? ` · ${data.unit}` : ''}</div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
        </div>

        <div className="drawer-body">
          {error && <div className="error">{error}</div>}
          {!data && !error && <p className="muted">در حال بارگذاری…</p>}
          {data && (
            <>
              <KardexSummary data={data} />
              <KardexTable data={data} />
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
