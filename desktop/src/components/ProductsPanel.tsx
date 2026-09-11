import { useEffect, useMemo, useState } from 'react'
import { Package, Pencil, Plus, Save, Trash2, X, Camera } from 'lucide-react'
import {
  createItemLive,
  deleteItemLive,
  fetchAccountsLive,
  fetchItemsLive,
  updateItemLive,
  type ItemRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { BarcodeScanner } from './BarcodeScanner'

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
  name2: string
  category: string
  unit: string
  salesPrice: string
  barcode: string
  iranCode: string
  barcode2: string
  reorderPoint: string
  taxStuffId: string
  vatStatus: string
  purchaseVatStatus: string
  taxRate: string
  dutyRate: string
  expenseAccountId: string
  isService: boolean
  isSellable: boolean
  isSerialTracked: boolean
}

const EMPTY_FORM: DraftForm = {
  sku: '', name: '', name2: '', category: '', unit: 'عدد', salesPrice: '',
  barcode: '', iranCode: '', barcode2: '', reorderPoint: '', taxStuffId: '',
  vatStatus: 'taxable', purchaseVatStatus: 'taxable', taxRate: '', dutyRate: '',
  expenseAccountId: '', isService: false, isSellable: true, isSerialTracked: false,
}

/**
 * تعریفِ کالا و خدمت — **یک شناسنامه برای هر قلم، رفتارِ وابسته به نوع**.
 *
 * کوبیتا عمداً برای خرید و فروش و انبار سه تعریفِ جدا از یک کالا ندارد؛ همین یک
 * رکورد در فروش، خرید، انبار، صندوق، تولید و مؤدیان به‌کار می‌رود. ولی رفتارشان
 * یکی نیست: خدمت موجودی ندارد و بهای خریدش به حسابِ **هزینه** می‌نشیند، نه به
 * موجودیِ کالا — پس بخش‌های انباریِ فرم برای خدمت اصلاً نشان داده نمی‌شوند.
 *
 * چیزی که این‌جا **نیست** و عمدی است: موجودی. مانده همیشه از حرکاتِ انبار مشتق
 * می‌شود و «درست‌کردنِ موجودی با ویرایشِ کالا» نباید ممکن باشد.
 */
