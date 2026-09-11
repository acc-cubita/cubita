/**
 * صفِ نوشتنِ آفلاین.
 *
 * **مسئله:** ثبتِ فاکتور و دریافت/پرداخت آنلاین‌محور بودند. ویزیتوری که در محلِ
 * مشتری آنتن ندارد یا کارش را از دست می‌داد یا باید بیرون می‌آمد و دوباره وارد
 * می‌کرد. حالا کار روی دیسک می‌نشیند و خودش می‌رود.
 *
 * ## چرا این کار *بدونِ* idempotency خطرناک بود
 *
 * صفی که پاسخ را نگیرد دوباره می‌فرستد — رفتارِ درستش همین است، چون نمی‌داند
 * درخواست به سرور رسیده یا نه. ولی برای یک سندِ مالی، «دوباره فرستادن» یعنی
 * احتمالِ دو فاکتور و دو سندِ حسابداری، **بدونِ هیچ خطایی**. فقط دفتر غلط
 * می‌شود و ساکت است.
 *
 * برای همین هر آیتم یک `Idempotency-Key` ثابت دارد که *هنگامِ ساخت* تولید
 * می‌شود و در تلاش‌های بعدی عوض نمی‌شود. بک‌اند (`app/services/idempotency.py`)
 * با همان کلید عملیات را یک‌بار اجرا می‌کند و دفعاتِ بعد همان نتیجه را
 * برمی‌گرداند.
 *
 * ## چرا شماره‌ی سند اینجا ساخته نمی‌شود
 *
 * شماره‌ی اسناد را سرور با شمارنده‌ی بی‌شکافِ درونِ تراکنش می‌دهد
 * (`next_document_number`). کلاینت نمی‌تواند از پیش بدهد — دو گوشیِ آفلاین شماره‌ی
 * یکسان می‌ساختند. پس آیتمِ صف تا وقتی ارسال نشده «شماره ندارد»، و این در UI هم
 * باید همین‌طور نشان داده شود.
 */
import { File, Paths } from 'expo-file-system'
import { onlineManager } from '@tanstack/react-query'

import { apiPost, isApiError } from '../api/client'
import type { SalesInvoiceIn, SalesInvoiceOut, TreasuryTxn, TreasuryTxnIn } from '../api/types'

/**
 * عملیاتی که صف پشتیبانی می‌کند — هر کدام روی بک‌اند idempotent است.
 *
 * **بدنه و پاسخ تایپ‌دار می‌مانند.** نسخه‌ی اول `body: unknown` می‌گرفت و همان
 * لحظه که صفحه‌ها از `createSalesInvoice` به `enqueue` منتقل شدند، کنترلِ نوعِ
 * بدنه از بین رفت: یک نامِ فیلدِ اشتباه دیگر کامپایل را قرمز نمی‌کرد و فقط سرور
 * ۴۲۲ می‌داد — سرِ مشتری، وسطِ کار.
 */
export interface OutboxBodies {
  salesInvoice: SalesInvoiceIn
  receipt: TreasuryTxnIn
  payment: TreasuryTxnIn
}

export interface OutboxResponses {
  salesInvoice: SalesInvoiceOut
  receipt: TreasuryTxn
  payment: TreasuryTxn
}

export type OutboxKind = keyof OutboxBodies

const PATHS: Record<OutboxKind, string> = {
  salesInvoice: '/api/sales-invoices',
  receipt: '/api/treasury/receipts',
  payment: '/api/treasury/payments',
}

export const KIND_LABELS: Record<OutboxKind, string> = {
  salesInvoice: 'فاکتورِ فروش',
  receipt: 'رسیدِ دریافت',
  payment: 'اعلامیه‌ی پرداخت',
}

export interface OutboxItem {
  /** همان کلیدِ idempotency — یک‌بار ساخته می‌شود و هرگز عوض نمی‌شود. */
  key: string
  kind: OutboxKind
  body: unknown
  createdAt: string
  attempts: number
  /** آخرین خطای غیرشبکه‌ای؛ یعنی سرور رد کرده و تلاشِ دوباره کمکی نمی‌کند. */
  rejectedReason?: string
}

const QUEUE_FILE = 'outbox.json'
const MAX_ITEMS = 100

const file = (): File => new File(Paths.document, QUEUE_FILE)

async function read(): Promise<OutboxItem[]> {
  try {
    const f = file()
    if (!f.exists) return []
    const parsed: unknown = JSON.parse(await f.text())
    return Array.isArray(parsed) ? (parsed as OutboxItem[]) : []
  } catch {
    return []
  }
}

