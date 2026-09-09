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

import { API_BASE_URL } from './../api/config'

/** عملیاتی که صف پشتیبانی می‌کند — هر کدام روی بک‌اند idempotent است. */
export type OutboxKind = 'salesInvoice' | 'receipt' | 'payment'

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

/** کار را در صف می‌گذارد و بلافاصله یک تلاش می‌زند. */
export async function enqueue(
  kind: OutboxKind,
  body: unknown,
  token: string | null = null,
): Promise<OutboxItem> {
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
  // منتظرِ تلاشِ ارسال می‌ماند تا رفتار قطعی باشد. نوشتنِ روی دیسک *پیش از* این
  // انجام شده، پس شبکه‌ی کند فقط زمانِ برگشت را عوض می‌کند نه ماندگاری را — و
  // اگر آفلاین باشیم drain بی‌درنگ برمی‌گردد.
  await drain(token)
  return item
}

/** حذفِ دستیِ یک آیتم — برای وقتی سرور ردش کرده و کاربر می‌خواهد بی‌خیالش شود. */
export async function discard(key: string): Promise<void> {
  await write((await read()).filter((i) => i.key !== key))
  await publish()
}

// ── ارسال ──────────────────────────────────────────────────────────────────

let draining = false

async function send(item: OutboxItem, token: string | null): Promise<'sent' | 'retry' | 'rejected'> {
  try {
    const res = await fetch(`${API_BASE_URL}${PATHS[item.kind]}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // کلیدِ ثابت: قلبِ ایمنیِ این صف.
        'Idempotency-Key': item.key,
        // بک‌اند سقفِ اعتبار را سرِ همگام‌سازی نمی‌گیرد؛ آن فروش قبلاً انجام شده.
        'X-Cubita-Offline-Replay': '1',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(item.body),
    })
    if (res.ok) return 'sent'
    // ۴۰۱ یعنی نشست خراب است نه خودِ کار — بماند تا کاربر دوباره وارد شود.
    if (res.status === 401 || res.status >= 500) return 'retry'
    // ۴xxِ دیگر یعنی سرور این کار را نمی‌پذیرد؛ تلاشِ دوباره همان جواب را می‌دهد.
    return 'rejected'
  } catch {
    return 'retry'
  }
}

/**
 * تلاش برای فرستادنِ همه‌ی آیتم‌های صف.
 *
 * ترتیب حفظ می‌شود و روی اولین «تلاشِ دوباره» متوقف می‌شود: اگر شبکه قطع است،
 * آیتم‌های بعدی هم شکست می‌خورند و فقط شمارنده‌ی تلاششان را بی‌دلیل بالا می‌برند.
 */
export async function drain(token: string | null = null): Promise<void> {
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
      const result = await send(item, token)
      if (result === 'sent') continue
      item.attempts += 1
      if (result === 'rejected') {
        item.rejectedReason = 'سرور این مورد را نپذیرفت؛ برای بررسی نگه داشته شد.'
      } else {
        stop = true
      }
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
