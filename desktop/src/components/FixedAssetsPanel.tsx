import { useEffect, useState } from 'react'
import {
  Building2,
  Plus,
  Pencil,
  X,
  Save,
  Trash2,
  PackageX,
  Landmark,
  TrendingDown,
  Wallet,
  Play,
} from 'lucide-react'
import {
  createFixedAsset,
  deleteFixedAsset,
  disposeFixedAsset,
  fetchChartAccounts,
  fetchDepreciationEntries,
  fetchFixedAssets,
  runDepreciation,
  updateFixedAsset,
  type ChartAccount,
  type DepreciationEntryRecord,
  type FixedAssetRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { StatCard } from './StatCard'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

const EMPTY = { name: '', category: '', acquired_date: todayIso(), cost: '', salvage_value: '0', useful_life_months: '', notes: '', funding_account_id: '' }

// حساب‌هایی که می‌شود بابتِ خریدِ دارایی از آن‌ها پرداخت کرد (بر پایه‌ی نقشِ سیستمی،
// نه کدِ حساب — تا با چارتِ سفارشیِ مشتری هم درست کار کند).
const FUNDING_ROLES = ['cash', 'bank', 'petty_cash', 'accounts_payable']

export function FixedAssetsPanel({ token }: { token: string }) {
  const [assets, setAssets] = useState<FixedAssetRecord[]>([])
  const [entries, setEntries] = useState<DepreciationEntryRecord[]>([])
  const [accounts, setAccounts] = useState<ChartAccount[]>([])
  const [form, setForm] = useState({ ...EMPTY })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formMsg, setFormMsg] = useState<string | null>(null)
  const [periodDate, setPeriodDate] = useState(todayIso())
  const [runMsg, setRunMsg] = useState<string | null>(null)

  async function refresh() {
    try {
      const [a, e, acc] = await Promise.all([
        fetchFixedAssets(token),
        fetchDepreciationEntries(token),
        fetchChartAccounts(token),
      ])
      setAssets(a)
      setEntries(e)
      setAccounts(acc)
    } catch (err) {
      setFormMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  function resetForm() {
    setForm({ ...EMPTY })
    setEditingId(null)
    setFormMsg(null)
  }

  function startEdit(a: FixedAssetRecord) {
    setEditingId(a.id)
    setFormMsg(null)
    setForm({
      name: a.name,
      category: a.category,
      acquired_date: a.acquired_date,
      cost: String(a.cost),
      salvage_value: String(a.salvage_value),
      useful_life_months: String(a.useful_life_months),
      notes: a.notes,
      funding_account_id: '', // تأمینِ مالی فقط هنگامِ ثبتِ اولیه معنا دارد، نه ویرایش
    })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormMsg(null)
    const payload = {
      name: form.name,
      category: form.category,
      acquired_date: form.acquired_date,
      cost: Number(form.cost) || 0,
      salvage_value: Number(form.salvage_value) || 0,
      useful_life_months: Number(form.useful_life_months) || 0,
      notes: form.notes,
      // تأمینِ مالی فقط در ثبتِ اولیه: سندِ خرید را خودکار می‌زند (خالی = بدونِ سند).
      funding_account_id: form.funding_account_id || null,
    }
    try {
      if (editingId) await updateFixedAsset(token, editingId, payload)
      else await createFixedAsset(token, payload)
      resetForm()
      await refresh()
    } catch (err) {
      setFormMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDispose(a: FixedAssetRecord) {
    if (!window.confirm(`دارایی «${a.name}» واگذارشده علامت بخورد؟ (دیگر مستهلک نمی‌شود)`)) return
    try {
      await disposeFixedAsset(token, a.id, todayIso())
      await refresh()
    } catch (err) {
      setFormMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDelete(a: FixedAssetRecord) {
    if (!window.confirm(`دارایی «${a.name}» حذف شود؟`)) return
    try {
      await deleteFixedAsset(token, a.id)
      await refresh()
    } catch (err) {
      setFormMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleRun() {
    setRunMsg(null)
    try {
      const res = await runDepreciation(token, periodDate)
      setRunMsg(
        res.asset_count === 0
          ? 'برای این دوره داراییِ قابل‌استهلاکی نبود (یا قبلاً ثبت شده).'
          : `استهلاک ${fa(res.asset_count)} دارایی ثبت شد؛ جمع ${fa(res.total_amount)} — سند شماره ${res.journal_entry_number != null ? fa(res.journal_entry_number) : '—'}.`,
      )
      await refresh()
    } catch (err) {
      setRunMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const active = assets.filter((a) => !a.is_disposed)
  const totalCost = active.reduce((s, a) => s + Number(a.cost), 0)
  const totalAccum = active.reduce((s, a) => s + Number(a.accumulated_depreciation), 0)
  const totalBook = active.reduce((s, a) => s + Number(a.book_value), 0)

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<Landmark size={18} />} label="تعداد دارایی فعال" value={fa(active.length)} hint="واگذارنشده" />
        <StatCard icon={<Building2 size={18} />} label="بهای تمام‌شده" value={fa(totalCost)} tone="default" />
        <StatCard icon={<TrendingDown size={18} />} label="استهلاک انباشته" value={fa(totalAccum)} tone="warning" />
        <StatCard icon={<Wallet size={18} />} label="ارزش دفتری" value={fa(totalBook)} tone="success" />
      </div>

      <div className="workspace-split">
        <SectionCard
          icon={editingId ? Pencil : Plus}
          title={editingId ? 'ویرایش دارایی' : 'دارایی ثابت جدید'}
          description="خودرو، تجهیزات، ساختمان و ... — استهلاک خط مستقیم بر پایه‌ی عمر مفید."
          actions={editingId ? <button onClick={resetForm}><X size={13} /> انصراف</button> : undefined}
        >
          <form className="invoice-form form-full" onSubmit={handleSubmit}>
            <label>
              نام دارایی
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="مثلاً وانت نیسان" />
            </label>
            <label>
              دسته
              <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="وسیله نقلیه" />
            </label>
            <label>
              تاریخ تحصیل
              <JalaliDatePicker value={form.acquired_date} onChange={(v) => setForm({ ...form, acquired_date: v })} />
            </label>
            <label>
              بهای تمام‌شده
              <input type="number" min="0" value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} />
            </label>
            <label>
              ارزش اسقاط
              <input type="number" min="0" value={form.salvage_value} onChange={(e) => setForm({ ...form, salvage_value: e.target.value })} />
            </label>
            <label>
              عمر مفید (ماه)
              <input type="number" min="1" value={form.useful_life_months} onChange={(e) => setForm({ ...form, useful_life_months: e.target.value })} />
            </label>
            {!editingId && (
              <label>
                پرداخت از
                <select value={form.funding_account_id} onChange={(e) => setForm({ ...form, funding_account_id: e.target.value })}>
                  <option value="">— بدون سند (آورده / قبلاً در دفاتر) —</option>
                  {accounts
                    .filter((a) => !a.is_group && FUNDING_ROLES.includes(a.system_role ?? ''))
                    .sort((x, y) => x.code.localeCompare(y.code))
                    .map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                </select>
              </label>
            )}
            <label>
              توضیحات
              <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={14} /> {editingId ? 'ذخیره' : 'ثبت دارایی'}</button>
            </div>
            {formMsg && <div className="hint">{formMsg}</div>}
          </form>
        </SectionCard>

        <SectionCard icon={Landmark} title="فهرست دارایی‌ها" description={`${fa(assets.length)} قلم دارایی`}>
          {assets.length === 0 ? (
            <EmptyState icon={Landmark} text="هنوز دارایی ثابتی ثبت نشده." />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>نام</th>
                    <th>تحصیل</th>
                    <th>بها</th>
                    <th>ماهانه</th>
                    <th>انباشته</th>
                    <th>ارزش دفتری</th>
                    <th>وضعیت</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {assets.map((a) => (
                    <tr key={a.id} style={a.is_disposed ? { opacity: 0.55 } : undefined}>
                      <td>{a.name}</td>
                      <td>{formatJalali(a.acquired_date)}</td>
                      <td>{fa(a.cost)}</td>
                      <td>{fa(a.monthly_depreciation)}</td>
                      <td>{fa(a.accumulated_depreciation)}</td>
                      <td>{fa(a.book_value)}</td>
                      <td>
                        <span className={`status-badge ${a.is_disposed ? 'tone-danger' : a.fully_depreciated ? 'tone-warning' : 'tone-success'}`}>
                          {a.is_disposed ? 'واگذارشده' : a.fully_depreciated ? 'مستهلک کامل' : 'فعال'}
                        </span>
                      </td>
                      <td>
                        <div className="check-actions">
                          <button type="button" onClick={() => startEdit(a)} aria-label="ویرایش"><Pencil size={13} /></button>
                          {!a.is_disposed && (
                            <button type="button" onClick={() => void handleDispose(a)} aria-label="واگذاری"><PackageX size={13} /></button>
                          )}
                          <button type="button" className="icon-btn-danger" onClick={() => void handleDelete(a)} aria-label="حذف"><Trash2 size={13} /></button>
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

      <SectionCard
        icon={Play}
        title="اجرای استهلاک دوره"
        description="یک تاریخ (معمولاً پایان ماه) انتخاب کنید؛ برای همه‌ی دارایی‌های فعال یک سند استهلاک ثبت می‌شود. هر دوره فقط یک‌بار."
      >
        <div className="check-actions">
          <div style={{ maxWidth: 220, flex: '1 1 180px' }}>
            <JalaliDatePicker value={periodDate} onChange={setPeriodDate} />
          </div>
          <button type="button" className="btn-primary" onClick={() => void handleRun()}><Play size={14} /> ثبت استهلاک این دوره</button>
        </div>
        {runMsg && <div className="hint">{runMsg}</div>}

        {entries.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>دوره</th>
                  <th>دارایی</th>
                  <th>مبلغ استهلاک</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id}>
                    <td>{formatJalali(e.period_date)}</td>
                    <td>{e.asset_name}</td>
                    <td>{fa(e.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  )
}
