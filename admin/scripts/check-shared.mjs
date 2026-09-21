/**
 * نگهبانِ واگراییِ فایل‌های مشترک.
 *
 * اپِ ستاد پروژه‌ی مستقلی است و چند فایلِ پایه را از `desktop/src` **کپی**
 * می‌کند. هزینه‌ی این تصمیم واگرایی است: کسی `jalali.ts` را آن‌طرف درست می‌کند
 * و این‌طرف باگ می‌ماند، و هیچ‌کس نمی‌فهمد.
 *
 * این اسکریپت واگرایی را **پرصدا** می‌کند نه ناممکن. مقایسه بایت‌به‌بایت است:
 * هر تفاوتی CI را قرمز می‌کند و تصمیم با آدم است — یا همگام کن، یا فایل را از
 * مانیفست بردار و بنویس چرا.
 *
 * اگر روزی مصرف‌کننده‌ی سومی پیدا شد، جای این اسکریپت یک پکیجِ مشترک است.
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DESKTOP = path.resolve(ROOT, '..', 'desktop')

/** نسخه‌ی اپِ ستاد ← اصلِ اپِ مشتری. */
export const SHARED_FILES = {
  'src/lib/jalali.ts': 'src/lib/jalali.ts',
  'src/lib/format.ts': 'src/lib/format.ts',
  'src/lib/faText.ts': 'src/lib/faText.ts',
  'src/styles/tokens.css': 'src/index.css',
}

function read(file) {
  try {
    return readFileSync(file, 'utf8')
  } catch {
    return null
  }
}

let bad = 0
for (const [mine, theirs] of Object.entries(SHARED_FILES)) {
  const a = read(path.join(ROOT, mine))
  const b = read(path.join(DESKTOP, theirs))

  if (a == null) {
    console.error(`✖ ${mine} در اپِ ستاد نیست`)
    bad++
    continue
  }
  if (b == null) {
    console.error(`✖ اصلِ آن (desktop/${theirs}) پیدا نشد — مسیر عوض شده؟`)
    bad++
    continue
  }
  //: پایانه‌ی خط عمداً نرمال می‌شود: چک‌اوتِ ویندوزی نباید تفاوتِ کاذب بسازد.
  if (a.replace(/\r\n/g, '\n') !== b.replace(/\r\n/g, '\n')) {
    console.error(`✖ ${mine} با desktop/${theirs} فرق دارد`)
    bad++
  }
}

console.log(
  bad === 0
    ? `فایل‌های مشترک: هر ${Object.keys(SHARED_FILES).length} تا با اپِ مشتری یکی‌اند.`
    : `\n${bad} فایلِ واگرا. یا همگامشان کنید، یا از SHARED_FILES برداریدشان و دلیلش را بنویسید.`,
)
process.exit(bad ? 1 : 0)
