/**
 * پیش‌نویسِ محلیِ انبارگردانی.
 *
 * **چرا صفِ عمومی (`offline/outbox`) اینجا جواب نمی‌داد:** آن صف «بفرست و فراموش
 * کن» است و برای سندِ مالی ساخته شده که یک‌بار ثبت می‌شود. انبارگردانی فرق دارد:
 *
 * ۱. کاربر باید عددی که همین الان زد را **روی صفحه ببیند**، حتی اگر هنوز نرفته
 *    باشد. اگر صفحه از کشِ سرور رندر شود، عدد به مقدارِ قبلی برمی‌گردد و انباردار
 *    فکر می‌کند ثبت نشده و دوباره می‌شمارد.
 * ۲. یک کالا ممکن است چند بار اصلاح شود (شمردم، اشتباه شد، دوباره شمردم). صف
 *    یعنی سه درخواستِ پشتِ‌هم؛ اینجا فقط «آخرین مقدار» معنا دارد.
 * ۳. عملیات ذاتاً idempotent است (نشاندنِ یک مقدار)، پس کلیدِ idempotency لازم
 *    ندارد — برخلافِ فاکتور و رسید.
 *
 * ## قاعده‌ی سختِ این فایل
 *
 * **فقط ردیف‌هایی فرستاده می‌شوند که کاربر روی همین گوشی دست زده.**
 *
 * `PUT /api/stock-counts/{id}/counts` در بک‌اند یک patchِ جزئی است: هر `line_id`
 * که بفرستی نوشته می‌شود، بقیه دست‌نخورده می‌مانند. انبارِ بزرگ را دو نفر با دو
 * گوشی می‌شمارند. اگر این گوشی کلِ فهرست را بفرستد — که کارِ ساده و طبیعی است —
 * شمارشِ نفرِ دوم با مقدارِ کهنه‌ی عکسِ اولیه **بازنویسی می‌شود**. نه خطایی، نه
 * هشداری؛ فقط انبارگردانیِ غلط و یک سندِ تعدیلِ غلط پشتش.
 */
import { File, Paths } from 'expo-file-system'

import { setStockCounts } from '../api/stock'
import { isApiError } from '../api/client'

const DRAFT_FILE = 'stock-count-drafts.json'

/** sessionId → (lineId → مقدارِ شمرده‌شده، دقیقاً همان‌طور که کاربر تایپ کرد). */
type Drafts = Record<string, Record<string, string>>

const file = (): File => new File(Paths.document, DRAFT_FILE)

async function readAll(): Promise<Drafts> {
  try {
    const f = file()
    if (!f.exists) return {}
    const parsed: unknown = JSON.parse(await f.text())
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Drafts) : {}
  } catch {
    return {}
  }
}

async function writeAll(drafts: Drafts): Promise<void> {
  try {
    const f = file()
    if (!f.exists) f.create({ intermediates: true })
    f.write(JSON.stringify(drafts))
  } catch {
    /* دیسکِ پر: شمارش ذخیره نمی‌شود ولی اپ نباید بشکند */
  }
}

// ── اشتراک ─────────────────────────────────────────────────────────────────

type Listener = (drafts: Drafts) => void
const listeners = new Set<Listener>()

export function subscribeDrafts(fn: Listener): () => void {
  listeners.add(fn)
  void readAll().then(fn)
  return () => listeners.delete(fn)
}

async function publish(): Promise<void> {
  const drafts = await readAll()
  listeners.forEach((l) => l(drafts))
}

// ── خواندن/نوشتنِ محلی ─────────────────────────────────────────────────────

/** شمارش‌های ثبت‌نشده‌ی یک جلسه روی این گوشی. */
export async function getDraft(sessionId: string): Promise<Record<string, string>> {
  return (await readAll())[sessionId] ?? {}
}

