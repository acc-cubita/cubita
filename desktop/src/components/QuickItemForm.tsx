import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { PackagePlus, Save, X } from 'lucide-react'
import { createItemLive, type ItemRecord } from '../api'
import { NumberInput } from './NumberInput'

// همان واحدهای رایجِ فرمِ کالا؛ اینجا هم برای انتخابِ سریع تکرار شده تا این کامپوننت
// خودبسنده بماند و به ProductsPanel گره نخورد.
const COMMON_UNITS = [
  'عدد', 'متر', 'متر مربع', 'متر مکعب', 'سانتی‌متر', 'کیلوگرم', 'گرم', 'تن',
  'لیتر', 'بسته', 'کارتن', 'جعبه', 'جفت', 'دست', 'رول', 'طاقه', 'شاخه', 'عدل', 'ساعت',
]

/**
 * ساختِ سریعِ کالای جدید — یک مودالِ کوچک که از داخلِ فرمِ خرید (یا هر فرمِ دیگری با
 * انتخاب‌گرِ کالا) باز می‌شود تا کاربر بدونِ ترکِ فاکتور محصولِ تازه را ثبت کند.
 *
 * پس از ثبت، خودِ کالا (ItemRecord) به بالادست داده می‌شود تا هم در همان ردیف انتخاب
 * شود و هم کشِ سراسریِ کالاها تازه شود؛ خرید سپس موجودیِ همان کالا را بالا می‌برد.
 */
export function QuickItemForm({
  token,
  initialName = '',
  onCreated,
  onClose,
}: {
  token: string
  /** نامِ اولیه — معمولاً همان چیزی که کاربر در انتخاب‌گر تایپ کرده بود. */
  initialName?: string
  onCreated: (item: ItemRecord) => void
  onClose: () => void
}) {
  const [name, setName] = useState(initialName)
  // کدِ پیشنهادی تا اصطکاکِ «کد یکتا» کم شود؛ کاربر می‌تواند تغییرش دهد.
  const [sku, setSku] = useState(() => `K-${Date.now().toString().slice(-6)}`)
  const [unit, setUnit] = useState('عدد')
  const [salesPrice, setSalesPrice] = useState('')
  const [barcode, setBarcode] = useState('')
  const [isService, setIsService] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const nameRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    requestAnimationFrame(() => nameRef.current?.focus())
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!name.trim()) { setError('نام کالا الزامی است.'); return }
    if (!sku.trim()) { setError('کد کالا (SKU) الزامی است.'); return }
    setSaving(true)
    try {
      const item = await createItemLive(token, {
        sku: sku.trim(),
        name: name.trim(),
        category: '',
        unit: unit.trim() || 'عدد',
        is_service: isService,
        sales_price: Number(salesPrice) || 0,
        barcode: barcode.trim() || null,
        reorder_point: 0,
      })
      onCreated(item)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
      setSaving(false)
    }
  }

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div
        className="drawer-panel drawer-panel--narrow"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="drawer-head">
          <div className="drawer-title">
            <PackagePlus size={17} />
            <div>
              <div className="drawer-title-main">کالای جدید</div>
              <div className="drawer-title-sub">همین‌جا بسازید تا در همین فاکتور انتخاب شود</div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
        </div>

        <div className="drawer-body">
          <form className="invoice-form form-full" onSubmit={handleSubmit}>
            <label>
              نام کالا
              <input
                ref={nameRef}
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="نام کالا یا خدمات"
                required
              />
            </label>
            <div className="field-row">
              <label>
                کد کالا (SKU)
                <input
                  type="text"
                  value={sku}
                  onChange={(e) => setSku(e.target.value)}
                  placeholder="مثلاً A-1001"
                  required
                />
              </label>
              <label>
                واحد
                <select
                  value={COMMON_UNITS.includes(unit) ? unit : '__custom__'}
                  onChange={(e) => setUnit(e.target.value === '__custom__' ? '' : e.target.value)}
                >
                  {COMMON_UNITS.map((u) => (<option key={u} value={u}>{u}</option>))}
                  <option value="__custom__">سایر (دستی)…</option>
                </select>
                {!COMMON_UNITS.includes(unit) && (
                  <input
                    type="text"
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    placeholder="واحدِ دلخواه"
                    style={{ marginTop: 6 }}
                  />
                )}
              </label>
            </div>
            <div className="field-row">
              <label>
                قیمت فروش (ریال، اختیاری)
                <NumberInput value={salesPrice} onChange={setSalesPrice} placeholder="۰" />
              </label>
              <label>
                بارکد (اختیاری)
                <input
                  type="text"
                  value={barcode}
                  onChange={(e) => setBarcode(e.target.value)}
                  placeholder="اسکن یا تایپ"
                  inputMode="numeric"
                />
              </label>
            </div>
            <label className="cal-check-inline">
              <input
                type="checkbox"
                checked={isService}
                onChange={(e) => setIsService(e.target.checked)}
              />
              این یک خدمات است (بدون موجودیِ انبار)
            </label>
            {error && <div className="error">{error}</div>}
            <div className="invoice-form-footer">
              <button type="button" onClick={onClose}>انصراف</button>
              <button type="submit" className="btn-primary" disabled={saving}>
                <Save size={14} /> {saving ? 'در حال ثبت…' : 'ثبت و انتخاب'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>,
    document.body,
  )
}
