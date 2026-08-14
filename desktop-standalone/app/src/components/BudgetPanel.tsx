import { useEffect, useMemo, useState } from 'react'
import { Target, Plus, Pencil, X, Save, Trash2, Wallet, ListChecks } from 'lucide-react'
import {
  createBudgetLine,
  deleteBudgetLine,
  fetchBudgetLines,
  updateBudgetLine,
  type BudgetLineRecord,
} from '../api'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { StatCard } from './StatCard'
import { EmptyState } from './EmptyState'
import { JALALI_MONTH_NAMES, isoToJalali, jalaliToIso, toFaDigits, todayIso } from '../lib/jalali'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

function monthLabel(iso: string): string {
  try {
    const { jy, jm } = isoToJalali(iso)
    return `${JALALI_MONTH_NAMES[jm - 1]} ${toFaDigits(jy)}`
  } catch {
    return iso
  }
}

export function BudgetPanel({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const nowJy = isoToJalali(todayIso()).jy
  const nowJm = isoToJalali(todayIso()).jm
  const emptyForm = { accountId: '', jy: nowJy, jm: nowJm, amount: '', notes: '' }

  const [lines, setLines] = useState<BudgetLineRecord[]>([])
  const [form, setForm] = useState({ ...emptyForm })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const postable = useMemo(() => accounts.filter((a) => !a.is_group), [accounts])
  const years = [nowJy - 1, nowJy, nowJy + 1]

  async function refresh() {
    try {
      setLines(await fetchBudgetLines(token))
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  function resetForm() {
    setForm({ ...emptyForm })
    setEditingId(null)
    setMsg(null)
  }

  function startEdit(l: BudgetLineRecord) {
    const { jy, jm } = isoToJalali(l.period_date)
    setEditingId(l.id)
    setMsg(null)
    setForm({ accountId: l.account_id, jy, jm, amount: String(l.amount), notes: l.notes })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!form.accountId) {
      setMsg('ابتدا یک حساب انتخاب کنید.')
      return
    }
    const payload = {
      account_id: form.accountId,
      period_date: jalaliToIso(form.jy, form.jm, 1),
      amount: Number(form.amount) || 0,
      notes: form.notes,
    }
    try {
      if (editingId) await updateBudgetLine(token, editingId, payload)
      else await createBudgetLine(token, payload)
      resetForm()
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDelete(l: BudgetLineRecord) {
    if (!window.confirm(`بودجه‌ی «${l.account_name}» برای ${monthLabel(l.period_date)} حذف شود؟`)) return
    try {
      await deleteBudgetLine(token, l.id)
      if (editingId === l.id) resetForm()
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const totalBudget = lines.reduce((s, l) => s + Number(l.amount), 0)

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<ListChecks size={18} />} label="تعداد ردیف بودجه" value={fa(lines.length)} hint="حساب × ماه" />
        <StatCard icon={<Wallet size={18} />} label="جمع بودجه‌ی ثبت‌شده" value={fa(totalBudget)} tone="success" />
      </div>

      <div className="workspace-split">
        <SectionCard
          icon={editingId ? Pencil : Plus}
          title={editingId ? 'ویرایش بودجه' : 'بودجه‌ی جدید'}
          description="برای هر حساب و هر ماه، مبلغِ برنامه‌ریزی‌شده را وارد کنید. ثبتِ دوباره‌ی همان حساب/ماه، رقم را به‌روزرسانی می‌کند."
          actions={editingId ? <button onClick={resetForm}><X size={13} /> انصراف</button> : undefined}
        >
          <form className="invoice-form form-full" onSubmit={handleSubmit}>
            <label>
              حساب
              <select value={form.accountId} onChange={(e) => setForm({ ...form, accountId: e.target.value })}>
                <option value="">— انتخاب حساب —</option>
                {postable.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              سال
              <select value={form.jy} onChange={(e) => setForm({ ...form, jy: Number(e.target.value) })}>
                {years.map((y) => (
                  <option key={y} value={y}>
                    {toFaDigits(y)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              ماه
              <select value={form.jm} onChange={(e) => setForm({ ...form, jm: Number(e.target.value) })}>
                {JALALI_MONTH_NAMES.map((name, i) => (
                  <option key={name} value={i + 1}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              مبلغ بودجه
              <NumberInput value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} />
            </label>
            <label>
              توضیحات
              <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={14} /> {editingId ? 'ذخیره' : 'ثبت بودجه'}</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        </SectionCard>

        <SectionCard icon={Target} title="ردیف‌های بودجه" description={`${fa(lines.length)} ردیف`}>
          {lines.length === 0 ? (
            <EmptyState icon={Target} text="هنوز بودجه‌ای تعریف نشده." />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>حساب</th>
                    <th>دوره</th>
                    <th>مبلغ بودجه</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l) => (
                    <tr key={l.id}>
                      <td>{l.account_code} — {l.account_name}</td>
                      <td>{monthLabel(l.period_date)}</td>
                      <td>{fa(l.amount)}</td>
                      <td>
                        <div className="check-actions">
                          <button type="button" onClick={() => startEdit(l)} aria-label="ویرایش"><Pencil size={13} /></button>
                          <button type="button" className="icon-btn-danger" onClick={() => void handleDelete(l)} aria-label="حذف"><Trash2 size={13} /></button>
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
    </>
  )
}
