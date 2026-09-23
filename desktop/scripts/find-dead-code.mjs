/**
 * کدِ مرده در `src/`: فایلی که هیچ‌کس importش نمی‌کند، و نامِ صادرشده‌ای که
 * هیچ‌جا مصرف نمی‌شود.
 *
 * **چرا اسکریپت و نه چشم:** یک فایلِ ۱۳۰خطی که هیچ ارجاعی ندارد از بازبینی رد
 * می‌شود — همان‌طور که `JournalDaybookPanel` سه بار رد شد. `tsc` هم نمی‌گیردش،
 * چون فایلِ بی‌مصرف خطا نیست.
 *
 * روش: گرافِ importها از `main.tsx` پیمایش می‌شود؛ هر چه نرسیدیم مرده است.
 * نام‌های صادرشده جدا شمرده می‌شوند (فایلِ زنده با صادراتِ بی‌مصرف).
 *
 * `.d.ts` مستثناست: اعلانِ محیطی از راهِ `include` در tsconfig وارد می‌شود، نه با
 * import — پس «بی‌ارجاع» بودنش طبیعی است، نه مرگ.
 *
 * اجرا:  node scripts/find-dead-code.mjs [--exports]
 * از ممیزِ صفحه‌ها هم به‌عنوانِ قاعده‌ی R12 فراخوانی می‌شود.
 */
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const SRC = path.join(process.cwd(), 'src')
const ROOTS = ['main.tsx']
//: نقاطِ ورودیِ بیرون از گرافِ React — الکترون و اسکریپت‌ها اینها را جدا می‌خوانند.
const EXTRA_ROOTS = ['electron.d.ts', 'vite-env.d.ts']

const files = []
;(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) walk(p)
    else if (/\.(ts|tsx)$/.test(e.name)) files.push(p)
  }
})(SRC)

const rel = (p) => path.relative(SRC, p).replace(/\\/g, '/')

/** مسیرِ importِ نسبی → فایلِ واقعی روی دیسک. */
function resolve(fromFile, spec) {
  if (!spec.startsWith('.')) return null
  const base = path.resolve(path.dirname(fromFile), spec)
  for (const c of [
    base,
    base + '.ts',
    base + '.tsx',
    path.join(base, 'index.ts'),
    path.join(base, 'index.tsx'),
  ]) {
    if (fs.existsSync(c) && fs.statSync(c).isFile()) return c
  }
  return null
}

const IMPORT_RE = /(?:^|\n)\s*(?:import|export)\s[^;]*?from\s*['"]([^'"]+)['"]/g
const BARE_IMPORT_RE = /(?:^|\n)\s*import\s*['"]([^'"]+)['"]/g
const DYNAMIC_RE = /import\(\s*['"]([^'"]+)['"]\s*\)/g

const graph = new Map()
for (const f of files) {
  const text = fs.readFileSync(f, 'utf8')
  const out = new Set()
  for (const re of [IMPORT_RE, BARE_IMPORT_RE, DYNAMIC_RE]) {
    re.lastIndex = 0
    for (const m of text.matchAll(re)) {
      const target = resolve(f, m[1])
      if (target) out.add(target)
    }
  }
  graph.set(f, out)
}

// ── ۱) فایل‌هایی که از ریشه‌ها دیده نمی‌شوند ──────────────────────────────
const reached = new Set()
const queue = [...ROOTS, ...EXTRA_ROOTS]
  .map((r) => path.join(SRC, r))
  .filter((p) => fs.existsSync(p))
while (queue.length) {
  const f = queue.pop()
  if (reached.has(f)) continue
  reached.add(f)
  for (const dep of graph.get(f) ?? []) queue.push(dep)
}

//: `.test.ts` هم مثلِ `.d.ts` نقطه‌ی ورودِ خودش است — vitest مستقیم اجرایش
//: می‌کند و هیچ فایلی importش نمی‌کند. بدونِ این استثنا، هر تستِ تازه یک
//: «کدِ مرده»ی کاذب می‌سازد و قاعده را بی‌اعتبار می‌کند.
//:
//: `src/test/` به همان دلیل: پشتیبانِ مشترکِ چند تست است (پیش‌نویسِ آزمایشیِ
//: گرید) و فقط از فایل‌های `.test` خوانده می‌شود. عمداً فقط همین پوشه، نه «هر
//: فایلی که تستی آن را می‌خواند» — ماژولِ برنامه‌ای که دیگر فقط تست مصرفش می‌کند
//: همچنان باید مرده گزارش شود.
const TEST_SUPPORT = path.join(SRC, 'test') + path.sep
const orphans = files.filter(
  (f) => !reached.has(f) && !f.endsWith('.d.ts') && !/\.test\.tsx?$/.test(f) && !f.startsWith(TEST_SUPPORT),
)

// ── ۲) نام‌های صادرشده‌ی بی‌مصرف در فایل‌های زنده ─────────────────────────
const EXPORT_NAME_RE =
  /^export\s+(?:async\s+)?(?:function|const|let|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/gm
const allText = new Map(files.map((f) => [f, fs.readFileSync(f, 'utf8')]))

const unusedExports = []
for (const f of files) {
  if (orphans.includes(f)) continue // فایلِ مرده کلاً گزارش شده
  const text = allText.get(f)
  for (const m of text.matchAll(EXPORT_NAME_RE)) {
    const name = m[1]
    let used = false
    for (const [other, otherText] of allText) {
      if (other === f) continue
      if (new RegExp(`\\b${name}\\b`).test(otherText)) {
        used = true
        break
      }
    }
    if (!used) {
      // مصرفِ درون‌فایلی هم حساب است: چیزی که خودش استفاده می‌شود مرده نیست،
      // فقط `export`ش زیادی است.
      const selfUses = (text.match(new RegExp(`\\b${name}\\b`, 'g')) ?? []).length
      unusedExports.push({ file: rel(f), name, selfUses })
    }
  }
}

const countLines = (text) => text.split(/\r?\n/).length

/** فهرستِ فایل‌های بی‌ارجاع — ممیزِ صفحه‌ها (قاعده‌ی R12) از این می‌خواند. */
export function deadFiles() {
  return orphans.map((f) => ({ file: rel(f), lines: countLines(allText.get(f)) }))
}

/** صادراتی که هیچ فایلِ دیگری مصرفش نمی‌کند (فایلِ زنده، صادراتِ زیادی). */
export function unusedExportNames() {
  return unusedExports.filter((u) => u.selfUses <= 1)
}

// ── گزارش (فقط وقتی مستقیم اجرا شود، نه وقتی ممیز importش می‌کند) ─────────
if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  console.log(`
فایل‌های بررسی‌شده: ${files.length}   رسیده از ریشه: ${reached.size}
`)

  if (orphans.length === 0) console.log('[OK  ] فایلِ بی‌ارجاع: ۰')
  else {
    console.log(`[DEAD] فایلِ بی‌ارجاع: ${orphans.length}`)
    for (const d of deadFiles()) console.log(`        ${d.file}  (${d.lines} خط)`)
  }

  if (process.argv.includes('--exports')) {
    const real = unusedExportNames()
    console.log(`
[INFO] صادراتِ بی‌مصرف در فایل‌های زنده: ${real.length}`)
    for (const u of real) console.log(`        ${u.file}  →  ${u.name}`)
  }

  console.log('')
  process.exit(orphans.length ? 1 : 0)
}
