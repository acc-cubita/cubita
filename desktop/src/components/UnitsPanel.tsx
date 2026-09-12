import { useCallback, useEffect, useState } from 'react'
import { Ruler, Plus, Save, Pencil, X, RefreshCw, Trash2, AlertTriangle } from 'lucide-react'
import { createUnit, deleteUnit, fetchUnits, updateUnit, type UnitRecord } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'

const faMoney = (n: number) => n.toLocaleString('fa-IR')

/**
 * واحدهای سنجش — داده‌ی پایه‌ی مشترکِ خرید، فروش، انبار و صندوق.
 *
 * **چرا فهرست شد و نه متنِ آزاد:** تا امروز واحد یک رشته بود که کاربر هر بار
 * تایپ می‌کرد، پس «کیلوگرم» و «كيلوگرم» (با کاف و یای عربی) دو واحدِ متفاوت
 * می‌شدند — و نگاشتِ کدِ واحدِ سامانه‌ی مؤدیان، که روی همان نوشتار کلید می‌خورد،
 * برای هر املا جدا لازم می‌شد.
 *
 * واحد **موجودی نیست**: خدمت هم می‌تواند واحد داشته باشد («ساعت» برای مشاوره)
 * بی‌آنکه چیزی وارد انبار شود.
 */
export function UnitsPanel({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [rows, setRows] = useState<UnitRecord[] | null>(null)
  const pg = usePagination(rows ?? [], 12)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [draft, setDraft] = useState({ name: '', name2: '' })
  const [saving, setSaving] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [edit, setEdit] = useState({ name: '', name2: '' })

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setRows(await fetchUnits(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!draft.name.trim()) { setMessage('نامِ واحد الزامی است.'); return }
    setSaving(true)
    try {
      await createUnit(token, { name: draft.name.trim(), name2: draft.name2.trim() })
      setDraft({ name: '', name2: '' })
      setMessage('واحد ساخته شد.')
      await refresh()
      onChanged?.()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setSaving(false)
    }
  }

  async function saveEdit() {
    if (!editId || !edit.name.trim()) return
    setError(null)
    try {
      await updateUnit(token, editId, { name: edit.name.trim(), name2: edit.name2.trim() })
      setEditId(null)
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  /**
   * غیرفعال‌سازی — واحدی که روی کالایی نشسته رد می‌شود.
   *
   * تعداد را از همین ردیف داریم، پس پیش از فشردنِ دکمه می‌گوییم چند قلم — بهتر
   * از خوردنِ خطا بعدش.
   */
  async function toggleActive(u: UnitRecord) {
    setError(null)
    if (u.is_active && u.item_count > 0) {
      setError(
        `واحدِ «${u.name}» روی ${faMoney(u.item_count)} قلم کالا نشسته و غیرفعال نمی‌شود. ` +
          'اول واحدِ آن کالاها را عوض کنید.',
      )
      return
    }
    try {
      await updateUnit(token, u.id, { is_active: !u.is_active })
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDelete(u: UnitRecord) {
    setError(null)
    if (!window.confirm(`واحدِ «${u.name}» برای همیشه حذف شود؟`)) return
    try {
      await deleteUnit(token, u.id)
      if (editId === u.id) setEditId(null)
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard
        icon={Plus}
        title="واحدِ جدید"
        description="واحدها داده‌ی پایه‌اند: خرید، فروش، انبار و صندوق همگی از همین فهرست انتخاب می‌کنند."
      >
        <form className="invoice-form form-full" onSubmit={handleCreate}>
          <div className="field-row">
            <label>
              نام واحد
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="مثلاً کارتن"
              />
            </label>
            <label>
              عنوان دوم
              <input
                value={draft.name2}
                onChange={(e) => setDraft({ ...draft, name2: e.target.value })}
                placeholder="اختیاری — مثلاً Carton"
              />
            </label>
          </div>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={saving}>
              <Save size={14} /> ثبت واحد
            </button>
          </div>
          {message && <div className="hint">{message}</div>}
          <p className="hint">
            نامِ واحد در سطحِ کسب‌وکار یکتاست. تغییرِ نام روی همه‌ی کالاهایی که این واحد را
            دارند هم دیده می‌شود — چون واحد یک رکورد است، نه یک نوشتارِ تکرارشده.
          </p>
        </form>
      </SectionCard>

      <SectionCard
        icon={Ruler}
        title="واحدهای سنجش"
        description={rows ? `${faMoney(rows.length)} واحد` : ''}
        actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
      >
        {error && <div className="error"><AlertTriangle size={13} /> {error}</div>}
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState icon={Ruler} text="هنوز واحدی تعریف نشده." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>واحد</th>
                    <th>کالاها</th>
                    <th>وضعیت</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((u) => (
                    <tr key={u.id}>
                      <td className="card-title" data-label="واحد">
                        <div className="entity-name">{u.name}</div>
                        {u.name2 ? <div className="entity-sub">{u.name2}</div> : null}
                      </td>
                      <td data-label="کالاها">{u.item_count ? faMoney(u.item_count) : '—'}</td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${u.is_active ? 'tone-success' : 'tone-warning'}`}>
                          {u.is_active ? 'فعال' : 'غیرفعال'}
                        </span>
                      </td>
                      <td className="check-actions card-actions">
                        <button type="button" onClick={() => { setEditId(u.id); setEdit({ name: u.name, name2: u.name2 }) }}>
                          <Pencil size={13} /> ویرایش
                        </button>
                        <button type="button" onClick={() => void toggleActive(u)}>
                          {u.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}
                        </button>
                        {u.item_count === 0 && (
                          <button type="button" className="icon-btn-danger" onClick={() => void handleDelete(u)} aria-label="حذف واحد">
                            <Trash2 size={13} /> حذف
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

        {editId && (
          <form className="invoice-form form-full" onSubmit={(e) => { e.preventDefault(); void saveEdit() }}>
            <h4>ویرایشِ واحد</h4>
            <div className="field-row">
              <label>نام واحد<input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></label>
              <label>عنوان دوم<input value={edit.name2} onChange={(e) => setEdit({ ...edit, name2: e.target.value })} /></label>
            </div>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={13} /> ذخیره</button>
              <button type="button" onClick={() => setEditId(null)}><X size={13} /> انصراف</button>
            </div>
          </form>
        )}
      </SectionCard>
    </div>
  )
}
