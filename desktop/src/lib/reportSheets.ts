import type { BalanceSheet, CashFlow, EquityStatement, IncomeStatement, SeasonalSection } from '../api'

/**
 * صورت‌های مالیِ صفحه‌ی «گزارش‌ها» به‌شکلِ **ردیف‌های یک برگه** — منطقِ خالص، بی React.
 *
 * هر صورت یک گریدِ سه‌ستونه است (کد، شرح، مبلغ) با ردیف‌های بخش، قلم، جمعِ بخش و جمعِ نهایی؛ همان
 * چیزی که حسابدار در اکسل می‌سازد. ارقام همه از سرورند: جمعِ هر بخش `total_*`ِ پاسخ است، نه جمعِ
 * دوباره‌ی قلم‌ها در مرورگر. خروجیِ CSV هم از همین ردیف‌ها ساخته می‌شود، تا آنچه روی صفحه است عیناً
 * در اکسل بیاید.
 */

export type StatementRow =
  | { kind: 'section'; label: string }
  /** `accountId` یعنی قلم به دفترِ حساب باز می‌شود. */
  | { kind: 'line'; label: string; amount: number; code?: string; accountId?: string; note?: string }
  | { kind: 'subtotal'; label: string; amount: number }
  | { kind: 'total'; label: string; amount: number }

const n = (v: string | number | null | undefined) => Number(v || 0)

export function incomeStatementRows(s: IncomeStatement): StatementRow[] {
  const net = n(s.net_profit)
  return [
    { kind: 'section', label: 'درآمدها' },
    ...s.income.map((r) => line(r)),
    { kind: 'subtotal', label: 'جمعِ درآمدها', amount: n(s.total_income) },
    { kind: 'section', label: 'هزینه‌ها' },
    ...s.expenses.map((r) => line(r)),
    { kind: 'subtotal', label: 'جمعِ هزینه‌ها', amount: n(s.total_expenses) },
    { kind: 'total', label: net >= 0 ? 'سود خالص' : 'زیان خالص', amount: net },
  ]
}

/**
 * ترازنامه. «سود/زیانِ دوره‌ی جاری» قلمی از حقوقِ صاحبان سرمایه است (تا سندِ اختتامیه به حسابی نرفته)،
 * پس جمعِ آن بخش با همین قلم است — جمعی که روی صفحه دقیقاً جمعِ ردیف‌های بالایش باشد.
 */
export function balanceSheetRows(s: BalanceSheet): StatementRow[] {
  const profit = n(s.current_period_profit)
  const equity = n(s.total_equity) + profit
  return [
    { kind: 'section', label: 'دارایی‌ها' },
    ...s.assets.map((r) => line(r)),
    { kind: 'subtotal', label: 'جمعِ دارایی‌ها', amount: n(s.total_assets) },
    { kind: 'section', label: 'بدهی‌ها' },
    ...s.liabilities.map((r) => line(r)),
    { kind: 'subtotal', label: 'جمعِ بدهی‌ها', amount: n(s.total_liabilities) },
    { kind: 'section', label: 'حقوق صاحبان سرمایه' },
    ...s.equity.map((r) => line(r)),
    { kind: 'line', label: 'سود/زیانِ دوره‌ی جاری', amount: profit, note: 'هنوز با سندِ اختتامیه به حسابی نرفته' },
    { kind: 'subtotal', label: 'جمعِ حقوق صاحبان سرمایه', amount: equity },
    { kind: 'total', label: 'جمعِ بدهی‌ها و حقوق صاحبان سرمایه', amount: n(s.total_liabilities) + equity },
  ]
}

/** اختلافی کمتر از یک ریال گردِ اعشارِ سرور است، نه ناترازی. */
export function balanceSheetCheck(s: BalanceSheet): { ok: boolean; diff: number } {
  const diff = n(s.total_assets) - (n(s.total_liabilities) + n(s.total_equity) + n(s.current_period_profit))
  return { ok: Math.abs(diff) < 1, diff }
}

