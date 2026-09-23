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
 * حساب، تفصیلی و شرحِ ردیفِ قبل را در ردیفِ جاری می‌نشاند — **بدونِ مبلغ**.
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
      ? { ...line, accountId: src.accountId, analyticId: src.analyticId, description: src.description }
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

/** جمعِ یک طرف. رشته‌ی خالی یا نامعتبر صفر است، مثلِ خودِ فرم. */
export function sumSide(lines: JournalDraftLine[], side: 'debit' | 'credit'): number {
  return lines.reduce((sum, l) => sum + (Number(l[side]) || 0), 0)
}
