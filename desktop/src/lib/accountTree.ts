/**
 * منطقِ خالصِ «مرور حساب‌ها» (UI-02) — ساختِ درخت، ردیف‌های پیدا، جست‌وجو و کیبورد.
 *
 * **هیچ عددِ مالی این‌جا ساخته نمی‌شود.** مانده و گردشِ هر گره — برگ یا سرفصل —
 * از سرور می‌آید (`/api/accounting/balance-tree`) که جمعِ زیرشاخه‌ها را همان‌جا
 * زده است. این فایل فقط ساختار را می‌چیند و علامت را به «بد/بس» ترجمه می‌کند.
 *
 * جدا از کامپوننت نگه داشته شده تا بی‌DOM تست شود و تا رندرِ درختِ هزارحسابی فقط
 * با یک `useMemo` روی همین توابع انجام شود.
 */
import type { BalanceTreeNode } from '../api'

export interface TreeIndex {
  byId: Map<string, BalanceTreeNode>
  /** فرزندانِ مستقیمِ هر گره به ترتیبِ کد؛ کلیدِ `''` ریشه‌هاست. */
  children: Map<string, BalanceTreeNode[]>
  roots: BalanceTreeNode[]
}

const ROOT = ''

export function buildTreeIndex(rows: BalanceTreeNode[]): TreeIndex {
  const byId = new Map(rows.map((r) => [r.account_id, r]))
  const children = new Map<string, BalanceTreeNode[]>()
  for (const row of rows) {
    //: والدی که در پاسخ نیست گره را ریشه می‌کند — نه یتیم و نامرئی.
    const pid = row.parent_id && byId.has(row.parent_id) ? row.parent_id : ROOT
    const list = children.get(pid)
    if (list) list.push(row)
    else children.set(pid, [row])
  }
  for (const list of children.values()) list.sort((a, b) => a.account_code.localeCompare(b.account_code))
  return { byId, children, roots: children.get(ROOT) ?? [] }
}

export const childrenOf = (index: TreeIndex, id: string): BalanceTreeNode[] => index.children.get(id) ?? []

export const hasChildren = (index: TreeIndex, id: string) => (index.children.get(id)?.length ?? 0) > 0

export interface VisibilityFilter {
  /** حساب‌هایی که در این دامنه هیچ ردیفی (پیش از بازه یا درونش) ندارند پنهان شوند. */
  activeOnly?: boolean
  /** حساب‌هایی که مانده‌ی پایانِ دوره‌شان صفر است پنهان شوند. */
  hideZero?: boolean
}

export function isHidden(node: BalanceTreeNode, f: VisibilityFilter): boolean {
  if (f.activeOnly && !node.has_activity) return true
  if (f.hideZero && Number(node.closing) === 0) return true
  return false
}

export interface VisibleRow {
  node: BalanceTreeNode
  /** عمقِ *نمایشی* — از ریشه‌ی درخت، نه `node.depth` (که در داده‌ی خراب ممکن است نخواند). */
  level: number
  expandable: boolean
}

/**
 * ردیف‌های پیدا به ترتیبِ نمایش: فقط فرزندانِ گره‌های باز پیموده می‌شوند.
 * هزینه‌اش متناسب با *ردیف‌های دیده‌شده* است، نه کلِ چارت — «باز کردنِ سبک».
 */
export function visibleRows(index: TreeIndex, expanded: ReadonlySet<string>, f: VisibilityFilter = {}): VisibleRow[] {
  const out: VisibleRow[] = []
  const walk = (list: BalanceTreeNode[], level: number, seen: Set<string>) => {
    for (const node of list) {
      if (seen.has(node.account_id) || isHidden(node, f)) continue
      seen.add(node.account_id)
      const kids = childrenOf(index, node.account_id)
      const expandable = kids.some((k) => !isHidden(k, f))
      out.push({ node, level, expandable })
      if (expandable && expanded.has(node.account_id)) walk(kids, level + 1, seen)
    }
  }
  walk(index.roots, 0, new Set())
  return out
}

