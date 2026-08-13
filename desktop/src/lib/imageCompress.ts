// فشرده‌سازیِ عکسِ کاتالوگ در مرورگر — پیش از ارسال به سرور.
//
// عکسِ خامِ موبایل/دوربین چند مگابایت است؛ اگر خام ذخیره شود پایگاه‌داده را باد
// می‌کند (عکس‌ها به‌صورتِ data URI در JSONB می‌نشینند، نه فایلِ روی دیسک). اینجا
// عکس روی canvas به بلندترین‌ضلعِ MAX_EDGE کوچک و با کیفیتِ QUALITY به JPEG تبدیل
// می‌شود (خروجی معمولاً ۴۰–۱۵۰ کیلوبایت). اگر باز بزرگ بود، کیفیت پله‌ای کم می‌شود.
// سرور همین سقف را دوباره سخت‌گیرانه بررسی می‌کند؛ به این کلاینت اعتماد نمی‌کند.

const MAX_EDGE = 1024 // بلندترین ضلعِ خروجی (پیکسل)
const QUALITY = 0.72 // کیفیتِ اولیه‌ی JPEG
/** باید با `MP_MAX_IMAGE_BYTES`ِ سمتِ سرور هم‌خوان بماند. */
export const MAX_IMAGE_BYTES = 400 * 1024

/** یک فایلِ عکس را به data URIِ JPEGِ کوچک‌شده تبدیل می‌کند. */
export async function compressImage(file: File): Promise<string> {
  const source = await loadImage(file)
  const sw = 'naturalWidth' in source ? source.naturalWidth : source.width
  const sh = 'naturalHeight' in source ? source.naturalHeight : source.height
  const scale = Math.min(1, MAX_EDGE / Math.max(sw, sh || 1))
  const w = Math.max(1, Math.round(sw * scale))
  const h = Math.max(1, Math.round(sh * scale))

  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('ساختِ بومِ ترسیم ناموفق بود')
  ctx.drawImage(source, 0, 0, w, h)
  if ('close' in source) source.close()

  let quality = QUALITY
  let dataUrl = canvas.toDataURL('image/jpeg', quality)
  while (dataUrlBytes(dataUrl) > MAX_IMAGE_BYTES && quality > 0.4) {
    quality -= 0.12
    dataUrl = canvas.toDataURL('image/jpeg', quality)
  }
  if (dataUrlBytes(dataUrl) > MAX_IMAGE_BYTES) {
    throw new Error('عکس حتی پس از فشرده‌سازی بزرگ است؛ عکسِ کوچک‌تری انتخاب کنید')
  }
  return dataUrl
}

/** طولِ بخشِ base64ِ یک data URI را به بایتِ خام برمی‌گرداند. */
function dataUrlBytes(dataUrl: string): number {
  const i = dataUrl.indexOf(',')
  const b64 = i >= 0 ? dataUrl.slice(i + 1) : dataUrl
  const pad = b64.endsWith('==') ? 2 : b64.endsWith('=') ? 1 : 0
  return Math.floor((b64.length * 3) / 4) - pad
}

/** با `createImageBitmap` (سریع) رمزگشایی می‌کند و اگر نبود به `<img>` می‌افتد. */
async function loadImage(file: File): Promise<ImageBitmap | HTMLImageElement> {
  if (typeof createImageBitmap === 'function') {
    try {
      return await createImageBitmap(file)
    } catch {
      /* افت به روشِ <img> */
    }
  }
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('بارگذاریِ عکس ناموفق بود'))
      img.src = url
    })
    return img
  } finally {
    URL.revokeObjectURL(url)
  }
}
