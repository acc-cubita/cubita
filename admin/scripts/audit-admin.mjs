/**
 * ممیزِ ساختاریِ اپِ ستاد.
 *
 * چرا نسخه‌ی خودش و نه `desktop/scripts/audit-pages.mjs`: آن اسکریپت مسیرِ
 * `desktop/src` را سیم‌کشی کرده و چهار قاعده‌اش (R11/R12/R13/R14) روی
 * `NAV_GROUPS` و `OPS_LIST_MAP` کار می‌کنند — مفاهیمی که اینجا وجود ندارند.
 * الگو: `mobile/scripts/audit-mobile.mjs`.
 *
 * قاعده‌هایی که منتقل شدند، چون به مدلِ ناوبری ربطی ندارند و واقعاً اینجا هم
 * می‌شکنند: قراردادِ جدولِ موبایل، ارقامِ فارسی، سقفِ صفحه‌بندی، توازنِ CSS.
 *
 * اجرا: `node scripts/audit-admin.mjs` — خروجِ ناصفر یعنی قاعده‌ای شکسته.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SRC = path.join(ROOT, 'src')

const errors = []
const warnings = []
const err = (file, rule, msg) => errors.push(`${rule} ${path.relative(ROOT, file)}: ${msg}`)
const warn = (file, rule, msg) => warnings.push(`${rule} ${path.relative(ROOT, file)}: ${msg}`)

function walk(dir, ext) {
  const out = []
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name)
    if (statSync(full).isDirectory()) out.push(...walk(full, ext))
    else if (full.endsWith(ext)) out.push(full)
  }
  return out
}

const tsx = walk(SRC, '.tsx')
const ts = [...tsx, ...walk(SRC, '.ts')]
const css = walk(SRC, '.css')

// ── A1: هر <table> باید نمای کارتی داشته باشد ───────────────────────────────
// زیرِ ۷۶۰px جدولِ بی‌کلاس یا صفحه را پهن می‌کند یا ناخوانا می‌شود.
for (const file of tsx) {
  const src = readFileSync(file, 'utf8')
  for (const m of src.matchAll(/<table\b([^>]*)>/g)) {
    const attrs = m[1]
    if (!attrs.includes('cards-on-mobile') && !attrs.includes('table-plain')) {
      err(file, 'A1', 'جدول بدونِ cards-on-mobile (یا table-plain برای استثنای عمدی)')
    }
  }
}

// ── A2: هر <td> برچسب می‌خواهد ──────────────────────────────────────────────
// در نمای کارتی سرستون‌ها ناپدید می‌شوند؛ سلولِ بی‌برچسب یک عددِ بی‌عنوان است.
const TD_EXEMPT = ['card-title', 'card-actions', 'card-hide', 'colSpan']
for (const file of tsx) {
  const src = readFileSync(file, 'utf8')
  for (const m of src.matchAll(/<td\b([^>]*)>/g)) {
    const attrs = m[1]
    if (attrs.includes('data-label')) continue
    if (TD_EXEMPT.some((k) => attrs.includes(k))) continue
    err(file, 'A2', 'سلولِ <td> بدونِ data-label')
  }
}

// ── A3: جدول باید داخلِ ظرفِ لغزش باشد ──────────────────────────────────────
for (const file of tsx) {
  const src = readFileSync(file, 'utf8')
  const tables = (src.match(/<table\b/g) ?? []).length
  const scrolls = (src.match(/<TableScroll\b/g) ?? []).length
  if (tables > scrolls) {
    err(file, 'A3', `${tables} جدول ولی ${scrolls} <TableScroll> — جدولِ بی‌ظرف صفحه را پهن می‌کند`)
  }
}

// ── A4: ارقامِ فارسی ────────────────────────────────────────────────────────
// `toLocaleString()` بدونِ زبان روی ویندوزِ انگلیسی رقمِ لاتین می‌دهد.
for (const file of ts) {
  const src = readFileSync(file, 'utf8')
  for (const m of src.matchAll(/toLocaleString\(\s*([^)'"]|$)/g)) {
    if (!m[0].includes("'fa-IR'")) err(file, 'A4', "toLocaleString() بدونِ 'fa-IR'")
  }
  if (/toLocaleDateString\(/.test(src)) {
    err(file, 'A4', 'toLocaleDateString — تاریخ باید جلالی باشد (formatJalali)')
  }
}

// ── A5: سقفِ صفحه‌بندیِ سرور ────────────────────────────────────────────────
// `limit` بزرگ‌تر از MAX_LIMIT پاسخِ ۴۲۲ می‌گیرد و صفحه بی‌صدا خالی می‌شود.
for (const file of ts) {
  const src = readFileSync(file, 'utf8')
  for (const m of src.matchAll(/limit[=:]\s*(\d+)/g)) {
    if (Number(m[1]) > 200) err(file, 'A5', `limit=${m[1]} بیش از سقفِ ۲۰۰ سرور`)
  }
}

// ── A6: placeholderِ فارسی روی فیلدِ dir="ltr" ──────────────────────────────
// «۱۳ رقم — اختیاری» آنجا وارونه خوانده می‌شود؛ راهنما زیرِ فیلد می‌رود.
for (const file of tsx) {
  const src = readFileSync(file, 'utf8')
  for (const m of src.matchAll(/<input\b[^>]*>/g)) {
    const tag = m[0]
    if (tag.includes('dir="ltr"') && /placeholder="[^"]*[؀-ۿ]/.test(tag)) {
      err(file, 'A6', 'placeholderِ فارسی روی فیلدِ dir="ltr" — راهنما را زیرِ فیلد بگذارید')
    }
  }
}

// ── A7: توازنِ آکولادِ CSS ──────────────────────────────────────────────────
for (const file of css) {
  const src = readFileSync(file, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  const open = (src.match(/\{/g) ?? []).length
  const close = (src.match(/\}/g) ?? []).length
  if (open !== close) err(file, 'A7', `توازنِ آکولاد به هم خورده (${open} باز، ${close} بسته)`)
}

// ── A8: کدِ مرده ────────────────────────────────────────────────────────────
// فایلی که از main.tsx قابلِ دسترس نیست یا یادش رفته وصل شود یا باید حذف شود.
const reachable = new Set()
function reach(file) {
  if (reachable.has(file)) return
  reachable.add(file)
  let src
  try {
    src = readFileSync(file, 'utf8')
  } catch {
    return
  }
  for (const m of src.matchAll(/from\s+['"](\.[^'"]+)['"]/g)) {
    const base = path.resolve(path.dirname(file), m[1])
    for (const cand of [base, `${base}.ts`, `${base}.tsx`, path.join(base, 'index.ts')]) {
      try {
        if (statSync(cand).isFile()) {
          reach(cand)
          break
        }
      } catch {
        /* نامزدِ بعدی */
      }
    }
  }
  for (const m of src.matchAll(/import\s+['"](\.[^'"]+\.css)['"]/g)) {
    reachable.add(path.resolve(path.dirname(file), m[1]))
  }
}
reach(path.join(SRC, 'main.tsx'))