async function write(items: OutboxItem[]): Promise<void> {
  try {
    const f = file()
    if (!f.exists) f.create({ intermediates: true })
    f.write(JSON.stringify(items.slice(-MAX_ITEMS)))
  } catch {
    /* دیسکِ پر: صف ذخیره نمی‌شود ولی اپ نباید بشکند */
  }
}

// ── اشتراک، تا UI بتواند تعداد را نشان دهد ─────────────────────────────────

type Listener = (items: OutboxItem[]) => void
const listeners = new Set<Listener>()

export function subscribeOutbox(fn: Listener): () => void {
  listeners.add(fn)
  void read().then(fn)
  return () => listeners.delete(fn)
}

async function publish(): Promise<OutboxItem[]> {
  const items = await read()
  listeners.forEach((l) => l(items))
  return items
}

export const listOutbox = (): Promise<OutboxItem[]> => read()

// ── افزودن ─────────────────────────────────────────────────────────────────

function newKey(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}

/**
 * نتیجه‌ی `enqueue` — صفحه باید بداند کدام پیام را نشان دهد.
 *
 * `sent` پاسخِ سرور را هم می‌آورد، چون پیامِ موفقیت به شماره‌ی سند و نامِ طرف
 * حساب نیاز دارد؛ `queued` یعنی هنوز شماره‌ای وجود ندارد.
 */
export type EnqueueResult<K extends OutboxKind = OutboxKind> =
  | { status: 'sent'; data: OutboxResponses[K] }
  | { status: 'queued'; item: OutboxItem }

/**
 * کار را روی دیسک می‌نشاند و بلافاصله یک تلاش می‌زند.
 *
 * **ردِ سرور اینجا پرتاب می‌شود، نه در صف پارک.** کاربری که همین حالا دکمه را
 * زده جلوی گوشی ایستاده و می‌تواند اشکال را درست کند؛ پارک‌کردنش یعنی فرم بسته
 * شود و کار به فهرستی برود که باید بعداً کشفش کند. پارک‌کردن فقط برای ردهایی
 * است که حینِ `drain`ِ پس‌زمینه رخ می‌دهند و کاربر آنجا نیست.
 */
export async function enqueue<K extends OutboxKind>(
  kind: K,
  body: OutboxBodies[K],
): Promise<EnqueueResult<K>> {
  const item: OutboxItem = {
    key: newKey(),
    kind,
    body,
    createdAt: new Date().toISOString(),
    attempts: 0,
  }
  const items = await read()
  items.push(item)
  await write(items)
  await publish()

  if (!onlineManager.isOnline()) return { status: 'queued', item }

  // منتظرِ تلاشِ ارسال می‌ماند تا رفتار قطعی باشد. نوشتنِ روی دیسک *پیش از* این
  // انجام شده، پس شبکه‌ی کند فقط زمانِ برگشت را عوض می‌کند نه ماندگاری را.
  const result = await send(item)
  if (result.kind === 'sent') {
    await discard(item.key)
    return { status: 'sent', data: result.data as OutboxResponses[K] }
  }
  if (result.kind === 'rejected') {
    await discard(item.key)
    throw { status: 422, message: result.reason }
  }
  // شبکه/سرور جواب نداد — روی دیسک می‌ماند و `drain` بعداً می‌بردش.
  item.attempts += 1
  await write((await read()).map((i) => (i.key === item.key ? item : i)))
  await publish()
  return { status: 'queued', item }
}

/**
 * تلاشِ دوباره‌ی دستی روی یک آیتم.
 *
 * **چرا لازم است:** `drain` عمداً از آیتمِ ردشده رد می‌شود — تلاشِ خودکارِ بی‌پایان
 * روی چیزی که سرور نمی‌پذیرد فقط باتری می‌سوزاند. ولی گاهی علتِ رد بیرون از سند
 * است و درست می‌شود: انبار شارژ شد، سقفِ اعتبار بالا رفت، حساب باز شد. بدونِ این
 * تابع تنها راهِ باقی‌مانده حذف بود، یعنی دور ریختنِ کارِ کاربر.
 */
