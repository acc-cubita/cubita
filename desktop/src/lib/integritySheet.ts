import type { IntegrityCheck, IntegrityRow } from '../api'

/**
 * منطقِ خالصِ «بررسی یکپارچگی» — یک گرید برای همه‌ی بررسی‌ها.
 *
 * هر بررسی یک **ردیفِ سرگروه** است (وضعیت، عنوان، شمارِ یافته) و یافته‌هایش زیرش؛ همان چیدمانِ روزنامه‌ی «گزارش دفتر».
 * پیش از این هر بررسی یک کارتِ جدا بود و نُه کارت که هفت‌تایش «چیزی پیدا نکرد» می‌گفتند، دو یافته‌ی واقعی را ته صفحه
 * می‌بردند.
 */

export type CheckTone = 'ok' | 'error' | 'warning'

/** «سالم» فقط وقتی یافته‌ای نیست؛ وگرنه شدتِ خودِ بررسی. */
export const checkTone = (c: Pick<IntegrityCheck, 'ok' | 'severity'>): CheckTone => (c.ok ? 'ok' : c.severity)

export const SEVERITY_LABEL: Record<IntegrityCheck['severity'], string> = { error: 'خطا', warning: 'هشدار' }

export interface IntegritySummary {
  /** بررسی‌های خطا که یافته دارند — همین‌ها دفتر را «نیازمندِ رسیدگی» می‌کنند. */
  errors: number
  /** بررسی‌های هشدار که یافته دارند — دیده می‌شوند ولی دفتر را ناسالم نمی‌کنند. */
  warnings: number
  healthy: number
  /** شمارِ کاملِ یافته‌ها از سرور (`count`)، نه ردیف‌های بریده‌شده. */
  findings: number
}

export function integritySummary(checks: readonly IntegrityCheck[]): IntegritySummary {
  return checks.reduce(
    (s, c) => {
      const tone = checkTone(c)
      return {
        errors: s.errors + (tone === 'error' ? 1 : 0),
        warnings: s.warnings + (tone === 'warning' ? 1 : 0),
        healthy: s.healthy + (tone === 'ok' ? 1 : 0),
        findings: s.findings + (c.ok ? 0 : c.count),
      }
    },
    { errors: 0, warnings: 0, healthy: 0, findings: 0 },
  )
}

/**
 * برچسبِ ردیفِ حساب و کالا «کد — نام» است. سرور شناسه را جدا می‌دهد، پس این تجزیه فقط عنوانِ کشوست؛ اگر شکلِ برچسب
 * عوض شود، بدترین حالت یک عنوانِ خام است نه خطا.
 */
export function splitLabel(label: string): { code: string; name: string } {
  const [code, ...rest] = label.split(' — ')
  return { code, name: rest.join(' — ') || code }
}

export type Target =
  | { kind: 'entry'; id: string }
  | { kind: 'item'; id: string; sku: string; name: string }
  | { kind: 'account'; id: string; code: string; name: string }

export const TARGET_LABEL: Record<Target['kind'], string> = { entry: 'سند', item: 'کاردکس', account: 'دفترِ حساب' }

/**
 * جاهایی که یک یافته به آن‌ها می‌برد، به‌ترتیبِ مشخص‌بودن: سند (خودِ ثبت)، بعد کاردکسِ کالا، بعد دفترِ حساب. اولی کلیک
 * و Enterِ ردیف است؛ بقیه دکمه‌اند. یافته‌ای که هیچ‌کدام را ندارد (تخصیصِ بیش از مانده) فقط خوانده می‌شود.
 */
export function targetsOf(row: IntegrityRow): Target[] {
  const out: Target[] = []
  if (row.entry_id) out.push({ kind: 'entry', id: row.entry_id })
  if (row.item_id) {
    const { code, name } = splitLabel(row.label)
    out.push({ kind: 'item', id: row.item_id, sku: code, name })
  }
  if (row.account_id) out.push({ kind: 'account', id: row.account_id, ...splitLabel(row.label) })
  return out
}

export type SheetRow =
  | { kind: 'check'; check: IntegrityCheck; open: boolean }
  | { kind: 'finding'; check: IntegrityCheck; row: IntegrityRow; index: number }
  | { kind: 'more'; check: IntegrityCheck }

const TONE_RANK: Record<CheckTone, number> = { error: 0, warning: 1, ok: 2 }

/**
 * ردیف‌های گرید. بررسیِ سالم فقط سرگروه است؛ بررسیِ دارای یافته، بسته نشده باشد، یافته‌هایش را زیرش دارد و اگر سرور
 * بریده (`truncated`) یک ردیفِ «بقیه» ته آن‌ها. `onlyFindings` بررسی‌های سالم را برمی‌دارد.
 *
 * **یافته‌ها اول:** خطاها، بعد هشدارها، بعد سالم‌ها — هر دسته به‌ترتیبِ سرور. به‌ترتیبِ سرور، شش سرگروهِ «بدونِ یافته»
 * یافته‌ی واقعی را زیرِ لبه‌ی صفحه می‌بردند.
 */
export function sheetRows(
  checks: readonly IntegrityCheck[],
  opts: { onlyFindings: boolean; closed: ReadonlySet<string> },
): SheetRow[] {
  const out: SheetRow[] = []
  const ordered = checks
    .map((check, i) => ({ check, i }))
    .sort((a, b) => TONE_RANK[checkTone(a.check)] - TONE_RANK[checkTone(b.check)] || a.i - b.i)
    .map((x) => x.check)
  for (const check of ordered) {
    if (opts.onlyFindings && check.ok) continue
    const open = !check.ok && !opts.closed.has(check.key)
    out.push({ kind: 'check', check, open })
    if (!open) continue
    check.rows.forEach((row, index) => out.push({ kind: 'finding', check, row, index }))
    if (check.truncated) out.push({ kind: 'more', check })
  }
  return out
}

/**
 * خروجیِ CSV برای حسابرس: هر یافته یک ردیف با نامِ بررسی و شدتش، و هر بررسیِ سالم هم یک ردیفِ «بدونِ یافته» — فایل باید
 * نشان دهد چه چیزی سنجیده شد، نه فقط چه چیزی پیدا شد.
 */
export function integrityCsv(checks: readonly IntegrityCheck[]): { headers: string[]; rows: (string | number)[][] } {
  return {
    headers: ['بررسی', 'شدت', 'مورد', 'توضیح', 'بدهکار', 'بستانکار', 'اختلاف'],
    rows: checks.flatMap((c) =>
      c.ok
        ? [[c.title, 'سالم', '', 'بدونِ یافته', '', '', '']]
        : [
            ...c.rows.map((r) => [
              c.title,
              SEVERITY_LABEL[c.severity],
              r.label,
              r.detail,
              Number(r.debit),
              Number(r.credit),
              Number(r.difference),
            ]),
            //: سرور بریده؛ فایل نباید وانمود کند همه‌ی یافته‌ها را دارد.
            ...(c.truncated
              ? [[c.title, SEVERITY_LABEL[c.severity], '', `و ${(c.count - c.rows.length).toLocaleString('fa-IR')} موردِ دیگر — بازه یا فیلتر را محدودتر کنید`, '', '', '']]
              : []),
          ],
    ),
  }
}
