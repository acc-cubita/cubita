/**
 * «`display` که سلولِ جدول را از جدول بیرون می‌اندازد» — تجزیه‌ی CSS برای R17.
 *
 * **باگی که این را لازم کرد.** در گریدِ سندِ حسابداری نوشته شده بود
 * `.jg-actions { display: flex }` و آن کلاس روی یک `<td>` بود. طبق مشخصه،
 * عوض‌کردنِ `display`ِ یک عنصرِ درونیِ جدول آن را از الگوریتمِ چیدمانِ جدول
 * بیرون می‌برد: سلول دیگر به عرضِ ستونش گوش نمی‌دهد. اندازه گرفته شد — ستون
 * ۱۲۲px بود و سلول به ۱۷px جمع می‌شد، پس هر سه دکمه بیرون می‌زدند روی کادرِ
 * «بستانکار».
 *
 * **چرا هیچ ابزارِ دیگری نمی‌گیردش.** `tsc` و `oxlint` به CSS نگاه نمی‌کنند،
 * ویت CSS را بی‌اعتراض عبور می‌دهد، و مرورگر هم خطا نمی‌دهد — فقط چیدمان را
 * بی‌صدا عوض می‌کند. حتی تستِ jsdom هم بی‌فایده است چون jsdom چیدمان ندارد.
 * تنها راهِ خودکار، خواندنِ خودِ برگه‌ی سبک است.
 *
 * **دو محدودسازیِ عمدی، تا هشدارِ کاذب ندهد:**
 *
 * ۱. فقط قاعده‌های **سطحِ بالا**. داخلِ `@media` این کار اغلب درست است: در نمای
 *    کارتیِ موبایل خودِ `table`/`tr`/`td` به `block`/`grid` تبدیل شده‌اند و
 *    دیگر جدولی در کار نیست که سلول از آن بیرون بیفتد.
 * ۲. فقط وقتی **فاعلِ** انتخابگر (آخرین بخشش) همان کلاسِ `<td>` باشد.
 *    `td.card-actions .row-actions { display: flex }` درست است و فاعلش
 *    `.row-actions` است، نه سلول — دقیقاً همان رفعی که برای باگ بالا نوشته شد.
 */

const LAYOUT_DISPLAYS = new Set(['flex', 'grid', 'inline-flex', 'inline-grid'])

/** متنِ بیرون از کامنت‌ها و رشته‌ها را حفظ می‌کند و بقیه را با فاصله پر می‌کند. */
function blank(text) {
  let out = ''
  let i = 0
  while (i < text.length) {
    const ch = text[i]
    if (ch === '/' && text[i + 1] === '*') {
      const end = text.indexOf('*/', i + 2)
      const stop = end === -1 ? text.length : end + 2
      out += text.slice(i, stop).replace(/[^\n]/g, ' ')
      i = stop
    } else if (ch === '"' || ch === "'") {
      let j = i + 1
      while (j < text.length && text[j] !== ch) j += text[j] === '\\' ? 2 : 1
      out += ' '.repeat(Math.min(j + 1, text.length) - i)
      i = j + 1
    } else {
      out += ch
      i++
    }
  }
  return out
}

/**
 * کلاس‌هایی که در این فایلِ TSX روی یک `<td>` می‌نشینند.
 *
 * هر رشته‌ی داخلِ تگِ باز شکسته می‌شود، پس `className={x ? 'a' : 'b'}` هر دو را
 * می‌دهد — که درست است، چون هر دو ممکن است روی سلول بنشینند.
 */
export function tdClassesIn(tsx) {
  const found = new Set()
  for (const m of tsx.matchAll(/<td(?=[\s>])/g)) {
    let i = m.index + 3
    let depth = 0
    let quote = null
    let tag = ''
    while (i < tsx.length) {
      const ch = tsx[i]
      tag += ch
      if (quote) {
        if (ch === quote) quote = null
      } else if (ch === '"' || ch === "'" || ch === '`') quote = ch
      else if (ch === '{') depth++
      else if (ch === '}') depth--
      else if (ch === '>' && depth === 0) break
      i++
    }
    for (const s of tag.matchAll(/["'`]([^"'`]*)["'`]/g))
      for (const cls of s[1].split(/\s+/)) if (cls && /^[a-zA-Z_-][\w-]*$/.test(cls)) found.add(cls)
  }
  return found
}

/** فاعلِ یک انتخابگر: آخرین بخشِ آن، پس از فاصله یا `>`/`+`/`~`. */
function subjectOf(selector) {
  const parts = selector.trim().split(/[\s>+~]+/).filter(Boolean)
  return parts[parts.length - 1] ?? ''
}

/** کلاس‌های یک بخشِ انتخابگر (`td.card-actions.x` → `['card-actions','x']`). */
function classesOf(compound) {
  return [...compound.matchAll(/\.([\w-]+)/g)].map((m) => m[1])
}

/**
 * قاعده‌های سطحِ بالایی که `display`ِ چیدمانی را روی یک کلاسِ `<td>` می‌گذارند.
 *
 * هر یافته: `{ line, selector, cls, value }`.
 */
export function tdDisplayFindings(css, tdClasses) {
  const text = blank(css)
  const found = []
  let depth = 0
  let line = 1
  let i = 0
  let headStart = 0

  while (i < text.length) {
    const ch = text[i]
    if (ch === '\n') {
      line++
      i++
    } else if (ch === '{') {
      const head = text.slice(headStart, i).split(/[;{}]/).pop().trim()
      const headLine = line - (head.match(/\n/g)?.length ?? 0)
      if (depth === 0 && head && !head.startsWith('@')) {
        const end = matchingClose(text, i)
        const body = text.slice(i + 1, end)
        const decl = /(?:^|[;{])\s*display\s*:\s*([\w-]+)/.exec(body)
        if (decl && LAYOUT_DISPLAYS.has(decl[1])) {
          for (const sel of head.split(',')) {
            const hit = classesOf(subjectOf(sel)).find((c) => tdClasses.has(c))
            if (hit) {
              found.push({ line: headLine, selector: sel.trim(), cls: hit, value: decl[1] })
              break
            }
          }
        }
      }
      depth++
      i++
      headStart = i
    } else if (ch === '}') {
      depth = Math.max(0, depth - 1)
      i++
      headStart = i
    } else i++
  }
  return found
}

/** ایندکسِ `}`ِ متناظر با `{`ِ داده‌شده؛ نبودش یعنی تا آخرِ متن. */
function matchingClose(text, openIndex) {
  let depth = 0
  for (let i = openIndex; i < text.length; i++) {
    if (text[i] === '{') depth++
    else if (text[i] === '}' && --depth === 0) return i
  }
  return text.length
}