export function cashFlowRows(s: CashFlow): StatementRow[] {
  const group = (label: string, lines: CashFlow['operating'], total: string, totalLabel: string): StatementRow[] => [
    { kind: 'section', label },
    ...lines.map((l) => line({ account_id: l.account_id, account_code: l.account_code, account_name: l.account_name, balance: l.amount })),
    { kind: 'subtotal', label: totalLabel, amount: n(total) },
  ]
  return [
    { kind: 'subtotal', label: 'ماندهٔ نقد ابتدای دوره', amount: n(s.opening_cash) },
    ...group('فعالیت‌های عملیاتی', s.operating, s.net_operating, 'خالصِ وجوهِ عملیاتی'),
    ...group('فعالیت‌های سرمایه‌گذاری', s.investing, s.net_investing, 'خالصِ وجوهِ سرمایه‌گذاری'),
    ...group('فعالیت‌های تأمین مالی', s.financing, s.net_financing, 'خالصِ وجوهِ تأمین مالی'),
    { kind: 'total', label: 'تغییرِ خالصِ نقد', amount: n(s.net_change) },
    { kind: 'total', label: 'ماندهٔ نقد پایان دوره', amount: n(s.closing_cash) },
  ]
}

/**
 * گردشِ حقوقِ صاحبان سهام. کاهشِ سرمایه **منفی** نشان داده می‌شود تا ستونِ مبلغ از بالا به پایین جمع
 * بخورد: اول دوره + آورده − کاهش + سایر = پایان دوره.
 */
export function equityRows(s: EquityStatement): StatementRow[] {
  return [
    { kind: 'subtotal', label: 'ماندهٔ اول دوره', amount: n(s.opening_equity) },
    { kind: 'line', label: 'آورده‌ی سرمایه', amount: n(s.contributions) },
    { kind: 'line', label: 'کاهشِ سرمایه', amount: -n(s.withdrawals) },
    {
      kind: 'line',
      label: 'سایر تغییرات',
      amount: n(s.other_changes),
      note: 'اسنادی که تراکنشِ شریکِ نظیر ندارند: سندِ دستی، اختتامیه، افتتاحیه',
    },
    { kind: 'total', label: 'ماندهٔ پایان دوره', amount: n(s.closing_equity) },
  ]
}

/** ردیف‌های برگه → سطرهای CSV: [شرح، کد، مبلغ]. بخش‌ها سطرِ عنوان‌اند و جمع‌ها عددِ خودشان را دارند. */
export function statementCsv(rows: readonly StatementRow[]): (string | number)[][] {
  return rows.map((r) => (r.kind === 'section' ? [r.label, '', ''] : [r.label, r.kind === 'line' ? (r.code ?? '') : '', r.amount]))
}

function line(r: { account_id: string; account_code: string; account_name: string; balance: string }): StatementRow {
  return { kind: 'line', label: r.account_name, code: r.account_code, accountId: r.account_id, amount: n(r.balance) }
}

// ─────────────────────────── معاملاتِ فصلی ───────────────────────────

export const ENTITY_LABEL: Record<string, string> = { real: 'حقیقی', legal: 'حقوقی', aggregate: 'تجمیعی' }

/**
 * برچسبِ هر کمبودِ هویتِ مالیاتی. سرور کدِ ماشین‌خوان می‌دهد؛ متن می‌گوید **دقیقاً چه چیزی** کم است، تا
 * حسابدار بداند در صفحه‌ی «اشخاص» سراغِ کدام فیلد برود.
 */
const ISSUE_LABEL: Record<string, string> = {
  national_id_missing: 'کد/شناسه ملی',
  national_id_length: 'طولِ کد ملی',
  economic_code_missing: 'کد اقتصادی',
  postal_code_missing: 'کد پستی',
}
export const issueText = (codes: readonly string[]) => codes.map((c) => ISSUE_LABEL[c] ?? c).join('، ')

/** سطرِ CSVِ معاملاتِ فصلی: نوع، طرف حساب، شخص، شناسه‌ها، تعداد، مبالغ و کمبودها. */
export const seasonalCsvRow = (kind: string, r: SeasonalSection['rows'][number]): (string | number)[] => [
  kind,
  r.contact_name,
  ENTITY_LABEL[r.entity_type],
  r.national_id ?? '',
  r.economic_code ?? '',
  r.postal_code ?? '',
  r.invoice_count,
  r.gross,
  r.discount,
  r.net,
  r.vat,
  r.total,
  issueText(r.issues),
]
