import type { JournalDraftLine } from './journalEntryDraft'

/**
 * کنش‌های ردیفِ سند — توابعِ خالص روی آرایه‌ی ردیف‌ها.
 *
 * **چرا بیرون از هوک.** محیطِ تستِ این پروژه `node` است و DOM ندارد، پس هر
 * منطقی که داخلِ `useJournalEntryDraft` بماند فقط با رندرِ واقعی سنجیده می‌شود —
 * یعنی عملاً سنجیده نمی‌شود. همان تصمیمی که برای `journalGridNav.ts` گرفته شد.
 *
 * هیچ‌کدام آرایه‌ی ورودی را تغییر نمی‌دهند: `setLines` به شیءِ تازه نیاز دارد تا
 * React تغییر را ببیند، و `GridRow` هم با `memo` روی همین تکیه دارد.
 */

/**
 * رونوشتِ کاملِ یک ردیف، بلافاصله بعد از خودش — **با مبلغ**.
 *
 * تفاوتش با `copyPreviousInto` همین است و عمدی: کسی که «تکرار» می‌زند همان ردیف
 * را می‌خواهد و بعد یک چیزش را عوض می‌کند. اگر مبلغ را خالی می‌گذاشتیم، دو کنش
 * یکی می‌شدند و یکی‌شان بی‌دلیل بود.
 */
export function duplicateAt(lines: JournalDraftLine[], index: number): JournalDraftLine[] {
  const src = lines[index]
  if (!src) return lines
  const next = [...lines]
  next.splice(index + 1, 0, { ...src })
  return next
}

/**
 * حساب، تفصیلی، مرکزِ هزینه و شرحِ ردیفِ قبل را در ردیفِ جاری می‌نشاند — **بدونِ مبلغ** (§۱۸).
 *
 * سناریوی واقعی: ده ردیفِ پشتِ‌هم روی یک حساب با تفصیلی‌های متفاوت. کپیِ مبلغ
 * این‌جا خطرناک است: کاربر می‌خواهد عددِ تازه بزند و عددِ جامانده بی‌صدا در سند
 * می‌ماند. شرح کپی می‌شود چون در این الگو معمولاً همان است.
 */
export function copyPreviousInto(lines: JournalDraftLine[], index: number): JournalDraftLine[] {
  const src = lines[index - 1]
  if (!src) return lines
  return lines.map((line, i) =>
    i === index
      ? {
          ...line,
          accountId: src.accountId,
          analyticId: src.analyticId,
          costCenterId: src.costCenterId,
          description: src.description,
        }
      : line,
  )
}

/** حذفِ ردیف با حفظِ کفِ دو ردیف — سندِ تک‌ردیفی معنا ندارد. */
export function removeAt(lines: JournalDraftLine[], index: number): JournalDraftLine[] {
  return lines.length > 2 ? lines.filter((_, i) => i !== index) : lines
}

export interface Remaining {
  amount: number
  side: 'debit' | 'credit'
}

/**
 * مبلغی که سند را متوازن می‌کند، و طرفی که باید رویش بنشیند.
 *
 * `null` یعنی جمع‌ها برابرند (چه هر دو صفر، چه سندِ متوازن) — در هر دو حالت
 * پیشنهادی وجود ندارد.
 *
 * **هیچ محاسبه‌ی مالیِ تازه‌ای این‌جا نیست:** همان تفاضلِ دو جمعی است که نوارِ
 * پایین هم نشان می‌دهد، و اعتبارسنجیِ نهایی همچنان `submit` و سرور است.
 */
export function remainingOf(totalDebit: number, totalCredit: number): Remaining | null {
  if (totalDebit === totalCredit) return null
  return {
    amount: Math.abs(totalDebit - totalCredit),
    side: totalDebit > totalCredit ? 'credit' : 'debit',
  }
}

/**
 * ردیفی که در سند می‌رود: حساب دارد و یکی از دو مبلغ. ردیفِ خالی — دو ردیفِ آغازینِ
 * فرم، یا ردیفی که کاربر رها کرده — فرستاده نمی‌شود.
 */
