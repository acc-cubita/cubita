import { useEffect, useState } from 'react'
import {
  createFixedAsset,
  deleteFixedAsset,
  fetchChartAccounts,
  fetchDepreciationEntries,
  fetchFixedAssets,
  runDepreciation,
  updateFixedAsset,
  type ChartAccount,
  type DepreciationEntryRecord,
  type FixedAssetRecord,
} from '../api'
import { todayIso } from './jalali'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

const EMPTY = {
  name: '',
  category: '',
  acquired_date: todayIso(),
  cost: '',
  salvage_value: '0',
  useful_life_months: '',
  notes: '',
  funding_account_id: '',
}

// حساب‌هایی که می‌شود بابتِ خریدِ دارایی از آن‌ها پرداخت کرد (بر پایه‌ی نقشِ سیستمی،
// نه کدِ حساب — تا با چارتِ سفارشیِ مشتری هم درست کار کند).
const FUNDING_ROLES = ['cash', 'bank', 'petty_cash', 'accounts_payable']

/** منطقِ مشترکِ «دارایی ثابت» — فرمِ ثبت/ویرایش + فهرست + اجرای استهلاکِ دوره. */
export function useFixedAssetDraft({ token }: { token: string }) {
  const [assets, setAssets] = useState<FixedAssetRecord[]>([])
  const [entries, setEntries] = useState<DepreciationEntryRecord[]>([])
  const [accounts, setAccounts] = useState<ChartAccount[]>([])
  const [form, setForm] = useState({ ...EMPTY })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formMsg, setFormMsg] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [periodDate, setPeriodDate] = useState(todayIso())
  const [runMsg, setRunMsg] = useState<string | null>(null)
  // با هر ریست/شروعِ ویرایش/ثبتِ موفق زیاد می‌شود تا ویزارد به مرحله‌ی اول برگردد.
  const [formVersion, setFormVersion] = useState(0)

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const fundingAccounts = accounts
    .filter((a) => !a.is_group && FUNDING_ROLES.includes(a.system_role ?? ''))
    .sort((x, y) => x.code.localeCompare(y.code))

  function setFormField<K extends keyof typeof EMPTY>(key: K, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function resetForm() {
    setForm({ ...EMPTY })
    setEditingId(null)
    setFormMsg(null)
    setFormVersion((v) => v + 1)
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
    setFormVersion((v) => v + 1)
  }

  const identityValid = !!form.name && Number(form.cost) > 0 && Number(form.useful_life_months) > 0

  async function submit(): Promise<boolean> {
    setFormMsg(null)
    if (!identityValid) {
      setFormMsg('نام، بهای تمام‌شده (بزرگ‌تر از صفر) و عمر مفید (ماه) الزامی است.')
      return false
    }
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
    setSubmitting(true)
    try {
      if (editingId) await updateFixedAsset(token, editingId, payload)
      else await createFixedAsset(token, payload)
      resetForm()
      await refresh()
      return true
    } catch (err) {
      setFormMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  //: «واگذاری» دیگر یک کلیکِ تکی نیست. خروجِ دارایی سند می‌زند و برای سند باید نوعِ
  //: خروج، مبلغِ دریافتی و حسابِ دریافت معلوم باشد — چیزی که در یک `confirm()` جا
  //: نمی‌شود. دکمه‌ی ردیف حالا به تبِ «خروج دارایی» می‌برد با همان دارایی انتخاب‌شده.

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

  // تخمینِ استهلاکِ ماهانه برای پیش‌نمایش (خطِ مستقیم): (بها − اسقاط) ÷ عمرِ مفید
  const monthlyEstimate = (() => {
    const life = Number(form.useful_life_months) || 0
    if (life <= 0) return 0
    return Math.round(((Number(form.cost) || 0) - (Number(form.salvage_value) || 0)) / life)
  })()

  return {
    assets,
    entries,
    accounts,
    fundingAccounts,
    form,
    setFormField,
    editingId,
    formMsg,
    submitting,
    periodDate,
    setPeriodDate,
    runMsg,
    formVersion,
    refresh,
    resetForm,
    startEdit,
    identityValid,
    submit,
    handleDelete,
    handleRun,
    active,
    totalCost,
    totalAccum,
    totalBook,
    monthlyEstimate,
  }
}

export type FixedAssetDraft = ReturnType<typeof useFixedAssetDraft>
