import type { RecurringEntry, RecurringEntryInput, RecurringFrequency } from '../api'
import { toNumber } from './csv'
import { toFaDigits } from './jalali'

/**
 * منطقِ خالصِ صفحه‌ی «اسناد تکرارشونده» — قالبی که سندِ دوره‌ای (اجاره، بیمه، اقساط) را در هر سررسید
 * خودکار می‌سازد. بی DOM و بی React، تا مستقیم تست شود (همان الگوی `analyticsSheet.ts`).
 *
 * سرور قالب را کامل می‌گیرد و کامل جایگزین می‌کند (`PUT`)؛ پس فرم یک سند است، نه برگه‌ی ردیف‌به‌ردیف:
 * سربرگ + ردیف‌های بدهکار/بستانکار که باید تراز شوند (الگوی «الف»ِ تمِ اکسلی). همان قیدهای سرور این‌جا
 * پیش از ارسال سنجیده می‌شوند تا کاربر به‌جای ۴۲۲، جمله‌ی روشن ببیند.
 */
export type RecurringLineDraft = { account_id: string; description: string; debit: string; credit: string }

export interface TemplateForm {
  title: string
  description: string
  frequency: RecurringFrequency
  /** «هر چند دوره یک‌بار» — متنِ خامِ کادر. */
  interval: string
  start_date: string
  /** خالی یعنی بی‌پایان. */
  end_date: string
  cost_center_id: string
}

export const blankLine = (): RecurringLineDraft => ({ account_id: '', description: '', debit: '', credit: '' })
export const blankForm = (today: string): TemplateForm => ({
  title: '',
  description: '',
  frequency: 'monthly',
  interval: '1',
  start_date: today,
  end_date: '',
  cost_center_id: '',
})

export const FREQ_LABEL: Record<RecurringFrequency, string> = { weekly: 'هفتگی', monthly: 'ماهانه', yearly: 'سالانه' }
const FREQ_UNIT: Record<RecurringFrequency, string> = { weekly: 'هفته', monthly: 'ماه', yearly: 'سال' }

/** «ماهانه» یا «هر ۳ ماه». */
export function freqText(f: RecurringFrequency, interval: number): string {
  return interval > 1 ? `هر ${toFaDigits(interval)} ${FREQ_UNIT[f]}` : FREQ_LABEL[f]
}

/** ردیفی که حساب و مبلغ دارد — همان که به سرور می‌رود. ردیفِ کاملاً خالی نادیده گرفته می‌شود. */
export const lineIsFilled = (l: RecurringLineDraft) => Boolean(l.account_id) && (toNumber(l.debit) > 0 || toNumber(l.credit) > 0)
const lineIsEmpty = (l: RecurringLineDraft) => !l.account_id && !l.description.trim() && !toNumber(l.debit) && !toNumber(l.credit)

export function lineTotals(lines: readonly RecurringLineDraft[]): { debit: number; credit: number } {
  return lines.reduce(
    (t, l) => ({ debit: t.debit + toNumber(l.debit), credit: t.credit + toNumber(l.credit) }),
    { debit: 0, credit: 0 },
  )
}

/** قالبِ ثبت‌شده → فرم و ردیف‌ها برای ویرایش. مبلغِ صفر خالی می‌شود تا کادر «۰» نشان ندهد. */
export function formFromEntry(e: RecurringEntry): { form: TemplateForm; lines: RecurringLineDraft[] } {
  const amount = (v: string) => (Number(v) ? String(Number(v)) : '')
  return {
    form: {
      title: e.title,
      description: e.description,
      frequency: e.frequency,
      interval: String(e.interval),
      start_date: e.start_date,
      end_date: e.end_date ?? '',
      cost_center_id: e.cost_center_id ?? '',
    },
    lines: e.lines.map((l) => ({
      account_id: l.account_id,
      description: l.description ?? '',
      debit: amount(l.debit),
      credit: amount(l.credit),
    })),
  }
}

/**
 * خطای قالب پیش از ارسال، به زبانِ کاربر؛ `null` یعنی آماده. همان قیدهای `RecurringEntryIn`ِ سرور،
 * به‌اضافه‌ی ردیفِ نیمه‌کاره (حساب بی‌مبلغ یا مبلغ بی‌حساب) که سرور بی‌صدا نمی‌فهمید کدام است.
 */
export function templateProblem(form: TemplateForm, lines: readonly RecurringLineDraft[]): string | null {
  if (!form.title.trim()) return 'عنوانِ قالب را بنویسید.'
  const interval = Number(form.interval)
  if (!Number.isInteger(interval) || interval < 1) return '«هر چند دوره» باید عددِ صحیحِ ۱ یا بیشتر باشد.'
  if (!form.start_date) return 'تاریخِ شروع را انتخاب کنید.'
  if (form.end_date && form.end_date < form.start_date) return 'تاریخِ پایان پیش از تاریخِ شروع است.'
  const half = lines.findIndex((l) => !lineIsEmpty(l) && !lineIsFilled(l))
  if (half !== -1) {
    const l = lines[half]
    return `ردیفِ ${toFaDigits(half + 1)} ${l.account_id ? 'مبلغ' : 'حساب'} ندارد.`
  }
  if (lines.filter(lineIsFilled).length < 2) return 'سند دست‌کم دو ردیف با حساب و مبلغ می‌خواهد.'
  const t = lineTotals(lines)
  if (Math.abs(t.debit - t.credit) >= 0.005) return 'سند متوازن نیست — جمعِ بدهکار و بستانکار باید برابر باشد.'
  return null
}

export function toPayload(form: TemplateForm, lines: readonly RecurringLineDraft[]): RecurringEntryInput {
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    frequency: form.frequency,
    interval: Math.max(1, Math.trunc(Number(form.interval)) || 1),
    start_date: form.start_date,
    end_date: form.end_date || null,
    cost_center_id: form.cost_center_id || null,
    lines: lines.filter(lineIsFilled).map((l) => ({
      account_id: l.account_id,
      debit: toNumber(l.debit),
      credit: toNumber(l.credit),
      description: l.description.trim(),
    })),
  }
}

/** فهرستِ قالب‌ها به ترتیبِ اقدام: سررسیدشده بالا، بعد فعال‌ها به سررسیدِ نزدیک‌تر، غیرفعال ته. */
export function sortTemplates(entries: readonly RecurringEntry[]): RecurringEntry[] {
  const rank = (e: RecurringEntry) => (!e.is_active ? 2 : e.is_due ? 0 : 1)
  return [...entries].sort(
    (a, b) => rank(a) - rank(b) || a.next_run_date.localeCompare(b.next_run_date) || a.title.localeCompare(b.title, 'fa'),
  )
}

/** جست‌وجوی سرِ فهرست: عنوان، شرح، و کد یا نامِ حساب‌های ردیف‌ها. */
export function templateMatches(e: RecurringEntry, query: string): boolean {
  const q = query.trim()
  if (!q) return true
  return [e.title, e.description, ...e.lines.flatMap((l) => [l.account_code, l.account_name])].some((s) => s.includes(q))
}