export function isPostedLine(l: JournalDraftLine): boolean {
  return Boolean(l.accountId) && ((Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0)
}

/**
 * شماره‌ی ردیفِ گرید برای هر ردیفِ فرستاده‌شده، به ترتیبِ payload (از ۱).
 *
 * **شماره همان است که کاربر کنارِ ردیف می‌بیند**، نه جایگاهش میانِ ردیف‌های پُر.
 * پیامِ تفصیلی پیش از این `validLines.map((l, i) => i + 1)` بود، و با یک ردیفِ
 * خالیِ وسطِ سند برای ردیفِ سوم «ردیف ۲» می‌گفت — در سندِ ۳۰۰ ردیفی یعنی کاربر
 * ردیفِ اشتباه را اصلاح می‌کند. خطای سرور هم ردیفِ *payload* را می‌شمارد، و همین
 * نگاشت آن را به ردیفِ گرید برمی‌گرداند.
 */
export function postedRowNumbers(lines: JournalDraftLine[]): number[] {
  return lines.flatMap((l, i) => (isPostedLine(l) ? [i + 1] : []))
}

/** ردیف‌های گریدی که حسابشان تفصیلی می‌خواهد و نه خودشان تفصیلی دارند نه سربرگ. */
export function rowsMissingTafsili(
  lines: JournalDraftLine[],
  required: ReadonlySet<string>,
  headerAnalyticId: string,
): number[] {
  return lines.flatMap((l, i) =>
    isPostedLine(l) && required.has(l.accountId) && !(l.analyticId || headerAnalyticId) ? [i + 1] : [],
  )
}

const hasAmount = (l: JournalDraftLine) => (Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0

/**
 * ردیف‌هایی که مبلغ دارند ولی حساب ندارند.
 *
 * تا امروز بی‌صدا دور ریخته می‌شدند: نوارِ پایین مبلغشان را در جمع می‌شمرد و «متوازن»
 * می‌گفت، ولی ثبت با «سند متوازن نیست» رد می‌شد — و کاربر نمی‌دانست کدام ردیف.
 */
export function rowsWithoutAccount(lines: JournalDraftLine[]): number[] {
  return lines.flatMap((l, i) => (!l.accountId && hasAmount(l) ? [i + 1] : []))
}

/**
 * ردیف‌هایی که حساب دارند ولی مبلغ ندارند — مثلاً بعد از «کپی از ردیفِ قبل».
 * این‌ها هم بی‌صدا حذف می‌شدند؛ ردیفی که کاربر شروع کرده و رها کرده، باید دیده شود.
 */
export function rowsWithoutAmount(lines: JournalDraftLine[]): number[] {
  return lines.flatMap((l, i) => (l.accountId && !hasAmount(l) ? [i + 1] : []))
}

/** نامِ فارسیِ فیلدهای `JournalLineIn` — برای پیامِ پایدانتیکی که فارسی نیست. */
const LINE_FIELD_FA: Record<string, string> = {
  account_id: 'حساب',
  debit: 'بدهکار',
  credit: 'بستانکار',
  description: 'شرح',
  currency_code: 'ارز',
  fx_amount: 'مبلغ ارزی',
  fx_rate: 'نرخ ارز',
  analytic_id: 'تفصیلی',
  cost_center_id: 'مرکز هزینه',
  tracking_no: 'شماره پیگیری',
  tracking_date: 'تاریخ پیگیری',
}

/**
 * خطای اعتبارسنجیِ سرور (۴۲۲) ← «ردیفِ n: …» با شماره‌ی **گرید**.
 *
 * `loc`ِ خطای ردیف `["body", "lines", i, field]` است و `i` جای ردیف در **payload** است،
 * نه در گرید — ردیف‌های خالی فرستاده نمی‌شوند. `postedRows` (از `postedRowNumbers`)
 * همان نگاشت را برمی‌گرداند. پیامی که فارسی نیست (پایدانتیک برای طول و نوع انگلیسی
 * می‌نویسد) به «مقدارِ «فیلد» نامعتبر است» تبدیل می‌شود. `null` یعنی هیچ خطای
 * ردیفی نبود — پیامِ عمومی کافی است.
 *
 * قراردادِ خطای سرور دست نخورده: خطاهای ردیفیِ بی‌شماره (تفصیلی، پیگیری) حساب را
 * با کد و نام می‌گویند و این‌جا عمداً تجزیه نمی‌شوند.
 */
export function serverLineErrors(detail: unknown, postedRows: number[]): string | null {
  if (!Array.isArray(detail)) return null
  const byRow = new Map<number, string[]>()
  for (const d of detail) {
    const { loc, msg } = (d ?? {}) as { loc?: unknown; msg?: unknown }
    if (!Array.isArray(loc) || loc[0] !== 'body' || loc[1] !== 'lines' || typeof loc[2] !== 'number') continue
    const row = postedRows[loc[2]]
    if (!row) continue
    const text = typeof msg === 'string' ? msg.replace(/^Value error, /, '') : ''
    const field = typeof loc[3] === 'string' ? LINE_FIELD_FA[loc[3]] ?? loc[3] : null
    const shown = /[؀-ۿ]/.test(text) ? text : `مقدارِ «${field ?? 'ردیف'}» نامعتبر است`
    byRow.set(row, [...(byRow.get(row) ?? []), shown])
  }
  if (byRow.size === 0) return null
  return [...byRow]
    .sort((a, b) => a[0] - b[0])
    .map(([row, msgs]) => `ردیفِ ${row.toLocaleString('fa-IR')}: ${[...new Set(msgs)].join('؛ ')}`)
    .join(' — ')
}

/** «۳، ۵ و ۱۷» — شماره‌ی ردیف‌ها برای پیامِ خطا. */
export function faRows(rows: number[]): string {
  const fa = rows.map((r) => r.toLocaleString('fa-IR'))
  return fa.length < 2 ? (fa[0] ?? '') : `${fa.slice(0, -1).join('، ')} و ${fa.at(-1)}`
}

/** جمعِ یک طرف. رشته‌ی خالی یا نامعتبر صفر است، مثلِ خودِ فرم. */
export function sumSide(lines: JournalDraftLine[], side: 'debit' | 'credit'): number {
  return lines.reduce((sum, l) => sum + (Number(l[side]) || 0), 0)
}