/** یک شمارش را محلی می‌نشاند (فوراً روی دیسک) و بعد باید همگام شود. */
export async function setCount(sessionId: string, lineId: string, qty: string): Promise<void> {
  const drafts = await readAll()
  drafts[sessionId] = { ...(drafts[sessionId] ?? {}), [lineId]: qty }
  await writeAll(drafts)
  await publish()
}

/** پیش‌نویسِ یک جلسه را دور می‌ریزد (پس از ثبت/لغوِ جلسه، یا به‌خواستِ کاربر). */
export async function discardDraft(sessionId: string): Promise<void> {
  const drafts = await readAll()
  delete drafts[sessionId]
  await writeAll(drafts)
  rejections.delete(sessionId)
  await publish()
}

/** همه‌ی پیش‌نویس‌ها — هنگامِ خروج از حساب. روی گوشیِ مشترک نباید بماند. */
export function clearDrafts(): void {
  try {
    const f = file()
    if (f.exists) f.delete()
  } catch {
    /* مهم نیست */
  }
  rejections.clear()
  listeners.forEach((l) => l({}))
}

// ── همگام‌سازی ─────────────────────────────────────────────────────────────

export type SyncResult = 'synced' | 'nothing' | 'retry' | 'rejected'

/** آخرین دلیلِ ردِ سرور برای هر جلسه (مثلاً «فقط جلسه‌ی باز قابل ویرایش است»). */
const rejections = new Map<string, string>()
export const rejectionFor = (sessionId: string): string | undefined => rejections.get(sessionId)

let syncing = false

/**
 * شمارش‌های ثبت‌نشده‌ی یک جلسه را می‌فرستد.
 *
 * پس از موفقیت **فقط همان مقادیری** پاک می‌شوند که فرستاده شدند. اگر انباردار
 * وسطِ درخواست کالای دیگری بشمارد (که در انبار عادی است)، پاک‌کردنِ کلِ پیش‌نویس
 * آن شمارش را می‌بلعید — رفته از حافظه، نرفته به سرور.
 */
export async function syncSession(sessionId: string): Promise<SyncResult> {
  if (syncing) return 'retry'
  const sent = await getDraft(sessionId)
  const lineIds = Object.keys(sent)
  if (lineIds.length === 0) return 'nothing'

  syncing = true
  try {
    await setStockCounts(
      sessionId,
      lineIds.map((line_id) => ({ line_id, counted_qty: sent[line_id] })),
    )
  } catch (e) {
    // قطعیِ شبکه (۰)، نشستِ منقضی (۴۰۱) و خطای سرور (۵xx): کارِ کاربر سرِ جایش
    // می‌ماند و بعداً می‌رود. فقط ۴xxِ دیگر یعنی «سرور این را نمی‌پذیرد».
    const status = isApiError(e) ? e.status : 0
    if (status !== 0 && status !== 401 && status < 500) {
      rejections.set(sessionId, isApiError(e) ? e.message : 'سرور این شمارش را نپذیرفت.')
      return 'rejected'
    }
    return 'retry'
  } finally {
    syncing = false
  }

  rejections.delete(sessionId)
  const drafts = await readAll()
  const remaining = { ...(drafts[sessionId] ?? {}) }
  for (const id of lineIds) {
    // مقداری که حین ارسال عوض شده هنوز ثبت‌نشده است — نگهش می‌داریم.
    if (remaining[id] === sent[id]) delete remaining[id]
  }
  if (Object.keys(remaining).length === 0) delete drafts[sessionId]
  else drafts[sessionId] = remaining
  await writeAll(drafts)
  await publish()
  return 'synced'
}

/** هر جلسه‌ای که شمارشِ ثبت‌نشده دارد — سرِ بازگشتِ شبکه. */
export async function syncAllDrafts(): Promise<void> {
  for (const sessionId of Object.keys(await readAll())) {
    if (rejections.has(sessionId)) continue
    // شکستِ شبکه روی یکی یعنی بقیه هم شکست می‌خورند؛ ادامه بی‌فایده است.
    if ((await syncSession(sessionId)) === 'retry') return
  }
}
