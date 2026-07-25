import { useEffect, useMemo, useState } from 'react'
import { ClipboardCheck, Plus, Save, CheckCircle2, XCircle, ListChecks } from 'lucide-react'
import type { WarehouseCache } from '../electron.d'
import {
  cancelStockCount,
  createStockCount,
  fetchStockCount,
  fetchStockCounts,
  postStockCount,
  setStockCounts,
  type StockCountSession,
  type StockCountStatus,
  type StockCountSummary,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

const STATUS_LABEL: Record<StockCountStatus, string> = {
  open: 'باز',
  posted: 'ثبت‌شده',
  cancelled: 'لغوشده',
}
const STATUS_TONE: Record<StockCountStatus, string> = {
  open: 'tone-warning',
  posted: 'tone-success',
  cancelled: 'tone-danger',
}

const faInt = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
const faQty = (v: string | number) => Number(v).toLocaleString('fa-IR')

export function StockCountPanel({ token, warehouses }: { token: string; warehouses: WarehouseCache[] }) {
  const [sessions, setSessions] = useState<StockCountSummary[]>([])
  const [selected, setSelected] = useState<StockCountSession | null>(null)
  const [counts, setCounts] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [warehouseId, setWarehouseId] = useState('')
  const [countDate, setCountDate] = useState(todayIso())
  const [notes, setNotes] = useState('')

  async function refreshList() {
    try {
      setSessions(await fetchStockCounts(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refreshList()
  }, [])

  function loadDraft(session: StockCountSession) {
    setSelected(session)
    setCounts(Object.fromEntries(session.lines.map((l) => [l.id, String(Number(l.counted_qty))])))
    setMessage(null)
  }

  async function openSession(id: string) {
    setError(null)
    try {
      loadDraft(await fetchStockCount(token, id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setMessage(null)
    const wid = warehouseId || warehouses[0]?.id
    if (!wid) {
      setError('ابتدا یک انبار انتخاب کنید.')
      return
    }
    try {
      const session = await createStockCount(token, { warehouse_id: wid, count_date: countDate, notes })
      loadDraft(session)
      setNotes('')
      await refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleSaveCounts() {
    if (!selected) return
    setMessage(null)
    const lines = selected.lines.map((l) => ({ line_id: l.id, counted_qty: Number(counts[l.id] ?? l.counted_qty) || 0 }))
    try {
      const updated = await setStockCounts(token, selected.id, lines)
      loadDraft(updated)
      setMessage('شمارش‌ها ذخیره شد.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handlePost() {
    if (!selected) return
    setMessage(null)
    // شمارش‌های ویرایش‌شده اول ذخیره، بعد ثبت — تا آنچه کاربر می‌بیند همان چیزی باشد که اعمال می‌شود.
    const lines = selected.lines.map((l) => ({ line_id: l.id, counted_qty: Number(counts[l.id] ?? l.counted_qty) || 0 }))
    try {
      await setStockCounts(token, selected.id, lines)
      const posted = await postStockCount(token, selected.id)
      loadDraft(posted)
      setMessage('انبارگردانی ثبت شد و سند تعدیل صادر شد.')
      await refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleCancel() {
    if (!selected) return
    try {
      const cancelled = await cancelStockCount(token, selected.id)
      loadDraft(cancelled)
      await refreshList()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const editable = selected?.status === 'open'

  // مغایرت و ارزش را زنده از شمارشِ در حال ویرایش حساب می‌کنیم تا کاربر همان لحظه ببیند.
  const liveRows = useMemo(() => {
    if (!selected) return []
    return selected.lines.map((l) => {
      const counted = Number(counts[l.id] ?? l.counted_qty) || 0
      const variance = counted - Number(l.system_qty)
      return { line: l, counted, variance, value: variance * Number(l.unit_cost) }
    })
  }, [selected, counts])

  const totalVarianceValue = liveRows.reduce((s, r) => s + r.value, 0)
  const varianceCount = liveRows.filter((r) => r.variance !== 0).length

  return (
    <div className="split-2col">
      <SectionCard
        icon={ClipboardCheck}
        title="جلسه‌ی انبارگردانی جدید"
        description="از موجودی سیستمیِ همه‌ی کالاهای انبار عکس‌برداری می‌شود؛ سپس شمارش فیزیکی را وارد کنید."
      >
        <form className="invoice-form form-full" onSubmit={handleCreate}>
          <label>
            انبار
            <select value={warehouseId || warehouses[0]?.id || ''} onChange={(e) => setWarehouseId(e.target.value)}>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            تاریخ شمارش
            <JalaliDatePicker value={countDate} onChange={setCountDate} />
          </label>
          <label>
            توضیحات
            <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="اختیاری" />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary">
              <Plus size={14} /> ایجاد جلسه و عکس‌برداری
            </button>
          </div>
        </form>

        <h3 className="panel-subhead"><ListChecks size={15} /> جلسه‌های اخیر</h3>
        {sessions.length === 0 ? (
          <EmptyState icon={ClipboardCheck} text="هنوز جلسه‌ای ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead>
                <tr>
                  <th>انبار</th>
                  <th>تاریخ</th>
                  <th>وضعیت</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} className={selected?.id === s.id ? 'row-selected' : undefined}>
                    <td className="entity-name">{s.warehouse_name}</td>
                    <td>{formatJalali(s.count_date)}</td>
                    <td>
                      <span className={`status-badge ${STATUS_TONE[s.status]}`}>{STATUS_LABEL[s.status]}</span>
                    </td>
                    <td>
                      <button type="button" onClick={() => void openSession(s.id)}>
                        باز کردن
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {error && <div className="error">{error}</div>}
      </SectionCard>

      <SectionCard
        icon={ClipboardCheck}
        title={selected ? `شمارش انبار «${selected.warehouse_name}»` : 'شمارش'}
        description={
          selected
            ? `${formatJalali(selected.count_date)} — ${STATUS_LABEL[selected.status]}`
            : 'یک جلسه را از فهرست باز کنید یا جلسه‌ی تازه بسازید.'
        }
        actions={
          editable ? (
            <div className="check-actions">
              <button type="button" onClick={() => void handleSaveCounts()}>
                <Save size={13} /> ذخیره
              </button>
              <button type="button" className="btn-primary" onClick={() => void handlePost()}>
                <CheckCircle2 size={13} /> ثبت نهایی
              </button>
              <button type="button" className="icon-btn-danger" onClick={() => void handleCancel()}>
                <XCircle size={13} /> لغو
              </button>
            </div>
          ) : undefined
        }
      >
        {!selected ? (
          <EmptyState icon={ClipboardCheck} text="جلسه‌ای انتخاب نشده." />
        ) : (
          <>
            <div className="stat-inline">
              <span>ردیف‌های دارای مغایرت: <strong>{faInt(varianceCount)}</strong></span>
              <span className={totalVarianceValue < 0 ? 'text-danger' : totalVarianceValue > 0 ? 'text-success' : ''}>
                ارزش خالص مغایرت: <strong>{faInt(totalVarianceValue)}</strong> تومان
              </span>
            </div>
            <div className="entity-table-wrap">
              <table className="entity-table">
                <thead>
                  <tr>
                    <th>کالا</th>
                    <th>سیستمی</th>
                    <th>شمارش</th>
                    <th>مغایرت</th>
                    <th>ارزش مغایرت</th>
                  </tr>
                </thead>
                <tbody>
                  {liveRows.map(({ line, variance, value }) => (
                    <tr key={line.id}>
                      <td>
                        <div className="entity-name">{line.item_name}</div>
                        <div className="entity-sub">{line.item_sku} · {line.unit}</div>
                      </td>
                      <td>{faQty(line.system_qty)}</td>
                      <td>
                        {editable ? (
                          <input
                            type="number"
                            min="0"
                            step="any"
                            className="count-input"
                            value={counts[line.id] ?? ''}
                            onChange={(e) => setCounts((prev) => ({ ...prev, [line.id]: e.target.value }))}
                          />
                        ) : (
                          faQty(line.counted_qty)
                        )}
                      </td>
                      <td className={variance < 0 ? 'text-danger' : variance > 0 ? 'text-success' : ''}>
                        {variance > 0 ? '+' : ''}
                        {faQty(variance)}
                      </td>
                      <td className={value < 0 ? 'text-danger' : value > 0 ? 'text-success' : ''}>{faInt(value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {message && <div className="hint">{message}</div>}
          </>
        )}
      </SectionCard>
    </div>
  )
}
