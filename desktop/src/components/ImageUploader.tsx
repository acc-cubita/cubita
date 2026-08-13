import { useRef, useState } from 'react'
import { ImagePlus, X, Loader2 } from 'lucide-react'
import { compressImage } from '../lib/imageCompress'

/**
 * انتخاب و پیش‌نمایشِ چند عکس با فشرده‌سازیِ خودکار در مرورگر.
 * مقدار آرایه‌ای از data URIِ JPEGِ کوچک‌شده است؛ همان چیزی که به سرور می‌رود.
 * سقفِ تعداد با `max` کنترل می‌شود (پیش‌فرض ۴) تا فضای زیادی مصرف نشود.
 */
export function ImageUploader({
  value,
  onChange,
  max = 4,
}: {
  value: string[]
  onChange: (next: string[]) => void
  max?: number
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    e.target.value = '' // تا انتخابِ دوباره‌ی همان فایل هم رویداد بدهد
    if (files.length === 0) return
    setErr(null)
    setBusy(true)
    try {
      const room = Math.max(0, max - value.length)
      const picked = files.filter((f) => f.type.startsWith('image/')).slice(0, room)
      const next = [...value]
      for (const f of picked) next.push(await compressImage(f))
      onChange(next)
      if (files.length > room) setErr(`حداکثر ${max} عکس مجاز است؛ عکس‌های اضافه نادیده گرفته شد.`)
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'خطا در پردازشِ عکس')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="image-uploader">
      <div className="image-uploader-grid">
        {value.map((src, i) => (
          <div key={i} className="image-thumb">
            <img src={src} alt={`عکس ${i + 1}`} />
            <button
              type="button"
              className="image-thumb-remove"
              onClick={() => onChange(value.filter((_, idx) => idx !== i))}
              aria-label="حذفِ عکس"
            >
              <X size={13} />
            </button>
          </div>
        ))}
        {value.length < max && (
          <button
            type="button"
            className="image-add"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
          >
            {busy ? <Loader2 size={18} className="spin" /> : <ImagePlus size={18} />}
            <span>{busy ? 'در حال فشرده‌سازی…' : 'افزودنِ عکس'}</span>
          </button>
        )}
      </div>
      <input ref={inputRef} type="file" accept="image/*" multiple hidden onChange={(e) => void onPick(e)} />
      <p className="image-uploader-hint">
        عکس‌ها خودکار کوچک و فشرده می‌شوند تا فضای کمی بگیرند (حداکثر {max} عکس).
      </p>
      {err && <div className="image-uploader-err">{err}</div>}
    </div>
  )
}