for (const file of [...ts, ...css]) {
  if (file.endsWith('.test.ts')) continue
  if (!reachable.has(file)) warn(file, 'A8', 'از main.tsx قابلِ دسترس نیست — کدِ مرده؟')
}

// ── A9: هر صفحه‌ی منو باید مسیرداشته باشد ───────────────────────────────────
// منویی که به هیچ کامپوننتی وصل نیست، کلیکِ بی‌اثر است.
{
  const nav = readFileSync(path.join(SRC, 'nav.tsx'), 'utf8')
  const app = readFileSync(path.join(SRC, 'App.tsx'), 'utf8')
  const keys = [...nav.matchAll(/key:\s*'([a-z]+)'/g)].map((m) => m[1])
  for (const key of keys) {
    if (!app.includes(`'${key}'`)) {
      err(path.join(SRC, 'App.tsx'), 'A9', `کلیدِ منویِ «${key}» در App.tsx مسیر ندارد`)
    }
  }
  const titles = [...nav.matchAll(/^\s{2}([a-z]+):\s*'/gm)].map((m) => m[1])
  for (const key of keys) {
    if (!titles.includes(key)) {
      err(path.join(SRC, 'nav.tsx'), 'A9', `«${key}» در PAGE_TITLES نیست`)
    }
  }
}

// ── گزارش ──────────────────────────────────────────────────────────────────
for (const w of warnings) console.warn(`⚠ ${w}`)
for (const e of errors) console.error(`✖ ${e}`)

console.log(
  `\nممیزِ ستاد: ${tsx.length} فایلِ TSX، ${css.length} فایلِ CSS — ` +
    `${errors.length} خطا، ${warnings.length} هشدار.`,
)
process.exit(errors.length ? 1 : 0)
