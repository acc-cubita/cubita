import { useCallback, useEffect, useState } from 'react'
import { Bookmark, BookmarkPlus, X } from 'lucide-react'
import {
  createSavedReport,
  deleteSavedReport,
  fetchSavedReports,
  type ReportFilters,
  type SavedReportRecord,
} from '../api'
import type { Preset, RangeState } from '../pages/accounting/kit'

/**
 * نماهای ذخیره‌شده‌ی یک گزارش — §۳۵.
 *
 * **چرا جدولِ تازه‌ای ساخته نشد.** `SavedReport` از قبل هست و دقیقاً برای همین
 * نوشته شده: «فقط *دستورِ ساخت* ذخیره می‌شود … `config` عمداً JSONB است». ساختنِ
 * جدولِ دومی برای ذخیره‌ی همان چیز، همان «دو نمای یک داده» بود که پروژه منعش
 * می‌کند. پس این قابلیت **هیچ مهاجرتی ندارد**.
 *
 * **پیشوندِ `view:`** ردیف‌های این‌جا را از ردیف‌های «گزارش‌ساز» جدا می‌کند. آن صفحه
 * منابعش را از `MODULE_LISTS` می‌سازد و کلیدهایش هرگز دونقطه ندارند، پس دو
 * دسته هرگز قاطی نمی‌شوند و هیچ‌کدام ردیف‌های دیگری را «ناموجود» نشان نمی‌دهد.
 *
 * **بازه به‌صورتِ پیش‌فرض ذخیره می‌شود، نه تاریخِ حل‌شده.** نمایی که «امسال» را
 * نگه دارد سالِ بعد هم درست است؛ نمایی که «۱۴۰۵/۰۱/۰۱ تا امروز» را نگه دارد،
 * فردا دروغ می‌گوید. همان دلیلی که `SavedReport` تعریف را ذخیره می‌کند نه نتیجه را.
 */

export interface SavedView {
  preset: Preset
  custom: { from: string; to: string }
  filters: ReportFilters
}

const PREFIX = 'view:'

export function SavedViewBar({
  token,
  viewKey,
  filters,
  range,
  setFilters,
}: {
  token: string
  /** کلیدِ گزارش، مثلِ `accounting.trial_balance` — نماها بینِ گزارش‌ها قاطی نمی‌شوند. */
  viewKey: string
  filters: ReportFilters
  range: RangeState
  setFilters: (f: ReportFilters) => void
}) {
  const source = PREFIX + viewKey
  const [views, setViews] = useState<SavedReportRecord[] | null>(null)
  const [naming, setNaming] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const all = await fetchSavedReports(token)
      setViews(all.filter((r) => r.source === source))
    } catch {
      //: مجوزِ `reports` را ممکن است این کاربر نداشته باشد. آن‌وقت نبودنِ نوار
      //: درست‌تر از خطا دادن است — این قابلیت جانبی است، نه خودِ گزارش.
      setViews(null)
    }
  }, [token, source])

  useEffect(() => {
    void load()
  }, [load])

  if (views === null) return null

  //: نمای قدیمی ممکن است میدانی نداشته باشد که بعداً اضافه شده؛ `config` عمداً
  //: JSONB است و شکلش با نسخه‌ها عوض می‌شود. پس هر میدان با پیش‌فرضِ امن خوانده
  //: می‌شود و نمای قدیمی صفحه را نمی‌شکند.
  const apply = (view: SavedView) => {
    if (view?.custom) range.setCustom(view.custom)
    if (view?.preset) range.setPreset(view.preset)
    setFilters(view?.filters ?? {})
  }

  const save = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setBusy(true)
    try {
      const config: SavedView = { preset: range.preset, custom: range.custom, filters }
      await createSavedReport(token, {
        name: trimmed,
        source,
        config: config as unknown as Record<string, unknown>,
      })
      setName('')
      setNaming(false)
      await load()
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: string) => {
    setBusy(true)
    try {
      await deleteSavedReport(token, id)
      await load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="cc-presets saved-views">
      <Bookmark size={15} />
      {views.map((v) => (
        <span key={v.id} className="saved-view">
          <button
            type="button"
            title={`اعمالِ نمای «${v.name}»`}
            onClick={() => apply(v.config as unknown as SavedView)}
          >
            {v.name}
          </button>
          <button
            type="button"
            className="saved-view-drop"
            title="حذفِ این نما"
            disabled={busy}
            onClick={() => void remove(v.id)}
          >
            <X size={12} />
          </button>
        </span>
      ))}

      {naming ? (
        <span className="saved-view-form">
          <input
            type="text"
            value={name}
            autoFocus
            maxLength={150}
            placeholder="نامِ نما"
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void save()
              if (e.key === 'Escape') setNaming(false)
            }}
          />
          <button type="button" disabled={busy || !name.trim()} onClick={() => void save()}>
            ذخیره
          </button>
          <button type="button" onClick={() => setNaming(false)}>
            انصراف
          </button>
        </span>
      ) : (
        <button type="button" title="ذخیره‌ی فیلترهای فعلی به‌نامِ یک نما" onClick={() => setNaming(true)}>
          <BookmarkPlus size={13} /> ذخیره‌ی نما
        </button>
      )}
    </div>
  )
}
