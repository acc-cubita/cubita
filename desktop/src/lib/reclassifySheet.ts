import { textMatches } from './faText'

/**
 * منطقِ خالصِ برگه‌ی «انتقال حساب به سرفصل دیگر» — درختِ نهایی، نوعِ نهایی و ترتیبِ ارسال.
 *
 * سرور (`reclassify_accounts`) دسته را روی **درختِ نهایی** می‌سنجد: حلقه را آن‌جا می‌گیرد، جابه‌جایی‌ها را از
 * کم‌عمق به پرعمق اجرا می‌کند، و زیرمجموعه‌ی سرفصلِ جابه‌جاشده را هم‌نوعِ آن می‌کند. این‌جا همان حساب پیش
 * از ارسال انجام می‌شود تا برگه **پیش از ذخیره** بگوید نوعِ کدام حساب‌ها عوض می‌شود (دارایی ← بدهی یعنی از
 * ترازنامه‌ی دیگری سر درمی‌آورد) و حلقه همان‌جا قرمز شود، نه بعد از رفت‌وبرگشت با سرور.
 */

export interface Acc {
  id: string
  code: string
  name: string
  type: string
  is_group: boolean
  parent_id: string | null
  system_role: string | null
}

/** شناسه‌ی حساب ← سرفصلِ تازه (`''` = ریشه). فقط چیزی که کاربر انتخاب کرده؛ برابر با فعلی یعنی بی‌تغییر. */
export type Edits = Record<string, string>

export interface ReclassifyItem {
  account_id: string
  parent_id: string | null
  type: string
}

export const TYPE_LABELS: Record<string, string> = {
  asset: 'دارایی',
  liability: 'بدهی',
  equity: 'سرمایه',
  income: 'درآمد',
  expense: 'هزینه',
}

const byCode = (a: Acc, b: Acc) => a.code.localeCompare(b.code, 'en', { numeric: true })

/**
 * ترتیبِ درختی (پیمایشِ عمقی، خواهر-برادرها به ترتیبِ کد) با عمقِ هر حساب — همان چیدمانِ درختواره، تا برگه
 * شکلِ چارت را داشته باشد. حسابِ بی‌والد (یا با والدِ ناپیدا) ریشه است؛ `seen` داده‌ی خرابِ حلقه‌دار را می‌شکند.
 */
export function treeRows(accounts: readonly Acc[]): { acc: Acc; depth: number }[] {
  const ids = new Set(accounts.map((a) => a.id))
  const children = new Map<string | null, Acc[]>()
  for (const a of accounts) {
    const p = a.parent_id && ids.has(a.parent_id) ? a.parent_id : null
    const list = children.get(p)
    if (list) list.push(a)
    else children.set(p, [a])
  }
  for (const list of children.values()) list.sort(byCode)
  const out: { acc: Acc; depth: number }[] = []
  const seen = new Set<string>()
  const walk = (parent: string | null, depth: number) => {
    for (const a of children.get(parent) ?? []) {
      if (seen.has(a.id)) continue
      seen.add(a.id)
      out.push({ acc: a, depth })
      walk(a.id, depth + 1)
    }
  }
  walk(null, 0)
  //: حسابِ درونِ حلقه‌ی خراب از ریشه دیده نمی‌شود — گم نشود.
  for (const a of [...accounts].sort(byCode)) if (!seen.has(a.id)) out.push({ acc: a, depth: 0 })
  return out
}

/** شناسه‌ی همه‌ی زیرمجموعه‌های حساب در درختِ **فعلی** (بی خودش) — سرفصل‌هایی که نباید مقصدش باشند. */
export function descendantsOf(accounts: readonly Acc[], id: string): Set<string> {
  const children = new Map<string, string[]>()
  for (const a of accounts) {
    if (!a.parent_id) continue
    const list = children.get(a.parent_id)
    if (list) list.push(a.id)
    else children.set(a.parent_id, [a.id])
  }
  const out = new Set<string>()
  const stack = [...(children.get(id) ?? [])]
  while (stack.length) {
    const cur = stack.pop()!
    if (out.has(cur) || cur === id) continue
    out.add(cur)
    stack.push(...(children.get(cur) ?? []))
  }
  return out
}

/** سرفصلِ تازه‌ی انتخاب‌شده، یا `undefined` وقتی همان سرفصلِ فعلی است. */
export function pendingParent(acc: Acc, edits: Edits): string | null | undefined {
  if (!(acc.id in edits)) return undefined
  const next = edits[acc.id] || null
  return next === acc.parent_id ? undefined : next
}

export interface Plan {
  /** حساب ← سرفصلِ تازه، فقط آن‌هایی که واقعاً جابه‌جا می‌شوند. */
  moves: Map<string, string | null>
  /** نوعِ نهاییِ هر حساب (همه‌ی حساب‌ها، از جمله نقش‌دارهای پنهان که زیرِ سرفصلِ جابه‌جاشده‌اند). */
  finalType: Map<string, string>
  /** حساب‌هایی که نوعشان عوض می‌شود — جابه‌جاشده یا زیرمجموعه‌ی سرفصلِ جابه‌جاشده. */
  typeChanged: Set<string>
  /** دلیلِ ردشدنِ ردیف پیش از ارسال (حلقه، سرفصلِ ناپیدا، …). */
  problems: Record<string, string>
  /** بدنه‌ی درخواست، به ترتیبِ عمقِ درختِ نهایی — فقط وقتی `problems` خالی است. */
  items: ReclassifyItem[]
}

