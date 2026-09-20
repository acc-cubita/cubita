import { useEffect, useMemo, useState } from 'react'
import { Package, Pencil, Plus, Save, Trash2, X, Camera } from 'lucide-react'
import {
  createItemLive,
  deleteItemLive,
  fetchAccountsLive,
  fetchItemsLive,
  fetchItemAttributes,
  fetchItemGroups,
  fetchUnits,
  fetchWarehousesAdmin,
  updateItemLive,
  type ItemAttributeRecord,
  type ItemGroupRecord,
  type ItemRecord,
  type UnitRecord,
  type WarehouseRecord,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { BarcodeScanner } from './BarcodeScanner'
import { SearchSelect } from '../components/SearchSelect'

const faMoney = (n: number) => n.toLocaleString('fa-IR')

// واحدها از داده‌ی پایه می‌آیند، نه از یک فهرستِ ثابت در کد و نه از تایپِ آزاد:
// «کیلوگرم» و «كيلوگرم» نباید دو واحدِ متفاوت شوند. مدیریتشان در تبِ «واحدها».
// قیمت/بها همیشه «per واحدِ اصلی» است، پس اگر واحد «متر» باشد قیمتِ فروش یعنی
// قیمتِ هر متر و تعداد می‌تواند اعشاری باشد (مثلاً ۲٫۵ متر).

/** یک انبارِ مرتبط در فرم. `null` در سقف/کف یعنی «همان عددِ کالا». */
interface WarehouseLinkDraft {
  warehouseId: string
  isDefault: boolean
  minStock: string
  maxStock: string
}

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
  primaryUnitId: string
  secondaryUnitId: string
  conversionFactor: string
  conversionMode: string
  unitWeight: string
  unitVolume: string
  minStock: string
  maxStock: string
  groupId: string
  attributes: Record<string, string>
  warehouses: WarehouseLinkDraft[]
  isService: boolean
  isSellable: boolean
  isSerialTracked: boolean
  isBatchTracked: boolean
  minShelfLifeDays: string
  hasConsumerPrice: boolean
  printedPrice: string
  suggestedPrice: string
  maxPrice: string
}

