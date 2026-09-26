import type { AccountTraits, ChartAccount } from '../api'
import { textMatches } from './faText'

/**
 * منطقِ خالصِ برگه‌ی «درختواره حساب‌ها» — ویرایشِ درجا به سبکِ اکسل روی **درخت**، با ذخیره‌ی یک‌جا.
 *
 * دو جنس ردیف: **ثبت‌شده** (از سرور) که ویرایش‌هایش در `edits` کنار می‌ماند، و **تازه** (`fresh`) که زیرِ یک
 * سرفصلِ ثبت‌شده (یا ریشه) اضافه شده و هنوز سرور ندیده. برخلافِ برگه‌های تخت، ردیفِ خالیِ ته ندارد: در درخت
 * «ته» یک جا نیست — ردیفِ تازه با «+»ِ هر ردیف (یا Ctrl+Enter) زیرِ همان سرفصل می‌نشیند.
 *
 * بی DOM و بی React، تا مستقیم تست شود.
 */

export type Nature = '' | 'debit' | 'credit' | 'any'

/** آنچه در خودِ برگه ویرایش می‌شود. ویژگی‌های حساب (شش پرچم) در کشوی ویرایش‌اند. */
export interface Values {
  code: string
  name: string
  name2: string
  /** '' یعنی «مشتق از نوعِ حساب» — همان null ِ بک‌اند. */
  nature: Nature
  is_active: boolean
}

export interface FreshAccount {
  key: string
  /** سرفصلِ مادرِ **ثبت‌شده**؛ null یعنی ریشه. زیرِ حسابِ تازه‌ی ذخیره‌نشده حساب ساخته نمی‌شود. */
  parentId: string | null
  code: string
  name: string
  name2: string
  nature: Nature
  isGroup: boolean
  /** فقط ریشه نوعِ دستی می‌گیرد؛ زیرِ هر سرفصل نوع همان نوعِ مادر است. */
  type: string
  traits: AccountTraits
}

export interface Draft {
  edits: Record<string, Partial<Values>>
  fresh: FreshAccount[]
}

/** پیش‌فرضِ ویژگی‌های حسابِ تازه — عیناً همان پیش‌فرضِ ستون‌ها در مهاجرتِ ۰۰۸۸. */
export const NEW_TRAITS: AccountTraits = {
  nature_control: false,
  is_fx: false,
  fx_revaluable: false,
  accepts_tafsili: false,
  has_tracking: false,
  in_management_reports: true,
}

/** واژگانِ سطحِ حساب در حسابداریِ ایران، بر پایه‌ی عمق در درخت. */
export const LEVEL_LABELS = ['گروه', 'کل', 'معین', 'تفصیلی']
export const levelLabel = (depth: number) => LEVEL_LABELS[Math.min(depth, LEVEL_LABELS.length - 1)]

export interface Node extends ChartAccount {
  depth: number
  children: Node[]
  /** «عنوانِ کامل» — مسیرِ حساب از ریشه، مثلِ «دارایی‌ها › دارایی‌های جاری › صندوق». */
  fullName: string
  /** مانده‌ی خودِ حساب (برگ) یا جمعِ زیرمجموعه (سرفصل). */
  balance: number
}

const byCode = (a: { code: string }, b: { code: string }) => a.code.localeCompare(b.code, 'en', { numeric: true })

