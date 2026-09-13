import { useCallback, useEffect, useState } from 'react'
import { Percent, Save, Pencil, Trash2, X, Power } from 'lucide-react'
import {
  PURCHASE_DEDUCTION_BASIS_LABELS,
  PURCHASE_DEDUCTION_NATURE_LABELS,
  can,
  createPurchaseDeductionType,
  deletePurchaseDeductionType,
  fetchAccountsLive,
  fetchPurchaseDeductionTypes,
  updatePurchaseDeductionType,
  type MeResponse,
  type PurchaseDeductionBasis,
  type PurchaseDeductionNature,
  type PurchaseDeductionType,
  type PurchaseDeductionTypeInput,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'

interface FormState {
  code: string
  name: string
  nature: PurchaseDeductionNature
  basis: PurchaseDeductionBasis
  rate: string
  accountId: string
  isActive: boolean
  description: string
}

const EMPTY_FORM: FormState = {
  code: '',
  name: '',
  nature: 'withholding_tax',
  basis: 'net_before_tax',
  rate: '',
  accountId: '',
  isActive: true,
  description: '',
}

//: نامِ حسابی که وقتی حسابی انتخاب نشده خودکار ساخته/استفاده می‌شود — همان نام‌های سرور.
const DEFAULT_ACCOUNT_LABEL: Record<PurchaseDeductionNature, string> = {
  withholding_tax: 'مالیات تکلیفی پرداختنی',
  insurance: 'حق بیمه پرداختنی اشخاص ثالث',
}

const faRate = (value: string | number) => Number(value).toLocaleString('fa-IR', { maximumFractionDigits: 3 })

function toInput(row: PurchaseDeductionType): PurchaseDeductionTypeInput {
  return {
    code: row.code,
    name: row.name,
    nature: row.nature,
    basis: row.basis,
    rate: Number(row.rate),
    account_id: row.account_id,
    is_active: row.is_active,
    description: row.description,
  }
}

/** «انواع کسورات» — داده‌ی پایه‌ی مالیات تکلیفی و بیمه‌ی فاکتور خرید خدمات.
 *
 *  هیچ نرخی از پیش ساخته نمی‌شود: درصدها به قانون و قرارداد بسته‌اند و کسب‌وکار خودش
 *  تعریفشان می‌کند. فاکتورِ ثبت‌شده Snapshotِ نرخ و حساب را دارد، پس ویرایشِ این‌جا
 *  فقط فاکتورهای بعدی را عوض می‌کند. */
export function PurchaseDeductionTypesPanel({
  token,
  me,
  onChanged,
}: {
  token: string
  me: MeResponse
  onChanged?: () => void
}) {
  const [rows, setRows] = useState<PurchaseDeductionType[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [accounts, setAccounts] = useState<{ id: string; code: string; name: string }[]>([])
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const canCreate = can(me, 'invoices', 'create')
  const canUpdate = can(me, 'invoices', 'update')
  const canDelete = can(me, 'invoices', 'delete')

  const refresh = useCallback(async () => {
    try {
      setRows(await fetchPurchaseDeductionTypes(token))
      setLoadError(null)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'دریافتِ انواع کسورات ناموفق بود')
      setRows([])
    }
  }, [token])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    //: کسر بدهی است؛ فقط حساب‌های بدهیِ سندپذیر در فهرست می‌آیند — سرور هم بقیه را رد می‌کند.
    fetchAccountsLive(token)
      .then((list) => setAccounts(list.filter((a) => !a.is_group && a.type === 'liability')))
      .catch(() => setAccounts([]))
  }, [token])

  function startEdit(row: PurchaseDeductionType) {
    setEditingId(row.id)
    setMessage(null)
    setForm({
      code: row.code,
      name: row.name,
      nature: row.nature,
      basis: row.basis,
      rate: String(Number(row.rate) || ''),
      accountId: row.account_id ?? '',
      isActive: row.is_active,
      description: row.description,
    })
  }

  function resetForm() {
    setEditingId(null)
    setForm(EMPTY_FORM)
  }

  async function save() {
    const rate = Number(form.rate) || 0
    if (!form.name.trim()) {
      setMessage('عنوانِ کسر را بنویسید؛ همین عنوان روی فاکتور و چاپ می‌آید.')
      return
    }
    if (rate < 0 || rate > 100) {
      setMessage('نرخ باید بین ۰ و ۱۰۰ باشد.')
      return
    }
    const payload: PurchaseDeductionTypeInput = {
      code: form.code.trim(),
      name: form.name.trim(),
      nature: form.nature,
      basis: form.basis,
      rate,
      account_id: form.accountId || null,
      is_active: form.isActive,
      description: form.description.trim(),
    }
    setBusy(true)
    setMessage(null)
    try {
      if (editingId) {
        await updatePurchaseDeductionType(token, editingId, payload)
        setMessage('ذخیره شد. فاکتورهای ثبت‌شده همان نرخ و حسابِ قبلی را نگه می‌دارند.')
      } else {
        await createPurchaseDeductionType(token, payload)
        setMessage(`«${payload.name}» ساخته شد و در فاکتور خرید خدمات قابلِ انتخاب است.`)
      }
      resetForm()
      await refresh()
      onChanged?.()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'ذخیره ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  async function toggleActive(row: PurchaseDeductionType) {
    setBusy(true)
    setMessage(null)
    try {
      await updatePurchaseDeductionType(token, row.id, { ...toInput(row), is_active: !row.is_active })
      setMessage(row.is_active ? `«${row.name}» غیرفعال شد و در فاکتورِ تازه نمی‌آید.` : `«${row.name}» دوباره فعال شد.`)
      await refresh()
      onChanged?.()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'تغییرِ وضعیت ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  async function remove(row: PurchaseDeductionType) {
    if (!window.confirm(`«${row.name}» حذف شود؟`)) return
    setBusy(true)
    setMessage(null)
    try {
      await deletePurchaseDeductionType(token, row.id)
      setMessage(`«${row.name}» حذف شد.`)
      if (editingId === row.id) resetForm()
      await refresh()
      onChanged?.()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'حذف ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  const showForm = editingId ? canUpdate : canCreate

  return (
    <SectionCard
      icon={Percent}
      title="انواع کسورات خرید خدمات"
      description="مالیات تکلیفی و بیمه‌ای که از فاکتور خرید خدمات کسر و به بدهیِ جدا منتقل می‌شود. نرخ را خودتان تعریف کنید؛ فاکتورِ ثبت‌شده با تغییرِ این‌جا عوض نمی‌شود."
    >
      {showForm && (
        <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void save()
          }}
        >
          <div className="field-row">
            <label>
              عنوان
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label>
              کد (اختیاری)
              <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </label>
          </div>
          <div className="field-row">
            <label>
              ماهیت
              <select
                value={form.nature}
                onChange={(e) => setForm({ ...form, nature: e.target.value as PurchaseDeductionNature })}
              >
                {(Object.keys(PURCHASE_DEDUCTION_NATURE_LABELS) as PurchaseDeductionNature[]).map((key) => (
                  <option key={key} value={key}>{PURCHASE_DEDUCTION_NATURE_LABELS[key]}</option>
                ))}
              </select>
            </label>
            <label>
              مبنای محاسبه
              <select
                value={form.basis}
                onChange={(e) => setForm({ ...form, basis: e.target.value as PurchaseDeductionBasis })}
              >
                {(Object.keys(PURCHASE_DEDUCTION_BASIS_LABELS) as PurchaseDeductionBasis[]).map((key) => (
                  <option key={key} value={key}>{PURCHASE_DEDUCTION_BASIS_LABELS[key]}</option>
                ))}
              </select>
            </label>
            <label>
              نرخِ پیش‌فرض (٪)
              <NumberInput allowDecimal value={form.rate} onChange={(value) => setForm({ ...form, rate: value })} />
            </label>
          </div>
          <label>
            حسابِ بدهی
            <select value={form.accountId} onChange={(e) => setForm({ ...form, accountId: e.target.value })}>
              <option value="">— پیش‌فرض: «{DEFAULT_ACCOUNT_LABEL[form.nature]}» —</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
              ))}
            </select>
            <span className="field-hint">
              خالی بگذارید تا حسابِ پیش‌فرضِ همین ماهیت بخورد؛ اگر در چارت نباشد، با اولین فاکتور ساخته می‌شود.
            </span>
          </label>
          <div className="field-row">
            <label>
              توضیح
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </label>
            <label>
              وضعیت
              <select
                value={form.isActive ? 'active' : 'inactive'}
                onChange={(e) => setForm({ ...form, isActive: e.target.value === 'active' })}
              >
                <option value="active">فعال</option>
                <option value="inactive">غیرفعال</option>
              </select>
            </label>
          </div>
          <div className="invoice-form-footer">
            {editingId && (
              <button type="button" onClick={resetForm}>
                <X size={14} /> انصراف
              </button>
            )}
            <button type="submit" className="btn-primary" disabled={busy}>
              <Save size={14} /> {editingId ? 'ذخیره‌ی تغییرات' : 'ساختِ نوعِ کسر'}
            </button>
          </div>
        </form>
      )}

      {message && <div className="hint">{message}</div>}
      {loadError && <div className="hint">{loadError}</div>}

      {rows === null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Percent}
          text="هنوز نوعِ کسری تعریف نشده. برای مالیات تکلیفی یا بیمه‌ی قراردادها یک نوع بسازید و نرخش را وارد کنید؛ کوبیتا درصدی از پیش فرض نمی‌کند."
        />
      ) : (
        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead>
              <tr>
                <th>عنوان</th>
                <th>کد</th>
                <th>ماهیت</th>
                <th>مبنا</th>
                <th>نرخ</th>
                <th>حساب</th>
                <th>وضعیت</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} style={row.is_active ? undefined : { opacity: 0.6 }}>
                  <td className="card-title" data-label="عنوان">{row.name}</td>
                  <td data-label="کد">{row.code || '—'}</td>
                  <td data-label="ماهیت">{row.nature_label}</td>
                  <td data-label="مبنا">{row.basis_label}</td>
                  <td className="num" data-label="نرخ">{faRate(row.rate)}٪</td>
                  <td data-label="حساب">
                    {row.account_code ? `${row.account_code} — ` : ''}
                    {row.account_name}
                    {row.account_is_default ? ' (پیش‌فرض)' : ''}
                  </td>
                  <td data-label="وضعیت">
                    {row.is_active ? 'فعال' : 'غیرفعال'}
                    {row.in_use ? ' · در فاکتور خورده' : ''}
                  </td>
                  <td className="card-actions">
                    <div className="check-actions">
                      {canUpdate && (
                        <button type="button" disabled={busy} onClick={() => startEdit(row)}>
                          <Pencil size={13} /> ویرایش
                        </button>
                      )}
                      {canUpdate && (
                        <button type="button" disabled={busy} onClick={() => void toggleActive(row)}>
                          <Power size={13} /> {row.is_active ? 'غیرفعال‌کردن' : 'فعال‌کردن'}
                        </button>
                      )}
                      {canDelete && !row.in_use && (
                        <button type="button" className="icon-btn-danger" disabled={busy} onClick={() => void remove(row)}>
                          <Trash2 size={13} /> حذف
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}