export function ProductsPanel({ token, onChanged }: { token: string; onChanged?: () => void }) {
  const [products, setProducts] = useState<ItemRecord[]>([])
  const [accounts, setAccounts] = useState<{ id: string; code: string; name: string; is_group: number }[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<DraftForm>(EMPTY_FORM)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [scanning, setScanning] = useState(false) // نمای دوربینِ اسکنِ بارکد باز است؟

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

  useEffect(() => {
    //: فقط حساب‌های برگی می‌توانند معینِ هزینه باشند — حسابِ گروه ردیفِ سند
    //: نمی‌پذیرد و سرور هم ردش می‌کند؛ نیاوردنش در فهرست یعنی کاربر اصلاً به آن
    //: خطا نمی‌خورد.
    void (async () => {
      try {
        setAccounts((await fetchAccountsLive(token)).filter((a) => !a.is_group))
      } catch {
        setAccounts([])
      }
    })()
  }, [token])

  const accountOptions = useMemo(
    () => accounts.map((a) => ({ id: a.id, label: `${a.code} — ${a.name}` })),
    [accounts],
  )

  const filtered = useMemo(
    () =>
      products.filter((p) => {
        const q = search.trim()
        if (!q) return true
        return (
          p.name.includes(q) ||
          p.name2.includes(q) ||
          p.sku.includes(q) ||
          p.category.includes(q) ||
          (p.barcode ?? '').includes(q) ||
          p.iran_code.includes(q)
        )
      }),
    [products, search],
  )
  // صفحه‌بندیِ جدولِ داده (۱۰ ردیف)؛ با تغییرِ جست‌وجو صفحه به اول برمی‌گردد.
  const { pageItems, page, setPage, pageCount } = usePagination(filtered, 10, search)

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
      name2: p.name2 ?? '',
      category: p.category,
      unit: p.unit,
      salesPrice: String(Number(p.sales_price) || ''),
      barcode: p.barcode ?? '',
      iranCode: p.iran_code ?? '',
      barcode2: p.barcode2 ?? '',
      reorderPoint: String(Number(p.reorder_point) || ''),
      taxStuffId: p.tax_stuff_id ?? '',
      vatStatus: p.vat_status ?? 'taxable',
      purchaseVatStatus: p.purchase_vat_status ?? 'taxable',
      taxRate: String(Number(p.tax_rate) || ''),
      dutyRate: String(Number(p.duty_rate) || ''),
      expenseAccountId: p.expense_account_id ?? '',
      isService: p.is_service,
      isSellable: p.is_sellable,
      isSerialTracked: p.is_serial_tracked,
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
    if (!form.sku.trim()) {
      setMessage('کد کالا (SKU) الزامی است.')
      return
    }
    //: فیلدهای مشترکِ ساخت و ویرایش. `is_service` عمداً فقط در ساخت می‌آید:
    //: تبدیلِ کالا به خدمت پس از گردش، تاریخِ انبار را غیرمنطقی می‌کند.
    const shared = {
      sku: form.sku.trim(),
      name: form.name.trim(),
      name2: form.name2.trim(),
      category: form.category.trim(),
      unit: form.unit.trim() || 'عدد',
      sales_price: Number(form.salesPrice) || 0,
      barcode: form.barcode.trim() || null,
      iran_code: form.iranCode.trim(),
      barcode2: form.barcode2.trim(),
      reorder_point: Number(form.reorderPoint) || 0,
      tax_stuff_id: form.taxStuffId.trim(),
      vat_status: form.vatStatus,
      purchase_vat_status: form.purchaseVatStatus,
      tax_rate: Number(form.taxRate) || 0,
      duty_rate: Number(form.dutyRate) || 0,
      expense_account_id: form.isService ? form.expenseAccountId || null : null,
      is_sellable: form.isSellable,
      is_serial_tracked: form.isService ? false : form.isSerialTracked,
    }
    setSaving(true)
    try {
      if (editingId) {
        await updateItemLive(token, editingId, shared)
        setMessage('کالا ویرایش شد.')
      } else {
        await createItemLive(token, { ...shared, is_service: form.isService })
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
        title={editingId ? 'ویرایش کالا/خدمت' : 'کالا/خدمتِ جدید'}
        description={
          editingId
            ? 'شناسنامه‌ی این قلم. تغییرش هیچ سند یا حرکتِ انباریِ گذشته‌ای را بازنویسی نمی‌کند.'
            : 'یک تعریف برای همه‌جا: فروش، خرید، انبار، صندوق و گزارش‌ها همگی از همین می‌خوانند.'
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
          <h4 className="form-section-title">اطلاعات پایه</h4>
          <div className="field-row">
            <label>
              کد کالا (SKU)
              <input
                type="text"
                value={form.sku}
                onChange={(e) => setForm({ ...form, sku: e.target.value })}
                placeholder="مثلاً A-1001"
                required
              />
              <span className="field-hint">
                شناسه‌ی کسب‌وکاری است و قابلِ اصلاح؛ پیوندهای درونیِ سیستم رویش بسته نیستند.
              </span>
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
              عنوان دوم
              <input
                type="text"
                value={form.name2}
                onChange={(e) => setForm({ ...form, name2: e.target.value })}
                placeholder="اختیاری — مثلاً نامِ انگلیسی"
              />
            </label>
            <label>
              دسته
              <input
                type="text"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                placeholder="اختیاری"
              />
            </label>
          </div>
          <div className="field-row">
            <label>
              واحد
              <select
                value={COMMON_UNITS.includes(form.unit) ? form.unit : '__custom__'}
                onChange={(e) => setForm({ ...form, unit: e.target.value === '__custom__' ? '' : e.target.value })}
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
                  style={{ marginTop: 6 }}
                />
              )}
              <span className="field-hint">خدمت هم واحد دارد — «ساعت» واحدِ مشاوره است، ولی موجودی نمی‌سازد.</span>
            </label>
            <label>
              قیمت فروش (ریال، هر {form.unit || 'واحد'})
              <NumberInput
                value={form.salesPrice}
                onChange={(v) => setForm({ ...form, salesPrice: v })}
                placeholder="۰"
              />
            </label>
          </div>
          <div className="field-row">
            <label className="cal-check-inline">
              <input
                type="checkbox"
                checked={form.isSellable}
                onChange={(e) => setForm({ ...form, isSellable: e.target.checked })}
              />
              قابل فروش
            </label>
            {!editingId && (
              <label className="cal-check-inline">
                <input
                  type="checkbox"
                  checked={form.isService}
                  onChange={(e) => setForm({ ...form, isService: e.target.checked })}
                />
                این یک خدمات است (بدون موجودیِ انبار)
              </label>
            )}
          </div>
          <p className="hint">
            «فعال» و «قابل فروش» دو چیزند: موادِ اولیه و موادِ بسته‌بندی موجودی دارند و گردش
            می‌کنند، ولی نباید در فاکتورِ فروش و صندوق انتخاب شوند.
            {editingId && ' نوعِ قلم (کالا/خدمت) پس از ایجاد تغییر نمی‌کند.'}
          </p>

          <h4 className="form-section-title">شناسه‌ها</h4>
          <div className="field-row">
            <label>
              بارکد (برای صندوق فروشگاهی)
              <div className="barcode-field">
                <input
                  type="text"
                  value={form.barcode}
                  onChange={(e) => setForm({ ...form, barcode: e.target.value })}
                  placeholder="اسکن یا تایپ — اختیاری"
                  inputMode="numeric"
                />
                <button type="button" className="barcode-scan-btn" onClick={() => setScanning(true)} title="اسکن با دوربین" aria-label="اسکن با دوربین">
                  <Camera size={16} />
                </button>
              </div>
            </label>
            <label>
              ایران‌کد
              <input
                type="text"
                value={form.iranCode}
                onChange={(e) => setForm({ ...form, iranCode: e.target.value })}
                placeholder="اختیاری"
                inputMode="numeric"
              />
            </label>
          </div>
          {scanning && (
            <BarcodeScanner
              once
              onDetected={(code) => setForm((f) => ({ ...f, barcode: code }))}
              onClose={() => setScanning(false)}
            />
          )}
          <div className="field-row">
            <label>
              بارکد دوبعدی
              <input
                type="text"
                value={form.barcode2}
                onChange={(e) => setForm({ ...form, barcode2: e.target.value })}
                placeholder="اختیاری — محتوای QR"
                dir="ltr"
              />
            </label>
            <label>
              شناسه کالا/خدمتِ مالیاتی (مؤدیان، ۱۳ رقمی)
              <input
                type="text"
                value={form.taxStuffId}
                onChange={(e) => setForm({ ...form, taxStuffId: e.target.value })}
                placeholder="اختیاری"
                inputMode="numeric"
              />
              <span className="field-hint">خالی بماند، «شناسه‌ی پیش‌فرض»ِ تنظیماتِ مؤدیان استفاده می‌شود.</span>
            </label>
          </div>
          <p className="hint">
            کدِ کالا، بارکد، ایران‌کد و بارکدِ دوبعدی چهار شناسه‌ی جدا هستند و یکی‌شان نمی‌کنیم.
          </p>

          <h4 className="form-section-title">مالیات و عوارض</h4>
          <div className="field-row">
            <label>
              وضعیت مالیاتی — فروش
              <select value={form.vatStatus} onChange={(e) => setForm({ ...form, vatStatus: e.target.value })}>
                <option value="taxable">مشمول</option>
                <option value="exempt">معاف</option>
              </select>
            </label>
            <label>
              وضعیت مالیاتی — خرید
              <select
                value={form.purchaseVatStatus}
                onChange={(e) => setForm({ ...form, purchaseVatStatus: e.target.value })}
              >
                <option value="taxable">مشمول</option>
                <option value="exempt">معاف</option>
              </select>
            </label>
          </div>
          <div className="field-row">
            <label>
              نرخ مالیات (٪)
              <NumberInput
                allowDecimal
                value={form.taxRate}
                onChange={(v) => setForm({ ...form, taxRate: v })}
                placeholder="۰ = نرخِ سرِ فاکتور"
              />
            </label>
            <label>
              نرخ عوارض (٪)
              <NumberInput
                allowDecimal
                value={form.dutyRate}
                onChange={(v) => setForm({ ...form, dutyRate: v })}
                placeholder="۰"
              />
            </label>
          </div>
          <p className="hint">
            «معاف» از «نرخِ صفر» جداست: نرخِ صفر نمی‌گوید کالا معاف بوده یا فقط آن فاکتور
            بی‌مالیات صادر شده. وضعیتِ خرید و فروش هم الزاماً یکی نیست. نرخِ خالی یعنی نرخِ
            سرِ فاکتور. تغییرِ این‌ها فقط روی معاملاتِ بعدی اثر دارد — فاکتورهای گذشته نرخِ
            روزِ خودشان را نگه می‌دارند.
          </p>

          {form.isService ? (
            <>
              <h4 className="form-section-title">حسابداریِ خدمت</h4>
              <label className="form-field">
                معین هزینه خرید خدمت
                <select
                  value={form.expenseAccountId}
                  onChange={(e) => setForm({ ...form, expenseAccountId: e.target.value })}
                >
                  <option value="">— حساب پیش‌فرضِ «هزینه خرید خدمات» —</option>
                  {accountOptions.map((a) => (
                    <option key={a.id} value={a.id}>{a.label}</option>
                  ))}
                </select>
                <span className="field-hint">
                  خریدِ خدمت به این حساب می‌نشیند، نه به «موجودی کالا» — خدمت حرکتِ انباری ندارد.
                </span>
              </label>
            </>
          ) : (
            <>
              <h4 className="form-section-title">انبار و موجودی</h4>
              <div className="field-row">
                <label>
                  نقطه‌ی سفارش (حداقلِ موجودی)
                  <NumberInput
                    allowDecimal
                    value={form.reorderPoint}
                    onChange={(v) => setForm({ ...form, reorderPoint: v })}
                    placeholder="۰ = بدون هشدار"
                  />
                  <span className="field-hint">وقتی موجودیِ کل به این عدد یا کمتر برسد، در «نیازمندِ سفارش» هشدار داده می‌شود.</span>
                </label>
                <label className="cal-check-inline">
                  <input
                    type="checkbox"
                    checked={form.isSerialTracked}
                    onChange={(e) => setForm({ ...form, isSerialTracked: e.target.checked })}
                  />
                  ثبت سریالی
                </label>
              </div>
              <p className="hint">
                «ثبت سریالی» پس از شروعِ گردشِ انباری قابل تغییر نیست: موجودیِ ثبت‌شده سریال
                ندارد و عوض‌کردنِ این تنظیم ردیابی را مبهم می‌کند.
              </p>
            </>
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
        title="لیست کالاها و خدمات"
        description={`${faMoney(filtered.length)} قلم`}
        actions={
          <div className="check-actions">
            <input
              type="text"
              placeholder="جستجو نام، کد، بارکد یا دسته..."
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
            <div className="table-scroll">
              <table className="entity-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>کالا</th>
                    <th>نوع</th>
                    <th>دسته</th>
                    <th>واحد</th>
                    <th>قیمت فروش</th>
                    <th>وضعیت</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((p) => (
                    <tr key={p.id}>
                      <td className="card-title" data-label="کالا">
                        <div className="entity-cell">
                          <div className="entity-avatar">{p.name.trim().charAt(0) || '؟'}</div>
                          <div>
                            <div className="entity-name">{p.name}</div>
                            {p.name2 && <div className="entity-sub">{p.name2}</div>}
                            <div className="entity-sub ltr-cell">{p.barcode ? `${p.sku} · ${p.barcode}` : p.sku}</div>
                            {!p.is_service && Number(p.reorder_point) > 0 && (
                              <div className="entity-sub">نقطه‌ی سفارش: {faMoney(Number(p.reorder_point))} {p.unit}</div>
                            )}
                            {p.is_service && p.expense_account_name && (
                              <div className="entity-sub">
                                معین هزینه: {p.expense_account_code} — {p.expense_account_name}
                                {p.expense_account_is_default ? ' (پیش‌فرض)' : ''}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td data-label="نوع">{p.is_service ? 'خدمت' : 'کالا'}</td>
                      <td data-label="دسته">{p.category || '—'}</td>
                      <td data-label="واحد">{p.unit}</td>
                      <td data-label="قیمت فروش" className="money-cell">{faMoney(Number(p.sales_price))}</td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${p.is_active ? 'tone-success' : 'tone-warning'}`}>
                          {p.is_active ? 'فعال' : 'غیرفعال'}
                        </span>
                        {!p.is_sellable && <div className="entity-sub">غیرقابل فروش</div>}
                        {p.is_serial_tracked && <div className="entity-sub">سریالی</div>}
                      </td>
                      <td className="card-actions">
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
            <Pager page={page} pageCount={pageCount} onChange={setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}
