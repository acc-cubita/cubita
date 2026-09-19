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
import { SearchSelect } from './SearchSelect'
import {
  ActionBar,
  CountBadge,
  FormField,
  FormGrid,
  FormStatus,
  InputAffix,
  RowAction,
} from './form/FormKit'

import { NumberInput } from './NumberInput'
import { StatCard } from './StatCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
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
  // صفحه‌بندیِ ردیف‌های بودجه (۱۰ در هر صفحه) — مثلِ چارتِ حساب‌ها.
  const pg = usePagination(lines, 10)

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<ListChecks size={18} />} label="تعداد ردیف بودجه" value={fa(lines.length)} hint="حساب × ماه" />
        <StatCard icon={<Wallet size={18} />} label="جمع بودجه‌ی ثبت‌شده" value={fa(totalBudget)} tone="success" />
      </div>

      <form noValidate onSubmit={handleSubmit}>
        <SectionCard
          icon={editingId ? Pencil : Plus}
          title={editingId ? 'ویرایش بودجه' : 'بودجه‌ی جدید'}
          tip="برای هر حساب و هر ماه، مبلغِ برنامه‌ریزی‌شده را وارد کنید. ثبتِ دوباره‌ی همان حساب و ماه، رقم را به‌روز می‌کند."
        >
          <FormGrid>
            <FormField id="bg-account" label="حساب" required>
              {(id) => (
                <SearchSelect
                  id={id}
                  value={form.accountId}
                  onChange={(e) => setForm({ ...form, accountId: e.target.value })}
                >
                  <option value="">— انتخاب حساب —</option>
                  {postable.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <FormField label="سال" required>
              {(id) => (
                <SearchSelect id={id} value={form.jy} onChange={(e) => setForm({ ...form, jy: Number(e.target.value) })}>
                  {years.map((y) => (
                    <option key={y} value={y}>
                      {toFaDigits(y)}
                    </option>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <FormField label="ماه" required>
              {(id) => (
                <SearchSelect id={id} value={form.jm} onChange={(e) => setForm({ ...form, jm: Number(e.target.value) })}>
                  {JALALI_MONTH_NAMES.map((name, i) => (
                    <option key={name} value={i + 1}>
                      {name}
                    </option>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <FormField label="مبلغ بودجه" required>
              {(id) => (
                <InputAffix unit="ریال">
                  <NumberInput id={id} value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} />
                </InputAffix>
              )}
            </FormField>
            <FormField label="توضیحات" optional span="full">
              {(id) => (
                <input id={id} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              )}
            </FormField>
          </FormGrid>
        </SectionCard>
        <ActionBar status={<FormStatus msg={msg ? { text: msg, kind: 'err' } : null} />}>
          {editingId && (
            <button type="button" className="ef-btn-secondary" onClick={resetForm}>
              <X size={15} /> انصراف
            </button>
          )}
          <button type="submit" className="btn-primary">
            <Save size={16} /> {editingId ? 'ذخیرهٔ تغییرات' : 'ثبت بودجه'}
          </button>
        </ActionBar>
      </form>

      <SectionCard
        icon={Target}
        title="ردیف‌های بودجه"
        badge={<CountBadge accent>{fa(lines.length)} ردیف</CountBadge>}
        description="بودجه‌ی هر حساب به تفکیکِ ماه."
      >
        {lines.length === 0 ? (
          <EmptyState icon={Target} text="هنوز بودجه‌ای تعریف نشده." />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead>
                <tr>
                  <th>حساب</th>
                  <th>دوره</th>
                  <th>مبلغ بودجه</th>
                  <th className="ef-col-min">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((l) => (
                  <tr key={l.id} className={editingId === l.id ? 'is-editing' : undefined}>
                    <td className="card-title" data-label="حساب">
                      {l.account_code} — {l.account_name}
                    </td>
                    <td data-label="دوره">{monthLabel(l.period_date)}</td>
                    <td className="money-cell" data-label="مبلغ بودجه">
                      {fa(l.amount)}
                    </td>
                    <td className="card-actions ef-col-min" data-label="عملیات">
                      <div className="row-actions ef-row-actions">
                        <RowAction
                          icon={Pencil}
                          label="ویرایش"
                          onClick={() => {
                            startEdit(l)
                            document.getElementById('bg-account')?.focus()
                          }}
                        />
                        <RowAction icon={Trash2} label="حذف" danger onClick={() => void handleDelete(l)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}
      </SectionCard>
    </>
  )
}