/**
 * برنامه‌ی ذخیره: کدام حساب کجا می‌رود، نوعِ نهاییِ هر حساب، و ردیف‌هایی که نباید فرستاده شوند.
 *
 * نوعِ نهایی آینه‌ی سرور است: حسابِ جابه‌جاشده نوعِ سرفصلِ مقصد را می‌گیرد (به ریشه: نوعِ خودش می‌ماند)، و
 * هر حسابِ دیگر نوعِ نزدیک‌ترین جدِّ جابه‌جاشده‌اش را در درختِ نهایی — یا اگر چنین جدی ندارد، نوعِ خودش.
 * ارسال به ترتیبِ عمقِ نهایی است و `type` صریح؛ سرورِ تازه ترتیب را خودش هم می‌چیند، ولی سرورِ سازمانیِ
 * قدیمی‌تر با همین ترتیب هم درست کار می‌کند.
 */
export function planReclassify(accounts: readonly Acc[], edits: Edits): Plan {
  const byId = new Map(accounts.map((a) => [a.id, a]))
  const moves = new Map<string, string | null>()
  const problems: Record<string, string> = {}

  for (const id of Object.keys(edits)) {
    const acc = byId.get(id)
    //: پیش‌نویسِ کهنه: حسابی که دیگر نیست بی‌صدا کنار می‌رود.
    if (!acc) continue
    const next = pendingParent(acc, edits)
    if (next === undefined) continue
    moves.set(id, next)
    if (acc.system_role) {
      problems[id] = 'نقشِ سیستمی دارد و ثبتِ خودکار به آن تکیه دارد؛ جابه‌جا نمی‌شود.'
      continue
    }
    if (next === null) continue
    const parent = byId.get(next)
    if (!parent) problems[id] = 'سرفصلِ مقصد دیگر نیست — سرفصلِ دیگری انتخاب کنید.'
    else if (!parent.is_group) problems[id] = `«${parent.name}» سرفصل نیست و زیرمجموعه نمی‌گیرد.`
  }

  const finalParent = (id: string): string | null =>
    moves.has(id) ? moves.get(id)! : (byId.get(id)?.parent_id ?? null)

  //: حلقه روی درختِ نهایی — هر حسابِ جابه‌جاشده‌ای که از بالا رفتن به خودش برسد.
  const depthOf = new Map<string, number>()
  for (const id of moves.keys()) {
    const seen = new Set<string>()
    let cur = finalParent(id)
    let cycle = false
    while (cur !== null) {
      if (cur === id) {
        cycle = true
        break
      }
      if (seen.has(cur)) break
      seen.add(cur)
      cur = finalParent(cur)
    }
    if (cycle) problems[id] ??= `«${byId.get(id)!.name}» زیرِ زیرمجموعه‌ی خودش می‌رود — درخت حلقه می‌شود.`
    else depthOf.set(id, seen.size)
  }

  const finalType = new Map<string, string>()
  const typeChanged = new Set<string>()
  const clean = Object.keys(problems).length === 0
  if (clean && moves.size > 0) {
    const typeOf = (id: string, guard = new Set<string>()): string => {
      const known = finalType.get(id)
      if (known) return known
      const acc = byId.get(id)!
      if (guard.has(id)) return acc.type
      guard.add(id)
      let t = acc.type
      if (moves.has(id)) {
        const p = moves.get(id)!
        if (p !== null) t = typeOf(p, guard)
      } else {
        const seen = new Set<string>()
        let cur = finalParent(id)
        while (cur !== null && !moves.has(cur) && !seen.has(cur) && byId.has(cur)) {
          seen.add(cur)
          cur = finalParent(cur)
        }
        if (cur !== null && moves.has(cur)) t = typeOf(cur, guard)
      }
      finalType.set(id, t)
      return t
    }
    for (const a of accounts) if (typeOf(a.id) !== a.type) typeChanged.add(a.id)
  }

  const items: ReclassifyItem[] = clean
    ? [...moves.entries()]
        .map(([id, parent_id]) => ({ id, parent_id, depth: depthOf.get(id) ?? 0 }))
        .sort((a, b) => a.depth - b.depth || byCode(byId.get(a.id)!, byId.get(b.id)!))
        .map(({ id, parent_id }) => ({ account_id: id, parent_id, type: finalType.get(id) ?? byId.get(id)!.type }))
    : []

  return { moves, finalType, typeChanged, problems, items }
}

/** پیش‌نویسِ `sessionStorage`؛ هر چیزِ خراب یعنی «هیچ». */
export function parseDraft(raw: string | null): Edits | null {
  if (!raw) return null
  try {
    const v: unknown = JSON.parse(raw)
    if (!v || typeof v !== 'object' || Array.isArray(v)) return null
    const out: Edits = {}
    for (const [k, p] of Object.entries(v)) {
      if (typeof p !== 'string') return null
      out[k] = p
    }
    return out
  } catch {
    return null
  }
}

/** جست‌وجوی برگه: کد، نام، یا نامِ سرفصلِ فعلی (تا «همه‌ی زیرِ بانک‌ها» هم پیدا شود). */
export function matches(acc: Acc, parentName: string, query: string): boolean {
  if (!query.trim()) return true
  return acc.code.includes(query.trim()) || textMatches(acc.name, query) || textMatches(parentName, query)
}

/**
 * ردیفِ خطای سرور: سرور نامِ حساب را در «» می‌آورد («نوعِ «X» با …»). اولین حسابِ جابه‌جاشده‌ای که نامش
 * آن‌جاست؛ نبود = خطای کلیِ دسته.
 */
export function errorAccountId(message: string, moved: readonly Acc[]): string | null {
  const names = [...message.matchAll(/«([^»]+)»/g)].map((m) => m[1])
  for (const n of names) {
    const hit = moved.find((a) => a.name === n)
    if (hit) return hit.id
  }
  return null
}