/** نیاکانِ یک گره از ریشه تا خودش (خودش آخر). حلقه‌ی داده‌ی خراب را می‌شکند. */
export function pathOf(index: TreeIndex, id: string): BalanceTreeNode[] {
  const out: BalanceTreeNode[] = []
  const seen = new Set<string>()
  let cur = index.byId.get(id)
  while (cur && !seen.has(cur.account_id)) {
    seen.add(cur.account_id)
    out.unshift(cur)
    cur = cur.parent_id ? index.byId.get(cur.parent_id) : undefined
  }
  return out
}

/** همه‌ی نیاکانِ یک گره باز شوند تا خودش در درخت دیده شود («نمایش در درخت»). */
export function revealIn(index: TreeIndex, expanded: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(expanded)
  for (const node of pathOf(index, id).slice(0, -1)) next.add(node.account_id)
  return next
}

// ─────────────────────────────── جست‌وجو ───────────────────────────────

const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
const AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'

/** «بانک ملي» با «بانک ملی» یکی است؛ «۱۱۰۲» با «1102». نیم‌فاصله و فاصله‌ی اضافه نادیده. */
export function normalizeSearch(text: string): string {
  let out = ''
  for (const ch of text) {
    const fa = FA_DIGITS.indexOf(ch)
    const ar = AR_DIGITS.indexOf(ch)
    if (fa >= 0) out += String(fa)
    else if (ar >= 0) out += String(ar)
    else if (ch === 'ي' || ch === 'ى') out += 'ی'
    else if (ch === 'ك') out += 'ک'
    else if (ch === 'ة') out += 'ه'
    else if (ch === '‌' || ch === '‏' || ch === '‎') out += ' '
    else out += ch
  }
  return out.replace(/\s+/g, ' ').trim().toLowerCase()
}

export interface SearchHit {
  node: BalanceTreeNode
  path: BalanceTreeNode[]
}

/**
 * جست‌وجو روی کد و نام. کدِ دقیق و پیشوندِ کد اول می‌آیند، بعد نامی که با عبارت
 * شروع می‌شود، بعد هر جای نام. همه‌ی کلمه‌ها باید در نام باشند («ملی بانک» هم پیدا می‌کند).
 */
export function searchAccounts(index: TreeIndex, term: string, limit = 50): SearchHit[] {
  const q = normalizeSearch(term)
  if (!q) return []
  const words = q.split(' ')
  const scored: { node: BalanceTreeNode; score: number }[] = []
  for (const node of index.byId.values()) {
    const code = normalizeSearch(node.account_code)
    const name = normalizeSearch(node.account_name)
    let score = -1
    if (code === q) score = 0
    else if (code.startsWith(q)) score = 1
    else if (name.startsWith(q)) score = 2
    else if (words.every((w) => name.includes(w))) score = 3
    else if (code.includes(q)) score = 4
    if (score >= 0) scored.push({ node, score })
  }
  scored.sort((a, b) => a.score - b.score || a.node.account_code.localeCompare(b.node.account_code))
  return scored.slice(0, limit).map(({ node }) => ({ node, path: pathOf(index, node.account_id) }))
}

// ─────────────────────────── مانده و جهت ───────────────────────────

/** مطابقِ `CREDIT_NORMAL_TYPES` در `backend/app/services/reports.py`. */
const CREDIT_NORMAL = new Set(['liability', 'equity', 'income'])

export type Side = 'debit' | 'credit' | null

/** عددِ خام (بدهکار منهای بستانکار) → مقدارِ مطلق و جهت. صفر جهت ندارد. */
export function sideOf(raw: number): { amount: number; side: Side } {
  if (raw > 0) return { amount: raw, side: 'debit' }
  if (raw < 0) return { amount: -raw, side: 'credit' }
  return { amount: 0, side: null }
}

