import { useEffect, useMemo, useState } from 'react'
import { Package, Pencil, Plus, Save, Trash2, X } from 'lucide-react'
import { createItemLive, deleteItemLive, fetchItemsLive, updateItemLive, type ItemRecord } from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'

const faMoney = (n: number) => n.toLocaleString('fa-IR')

// واحدهای رایج برای انتخابِ سریع؛ «سایر…» اجازه‌ی تایپِ واحدِ دلخواه را می‌دهد.
// قیمت/بها همیشه «per واحد» است، پس اگر واحد «متر» باشد قیمتِ فروش یعنی قیمتِ هر متر
// و تعداد می‌تواند اعشاری باشد (مثلاً ۲٫۵ متر).
const COMMON_UNITS = [
  'عدد', 'متر', 'متر مربع', 'متر مکعب', 'سانتی‌متر', 'کیلوگرم', 'گرم', 'تن',
  'لیتر', 'بسته', 'کارتن', 'جعبه', 'جفت', 'دست', 'رول', 'طاقه', 'شاخه', 'عدل', 'ساعت',
]

interface DraftForm {
  sku: string
  name: string
  category: string
  unit: string
  salesPrice: string
  barcode: string
  reorderPoint: string
  isService: boolean
}

const EMPTY_FORM: DraftForm = { sku: '', name: '', category: '', unit: 'عدد', salesPrice: '', barcode: '', reorderPoint: '', isService: false }

/**
 * مدیریتِ کالاها/محصولات — ثبت، ویرایش و فعال/غیرفعال‌سازی.
 *
 * فهرست همیشه زنده از سرور خوانده می‌شود (مثل «اشخاص»)، پس مستقل از کشِ آفلاین است.
 * `onChanged` به لایه‌ی بالا خبر می‌دهد تا کشِ سراسریِ کالاها هم تازه شود؛ این‌طور
 * کالای تازه بلافاصله در فرم‌های فروش/خرید هم پیدا می‌شود (در وب فوری، در دسکتاپ با
 * هم‌گام‌سازی). ویرایش فقط فیلدهایی را می‌فرستد که سرور در ItemUpdateIn می‌پذیرد.
 */