/** فهرستِ تخت را به درخت تبدیل می‌کند و مانده‌ها را پایین‌به‌بالا جمع می‌زند. */
export function buildTree(accounts: readonly ChartAccount[], balances: ReadonlyMap<string, number>): Node[] {
  const nodes = new Map<string, Node>()
  for (const a of accounts)
    nodes.set(a.id, { ...a, depth: 0, children: [], balance: balances.get(a.id) ?? 0, fullName: a.name })
  const roots: Node[] = []
  for (const node of nodes.values()) {
    const parent = node.parent_id ? nodes.get(node.parent_id) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  const walk = (list: Node[], depth: number, prefix: string): number => {
    list.sort(byCode)
    let sum = 0
    for (const node of list) {
      node.depth = depth
      node.fullName = prefix ? `${prefix} › ${node.name}` : node.name
      //: مانده‌ی گره = مانده‌ی خودش + جمعِ فرزندان. حسابِ معینی که تفصیلی گرفته ممکن است ردیفِ مستقیمِ قدیمی
      //: هم داشته باشد و جای‌گذاریِ ساده پنهانش می‌کرد.
      node.balance += walk(node.children, depth + 1, node.fullName)
      sum += node.balance
    }
    return sum
  }
  walk(roots, 0, '')
  return roots
}

/** گره‌هایی که با جست‌وجو می‌مانند — به‌همراه همه‌ی نیاکانشان، تا مسیر گم نشود. `null` یعنی «همه». */
export function matchingIds(roots: readonly Node[], query: string): Set<string> | null {
  if (!query.trim()) return null
  const keep = new Set<string>()
  const visit = (node: Node, ancestors: string[]): boolean => {
    const hit = textMatches(node.name, query) || textMatches(node.code, query) || textMatches(node.name2, query)
    let childHit = false
    for (const child of node.children) childHit = visit(child, [...ancestors, node.id]) || childHit
    if (hit || childHit) {
      keep.add(node.id)
      for (const id of ancestors) keep.add(id)
      return true
    }
    return false
  }
  for (const root of roots) visit(root, [])
  return keep
}

export interface ViewOptions {
  collapsed: ReadonlySet<string>
  /** نتیجه‌ی `matchingIds`؛ null یعنی بی‌جست‌وجو. */
  visible: ReadonlySet<string> | null
  type: string
  showInactive: boolean
  /** نمای تخت: بی تورفتگی و بی جمع‌شدن، به ترتیبِ کد (همان ترتیبِ پیمایشِ درخت). */
  flat: boolean
}

/** گره‌های روی صفحه به ترتیبِ درخت. در جست‌وجو و نمای تخت همه باز است، وگرنه مسیرِ نتیجه پنهان می‌ماند. */
export function visibleNodes(roots: readonly Node[], o: ViewOptions): Node[] {
  const out: Node[] = []
  const open = (n: Node) => o.flat || o.visible !== null || !o.collapsed.has(n.id)
  const walk = (list: readonly Node[]) => {
    for (const n of list) {
      if (o.visible && !o.visible.has(n.id)) continue
      if (o.type && n.type !== o.type) continue
      if (!o.showInactive && !n.is_active && !n.is_group) continue
      out.push(n)
      if (n.children.length && open(n)) walk(n.children)
    }
  }
  walk(roots)
  return out
}

export type SheetRow =
  | { kind: 'saved'; key: string; node: Node; values: Values }
  | { kind: 'new'; key: string; fresh: FreshAccount; depth: number; values: Values }

/**
 * ردیف‌های برگه: گره‌های دیدنی، و هر حسابِ تازه **بعد از آخرین فرزندِ دیدنیِ** مادرش (ته همان سرفصل)؛ تازه‌های
 * ریشه ته برگه. تازه‌ای که مادرش پنهان است (جمع‌شده یا فیلترشده) هم دیده می‌شود — بعد از خودِ مادر یا ته برگه —
 * تا حسابِ نیمه‌کاره با بستنِ یک سرفصل گم نشود.
 */
export function sheetRows(nodes: readonly Node[], draft: Draft, byId: ReadonlyMap<string, Node>): SheetRow[] {
  const saved: SheetRow[] = nodes.map((n) => ({ kind: 'saved', key: n.id, node: n, values: valuesOf(n, draft.edits[n.id]) }))
  const out = [...saved]
  const insertAfter = (index: number, row: SheetRow) => out.splice(index + 1, 0, row)
  for (const f of draft.fresh) {
    const parent = f.parentId ? byId.get(f.parentId) : undefined
    const row: SheetRow = {
      kind: 'new',
      key: f.key,
      fresh: f,
      depth: parent ? parent.depth + 1 : 0,
      values: { code: f.code, name: f.name, name2: f.name2, nature: f.nature, is_active: true },
    }
    const at = parent ? out.findIndex((r) => r.key === parent.id) : -1
    if (at < 0) {
      out.push(row)
      continue
    }
    //: ته زیرشاخه‌ی مادر: ردیف‌های بعدی تا جایی که عمقشان بیشتر از مادر است.
    let end = at
    while (end + 1 < out.length && depthOf(out[end + 1]) > parent!.depth) end++
    insertAfter(end, row)
  }
  return out
}

const depthOf = (r: SheetRow) => (r.kind === 'saved' ? r.node.depth : r.depth)

export function valuesOf(a: ChartAccount, edit?: Partial<Values>): Values {
  return {
    code: a.code,
    name: a.name,
    name2: a.name2 ?? '',
    nature: (a.nature ?? '') as Nature,
    is_active: a.is_active,
    ...edit,
  }
}

export interface Patch {
  /** `PATCH /accounts/{id}` — نام، عنوانِ دوم، ماهیت، وضعیت. */
  fields: { name?: string; name2?: string; nature?: string | null; is_active?: boolean } | null
  /** `PATCH /accounts/{id}/code` — جدا، چون سرور تغییرِ کد را جدا می‌سنجد و می‌تواند ردش کند. */
  code: string | null
}

/** آنچه واقعاً عوض شده (متن با trim). `null` یعنی چیزی برای ذخیره نیست. */
export function patchOf(a: ChartAccount, edit: Partial<Values> | undefined): Patch | null {
  if (!edit) return null
  const now = valuesOf(a, edit)
  const was = valuesOf(a)
  const fields: NonNullable<Patch['fields']> = {}
  if (now.name.trim() !== was.name.trim()) fields.name = now.name.trim()
  if (now.name2.trim() !== was.name2.trim()) fields.name2 = now.name2.trim()
  if (now.nature !== was.nature) fields.nature = now.nature || null
  if (now.is_active !== was.is_active) fields.is_active = now.is_active
  const code = now.code.trim() !== was.code.trim() ? now.code.trim() : null
  const hasFields = Object.keys(fields).length > 0
  return hasFields || code ? { fields: hasFields ? fields : null, code } : null
}

/**
 * خطای پیش از ارسال: کد و نام لازم‌اند و کد در کلِ چارت (ثبت‌شده و تازه) یکتاست. قاعده‌ی کدینگ (رقمِ هر سطح) را
 * سرور می‌سنجد و خطایش به همان ردیف برمی‌گردد.
 */
export function problemOf(values: { code: string; name: string }, key: string, codes: ReadonlyMap<string, string>): string | null {
  const code = values.code.trim()
  if (!code && !values.name.trim()) return 'کد و نام را وارد کنید.'
  if (!code) return 'کد را وارد کنید.'
  if (!values.name.trim()) return 'نام را وارد کنید.'
  const owner = codes.get(code)
  if (owner && owner !== key) return `کدِ «${code}» تکراری است.`
  return null
}

/** کدِ هر حساب (ثبت‌شده با ویرایشش، و تازه) → کلیدِ ردیف؛ پایه‌ی سنجشِ تکراری‌بودن. دومین کدِ تکراری برنده نمی‌شود. */
export function codeOwners(accounts: readonly ChartAccount[], draft: Draft): Map<string, string> {
  const out = new Map<string, string>()
  const add = (code: string, key: string) => {
    const c = code.trim()
    if (c && !out.has(c)) out.set(c, key)
  }
  for (const a of accounts) add(draft.edits[a.id]?.code ?? a.code, a.id)
  for (const f of draft.fresh) add(f.code, f.key)
  return out
}

/** شمارشِ تغییرهای ذخیره‌نشده، برای نوارِ پایین. */
export function pendingCount(draft: Draft, accounts: readonly ChartAccount[]): { fresh: number; edited: number } {
  const byId = new Map(accounts.map((a) => [a.id, a]))
  let edited = 0
  for (const [id, e] of Object.entries(draft.edits)) {
    const a = byId.get(id)
    if (a && patchOf(a, e)) edited++
  }
  return { fresh: draft.fresh.length, edited }
}

/** بدنه‌ی `POST /accounts` برای یک حسابِ تازه — نوع از مادر، مگر ریشه. */
export function createBody(f: FreshAccount, parent: ChartAccount | undefined) {
  return {
    code: f.code.trim(),
    name: f.name.trim(),
    name2: f.name2.trim(),
    nature: f.nature || null,
    type: parent?.type ?? f.type,
    is_group: f.isGroup,
    parent_id: parent?.id ?? null,
    ...f.traits,
  }
}

const NATURES: readonly string[] = ['', 'debit', 'credit', 'any']

/** پیش‌نویسِ خوانده‌شده از ذخیره‌ی نشست — هر شکلِ خرابی یعنی «هیچ». */
export function parseDraft(raw: string | null): Draft | null {
  if (!raw) return null
  try {
    const d = JSON.parse(raw) as Draft
    if (!d || typeof d !== 'object' || typeof d.edits !== 'object' || d.edits === null || !Array.isArray(d.fresh)) return null
    const fresh = d.fresh.filter(
      (f): f is FreshAccount =>
        Boolean(f) &&
        typeof f.key === 'string' &&
        (f.parentId === null || typeof f.parentId === 'string') &&
        ['code', 'name', 'name2', 'type'].every((k) => typeof (f as unknown as Record<string, unknown>)[k] === 'string') &&
        NATURES.includes(f.nature) &&
        typeof f.isGroup === 'boolean' &&
        Boolean(f.traits) &&
        typeof f.traits === 'object',
    )
    return { edits: d.edits, fresh }
  } catch {
    return null
  }
}

export const isEmptyDraft = (d: Draft) => Object.keys(d.edits).length === 0 && d.fresh.length === 0

/**
 * کدِ پیشنهادیِ سرور برای حسابِ تازه، اگر آزاد نیست، عددِ بعدیِ آزاد. سرور حساب‌های ذخیره‌نشده را نمی‌بیند؛ دو ردیفِ
 * تازه زیرِ یک سرفصل هر دو «۱۱۰۳» می‌گرفتند. کدِ غیرعددی همان می‌ماند — قاعده‌اش را کاربر می‌داند.
 */
export function nextFreeCode(code: string, owners: ReadonlyMap<string, string>): string {
  if (!/^\d+$/.test(code)) return code
  let n = BigInt(code)
  let out = code
  while (owners.has(out)) {
    n += 1n
    out = n.toString().padStart(code.length, '0')
  }
  return out
}
