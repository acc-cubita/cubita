/**
 * کلیدهای میان‌برِ کاربر — تعریف، ذخیره، و تشخیصِ برخورد.
 *
 * **چرا `code` و نه `key`:** درسی که با خودِ `Ctrl+K` گرفتیم. `e.key` حرفی است
 * که *چیدمان* تولید می‌کند، پس روی کیبوردِ فارسی `Ctrl+K` می‌شود `Ctrl+ن` و
 * میان‌بر بی‌صدا از کار می‌افتد. `e.code` جای **فیزیکیِ** کلید است و به چیدمان
 * کار ندارد. هر چیزی که این‌جا ذخیره می‌شود با `code` است.
 *
 * **چرا روی دستگاه و نه سرور:** همان الگوی «ظاهر و پوسته» — ترجیحِ شخص است نه
 * قاعده‌ی کسب‌وکار. یعنی میان‌برهای نسخه‌ی وب و نسخه‌ی ویندوز جدا‌اند؛ این
 * تصمیم است، نه فراموشی.
 */

export interface Chord {
  /** `KeyA`، `Digit1`، `F2`، … — جای فیزیکیِ کلید. */
  code: string
  ctrl: boolean
  alt: boolean
  shift: boolean
  meta: boolean
}

/** مقصدِ یک میان‌بر. `section` برای پریدن به تبِ مشخصی از یک صفحه. */
export interface ShortcutTarget {
  page: string
  section?: string
}

/** نگاشتِ ذخیره‌شده: شناسه‌ی ترکیب ← مقصد. */
export type ShortcutMap = Record<string, ShortcutTarget>

const STORAGE_KEY = 'cubita.shortcuts'

/** کلیدهایی که خودشان تغییردهنده‌اند و به‌تنهایی ترکیب نمی‌سازند. */
const MODIFIER_CODES = /^(Control|Alt|Shift|Meta)(Left|Right)$/

/**
 * ترکیب‌هایی که مرورگر برای خودش برمی‌دارد و به صفحه نمی‌دهد.
 *
 * عمداً **جلویشان گرفته نمی‌شود** — در نسخه‌ی دسکتاپ اغلب کار می‌کنند. فقط
 * هشدار داده می‌شود، همان قاعده‌ی «گزارش، نه گارد».
 */
const BROWSER_RESERVED = new Set([
  'ctrl+KeyT', 'ctrl+KeyN', 'ctrl+KeyW', 'ctrl+shift+KeyT', 'ctrl+shift+KeyN',
  'ctrl+shift+KeyW', 'ctrl+Tab', 'ctrl+shift+Tab', 'ctrl+KeyQ', 'meta+KeyQ',
  'meta+KeyW', 'meta+KeyT', 'meta+KeyN', 'ctrl+F4', 'alt+F4',
])

export function chordFromEvent(e: {
  code: string
  ctrlKey: boolean
  altKey: boolean
  shiftKey: boolean
  metaKey: boolean
}): Chord {
  return { code: e.code, ctrl: e.ctrlKey, alt: e.altKey, shift: e.shiftKey, meta: e.metaKey }
}

/**
 * شناسه‌ی متعارفِ یک ترکیب — همان رشته‌ای که ذخیره و مقایسه می‌شود.
 *
 * ترتیبِ تغییردهنده‌ها ثابت است تا `Ctrl+Alt+I` و `Alt+Ctrl+I` یک شناسه بدهند.
 */
export function chordId(chord: Chord): string {
  const parts: string[] = []
  if (chord.ctrl) parts.push('ctrl')
  if (chord.alt) parts.push('alt')
  if (chord.shift) parts.push('shift')
  if (chord.meta) parts.push('meta')
  parts.push(chord.code)
  return parts.join('+')
}

/** نامِ خواندنیِ یک کلیدِ فیزیکی: `KeyI` → `I`، `Digit1` → `1`. */
export function keyLabel(code: string): string {
  if (code.startsWith('Key')) return code.slice(3)
  if (code.startsWith('Digit')) return code.slice(5)
  if (code.startsWith('Numpad')) return `Num ${code.slice(6)}`
  const named: Record<string, string> = {
    Space: 'Space', Enter: 'Enter', Escape: 'Esc', Backquote: '`',
    Minus: '-', Equal: '=', BracketLeft: '[', BracketRight: ']',
    Backslash: '\\', Semicolon: ';', Quote: "'", Comma: ',', Period: '.', Slash: '/',
    ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→',
  }
  return named[code] ?? code
}

/** برچسبِ ترکیب برای نمایش. عمداً لاتین می‌ماند — روی خودِ کیبورد هم همین نوشته است. */
export function chordLabel(chord: Chord): string {
  const parts: string[] = []
  if (chord.ctrl) parts.push('Ctrl')
  if (chord.alt) parts.push('Alt')
  if (chord.shift) parts.push('Shift')
  if (chord.meta) parts.push('Meta')
  parts.push(keyLabel(chord.code))
  return parts.join(' + ')
}