export function ProductsPanel({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [products, setProducts] = useState<ItemRecord[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<DraftForm>(EMPTY_FORM)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function refresh() {
    setError(null)
    try {
      setProducts(await fetchItemsLive(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const filtered = useMemo(
    () =>
      products.filter((p) => {
        const q = search.trim()
        if (!q) return true
        return p.name.includes(q) || p.sku.includes(q) || p.category.includes(q)
      }),
    [products, search],
  )

  function resetForm() {
    setForm(EMPTY_FORM)
    setEditingId(null)
    setMessage(null)
  }

  function startEdit(p: ItemRecord) {
    setEditingId(p.id)
    setForm({
      sku: p.sku,
      name: p.name,
      category: p.category,
      unit: p.unit,
      salesPrice: String(Number(p.sales_price) || ''),
      barcode: p.barcode ?? '',
      reorderPoint: String(Number(p.reorder_point) || ''),
      isService: p.is_service,
    })
    setMessage(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!form.name.trim()) {
      setMessage('نام کالا الزامی است.')
      return
    }
    if (!editingId && !form.sku.trim()) {
      setMessage('کد کالا (SKU) الزامی است.')
      return
    }
    setSaving(true)
    try {
      if (editingId) {
        await updateItemLive(token, editingId, {
          name: form.name.trim(),
          sales_price: Number(form.salesPrice) || 0,
          barcode: form.barcode.trim() || null,
          reorder_point: Number(form.reorderPoint) || 0,
        })
        setMessage('کالا ویرایش شد.')
      } else {
        await createItemLive(token, {
          sku: form.sku.trim(),
          name: form.name.trim(),
          category: form.category.trim(),
          unit: form.unit.trim() || 'عدد',
          is_service: form.isService,
          sales_price: Number(form.salesPrice) || 0,
          barcode: form.barcode.trim() || null,
          reorder_point: Number(form.reorderPoint) || 0,
        })
        setMessage('کالای جدید ثبت شد.')
      }
      resetForm()
      await refresh()
      onChanged?.()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(p: ItemRecord) {
    setError(null)
    try {
      await updateItemLive(token, p.id, { is_active: !p.is_active })
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleDelete(p: ItemRecord) {
    setError(null)
    // حذف بازگشت‌ناپذیر است؛ کالاهایی که در سندی استفاده شده‌اند از سمتِ سرور با ۴۰۹ رد
    // می‌شوند و پیامِ «غیرفعال کنید» می‌گیرند — اینجا فقط یک تأییدِ ساده کافی است.
    if (!window.confirm(`کالای «${p.name}» برای همیشه حذف شود؟`)) return
    try {
      await deleteItemLive(token, p.id)
      if (editingId === p.id) resetForm()
      await refresh()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <div className="workspace-split">
      <SectionCard
        icon={editingId ? Pencil : Plus}
        title={editingId ? 'ویرایش کالا' : 'کالای جدید'}
        description={
          editingId
            ? 'نام و قیمت فروش این کالا را به‌روزرسانی کنید.'
            : 'کالا یا خدماتِ تازه را با کد یکتا ثبت کنید تا در فروش، خرید و انبار در دسترس باشد.'
        }
        actions={
          editingId ? (
            <button onClick={resetForm}>
              <X size={13} /> انصراف
            </button>
          ) : undefined
        }
      >
        <form className="invoice-form form-full" onSubmit={handleSubmit}>
          <div className="field-row">
            <label>
              کد کالا (SKU)
              <input
                type="text"
                value={form.sku}
                onChange={(e) => setForm({ ...form, sku: e.target.value })}
                placeholder="مثلاً A-1001"
                disabled={!!editingId}
                required={!editingId}
              />
            </label>
            <label>
              نام کالا
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="نام کالا یا خدمات"
                required
              />
            </label>
          </div>
          <div className="field-row">
            <label>
              دسته
              <input
                type="text"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                placeholder="اختیاری"
                disabled={!!editingId}
              />
            </label>
            <label>
              واحد
              <select
                value={COMMON_UNITS.includes(form.unit) ? form.unit : '__custom__'}
                onChange={(e) => setForm({ ...form, unit: e.target.value === '__custom__' ? '' : e.target.value })}
                disabled={!!editingId}
              >
                {COMMON_UNITS.map((u) => (<option key={u} value={u}>{u}</option>))}
                <option value="__custom__">سایر (دستی)…</option>
              </select>
              {!COMMON_UNITS.includes(form.unit) && (
                <input
                  type="text"
                  value={form.unit}
                  onChange={(e) => setForm({ ...form, unit: e.target.value })}
                  placeholder="واحدِ دلخواه، مثلاً «قواره»"
                  disabled={!!editingId}
                  style={{ marginTop: 6 }}
                />
              )}
            </label>
          </div>
          <div className="field-row">
            <label>
              قیمت فروش (ریال، هر {form.unit || 'واحد'})
              <input
                type="number"
                min="0"
                value={form.salesPrice}
                onChange={(e) => setForm({ ...form, salesPrice: e.target.value })}
                placeholder="۰"
              />
            </label>
            <label>
              بارکد (برای صندوق فروشگاهی)
              <input
                type="text"
                value={form.barcode}
                onChange={(e) => setForm({ ...form, barcode: e.target.value })}
                placeholder="اسکن یا تایپ — اختیاری"
                inputMode="numeric"
              />
            </label>
          </div>
          {!form.isService && (
            <div className="field-row">
              <label>
                نقطه‌ی سفارش (حداقلِ موجودی)
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={form.reorderPoint}
                  onChange={(e) => setForm({ ...form, reorderPoint: e.target.value })}
                  placeholder="۰ = بدون هشدار"
                />
                <span className="field-hint">وقتی موجودیِ کل به این عدد یا کمتر برسد، در «نیازمندِ سفارش» هشدار داده می‌شود.</span>
              </label>
              <span aria-hidden="true" />
            </div>
          )}
          {!editingId ? (
            <label className="cal-check-inline">
              <input
                type="checkbox"
                checked={form.isService}
                onChange={(e) => setForm({ ...form, isService: e.target.checked })}
              />
              این یک خدمات است (بدون موجودیِ انبار)
            </label>
          ) : (
            <p className="hint">کد، دسته و واحد پس از ایجاد ثابت‌اند و اینجا قابل تغییر نیستند.</p>
          )}
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={saving}>
              <Save size={14} /> {editingId ? 'ذخیره تغییرات' : 'ثبت کالا'}
            </button>
          </div>
          {message && <div className="hint">{message}</div>}
        </form>
      </SectionCard>

      <SectionCard
        icon={Package}
        title="لیست کالاها"
        description={`${faMoney(filtered.length)} کالا`}
        actions={
          <div className="check-actions">
            <input
              type="text"
              placeholder="جستجو نام، کد یا دسته..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        }
      >
        {error && <div className="error">{error}</div>}
        {filtered.length === 0 ? (
          <EmptyState icon={Package} text="هنوز کالایی ثبت نشده — از فرمِ کنار، اولین کالا را بسازید." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead>
                <tr>
                  <th>کالا</th>
                  <th>دسته</th>
                  <th>واحد</th>
                  <th>قیمت فروش</th>
                  <th>وضعیت</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <div className="entity-cell">
                        <div className="entity-avatar">{p.name.trim().charAt(0) || '؟'}</div>
                        <div>
                          <div className="entity-name">{p.name}</div>
                          <div className="entity-sub ltr-cell">{p.barcode ? `${p.sku} · ${p.barcode}` : p.sku}</div>
                          {!p.is_service && Number(p.reorder_point) > 0 && (
                            <div className="entity-sub">نقطه‌ی سفارش: {faMoney(Number(p.reorder_point))} {p.unit}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>{p.category || '—'}</td>
                    <td>{p.is_service ? 'خدمات' : p.unit}</td>
                    <td className="money-cell">{faMoney(Number(p.sales_price))}</td>
                    <td>
                      <span className={`status-badge ${p.is_active ? 'tone-success' : 'tone-warning'}`}>
                        {p.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td>
                      <div className="check-actions">
                        <button type="button" onClick={() => startEdit(p)}>
                          <Pencil size={13} /> ویرایش
                        </button>
                        <button type="button" onClick={() => void toggleActive(p)}>
                          {p.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}
                        </button>
                        <button type="button" className="icon-btn-danger" onClick={() => void handleDelete(p)} aria-label="حذف کالا">
                          <Trash2 size={13} /> حذف
                        </button>
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
