import { useCallback, useEffect, useMemo, useState } from 'react'
import { MapPin, Plus, Trash2, RotateCcw } from 'lucide-react'
import {
  createWarehouseLocation,
  deleteWarehouseLocation,
  fetchWarehouseLocations,
  fetchWarehousesLive,
  updateWarehouseLocation,
  type WarehouseLocationRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { SearchSelect } from '../components/SearchSelect'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * موقعیتِ قرارگیری داخلِ انبار — راهرو/قفسه/طبقه.
 *
 * **چرا لازم شد:** برگه‌ی جمع‌آوری می‌توانست بگوید «۱۰۰ عدد شیر از بارِ B001»
 * ولی نمی‌توانست بگوید کجاست، و انباردار باید حفظ می‌بود.
 *
 * فقط «کد» اجباری است. انبارِ کوچک همان یک رشته را می‌نویسد و بقیه را خالی
 * می‌گذارد؛ انبارِ بزرگ راهرو/قفسه/طبقه را جدا پر می‌کند تا بعداً بشود مرتب کرد.
 */
export function WarehouseLocationsPanel({ token }: { token: string }) {
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [rows, setRows] = useState<WarehouseLocationRecord[] | null>(null)
  const [warehouseId, setWarehouseId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [aisle, setAisle] = useState('')
  const [rack, setRack] = useState('')
  const [level, setLevel] = useState('')

  const shown = useMemo(
    () => (rows ?? []).filter((r) => !warehouseId || r.warehouse_id === warehouseId),
    [rows, warehouseId],
  )
  const pg = usePagination(shown, 10)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [ws, ls] = await Promise.all([fetchWarehousesLive(token), fetchWarehouseLocations(token)])
      setWarehouses(ws)
      setRows(ls)
      setWarehouseId((cur) => cur || ws[0]?.id || '')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!warehouseId || !code.trim()) {
      setMsg('انبار و کدِ موقعیت الزامی است.')
      return
    }
    try {
      await createWarehouseLocation(token, {
        warehouse_id: warehouseId,
        code: code.trim(),
        name: name.trim(),
        aisle: aisle.trim(),
        rack: rack.trim(),
        level: level.trim(),
      })
      setCode('')
      setName('')
      setAisle('')
      setRack('')
      setLevel('')
      setMsg('موقعیت ثبت شد.')
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function remove(row: WarehouseLocationRecord) {
    try {
      await deleteWarehouseLocation(token, row.id)
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function reactivate(row: WarehouseLocationRecord) {
    await updateWarehouseLocation(token, row.id, { is_active: true })
    await refresh()
  }

  const warehouseName = useMemo(
    () => new Map(warehouses.map((w) => [w.id, w.name])),
    [warehouses],
  )

  return (
    <div className="workspace-split">
      <SectionCard
        icon={Plus}
        title="ثبتِ موقعیت"
        description="کد همان چیزی است که روی قفسه نوشته‌اید — مثلاً A-02-04. بقیه‌ی فیلدها اختیاری‌اند."
      >
        <form className="invoice-form form-full" onSubmit={submit}>
          <label>
            انبار
            <SearchSelect value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} required>
              <option value="">— انتخاب —</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </SearchSelect>
          </label>
          <div className="field-row">
            <label>
              کدِ موقعیت
              <input type="text" value={code} onChange={(e) => setCode(e.target.value)} placeholder="A-02-04" />
            </label>
            <label>
              عنوان
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="اختیاری" />
            </label>
          </div>
          <div className="field-row">
            <label>
              راهرو
              <input type="text" value={aisle} onChange={(e) => setAisle(e.target.value)} placeholder="اختیاری" />
            </label>
            <label>
              قفسه
              <input type="text" value={rack} onChange={(e) => setRack(e.target.value)} placeholder="اختیاری" />
            </label>
            <label>
              طبقه
              <input type="text" value={level} onChange={(e) => setLevel(e.target.value)} placeholder="اختیاری" />
            </label>
          </div>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><Plus size={14} /> ثبتِ موقعیت</button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </form>
      </SectionCard>

      <SectionCard
        icon={MapPin}
        title="موقعیت‌های انبار"
        description="موقعیتی که باری رویش نشسته حذف نمی‌شود، غیرفعال می‌شود — وگرنه آن بارها محلشان را گم می‌کنند."
      >
        {error && <div className="error">{error}</div>}
        {rows === null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : shown.length === 0 ? (
          <EmptyState icon={MapPin} text="موقعیتی تعریف نشده — با فرمِ کنار اولین قفسه را ثبت کنید." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr><th>کد</th><th>انبار</th><th>عنوان</th><th>راهرو</th><th>قفسه</th><th>طبقه</th><th>بار</th><th>وضعیت</th><th></th></tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title ltr-cell" data-label="کد">{r.code}</td>
                      <td data-label="انبار">{warehouseName.get(r.warehouse_id) ?? '—'}</td>
                      <td data-label="عنوان">{r.name || '—'}</td>
                      <td data-label="راهرو">{r.aisle || '—'}</td>
                      <td data-label="قفسه">{r.rack || '—'}</td>
                      <td data-label="طبقه">{r.level || '—'}</td>
                      <td className="num" data-label="بار">{r.batch_count > 0 ? fa(r.batch_count) : '—'}</td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${r.is_active ? 'tone-success' : 'tone-muted'}`}>
                          {r.is_active ? 'فعال' : 'غیرفعال'}
                        </span>
                      </td>
                      <td className="card-actions">
                        {r.is_active ? (
                          <button type="button" className="icon-btn-danger" onClick={() => void remove(r)}>
                            <Trash2 size={13} /> {r.batch_count > 0 ? 'غیرفعال‌سازی' : 'حذف'}
                          </button>
                        ) : (
                          <button type="button" onClick={() => void reactivate(r)}>
                            <RotateCcw size={13} /> فعال‌سازی
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}
