import { useCallback, useEffect, useState } from 'react'
import { MapPin, Plus, Trash2, Pencil, X, Save } from 'lucide-react'
import { createMpZone, deleteMpZone, fetchMpZones, updateMpZone, type MpZone } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'

const faNum = (n: number) => n.toLocaleString('fa-IR')
const errMsg = (e: unknown) => (e instanceof Error ? e.message : 'خطای ناشناخته')

/**
 * مدیریتِ زون‌های ارسالِ پخش‌کننده — تقسیم‌بندیِ نام‌گذاری‌شده‌ی خودِ پخش‌کننده (نه نقشه).
 * فروشگاه‌ها در تبِ «اتصال‌ها» به زون تخصیص داده می‌شوند.
 */
export function MpZonesPanel({ token }: { token: string }) {
  const [zones, setZones] = useState<MpZone[]>([])
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [notes, setNotes] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const refresh = useCallback(async () => {
    setError(null)
    try { setZones(await fetchMpZones(token)) }
    catch (e) { setError(errMsg(e)) }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  function reset() { setName(''); setNotes(''); setEditingId(null) }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) { setError('نامِ زون الزامی است.'); return }
    setSaving(true); setError(null)
    try {
      if (editingId) await updateMpZone(token, editingId, { name: name.trim(), notes: notes.trim() })
      else await createMpZone(token, { name: name.trim(), notes: notes.trim() })
      reset()
      await refresh()
    } catch (e) { setError(errMsg(e)) }
    finally { setSaving(false) }
  }

  function startEdit(z: MpZone) { setEditingId(z.id); setName(z.name); setNotes(z.notes) }

  async function remove(z: MpZone) {
    if (!window.confirm(`زونِ «${z.name}» حذف شود؟ فروشگاه‌های این زون بدونِ زون می‌شوند.`)) return
    setError(null)
    try { await deleteMpZone(token, z.id); if (editingId === z.id) reset(); await refresh() }
    catch (e) { setError(errMsg(e)) }
  }

  return (
    <div className="workspace-split">
      <SectionCard
        icon={editingId ? Pencil : Plus}
        title={editingId ? 'ویرایشِ زون' : 'زونِ جدید'}
        description="زون‌ها تقسیم‌بندیِ خودتان برای مدیریتِ سریع‌ترِ ارسال‌اند (مثلاً «منطقهٔ شرق»)."
        actions={editingId ? <button type="button" onClick={reset}><X size={13} /> انصراف</button> : undefined}
      >
        <form className="invoice-form form-full" onSubmit={submit}>
          <label>نامِ زون
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="مثلاً منطقهٔ شرق" />
          </label>
          <label>توضیح (اختیاری)
            <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={saving}><Save size={14} /> {editingId ? 'ذخیره' : 'افزودنِ زون'}</button>
          </div>
          {error && <div className="hint">{error}</div>}
        </form>
      </SectionCard>

      <SectionCard icon={MapPin} title="زون‌ها" description={`${faNum(zones.length)} زون`}>
        {zones.length === 0 ? (
          <EmptyState icon={MapPin} text="هنوز زونی نساخته‌اید." />
        ) : (
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead><tr><th>زون</th><th>فروشگاه‌ها</th><th>توضیح</th><th></th></tr></thead>
                <tbody>
                  {zones.map((z) => (
                    <tr key={z.id}>
                      <td className="entity-name card-title" data-label="زون">{z.name}</td>
                      <td data-label="فروشگاه‌ها">{faNum(z.connection_count)}</td>
                      <td data-label="توضیح" className="entity-sub">{z.notes || '—'}</td>
                      <td className="card-actions">
                        <div className="check-actions">
                          <button type="button" onClick={() => startEdit(z)}><Pencil size={13} /> ویرایش</button>
                          <button type="button" className="icon-btn-danger" onClick={() => void remove(z)} aria-label="حذف"><Trash2 size={13} /> حذف</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