/**
 * مانده‌ی دفتر (`balance`/`opening_balance`/`closing_balance`) بر اساسِ *نوعِ حساب*
 * علامت می‌خورد (`_signed_balance`): برای حسابِ بستانکارماهیت، مثبت یعنی بستانکار.
 * این تابع همان قاعده را برمی‌گرداند تا جهت درست خوانده شود — عددی نمی‌سازد.
 */
export function ledgerRaw(balance: number, accountType: string): number {
  return CREDIT_NORMAL.has(accountType) ? -balance : balance
}

export const SIDE_LABEL: Record<'debit' | 'credit', string> = { debit: 'بدهکار', credit: 'بستانکار' }
export const SIDE_SHORT: Record<'debit' | 'credit', string> = { debit: 'بد', credit: 'بس' }

export const NATURE_LABEL: Record<string, string> = {
  debit: 'بدهکار',
  credit: 'بستانکار',
  any: 'آزاد',
}

// ─────────────────────────────── کیبورد ───────────────────────────────

export type TreeKeyResult =
  | { kind: 'focus'; id: string }
  | { kind: 'expand'; id: string }
  | { kind: 'collapse'; id: string }
  | { kind: 'open'; id: string }
  | { kind: 'none' }

/**
 * یک کلید روی درخت → یک کار. **راست‌به‌چپ:** زیرشاخه به سمتِ چپ تورفتگی دارد و
 * شِورونِ بسته به چپ اشاره می‌کند، پس `←` «جلو/داخل» است و `→` «عقب/بیرون» —
 * همان قراردادِ WAI-ARIA برای درختِ RTL.
 *
 *   ↑ ↓            ردیفِ قبل/بعد            Home / End   اولین/آخرین
 *   PageUp/Down    ده ردیف
 *   ←              بستهٔ باز شود؛ بازِ   ←  اولین فرزند
 *   →              بازِ بسته شود؛ بسته/برگ ← والد
 *   Enter          ورود به گردشِ حساب (دفتر)
 *   Escape         برگشت به والد (یک سطح بالا)
 */
export function treeKey(
  key: string,
  rows: VisibleRow[],
  focusedId: string | null,
  expanded: ReadonlySet<string>,
): TreeKeyResult {
  if (rows.length === 0) return { kind: 'none' }
  const at = focusedId ? rows.findIndex((r) => r.node.account_id === focusedId) : -1
  const row = at >= 0 ? rows[at] : null
  const focusAt = (i: number): TreeKeyResult => ({
    kind: 'focus',
    id: rows[Math.max(0, Math.min(rows.length - 1, i))].node.account_id,
  })
  const parentOf = (): TreeKeyResult => {
    if (!row) return { kind: 'none' }
    for (let i = at - 1; i >= 0; i--) if (rows[i].level < row.level) return focusAt(i)
    return { kind: 'none' }
  }

  switch (key) {
    case 'ArrowDown':
      return focusAt(at < 0 ? 0 : at + 1)
    case 'ArrowUp':
      return focusAt(at < 0 ? 0 : at - 1)
    case 'Home':
      return focusAt(0)
    case 'End':
      return focusAt(rows.length - 1)
    case 'PageDown':
      return focusAt(at + 10)
    case 'PageUp':
      return focusAt(at - 10)
    case 'ArrowLeft': {
      if (!row) return focusAt(0)
      if (!row.expandable) return { kind: 'none' }
      if (!expanded.has(row.node.account_id)) return { kind: 'expand', id: row.node.account_id }
      return at + 1 < rows.length ? focusAt(at + 1) : { kind: 'none' }
    }
    case 'ArrowRight': {
      if (!row) return focusAt(0)
      if (row.expandable && expanded.has(row.node.account_id)) return { kind: 'collapse', id: row.node.account_id }
      return parentOf()
    }
    case 'Escape':
      return parentOf()
    case 'Enter':
      return row ? { kind: 'open', id: row.node.account_id } : { kind: 'none' }
    default:
      return { kind: 'none' }
  }
}
