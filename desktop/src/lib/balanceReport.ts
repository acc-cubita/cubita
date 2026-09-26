import type { BalanceRow, ChartAccount } from '../api'
import { normalizeSearch } from './accountTree'

/**
 * منطقِ خالصِ «گزارش ترازها» — تجمیعِ سطح، فیلترِ نمایش، جمعِ ستون‌ها و سنجشِ توازن.
 *
 * ارقامِ سطحِ آخر از سرور می‌آیند (`/api/accounting/balances`)؛ تراز در سطحِ کل و معین جمعِ همان ردیف‌هاست،
 * پس این‌جا تجمیع می‌شود نه با کوئریِ جدا — یک منبعِ عدد برای هر چهار قالبِ ستونی.
 */

export type BalanceColumns = 2 | 4 | 6 | 8
/** فیلترِ نوعِ مانده (§۱۷). «بدونِ گردش» عمداً از «مانده صفر» جداست. */
export type BalanceFilter = 'all' | 'debit' | 'credit' | 'zero' | 'idle'
/** یک جفت ستونِ بدهکار/بستانکار در سرستونِ دوطبقه. */
export type BalanceGroup = 'opening' | 'period' | 'sum' | 'closing'

export const GROUP_LABELS: Record<BalanceGroup, string> = {
  opening: 'افتتاحیه',
  period: 'گردش',
  sum: 'جمع',
  closing: 'مانده',
}

/** گروه‌های ستونیِ هر قالب، به ترتیبِ نمایش. «سند کل» فقط گردش دارد. */
export function balanceGroups(columns: BalanceColumns, general: boolean): BalanceGroup[] {
  if (general) return ['period']
  if (columns === 2) return ['closing']
  if (columns === 4) return ['period', 'closing']
  if (columns === 6) return ['opening', 'period', 'closing']
  return ['opening', 'period', 'sum', 'closing']
}

/** [بدهکار، بستانکار]ِ یک گروه برای یک ردیف. «جمع» = افتتاحیه + گردش. */
export function pairOf(row: BalanceRow, group: BalanceGroup): [number, number] {
  switch (group) {
    case 'opening':
      return [Number(row.opening_debit), Number(row.opening_credit)]
    case 'period':
      return [Number(row.period_debit), Number(row.period_credit)]
    case 'sum':
      return [
        Number(row.opening_debit) + Number(row.period_debit),
        Number(row.opening_credit) + Number(row.period_credit),
      ]
    case 'closing':
      return [Number(row.closing_debit), Number(row.closing_credit)]
  }
}

/** سطحِ حساب در چارت: ۱ = گروه، ۲ = کل، ۳ = معین، ۴+ = تفصیلی. */
export function levelOf(account: ChartAccount, byId: Map<string, ChartAccount>): number {
  let level = 1
  let node = account
  const seen = new Set<string>()
  while (node.parent_id && !seen.has(node.id)) {
    seen.add(node.id)
    const parent = byId.get(node.parent_id)
    if (!parent) break
    node = parent
    level += 1
  }
  return level
}

/** جدِ حساب در سطحِ داده‌شده — پایه‌ی تجمیعِ تراز در سطحِ کل/معین. */
export function ancestorAtLevel(account: ChartAccount, byId: Map<string, ChartAccount>, level: number): ChartAccount {
  let node = account
  const seen = new Set<string>()
  while (levelOf(node, byId) > level && node.parent_id && !seen.has(node.id)) {
    seen.add(node.id)
    const parent = byId.get(node.parent_id)
    if (!parent) break
    node = parent
  }
  return node
}

/**
 * ردیف‌های سطحِ آخر → ردیف‌های سطحِ `level` (۰ = همان سطحِ آخر، بی‌تغییر).
 *
 * مانده‌ی افتتاحیه و پایانِ ردیفِ تجمیع‌شده **خالص** می‌شود، وگرنه یک سرفصل هم بدهکار و هم بستانکار نشان
 * می‌داد و جمعِ ستونِ مانده دو برابرِ واقعیت می‌شد. گردش خالص نمی‌شود — گردشِ دوطرفه خودش خبر است.
 */