const EMPTY_FORM: DraftForm = {
  sku: '', name: '', name2: '', category: '', unit: 'عدد', salesPrice: '',
  barcode: '', iranCode: '', barcode2: '', reorderPoint: '', taxStuffId: '',
  vatStatus: 'taxable', purchaseVatStatus: 'taxable', taxRate: '', dutyRate: '',
  expenseAccountId: '', primaryUnitId: '', secondaryUnitId: '', conversionFactor: '',
  conversionMode: 'fixed', unitWeight: '', unitVolume: '',
  minStock: '', maxStock: '', groupId: '', attributes: {}, warehouses: [],
  isService: false, isSellable: true, isSerialTracked: false,
  isBatchTracked: false, minShelfLifeDays: '',
  hasConsumerPrice: false, printedPrice: '', suggestedPrice: '', maxPrice: '',
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
  const [units, setUnits] = useState<UnitRecord[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseRecord[]>([])
  const [groups, setGroups] = useState<ItemGroupRecord[]>([])
  const [specs, setSpecs] = useState<ItemAttributeRecord[]>([])
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

  useEffect(() => {
    //: واحدها داده‌ی پایه‌اند و از سرور می‌آیند — نه فهرستِ ثابت در کد، نه تایپِ آزاد.
    void (async () => {
      try {
        setUnits((await fetchUnits(token)).filter((u) => u.is_active))
      } catch {
        setUnits([])
      }
    })()
  }, [token])

  const accountOptions = useMemo(
    () => accounts.map((a) => ({ id: a.id, label: `${a.code} — ${a.name}` })),
    [accounts],
  )

  useEffect(() => {
    void (async () => {
      try {
        setWarehouses((await fetchWarehousesAdmin(token)).filter((w) => w.is_active))
      } catch {
        setWarehouses([])
      }
    })()
  }, [token])

  useEffect(() => {
    //: گروه و مشخصه هر دو داده‌ی پایه‌اند و در تبِ «گروه و مشخصات» مدیریت می‌شوند.
    void (async () => {
      try {
        const [g, a] = await Promise.all([fetchItemGroups(token), fetchItemAttributes(token)])
        setGroups(g.filter((x) => x.is_active))
        setSpecs(a.filter((x) => x.is_active))
      } catch {
        setGroups([])
        setSpecs([])
      }
    })()
  }, [token])

  const unitName = (id: string) => units.find((u) => u.id === id)?.name ?? ''

  const linkFor = (warehouseId: string) => form.warehouses.find((w) => w.warehouseId === warehouseId)

  /** تیکِ یک انبار. برداشتنِ تیک هیچ حرکتِ انباریِ گذشته‌ای را پاک نمی‌کند. */
  function toggleWarehouse(warehouseId: string) {
    const existing = linkFor(warehouseId)
    setForm({
      ...form,
      warehouses: existing
        ? form.warehouses.filter((w) => w.warehouseId !== warehouseId)
        : [...form.warehouses, { warehouseId, isDefault: false, minStock: '', maxStock: '' }],
    })
  }

  function setLink(warehouseId: string, patch: Partial<WarehouseLinkDraft>) {
    setForm({
      ...form,
      warehouses: form.warehouses.map((w) => (w.warehouseId === warehouseId ? { ...w, ...patch } : w)),
    })
  }

  /** یک پیش‌فرض، نه دو تا — سرور هم همین را می‌گوید. */
  function makeDefault(warehouseId: string) {
    setForm({
      ...form,
      warehouses: form.warehouses.map((w) => ({ ...w, isDefault: w.warehouseId === warehouseId })),
    })
  }

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
      primaryUnitId: p.primary_unit_id ?? '',
      secondaryUnitId: p.secondary_unit_id ?? '',
      conversionFactor: String(Number(p.conversion_factor) || ''),
      conversionMode: p.conversion_mode ?? 'fixed',
      unitWeight: String(Number(p.unit_weight) || ''),
      unitVolume: String(Number(p.unit_volume) || ''),
      minStock: String(Number(p.min_stock) || ''),
      maxStock: String(Number(p.max_stock) || ''),
      groupId: p.group_id ?? '',
      attributes: Object.fromEntries((p.attributes ?? []).map((a) => [a.attribute_id, a.value])),
      warehouses: (p.warehouses ?? []).map((w) => ({
        warehouseId: w.warehouse_id,
        isDefault: w.is_default,
        minStock: w.min_stock == null ? '' : String(Number(w.min_stock)),
        maxStock: w.max_stock == null ? '' : String(Number(w.max_stock)),
      })),
      isService: p.is_service,
      isSellable: p.is_sellable,
      isSerialTracked: p.is_serial_tracked,
      isBatchTracked: p.is_batch_tracked ?? false,
      minShelfLifeDays: p.minimum_sellable_shelf_life_days == null ? '' : String(p.minimum_sellable_shelf_life_days),
      hasConsumerPrice: p.has_consumer_price ?? false,
      printedPrice: p.printed_consumer_price == null ? '' : String(p.printed_consumer_price),
      suggestedPrice: p.suggested_retail_price == null ? '' : String(p.suggested_retail_price),
      maxPrice: p.maximum_retail_price == null ? '' : String(p.maximum_retail_price),
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
      primary_unit_id: form.primaryUnitId || null,
      secondary_unit_id: form.secondaryUnitId || null,
      conversion_factor: Number(form.conversionFactor) || 0,
      conversion_mode: form.conversionMode,
      unit_weight: Number(form.unitWeight) || 0,
      unit_volume: Number(form.unitVolume) || 0,
      min_stock: Number(form.minStock) || 0,
      max_stock: Number(form.maxStock) || 0,
      group_id: form.groupId || null,
      attributes: Object.entries(form.attributes)
        .filter(([, value]) => value.trim())
        .map(([attribute_id, value]) => ({ attribute_id, value: value.trim() })),
      warehouses: form.isService
        ? []
        : form.warehouses.map((w) => ({
            warehouse_id: w.warehouseId,
            is_default: w.isDefault,
            min_stock: w.minStock === '' ? null : Number(w.minStock),
            max_stock: w.maxStock === '' ? null : Number(w.maxStock),
          })),
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
      is_batch_tracked: form.isService ? false : form.isBatchTracked,
      minimum_sellable_shelf_life_days: form.minShelfLifeDays === '' ? null : Number(form.minShelfLifeDays),
      has_consumer_price: form.hasConsumerPrice,
      //: رشته‌ی خالی → `null` و نه صفر: §۳۰ می‌گوید فیلدِ بی‌مقدار اصلاً نمایش
      //: داده نشود، و صفر یک مقدارِ معتبرِ دیگر است (کالای رایگان).
      printed_consumer_price: form.printedPrice === '' ? null : Number(form.printedPrice),
      suggested_retail_price: form.suggestedPrice === '' ? null : Number(form.suggestedPrice),
      maximum_retail_price: form.maxPrice === '' ? null : Number(form.maxPrice),
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
              گروه
              <SearchSelect value={form.groupId} onChange={(e) => setForm({ ...form, groupId: e.target.value })}>
                <option value="">— بدون گروه —</option>
                {groups.map((g) => (<option key={g.id} value={g.id}>{g.name}</option>))}
              </SearchSelect>
              <span className="field-hint">
                گروه یک رکورد است نه یک متن — گروهِ تازه را در تبِ «گروه و مشخصات» بسازید.
              </span>
            </label>
          </div>
          <div className="field-row">
            <label>
              واحد اصلی
              <SearchSelect
                value={form.primaryUnitId}
                onChange={(e) => {
                  const picked = units.find((u) => u.id === e.target.value)
                  setForm({ ...form, primaryUnitId: e.target.value, unit: picked?.name ?? form.unit })
                }}
              >
                <option value="">— انتخاب کنید —</option>
                {units.map((u) => (<option key={u.id} value={u.id}>{u.name}</option>))}
              </SearchSelect>
              <span className="field-hint">
                خدمت هم واحد دارد — «ساعت» واحدِ مشاوره است، ولی موجودی نمی‌سازد. واحدِ تازه را
                در تبِ «واحدها» بسازید.
              </span>
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

          <h4 className="form-section-title">واحدِ فرعی و تبدیل</h4>
          <div className="field-row">
            <label>
              واحد فرعی
              <SearchSelect
                value={form.secondaryUnitId}
                onChange={(e) => setForm({ ...form, secondaryUnitId: e.target.value })}
              >
                <option value="">— ندارد —</option>
                {units
                  .filter((u) => u.id !== form.primaryUnitId)
                  .map((u) => (<option key={u.id} value={u.id}>{u.name}</option>))}
              </SearchSelect>
            </label>
            <label>
              نحوه‌ی تبدیل
              <SearchSelect
                value={form.conversionMode}
                onChange={(e) => setForm({ ...form, conversionMode: e.target.value })}
                disabled={!form.secondaryUnitId}
              >
                <option value="fixed">نسبت ثابت</option>
                <option value="variable">نسبت متغیر</option>
              </SearchSelect>
            </label>
          </div>
          {form.secondaryUnitId && form.conversionMode === 'fixed' && (
            <label className="form-field">
              {`هر ۱ ${unitName(form.secondaryUnitId) || 'واحد فرعی'} چند ${unitName(form.primaryUnitId) || 'واحد اصلی'} است؟`}
              <NumberInput
                allowDecimal
                value={form.conversionFactor}
                onChange={(v) => setForm({ ...form, conversionFactor: v })}
                placeholder="مثلاً ۲۴"
              />
            </label>
          )}
          {form.secondaryUnitId && form.conversionMode === 'variable' && (
            <p className="hint">
              نسبتِ متغیر یعنی این عدد از پیش معلوم نیست (طاقه‌ی پارچه، شاخه‌ی میلگرد، بارِ فله).
              سیستم عددی از خودش درنمی‌آورد و مقدار باید به واحدِ اصلی وارد شود.
            </p>
          )}
          <div className="field-row">
            <label>
              وزن هر واحد اصلی
              <NumberInput
                allowDecimal
                value={form.unitWeight}
                onChange={(v) => setForm({ ...form, unitWeight: v })}
                placeholder="۰"
              />
            </label>
            <label>
              حجم هر واحد اصلی
              <NumberInput
                allowDecimal
                value={form.unitVolume}
                onChange={(v) => setForm({ ...form, unitVolume: v })}
                placeholder="۰"
              />
            </label>
          </div>
          <p className="hint">
            وزن و حجم متادیتای حمل‌ونقل و توزین‌اند، نه موجودی — هیچ ماندهٔ‌ای از رویشان
            حساب نمی‌شود.
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
              <SearchSelect value={form.vatStatus} onChange={(e) => setForm({ ...form, vatStatus: e.target.value })}>
                <option value="taxable">مشمول</option>
                <option value="exempt">معاف</option>
              </SearchSelect>
            </label>
            <label>
              وضعیت مالیاتی — خرید
              <SearchSelect
                value={form.purchaseVatStatus}
                onChange={(e) => setForm({ ...form, purchaseVatStatus: e.target.value })}
              >
                <option value="taxable">مشمول</option>
                <option value="exempt">معاف</option>
              </SearchSelect>
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
                <SearchSelect
                  value={form.expenseAccountId}
                  onChange={(e) => setForm({ ...form, expenseAccountId: e.target.value })}
                >
                  <option value="">— حساب پیش‌فرضِ «هزینه خرید خدمات» —</option>
                  {accountOptions.map((a) => (
                    <option key={a.id} value={a.id}>{a.label}</option>
                  ))}
                </SearchSelect>
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
                <label className="cal-check-inline">
                  <input
                    type="checkbox"
                    checked={form.isBatchTracked}
                    onChange={(e) => setForm({ ...form, isBatchTracked: e.target.checked })}
                  />
                  ردیابیِ بار (بچ)
                </label>
              </div>
              <p className="hint">
                «ثبت سریالی» پس از شروعِ گردشِ انباری قابل تغییر نیست: موجودیِ ثبت‌شده سریال
                ندارد و عوض‌کردنِ این تنظیم ردیابی را مبهم می‌کند.
              </p>
              <p className="hint">
                «ردیابیِ بار» یعنی هر خروجِ این کالا باید بگوید از کدام بار برداشته شده. فقط وقتی
                روشن می‌شود که همه‌ی موجودیِ فعلی به یک بار منتسب باشد؛ اگر نبود، سرور می‌گوید
                چه‌قدر بی‌بار مانده و با «انتسابِ موجودی به بار» می‌شود درستش کرد.
              </p>
              <label className="cal-check-inline">
                <input
                  type="checkbox"
                  checked={form.hasConsumerPrice}
                  onChange={(e) => setForm({ ...form, hasConsumerPrice: e.target.checked })}
                />
                قیمتِ مصرف‌کننده دارد
              </label>
              {/*
                §۱۷ — این قابلیت برای همه‌ی کالاها نیست: پیچ و مهره قیمتِ چاپی
                ندارد. §۲۸ هم می‌گوید هیچ‌کدام اجباری نشود، پس فیلدها فقط وقتی
                دیده می‌شوند که کاربر صریحاً گفته باشد این کالا چنین قیمتی دارد.
              */}
              {form.hasConsumerPrice && (
                <>
                  <div className="field-row">
                    <label>
                      قیمتِ چاپی روی بسته
                      <NumberInput value={form.printedPrice} onChange={(v) => setForm({ ...form, printedPrice: v })} placeholder="اختیاری" />
                    </label>
                    <label>
                      قیمتِ پیشنهادیِ فروش
                      <NumberInput value={form.suggestedPrice} onChange={(v) => setForm({ ...form, suggestedPrice: v })} placeholder="اختیاری" />
                    </label>
                    <label>
                      حداکثرِ قیمتِ فروش
                      <NumberInput value={form.maxPrice} onChange={(v) => setForm({ ...form, maxPrice: v })} placeholder="اختیاری" />
                    </label>
                  </div>
                  <p className="hint">
                    این سه قیمت از هم جدا هستند (§۱۸): «چاپی» آن‌چه واقعاً روی بسته نوشته شده،
                    «پیشنهادی» نظرِ تولیدکننده یا پخش‌کننده، و «حداکثر» سقفِ مجاز. هر بارِ ورودی
                    می‌تواند قیمتِ خودش را داشته باشد و بر این‌ها بچربد.
                  </p>
                </>
              )}
              {form.isBatchTracked && (
                <label>
                  حداقل عمرِ مفیدِ فروش (روز)
                  <NumberInput
                    value={form.minShelfLifeDays}
                    onChange={(v) => setForm({ ...form, minShelfLifeDays: v })}
                    placeholder="خالی = بدونِ قاعده"
                  />
                  <span className="field-hint">
                    باری که کمتر از این تعداد روز تا انقضا دارد، دیگر «قابلِ فروش» شمرده نمی‌شود —
                    ولی موجودیِ فیزیکی‌اش سرِ جایش می‌ماند.
                  </span>
                </label>
              )}
              <div className="field-row">
                <label>
                  حداقل موجودی
                  <NumberInput
                    allowDecimal
                    value={form.minStock}
                    onChange={(v) => setForm({ ...form, minStock: v })}
                    placeholder="۰ = بدون کنترل"
                  />
                </label>
                <label>
                  حداکثر موجودی
                  <NumberInput
                    allowDecimal
                    value={form.maxStock}
                    onChange={(v) => setForm({ ...form, maxStock: v })}
                    placeholder="۰ = بدون کنترل"
                  />
                </label>
              </div>
              <p className="hint">
                حداقل، حداکثر و نقطه‌ی سفارش سه آستانه‌ی جدا هستند و هر سه{' '}
                <b>داده‌ی برنامه‌ریزی‌اند، نه سدِ تراکنش</b>: حداکثرِ موجودی جلوی ورودِ کالا را
                نمی‌گیرد، فقط در «نیازمندِ سفارش» و «مازاد موجودی» سیگنال می‌سازد.
              </p>

              <h4 className="form-section-title">انبارهای مرتبط</h4>
              {warehouses.length === 0 ? (
                <p className="hint">انباری تعریف نشده.</p>
              ) : (
                <div className="table-scroll">
                  <table className="entity-table table-plain">
                    <thead>
                      <tr>
                        <th>انبار</th>
                        <th>پیش‌فرض</th>
                        <th>حداقل (این انبار)</th>
                        <th>حداکثر (این انبار)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {warehouses.map((w) => {
                        const link = linkFor(w.id)
                        return (
                          <tr key={w.id}>
                            <td>
                              <label className="cal-check-inline">
                                <input
                                  type="checkbox"
                                  checked={!!link}
                                  onChange={() => toggleWarehouse(w.id)}
                                />
                                {w.code} — {w.name}
                              </label>
                            </td>
                            <td>
                              <input
                                type="radio"
                                name="default-warehouse"
                                checked={!!link?.isDefault}
                                disabled={!link}
                                onChange={() => makeDefault(w.id)}
                                aria-label={`انبار پیش‌فرض: ${w.name}`}
                              />
                            </td>
                            <td>
                              <NumberInput
                                allowDecimal
                                value={link?.minStock ?? ''}
                                onChange={(v) => setLink(w.id, { minStock: v })}
                                placeholder="—"
                                disabled={!link}
                              />
                            </td>
                            <td>
                              <NumberInput
                                allowDecimal
                                value={link?.maxStock ?? ''}
                                onChange={(v) => setLink(w.id, { maxStock: v })}
                                placeholder="—"
                                disabled={!link}
                              />
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="hint">
                هیچ تیکی نزنید یعنی <b>همه‌ی انبارها</b> مجازند — نه «هیچ انباری». انبارِ
                پیش‌فرض فقط پیشنهادِ اولیه‌ی فرم است و کالا را به آن انبار قفل نمی‌کند، و
                برداشتنِ تیکِ یک انبار هیچ حرکتِ انباری یا کاردکسِ گذشته‌ای را پاک نمی‌کند.
                خالی‌گذاشتنِ حداقل/حداکثرِ هر ردیف یعنی همان عددِ بالا.
              </p>

            </>
          )}

          {specs.length > 0 && (
            <>
              <h4 className="form-section-title">مشخصات</h4>
              <div className="field-row spec-row">
                {specs.map((spec) => (
                  <label key={spec.id}>
                    {spec.name}
                    <input
                      type="text"
                      value={form.attributes[spec.id] ?? ''}
                      onChange={(e) =>
                        setForm({ ...form, attributes: { ...form.attributes, [spec.id]: e.target.value } })
                      }
                      placeholder="اختیاری"
                    />
                  </label>
                ))}
              </div>
              <p className="hint">
                مقدارِ خالی یعنی این کالا آن مشخصه را ندارد. فهرستِ مشخصه‌ها در تبِ «گروه و
                مشخصات» تعریف می‌شود.
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
                    <th>گروه</th>
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
                      <td data-label="گروه">{p.group_name || p.category || '—'}</td>
                      <td data-label="واحد">
                        {p.primary_unit_name || p.unit}
                        {p.secondary_unit_name && (
                          <div className="entity-sub">
                            {p.conversion_mode === 'variable'
                              ? `۱ ${p.secondary_unit_name} = متغیر`
                              : `۱ ${p.secondary_unit_name} = ${faMoney(Number(p.conversion_factor))} ${p.primary_unit_name || p.unit}`}
                          </div>
                        )}
                      </td>
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
