import { useCallback, useEffect, useMemo, useState } from 'react'
import { X, Layers, Plus, Power, AlertTriangle } from 'lucide-react'
import {
  allocateBatchToListing,
  fetchAvailableBatches,
  fetchCatalogAllocations,
  toggleCatalogAllocation,
  type CatalogAllocation,
  type Listing,
  type StockBatchRecord,
} from '../api'
import { EmptyState } from './EmptyState'
import { NumberInput } from './NumberInput'
import { SearchSelect } from '../components/SearchSelect'
import { formatJalali } from '../lib/jalali'

const fa = (n: number | string) => Number(n).toLocaleString('fa-IR')

const STATUS_LABEL: Record<string, string> = {
  available: 'قابلِ فروش',
  near_expiry: 'نزدیکِ انقضا',
  qc_pending: 'در انتظارِ کنترل',
  blocked: 'مسدود',
  recalled: 'فراخوان‌شده',
  expired: 'منقضی',
  depleted: 'تمام‌شده',
  closed: 'بسته',
  partially_reserved: 'بخشی رزرو',
  fully_reserved: 'کاملاً رزرو',
  draft: 'پیش‌نویس',
}

/**
 * «از کدام بار، چه‌قدر در کاتالوگ عرضه شود» (§۶).
 *
 * بارِ ۱۰۰۰تایی در انبار لزوماً یعنی ۱۰۰۰ تا برای فروشِ عمده نیست — مدیرِ پخش
 * ممکن است بخواهد بقیه را برای مشتریِ قدیمی یا شعبه‌ی دیگر نگه دارد.
 *
 * **تخصیصِ نداشتن یعنی بی‌سقف**، نه صفر: لیستینگی که هیچ تخصیصی نگرفته دقیقاً
 * مثلِ دیروز کلِ موجودی را عرضه می‌کند.
 */
export function CatalogAllocationDrawer({
  token,
  listing,
  warehouseId,
  onClose,
}: {
  token: string
  listing: Listing
  warehouseId: string
  onClose: () => void
}) {
  const [rows, setRows] = useState<CatalogAllocation[] | null>(null)
  const [batches, setBatches] = useState<StockBatchRecord[]>([])
  const [batchId, setBatchId] = useState('')
  const [qty, setQty] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  //: اجزای لیستینگ — بارها فقط از کالاهای همین اجزا می‌آیند.
  const itemIds = useMemo(
    () => listing.components.map((c) => c.item_id).filter(Boolean),
    [listing],
  )

  const refresh = useCallback(async () => {
    setMsg(null)
    try {
      const [allocs, ...perItem] = await Promise.all([
        fetchCatalogAllocations(token, listing.id),
        ...itemIds.map((id) => fetchAvailableBatches(token, id, warehouseId).catch(() => [])),
      ])
      setRows(allocs)
      setBatches(perItem.flat())
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token, listing.id, itemIds, warehouseId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!batchId || Number(qty) <= 0) {
      setMsg('بار و مقدار را مشخص کنید.')
      return
    }
    setBusy(true)
    try {
      await allocateBatchToListing(token, listing.id, batchId, Number(qty))
      setQty('')
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  async function toggle(row: CatalogAllocation) {
    setBusy(true)
    try {
      await toggleCatalogAllocation(token, row.id, !row.is_active)
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <div className="drawer-title-main">{listing.title}</div>
            <div className="drawer-title-sub">تخصیصِ بار به کاتالوگ</div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
        </div>

        <div className="drawer-body">
          {msg && <div className="hint">{msg}</div>}
          <p className="hint">
            تا وقتی هیچ باری تخصیص ندهید، کلِ موجودیِ انبار در کاتالوگ عرضه می‌شود. با تخصیص،
            فقط همان مقدار قابلِ سفارش می‌شود.
          </p>

          <form className="invoice-form form-full" onSubmit={submit}>
            <div className="field-row">
              <label>
                بار
                <SearchSelect value={batchId} onChange={(e) => setBatchId(e.target.value)}>
                  <option value="">— انتخاب —</option>
                  {batches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.batch_number} — قابلِ فروش {fa(b.sellable_qty)}
                      {b.expiry_date ? ` — انقضا ${formatJalali(b.expiry_date)}` : ''}
                    </option>
                  ))}
                </SearchSelect>
              </label>
              <label>
                مقدارِ عرضه
                <NumberInput allowDecimal value={qty} onChange={setQty} />
              </label>
            </div>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}><Plus size={14} /> تخصیص</button>
            </div>
          </form>

          <section className="drawer-section">
            <h4><Layers size={15} /> بارهای تخصیص‌داده‌شده</h4>
            {rows === null ? (
              <p className="muted">در حال بارگذاری…</p>
            ) : rows.length === 0 ? (
              <EmptyState icon={Layers} text="باری تخصیص داده نشده — کلِ موجودی عرضه می‌شود." />
            ) : (
              <div className="table-scroll">
                <table className="entity-table cards-on-mobile">
                  <thead>
                    <tr><th>بار</th><th>کالا</th><th>انقضا</th><th>عرضه</th><th>قابلِ فروشِ بار</th><th>وضعیت</th><th></th></tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const dead = Number(r.batch_sellable_qty) <= 0
                      return (
                        <tr key={r.id}>
                          <td className="card-title ltr-cell" data-label="بار">{r.batch_number}</td>
                          <td data-label="کالا">{r.item_name}</td>
                          <td data-label="انقضا">{r.expiry_date ? formatJalali(r.expiry_date) : '—'}</td>
                          <td className="num" data-label="عرضه">{fa(r.qty)}</td>
                          <td className="num" data-label="قابلِ فروشِ بار">
                            {dead ? <strong className="stock-over">{fa(r.batch_sellable_qty)}</strong> : fa(r.batch_sellable_qty)}
                          </td>
                          <td data-label="وضعیت">
                            <span className={`status-badge ${dead ? 'tone-danger' : r.is_active ? 'tone-success' : 'tone-muted'}`}>
                              {dead && <AlertTriangle size={12} />}
                              {r.is_active ? (STATUS_LABEL[r.batch_status] ?? r.batch_status) : 'خاموش'}
                            </span>
                          </td>
                          <td className="card-actions">
                            <button type="button" disabled={busy} onClick={() => void toggle(r)}>
                              <Power size={13} /> {r.is_active ? 'خاموش' : 'روشن'}
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
