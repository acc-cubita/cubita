import { useEffect, useState } from 'react'
import { FolderKanban, Plus, Pencil, X, Save, Trash2 } from 'lucide-react'
import {
  createCostCenter,
  deleteCostCenter,
  fetchCostCenters,
  updateCostCenter,
  type CostCenterRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'

const EMPTY = { code: '', name: '', is_active: true, notes: '' }

export function CostCentersPanel({ token }: { token: string }) {
  const [centers, setCenters] = useState<CostCenterRecord[]>([])
  const [form, setForm] = useState({ ...EMPTY })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  async function refresh() {
    try {
      setCenters(await fetchCostCenters(token))
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  function resetForm() {
    setForm({ ...EMPTY })
    setEditingId(null)
    setMsg(null)
  }

  function startEdit(c: CostCenterRecord) {
    setEditingId(c.id)
    setMsg(null)
    setForm({ code: c.code, name: c.name, is_active: c.is_active, notes: c.notes })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!form.name.trim()) {
      setMsg('نام مرکز الزامی است.')
      return
    }
    try {
      if (editingId) await updateCostCenter(token, editingId, form)
      else await createCostCenter(token, form)
      resetForm()
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDelete(c: CostCenterRecord) {
    if (!window.confirm(`مرکز «${c.name}» حذف شود؟`)) return
    try {
      await deleteCostCenter(token, c.id)
      if (editingId === c.id) resetForm()
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard
        icon={editingId ? Pencil : Plus}
        title={editingId ? 'ویرایش مرکز هزینه/پروژه' : 'مرکز هزینه/پروژه‌ی جدید'}
        description="پروژه، شعبه، یا هر بُعدی که می‌خواهید سود و هزینه‌اش را جدا بسنجید. فاکتورها و اسناد را به آن برچسب بزنید."
        actions={editingId ? <button onClick={resetForm}><X size={13} /> انصراف</button> : undefined}
      >
        <form className="invoice-form form-full" onSubmit={handleSubmit}>
          <label>
            کد (اختیاری)
            <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="مثلاً PRJ-01" />
          </label>
          <label>
            نام مرکز/پروژه
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="پروژه برج آسمان" />
          </label>
          <label>
            توضیحات
            <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </label>
          <label className="cal-check-inline">
            <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            فعال (در فرم‌ها پیشنهاد شود)
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><Save size={14} /> {editingId ? 'ذخیره' : 'ثبت مرکز'}</button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </form>
      </SectionCard>

      <SectionCard icon={FolderKanban} title="مراکز هزینه / پروژه‌ها" description={`${centers.length.toLocaleString('fa-IR')} مرکز`}>
        {centers.length === 0 ? (
          <EmptyState icon={FolderKanban} text="هنوز مرکزی تعریف نشده." />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>کد</th>
                  <th>نام</th>
                  <th>وضعیت</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {centers.map((c) => (
                  <tr key={c.id} style={c.is_active ? undefined : { opacity: 0.55 }}>
                    <td>{c.code || '—'}</td>
                    <td>{c.name}</td>
                    <td>
                      <span className={`status-badge ${c.is_active ? 'tone-success' : 'tone-warning'}`}>
                        {c.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td>
                      <div className="check-actions">
                        <button type="button" onClick={() => startEdit(c)} aria-label="ویرایش"><Pencil size={13} /></button>
                        <button type="button" className="icon-btn-danger" onClick={() => void handleDelete(c)} aria-label="حذف"><Trash2 size={13} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
