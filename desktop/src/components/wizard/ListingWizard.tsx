import { useState } from 'react'
import { Plus, Trash2, Boxes, Package } from 'lucide-react'
import type { ItemCache } from '../../electron.d'
import type { ListingDraft } from '../../lib/listingDraft'
import { ItemPicker } from '../ItemPicker'
import { NumberInput } from '../NumberInput'
import { ImageUploader } from '../ImageUploader'
import { TaskFlow, type WizardStep } from './TaskFlow'

const faMoney = (v: string | number) => Math.round(Number(v) || 0).toLocaleString('fa-IR')

/** ویزاردِ «ثبت/ویرایشِ لیستینگ» در ماژولِ پخشِ من (نسخه‌ی جدید). همان منطقِ فرمِ کلاسیک
 *  ([useListingDraft]) در چهار مرحله‌ی تاییدشونده + پیش‌نمایشِ زنده. */
export function ListingWizard({ draft, items }: { draft: ListingDraft; items: ItemCache[] }) {
  const [resetTick, setResetTick] = useState(0)
  const { form, setForm } = draft

  const steps: WizardStep[] = [
    {
      key: 'details',
      title: 'نوع و مشخصات',
      subtitle: 'کالای تکی یا پکِ چندمحصولی؟ عنوان و مشخصاتِ نمایشی را وارد کنید.',
      canAdvance: draft.detailsValid,
      blockHint: form.kind === 'single' ? 'عنوان و انتخابِ کالا الزامی است.' : 'عنوان و حداقل یک جزءِ معتبرِ پک الزامی است.',
      body: <DetailsStep draft={draft} items={items} />,
    },
    {
      key: 'price',
      title: 'قیمت و عکس',
      subtitle: 'قیمتِ عمده، دسته و عکس‌های محصول را مشخص کنید.',
      body: (
        <div className="invoice-form">
          <div className="field-pair">
            <label>
              قیمتِ عمده (ریال{form.kind === 'pack' ? '، کلِ پک' : '، هر واحد'})
              <NumberInput value={form.wholesalePrice} onChange={(v) => setForm({ ...form, wholesalePrice: v })} placeholder="۰" />
            </label>
            <label>
              دسته (اختیاری)
              <input type="text" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="مثلاً لبنیات" />
            </label>
          </div>
          <label className="field-full">
            عکس‌های محصول (اختیاری)
            <ImageUploader value={form.images} onChange={(imgs) => setForm({ ...form, images: imgs })} />
          </label>
        </div>
      ),
    },
    {
      key: 'limits',
      title: 'محدودیت و انتشار',
      subtitle: 'محدودیتِ سفارش (اختیاری) و اینکه لیستینگ همین حالا منتشر شود یا پیش‌نویس بماند.',
      body: (
        <div className="invoice-form">
          <label>
            حداقلِ هر سفارش
            <NumberInput allowDecimal value={form.minOrderQty} onChange={(v) => setForm({ ...form, minOrderQty: v })} placeholder="بدون حداقل" />
          </label>
          <label>
            حداکثرِ هر سفارش
            <NumberInput allowDecimal value={form.maxOrderQty} onChange={(v) => setForm({ ...form, maxOrderQty: v })} placeholder="بدون سقف" />
          </label>
          <label>
            سقفِ دفعاتِ سفارش در روز
            <NumberInput value={form.dailyOrderLimit} onChange={(v) => setForm({ ...form, dailyOrderLimit: v })} placeholder="بدون سقف" />
          </label>
          <label className="cal-check-inline field-full">
            <input type="checkbox" checked={form.isPublished} onChange={(e) => setForm({ ...form, isPublished: e.target.checked })} />
            همین حالا منتشر شود (فروشگاه‌های متصل ببینند)
          </label>
          <p className="hint field-full">۰ یا خالی یعنی بدونِ محدودیت. هر فروشگاه در هر سفارش باید بین حداقل و حداکثر سفارش دهد.</p>
        </div>
      ),
    },
    {
      key: 'review',
      title: 'بازبینی و ثبت',
      subtitle: 'یک‌بار مرور کنید، بعد ثبت را بزنید.',
      body: <ReviewStep draft={draft} items={items} />,
    },
  ]

  return (
    <TaskFlow
      title={draft.editingId ? 'ویرایشِ لیستینگ' : 'ثبتِ لیستینگِ جدید'}
      steps={steps}
      submitLabel={draft.editingId ? 'ذخیرهٔ ویرایش' : 'ثبت لیستینگ'}
      submitting={draft.saving}
      message={draft.msg}
      resetKey={`${draft.editingId ?? 'new'}-${resetTick}`}
      preview={<LivePreview draft={draft} items={items} />}
      onSubmit={() => {
        void draft.submit().then((ok) => {
          if (ok) setResetTick((t) => t + 1)
        })
      }}
    />
  )
}