export async function retryItem(key: string): Promise<'sent' | 'retry' | 'rejected'> {
  const items = await read()
  const item = items.find((i) => i.key === key)
  if (!item) return 'rejected'

  const result = await send(item)
  if (result.kind === 'sent') {
    await discard(key)
    return 'sent'
  }
  item.attempts += 1
  // پاک می‌شود تا اگر این بار فقط شبکه بود، `drain` دوباره سراغش برود.
  item.rejectedReason = result.kind === 'rejected' ? result.reason : undefined
  await write(items.map((i) => (i.key === key ? item : i)))
  await publish()
  return result.kind
}

/** حذفِ دستیِ یک آیتم — برای وقتی سرور ردش کرده و کاربر می‌خواهد بی‌خیالش شود. */
export async function discard(key: string): Promise<void> {
  await write((await read()).filter((i) => i.key !== key))
  await publish()
}

// ── ارسال ──────────────────────────────────────────────────────────────────

let draining = false

type SendResult = { kind: 'sent'; data: unknown } | { kind: 'retry' } | { kind: 'rejected'; reason: string }

/**
 * یک آیتم را می‌فرستد.
 *
 * **از `apiPost`ِ مشترک رد می‌شود، نه `fetch`ِ خام.** نسخه‌ی اول `fetch` مستقیم
 * می‌زد و توکن را به‌صورتِ پارامتر می‌گرفت — ولی `App.tsx` سرِ بازگشتِ شبکه
 * `drain()` را **بدونِ توکن** صدا می‌زد. یعنی هر تلاشِ خودکار ۴۰۱ می‌گرفت،
 * «تلاشِ دوباره» علامت می‌خورد، و کار تا ابد در صف می‌ماند بی‌آنکه کسی بفهمد.
 * کلاینتِ مشترک توکن را خودش تزریق می‌کند، روی ۴۰۱ رفرش می‌زند، و `detail`ِ
 * فارسیِ خطای سرور را بیرون می‌کشد.
 */
async function send(item: OutboxItem): Promise<SendResult> {
  try {
    const data = await apiPost<unknown>(PATHS[item.kind], item.body, {
      // کلیدِ ثابت: قلبِ ایمنیِ این صف.
      'Idempotency-Key': item.key,
      // بک‌اند سقفِ اعتبار را سرِ همگام‌سازی نمی‌گیرد؛ آن فروش قبلاً انجام شده.
      'X-Cubita-Offline-Replay': '1',
    })
    return { kind: 'sent', data }
  } catch (e) {
    const status = isApiError(e) ? e.status : 0
    // ۰ یعنی شبکه نبود، ۴۰۱ یعنی نشست خراب است نه کار، ۵xx یعنی مشکلِ سرور.
    if (status === 0 || status === 401 || status >= 500) return { kind: 'retry' }
    // ۴xxِ دیگر یعنی سرور این کار را نمی‌پذیرد؛ تلاشِ دوباره همان جواب را می‌دهد.
    return {
      kind: 'rejected',
      reason: isApiError(e) ? e.message : 'سرور این مورد را نپذیرفت.',
    }
  }
}

/**
 * تلاش برای فرستادنِ همه‌ی آیتم‌های صف.
 *
 * ترتیب حفظ می‌شود و روی اولین «تلاشِ دوباره» متوقف می‌شود: اگر شبکه قطع است،
 * آیتم‌های بعدی هم شکست می‌خورند و فقط شمارنده‌ی تلاششان را بی‌دلیل بالا می‌برند.
 */
export async function drain(): Promise<void> {
  if (draining || !onlineManager.isOnline()) return
  draining = true
  try {
    const items = await read()
    const remaining: OutboxItem[] = []
    let stop = false

    for (const item of items) {
      if (stop || item.rejectedReason) {
        remaining.push(item)
        continue
      }
      const result = await send(item)
      if (result.kind === 'sent') continue
      item.attempts += 1
      // **پیامِ خودِ سرور نگه داشته می‌شود.** پیشِ این، همه‌ی ردها یک جمله‌ی
      // یکسان می‌گرفتند و «موجودیِ انبار کافی نیست» از «حساب بسته است» قابلِ
      // تشخیص نبود — یعنی کاربر می‌دانست چیزی ثبت نشده ولی نه اینکه چرا.
      if (result.kind === 'rejected') item.rejectedReason = result.reason
      else stop = true
      remaining.push(item)
    }

    await write(remaining)
    await publish()
  } finally {
    draining = false
  }
}

/** فقط برای تست. */
export async function clearOutbox(): Promise<void> {
  try {
    const f = file()
    if (f.exists) f.delete()
  } catch {
    /* مهم نیست */
  }
  await publish()
}
