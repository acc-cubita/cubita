/**
 * ماندگارکردنِ کشِ خواندنی روی دیسک.
 *
 * **مسئله‌ای که حل می‌کند:** TanStack Query کش را در حافظه نگه می‌دارد. با بستنِ
 * اپ همه‌اش می‌رود. یعنی هر بار که کاربر اپ را باز می‌کند — حتی اگر ده ثانیه پیش
 * بسته باشد — تا وقتی شبکه جواب ندهد صفحه‌ی خالی می‌بیند. برای مدیری که در ماشین
 * یا انبار آنتن ندارد، اپ عملاً بی‌فایده است.
 *
 * حالا آخرین دیده‌ها روی دیسک می‌مانند و اپ **فوراً** با آن‌ها بالا می‌آید، بعد
 * در پس‌زمینه تازه می‌شود.
 *
 * **چرا بدونِ کتابخانه‌ی جانبی:** `dehydrate`/`hydrate` در هسته‌ی react-query
 * هستند و `expo-file-system` از قبل در اپ کار می‌کند (گزارشگرِ کرش از آن استفاده
 * می‌کند). سه بسته‌ی تازه — با همان ریسکِ تعارضِ peer که موقعِ jest دیدیم — برای
 * چیزی که صد خط کد است توجیه نداشت.
 */
import { dehydrate, hydrate, type QueryClient } from '@tanstack/react-query'
import { File, Paths } from 'expo-file-system'

const CACHE_FILE = 'query-cache.json'

/**
 * کشِ کهنه‌تر از این دور ریخته می‌شود.
 *
 * ۲۴ ساعت عمدی است: داده‌ی حسابداریِ دیروز به‌عنوانِ «آخرین وضعیتِ دیده‌شده» هنوز
 * مفید است، ولی داده‌ی هفته‌ی پیش گمراه‌کننده است — کاربر عددی می‌بیند که فکر
 * می‌کند امروزی است.
 */
const MAX_AGE_MS = 24 * 60 * 60 * 1000

/** نوشتن حداکثر هر این‌قدر یک‌بار — وگرنه هر تغییرِ کش یک نوشتنِ دیسک است. */
const WRITE_THROTTLE_MS = 3_000

interface Snapshot {
  savedAt: number
  state: unknown
}

const file = (): File => new File(Paths.document, CACHE_FILE)

/** آخرین کشِ ذخیره‌شده را برمی‌گرداند، اگر بود و کهنه نشده بود. */
export async function loadCache(client: QueryClient): Promise<boolean> {
  try {
    const f = file()
    if (!f.exists) return false
    const snap = JSON.parse(await f.text()) as Snapshot
    if (!snap?.savedAt || Date.now() - snap.savedAt > MAX_AGE_MS) {
      f.delete()
      return false
    }
    hydrate(client, snap.state)
    return true
  } catch {
    // فایلِ خراب یا نسخه‌ی ناسازگارِ ساختار: بی‌کش شروع کن، نه اینکه اپ بشکند.
    try {
      file().delete()
    } catch {
      /* حتی حذفش هم نشد؛ مهم نیست */
    }
    return false
  }
}

let timer: ReturnType<typeof setTimeout> | null = null

function writeNow(client: QueryClient): void {
  try {
    const snap: Snapshot = { savedAt: Date.now(), state: dehydrate(client) }
    const f = file()
    if (!f.exists) f.create({ intermediates: true })
    f.write(JSON.stringify(snap))
  } catch {
    // دیسکِ پر یا مجوز: کش ذخیره نمی‌شود، ولی اپ باید کار کند.
  }
}

/**
 * از این به بعد هر تغییرِ کش را (با فاصله) روی دیسک می‌نویسد.
 *
 * تابعِ برگشتی اشتراک را قطع می‌کند — برای تست لازم است، وگرنه تایمر بینِ تست‌ها
 * نشت می‌کند.
 */
export function startPersisting(client: QueryClient): () => void {
  const unsubscribe = client.getQueryCache().subscribe(() => {
    if (timer) return
    timer = setTimeout(() => {
      timer = null
      writeNow(client)
    }, WRITE_THROTTLE_MS)
  })

  return () => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    unsubscribe()
  }
}

/** پاک‌کردنِ کش — هنگامِ خروج از حساب، تا داده‌ی یک کاربر به کاربرِ بعدی نرسد. */
export function clearCache(): void {
  try {
    const f = file()
    if (f.exists) f.delete()
  } catch {
    /* مهم نیست */
  }
}
