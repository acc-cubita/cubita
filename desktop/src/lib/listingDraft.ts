import { useMemo, useState } from 'react'
import { createMpListing, updateMpListing, type Listing, type ListingIn } from '../api'

/** یک ردیفِ جزءِ پک (کالا + تعداد در پک). */
export interface PackRow {
  itemId: string
  qty: string
}

/** حالتِ فرمِ لیستینگِ «پخشِ من» — مشترکِ فرمِ کلاسیک و ویزارد. */
export interface ListingFormState {
  kind: 'single' | 'pack'
  title: string
  code: string
  unit: string
  wholesalePrice: string
  consumerPrice: string
  category: string
  isPublished: boolean
  itemId: string
  images: string[]
  minOrderQty: string
  maxOrderQty: string
  dailyOrderLimit: string
  /** اصنافی که این قلم، *علاوه بر* اصنافِ کلیِ پخش‌کننده، به آن‌ها هم می‌رسد. */
  extraTrades: string[]
  components: PackRow[]
}

export const EMPTY_LISTING_FORM: ListingFormState = {
  kind: 'single',
  title: '',
  code: '',
  unit: 'عدد',
  wholesalePrice: '',
  consumerPrice: '',
  category: '',
  isPublished: true,
  itemId: '',
  images: [],
  minOrderQty: '',
  maxOrderQty: '',
  dailyOrderLimit: '',
  extraTrades: [],
  components: [{ itemId: '', qty: '1' }],
}

/**
 * منطقِ مشترکِ «ثبت/ویرایشِ لیستینگ» در ماژولِ پخشِ من. state + اعتبارسنجی + submit یک‌جا،
 * تا فرمِ کلاسیک (پوسته‌های تیره/روشن) و ویزاردِ نسخه‌ی جدید هر دو یک رفتار داشته باشند.
 */
export function useListingDraft({ token, onSaved }: { token: string; onSaved: () => void | Promise<void> }) {
  const [form, setForm] = useState<ListingFormState>({ ...EMPTY_LISTING_FORM })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function reset() {
    setForm({ ...EMPTY_LISTING_FORM, images: [], extraTrades: [], components: [{ itemId: '', qty: '1' }] })
    setEditingId(null)
    setMsg(null)
  }

  function startEdit(l: Listing) {
    setEditingId(l.id)
    setForm({
      kind: l.kind,
      title: l.title,
      code: l.code,
      unit: l.unit,
      wholesalePrice: String(Number(l.wholesale_price) || ''),
      consumerPrice: Number(l.consumer_price) ? String(Number(l.consumer_price)) : '',
      category: l.category,
      isPublished: l.is_published,
      itemId: l.item_id ?? '',
      images: l.images ?? [],
      minOrderQty: Number(l.min_order_qty) ? String(Number(l.min_order_qty)) : '',
      maxOrderQty: Number(l.max_order_qty) ? String(Number(l.max_order_qty)) : '',
      dailyOrderLimit: Number(l.daily_order_limit) ? String(Number(l.daily_order_limit)) : '',
      extraTrades: l.extra_trades ?? [],
      components:
        l.kind === 'pack' && l.components.length
          ? l.components.map((c) => ({ itemId: c.item_id, qty: String(Number(c.qty)) }))
          : [{ itemId: '', qty: '1' }],
    })
    setMsg(null)
  }

  function setPackRow(i: number, patch: Partial<PackRow>) {
    setForm((f) => ({ ...f, components: f.components.map((r, idx) => (idx === i ? { ...r, ...patch } : r)) }))
  }
  const addPackRow = () => setForm((f) => ({ ...f, components: [...f.components, { itemId: '', qty: '1' }] }))
  const removePackRow = (i: number) =>
    setForm((f) => ({ ...f, components: f.components.length > 1 ? f.components.filter((_, idx) => idx !== i) : f.components }))

  // اجزای معتبرِ پک (کالا + مقدارِ بزرگ‌تر از صفر)
  const packRows = useMemo(() => form.components.filter((r) => r.itemId && Number(r.qty) > 0), [form.components])

  // مرحله‌ی «مشخصات» وقتی معتبر است که عنوان داشته باشیم و بسته به نوع، کالا یا حداقل یک جزءِ پک.
  const detailsValid = !!form.title.trim() && (form.kind === 'single' ? !!form.itemId : packRows.length > 0)

  function buildPayload(): ListingIn {
    return {
      kind: form.kind,
      title: form.title.trim(),
      code: form.code.trim(),
      unit: form.unit.trim() || 'عدد',
      wholesale_price: Number(form.wholesalePrice) || 0,
      consumer_price: Number(form.consumerPrice) || 0,
      category: form.category.trim(),
      is_published: form.isPublished,
      images: form.images,
      min_order_qty: Number(form.minOrderQty) || 0,
      max_order_qty: Number(form.maxOrderQty) || 0,
      daily_order_limit: Number(form.dailyOrderLimit) || 0,
      extra_trades: form.extraTrades,
      item_id: form.kind === 'single' ? form.itemId : null,
      components: form.kind === 'pack' ? packRows.map((r) => ({ item_id: r.itemId, qty: Number(r.qty) })) : [],
    }
  }

  async function submit(): Promise<boolean> {
    setMsg(null)
    if (!form.title.trim()) {
      setMsg('عنوان الزامی است.')
      return false
    }
    if (form.kind === 'single' && !form.itemId) {
      setMsg('برای کالای تکی، انتخابِ کالا الزامی است.')
      return false
    }
    if (form.kind === 'pack' && packRows.length === 0) {
      setMsg('پک حداقل یک جزءِ معتبر لازم دارد.')
      return false
    }
    setSaving(true)
    try {
      if (editingId) await updateMpListing(token, editingId, buildPayload())
      else await createMpListing(token, buildPayload())
      reset()
      await onSaved()
      return true
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'خطای ناشناخته')
      return false
    } finally {
      setSaving(false)
    }
  }

  return {
    form,
    setForm,
    editingId,
    startEdit,
    reset,
    setPackRow,
    addPackRow,
    removePackRow,
    packRows,
    detailsValid,
    submit,
    saving,
    msg,
  }
}

export type ListingDraft = ReturnType<typeof useListingDraft>