function DetailsStep({ draft, items }: { draft: ListingDraft; items: ItemCache[] }) {
  const { form, setForm } = draft
  return (
    <div className="invoice-form">
      <label className="field-full">
        نوعِ لیستینگ
        <div className="seg-toggle">
          <button type="button" className={form.kind === 'single' ? 'active' : ''} onClick={() => setForm({ ...form, kind: 'single' })}>کالای تکی</button>
          <button type="button" className={form.kind === 'pack' ? 'active' : ''} onClick={() => setForm({ ...form, kind: 'pack' })}>پکِ چندمحصولی</button>
        </div>
      </label>
      <div className="field-pair">
        <label>
          عنوان
          <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="عنوانِ نمایشیِ بازار" />
        </label>
        <label>
          کد (اختیاری)
          <input type="text" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="کدِ داخلی" />
        </label>
      </div>

      {form.kind === 'single' ? (
        <div className="field-pair">
          <label>
            کالا (از انبارِ خودتان)
            <ItemPicker items={items} value={form.itemId} onChange={(id) => setForm({ ...form, itemId: id })} />
          </label>
          <label>
            واحد
            <input type="text" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
          </label>
        </div>
      ) : (
        <div className="field-full">
          <div className="table-scroll">
            <table className="invoice-lines">
              <thead><tr><th>کالا</th><th>تعداد در پک</th><th></th></tr></thead>
              <tbody>
                {form.components.map((r, i) => (
                  <tr key={i}>
                    <td data-label="کالا"><ItemPicker items={items} value={r.itemId} onChange={(id) => draft.setPackRow(i, { itemId: id })} /></td>
                    <td data-label="تعداد"><NumberInput allowDecimal value={r.qty} onChange={(v) => draft.setPackRow(i, { qty: v })} /></td>
                    <td>
                      <button type="button" className="icon-btn-danger" onClick={() => draft.removePackRow(i)} disabled={form.components.length === 1} aria-label="حذف">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button type="button" onClick={draft.addPackRow}><Plus size={14} /> افزودن جزء</button>
        </div>
      )}
    </div>
  )
}

function ReviewStep({ draft, items }: { draft: ListingDraft; items: ItemCache[] }) {
  const { form } = draft
  const itemName = (id: string) => items.find((i) => i.id === id)?.name ?? '—'
  return (
    <div className="review-step">
      <div className="review-facts">
        <div className="live-preview-row"><span>نوع</span><strong>{form.kind === 'pack' ? 'پکِ چندمحصولی' : 'کالای تکی'}</strong></div>
        <div className="live-preview-row"><span>عنوان</span><strong>{form.title || '—'}</strong></div>
        {form.kind === 'single'
          ? <div className="live-preview-row"><span>کالا</span><strong>{form.itemId ? itemName(form.itemId) : '—'}</strong></div>
          : <div className="live-preview-row"><span>اجزای پک</span><strong>{draft.packRows.length.toLocaleString('fa-IR')} قلم</strong></div>}
        <div className="live-preview-row"><span>قیمتِ عمده</span><strong>{faMoney(form.wholesalePrice)} ریال</strong></div>
        {form.category && <div className="live-preview-row"><span>دسته</span><strong>{form.category}</strong></div>}
        <div className="live-preview-row"><span>وضعیت</span><strong>{form.isPublished ? 'منتشرشده' : 'پیش‌نویس'}</strong></div>
      </div>
      {form.kind === 'pack' && draft.packRows.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead><tr><th>قلم</th><th>تعداد در پک</th></tr></thead>
            <tbody>
              {draft.packRows.map((r, i) => (
                <tr key={i}><td>{itemName(r.itemId)}</td><td>{Number(r.qty).toLocaleString('fa-IR')}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function LivePreview({ draft, items }: { draft: ListingDraft; items: ItemCache[] }) {
  const { form } = draft
  const itemName = (id: string) => items.find((i) => i.id === id)?.name ?? '—'
  return (
    <div className="live-preview">
      <p className="live-preview-title">
        {form.kind === 'pack' ? <Boxes size={14} /> : <Package size={14} />} پیش‌نمایشِ لیستینگ
      </p>
      <div className="live-preview-row"><span>نوع</span><strong>{form.kind === 'pack' ? 'پک' : 'تکی'}</strong></div>
      <div className="live-preview-row"><span>عنوان</span><strong>{form.title || 'بدون عنوان'}</strong></div>
      {form.kind === 'single'
        ? <div className="live-preview-row"><span>کالا</span><strong>{form.itemId ? itemName(form.itemId) : '—'}</strong></div>
        : <div className="live-preview-row"><span>اجزا</span><strong>{draft.packRows.length.toLocaleString('fa-IR')} قلم</strong></div>}
      {form.category && <div className="live-preview-row"><span>دسته</span><strong>{form.category}</strong></div>}
      <div className="live-preview-row"><span>وضعیت</span><strong>{form.isPublished ? 'منتشر' : 'پیش‌نویس'}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total"><span>قیمتِ عمده</span><strong>{faMoney(form.wholesalePrice)}</strong></div>
    </div>
  )
}