/** همان، از روی شناسه‌ی ذخیره‌شده. */
export function labelFromId(id: string): string {
  const parts = id.split('+')
  const code = parts[parts.length - 1]
  return chordLabel({
    code,
    ctrl: parts.includes('ctrl'),
    alt: parts.includes('alt'),
    shift: parts.includes('shift'),
    meta: parts.includes('meta'),
  })
}

export type ChordProblem = 'modifier-only' | 'needs-modifier' | null

/**
 * آیا این ترکیب به‌دردِ میان‌بر می‌خورد؟
 *
 * `Shift` به‌تنهایی کافی **نیست**: `Shift+A` همان تایپ‌کردنِ حرفِ بزرگ است و
 * میان‌بر‌کردنش یعنی کاربر وسطِ نوشتن به صفحه‌ی دیگری پرتاب شود.
 */
export function chordProblem(chord: Chord): ChordProblem {
  if (MODIFIER_CODES.test(chord.code)) return 'modifier-only'
  const isFunctionKey = /^F\d{1,2}$/.test(chord.code)
  if (!chord.ctrl && !chord.alt && !chord.meta && !isFunctionKey) return 'needs-modifier'
  return null
}

/** آیا مرورگر این ترکیب را برای خودش برمی‌دارد؟ (در دسکتاپ معمولاً کار می‌کند.) */
export function isBrowserReserved(id: string): boolean {
  return BROWSER_RESERVED.has(id)
}

/** مقصدی که همین ترکیب را از قبل گرفته — جز خودِ `exceptPage`. */
export function findConflict(map: ShortcutMap, id: string, exceptKey?: string): string | null {
  const owner = map[id]
  if (!owner) return null
  const ownerKey = targetKey(owner)
  return exceptKey && ownerKey === exceptKey ? null : ownerKey
}

/** کلیدِ یکتای یک مقصد — صفحه، یا صفحه و تب. */
export function targetKey(t: ShortcutTarget): string {
  return t.section ? `${t.page}/${t.section}` : t.page
}

/** ترکیبی که به این مقصد نسبت داده شده، اگر باشد. */
export function idForTarget(map: ShortcutMap, key: string): string | null {
  return Object.keys(map).find((id) => targetKey(map[id]) === key) ?? null
}

/**
 * نسبت‌دادنِ یک ترکیب به یک مقصد.
 *
 * هر مقصد **یک** میان‌بر دارد و هر ترکیب **یک** مقصد؛ پس نسبت‌دادن، ترکیبِ قبلیِ
 * همان مقصد را هم برمی‌دارد. بدونِ این، کاربر با عوض‌کردنِ میان‌بر دو ترکیبِ فعال
 * پیدا می‌کرد و نمی‌فهمید قبلی از کجا می‌آید.
 */
export function assign(map: ShortcutMap, id: string, target: ShortcutTarget): ShortcutMap {
  const key = targetKey(target)
  const next: ShortcutMap = {}
  for (const [k, v] of Object.entries(map)) {
    if (k === id || targetKey(v) === key) continue
    next[k] = v
  }
  next[id] = target
  return next
}

/** برداشتنِ میان‌برِ یک مقصد. */
export function unassign(map: ShortcutMap, key: string): ShortcutMap {
  const next: ShortcutMap = {}
  for (const [k, v] of Object.entries(map)) if (targetKey(v) !== key) next[k] = v
  return next
}

/**
 * آیا رویدادِ صفحه‌کلید باید نادیده گرفته شود؟
 *
 * وقتی کاربر در حالِ نوشتن است، میان‌بر نباید بپرد — `Ctrl+B` وسطِ یک توضیح
 * نباید صفحه را عوض کند.
 */
export function isTypingTarget(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null
  if (!node || !node.tagName) return false
  const tag = node.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || node.isContentEditable === true
}

// ── ذخیره ────────────────────────────────────────────────────────────────────
//
// `localStorage` می‌تواند در پنجره‌ی ناشناس یا با دادهٔ سایتِ بسته **پرتاب کند**،
// نه اینکه فقط خالی برگردد. پس هر خواندن و نوشتنی در try/catch است و نبودنش
// برنامه را نمی‌شکند.

export function loadShortcuts(): ShortcutMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return {}
    const out: ShortcutMap = {}
    for (const [id, v] of Object.entries(parsed as Record<string, unknown>)) {
      //: دادهٔ ذخیره‌شده ممکن است از نسخه‌ی قدیمی‌تر یا دستکاری‌شده باشد.
      if (v && typeof v === 'object' && typeof (v as ShortcutTarget).page === 'string') {
        const t = v as ShortcutTarget
        out[id] = t.section ? { page: t.page, section: t.section } : { page: t.page }
      }
    }
    return out
  } catch {
    return {}
  }
}

export function saveShortcuts(map: ShortcutMap): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
    //: رویدادِ `storage` فقط به تب‌های *دیگر* می‌رسد. بدونِ این، میان‌برِ تازه
    //: در همین تب تا بارِ بعدیِ برنامه کار نمی‌کرد.
    window.dispatchEvent(new Event('cubita:shortcuts-changed'))
    return true
  } catch {
    return false
  }
}
