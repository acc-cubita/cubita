import { useCallback, useEffect, useState } from 'react'
import { Warehouse, Plus, Save, Pencil, X, RefreshCw } from 'lucide-react'
import { fetchWarehousesAdmin, createWarehouse, updateWarehouse, type WarehouseRecord } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'

/**
 * مدیریتِ انبارها — فهرست، ساختِ انبارِ تازه، تغییرِ نام و فعال/غیرفعال‌سازی.
 * کد پس از ساخت ثابت است (روی حرکاتِ انبار و اسناد نشسته)، پس فقط نام قابلِ ویرایش است.
 */
export function WarehousesPanel({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [rows, setRows] = useState<WarehouseRecord[] | null>(null)
  const pg = usePagination(rows ?? [], 10)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setRows(await fetchWarehousesAdmin(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!code.trim() || !name.trim()) { setMessage('کد و نام انبار الزامی است.'); return }
    setSaving(true)
    try {
      await createWarehouse(token, { code: code.trim(), name: name.trim() })
      setCode(''); setName('')
      setMessage('انبار ساخته شد.')
      await refresh()
      onChanged?.()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setSaving(false)
    }
  }

  async function saveRename(w: WarehouseRecord) {
    if (!editName.trim()) return
    try {
      await updateWarehouse(token, w.id, { name: editName.trim() })
      setEditId(null)
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function toggleActive(w: WarehouseRecord) {
    try {
      await updateWarehouse(token, w.id, { is_active: !w.is_active })
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={Plus} title="انبارِ جدید" description="یک انبار/شعبه‌ی تازه با کدِ یکتا بسازید.">
        <form className="invoice-form form-full" onSubmit={handleCreate}>
          <div className="field-row">
            <label>کد انبار<input value={code} onChange={(e) => setCode(e.target.value)} placeholder="مثلاً SHOP2" /></label>
            <label>نام انبار<input value={name} onChange={(e) => setName(e.target.value)} placeholder="مثلاً انبارِ شعبه ۲" /></label>
          </div>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={saving}><Save size={14} /> ثبت انبار</button>
          </div>
          {message && <div className="hint">{message}</div>}
          <p className="hint">کد پس از ساخت ثابت می‌ماند (روی حرکاتِ انبار نشسته)؛ فقط نام بعداً قابلِ تغییر است.</p>
        </form>
      </SectionCard>

      <SectionCard
        icon={Warehouse}
        title="انبارها"
        description={rows ? `${rows.length.toLocaleString('fa-IR')} انبار` : ''}
        actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
      >
        {error && <div className="error">{error}</div>}
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState icon={Warehouse} text="هنوز انباری ساخته نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table wh-table cards-on-mobile">
                <thead>
                  <tr><th>کد</th><th>نام</th><th>وضعیت</th><th></th></tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((w) => (
                    <tr key={w.id}>
                      <td data-label="کد" className="ltr-cell">{w.code}</td>
                      <td data-label="نام" className="entity-name">
                        {editId === w.id ? (
                          <input value={editName} onChange={(e) => setEditName(e.target.value)} autoFocus />
                        ) : (
                          w.name
                        )}
                      </td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${w.is_active ? 'tone-success' : 'tone-warning'}`}>
                          {w.is_active ? 'فعال' : 'غیرفعال'}
                        </span>
                      </td>
                      <td className="check-actions card-actions">
                        {editId === w.id ? (
                          <>
                            <button type="button" onClick={() => void saveRename(w)}><Save size={13} /> ذخیره</button>
                            <button type="button" onClick={() => setEditId(null)}><X size={13} /> انصراف</button>
                          </>
                        ) : (
                          <>
                            <button type="button" onClick={() => { setEditId(w.id); setEditName(w.name) }}><Pencil size={13} /> ویرایش نام</button>
                            <button type="button" onClick={() => void toggleActive(w)}>{w.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}</button>
                          </>
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