export function aggregateBalances(source: readonly BalanceRow[], accounts: readonly ChartAccount[], level: number): BalanceRow[] {
  if (level === 0) return [...source]
  const byId = new Map(accounts.map((a) => [a.id, a]))
  const totals = new Map<string, BalanceRow>()
  for (const row of source) {
    const leaf = byId.get(row.account_id)
    if (!leaf) continue
    const target = ancestorAtLevel(leaf, byId, level)
    const bucket = totals.get(target.id)
    if (!bucket) {
      totals.set(target.id, {
        ...row,
        account_id: target.id,
        account_code: target.code,
        account_name: target.name,
        account_type: target.type,
        parent_id: target.parent_id,
      })
      continue
    }
    bucket.opening_debit = String(Number(bucket.opening_debit) + Number(row.opening_debit))
    bucket.opening_credit = String(Number(bucket.opening_credit) + Number(row.opening_credit))
    bucket.period_debit = String(Number(bucket.period_debit) + Number(row.period_debit))
    bucket.period_credit = String(Number(bucket.period_credit) + Number(row.period_credit))
    bucket.closing_debit = String(Number(bucket.closing_debit) + Number(row.closing_debit))
    bucket.closing_credit = String(Number(bucket.closing_credit) + Number(row.closing_credit))
    //: سرفصلی که یکی از زیرحساب‌هایش گردش خورده، گردش داشته است — نه فقط اگر اولین‌شان خورده باشد.
    bucket.has_activity = bucket.has_activity !== false || row.has_activity !== false
  }
  return [...totals.values()]
    .map((r) => {
      const net = Number(r.closing_debit) - Number(r.closing_credit)
      const openNet = Number(r.opening_debit) - Number(r.opening_credit)
      return {
        ...r,
        opening_debit: String(openNet > 0 ? openNet : 0),
        opening_credit: String(openNet < 0 ? -openNet : 0),
        closing_debit: String(net > 0 ? net : 0),
        closing_credit: String(net < 0 ? -net : 0),
        balance: String(net),
      }
    })
    .sort((a, b) => a.account_code.localeCompare(b.account_code))
}

/**
 * فیلترِ **نمایش** — سمتِ رابط، چون ردیف‌ها از قبل در دست‌اند و دامنه‌ی محاسبه را عوض نمی‌کند (برخلافِ
 * `ReportFilterBar` که خودِ عددها را عوض می‌کند و سمتِ سرور است).
 * «سند کل» فقط حساب‌هایی را دارد که در بازه گردش خورده‌اند؛ جست‌وجو روی کد (پیشوند) و نام است.
 */
export function filterBalances(
  rows: readonly BalanceRow[],
  { general, filter, query = '' }: { general: boolean; filter: BalanceFilter; query?: string },
): BalanceRow[] {
  const q = normalizeSearch(query)
  const hit = (r: BalanceRow) =>
    !q || normalizeSearch(r.account_code).startsWith(q) || normalizeSearch(r.account_name).includes(q)
  if (general) return rows.filter((r) => (Number(r.period_debit) !== 0 || Number(r.period_credit) !== 0) && hit(r))
  return rows.filter((r) => {
    if (!hit(r)) return false
    if (filter === 'all') return true
    const net = Number(r.closing_debit) - Number(r.closing_credit)
    if (filter === 'idle') return r.has_activity === false
    if (filter === 'zero') return net === 0 && r.has_activity !== false
    if (filter === 'debit') return net > 0
    return net < 0
  })
}

/** جمعِ [بدهکار، بستانکار]ِ هر گروه روی ردیف‌های داده‌شده. */
export function balanceTotals(rows: readonly BalanceRow[], groups: readonly BalanceGroup[]): Map<BalanceGroup, [number, number]> {
  const out = new Map<BalanceGroup, [number, number]>(groups.map((g) => [g, [0, 0]]))
  for (const r of rows) {
    for (const g of groups) {
      const [d, c] = pairOf(r, g)
      const t = out.get(g)!
      t[0] += d
      t[1] += c
    }
  }
  return out
}

/** اختلافی کمتر از نیم ریال گردِ ممیزِ شناور است، نه ناترازی. */
const EPS = 0.5

export type BalanceCheck =
  | { kind: 'ok' }
  /** هر گروهِ ناتراز با اختلافش (بدهکار − بستانکار)، به ترتیبِ ستون‌ها. */
  | { kind: 'off'; off: { group: BalanceGroup; diff: number }[] }
  /** ردیف‌ها فیلتر شده‌اند؛ جمعِ بخشی از دفتر لازم نیست تراز باشد، پس سنجیده نمی‌شود. */
  | { kind: 'partial' }

/**
 * توازنِ تراز: در هر گروه جمعِ بدهکار باید با جمعِ بستانکار برابر باشد. فقط وقتی همه‌ی ردیف‌ها دیده می‌شوند
 * سنجیده می‌شود — فیلترِ «مانده بدهکار» به‌تعریف ناتراز است و هشدارِ دروغین می‌داد.
 */
export function balanceCheck(totals: Map<BalanceGroup, [number, number]>, complete: boolean): BalanceCheck {
  if (!complete) return { kind: 'partial' }
  const off = [...totals]
    .filter(([, [d, c]]) => Math.abs(d - c) >= EPS)
    .map(([group, [d, c]]) => ({ group, diff: d - c }))
  return off.length ? { kind: 'off', off } : { kind: 'ok' }
}
