/**
 * ممیزِ ساختاریِ اپِ موبایل.
 *
 * **چرا لازم شد:** دسکتاپ `audit-pages.mjs` را دارد و همان قاعده‌ها را خودکار
 * می‌سنجد؛ موبایل هیچ‌چیز نداشت. نتیجه‌اش این بود که `isOwner` و `hasPermission`
 * نوشته شدند، هیچ صفحه‌ای صدایشان نزد، و ماه‌ها کسی نفهمید — یعنی اپ برای همه‌ی
 * نقش‌ها یک منو نشان می‌داد در حالی که کدِ نقش‌محوری‌اش «آماده» به‌نظر می‌رسید.
 *
 * پنج قاعده، عمداً کم: چیزی که خطای اشتباه بدهد را همه یاد می‌گیرند نادیده بگیرند.
 *
 * اجرا: node scripts/audit-mobile.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SRC = path.join(ROOT, 'src')
const ENTRY = path.join(ROOT, 'App.tsx')

/**
 * همه‌ی فایل‌های منبع (به‌جز تست‌ها) — **شاملِ App.tsx**.
 *
 * نسخه‌ی اول فقط `src/` را می‌پیمود و App.tsx را نمی‌دید. نتیجه این بود که هرچه
 * *فقط* در App.tsx استفاده می‌شد (AuthProvider، RootNavigator، installGlobalHandler)
 * «استفاده‌نشده» گزارش می‌شد. قاعده‌ای که مثبتِ کاذب بدهد را همه یاد می‌گیرند
 * نادیده بگیرند — که از نداشتنش بدتر است.
 */
function sourceFiles(dir = SRC, out = []) {
  if (dir === SRC && fs.existsSync(ENTRY)) out.push(ENTRY)
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) {
      if (e.name !== '__tests__') sourceFiles(p, out)
    } else if (/\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name) && !e.name.endsWith('.d.ts')) {
      out.push(p)
    }
  }
  return out
}

const read = (f) => fs.readFileSync(f, 'utf8')
const rel = (f) => path.relative(ROOT, f).replace(/\\/g, '/')

/** importهای نسبیِ یک فایل را به مسیرِ واقعی حل می‌کند. */
function resolveImports(file) {
  const dir = path.dirname(file)
  const out = []
  for (const m of read(file).matchAll(/(?:from|import)\s+['"](\.[^'"]+)['"]/g)) {
    const base = path.resolve(dir, m[1])
    for (const cand of [
      base,
      `${base}.ts`,
      `${base}.tsx`,
      path.join(base, 'index.ts'),
      path.join(base, 'index.tsx'),
    ]) {
      if (fs.existsSync(cand) && fs.statSync(cand).isFile()) {
        out.push(cand)
        break
      }
    }
  }
  return out
}

// ── R1: کدِ مرده ────────────────────────────────────────────────────────────
function deadFiles() {
  const seen = new Set()
  const queue = [ENTRY]
  while (queue.length) {
    const f = queue.pop()
    if (seen.has(f)) continue
    seen.add(f)
    queue.push(...resolveImports(f))
  }
  return sourceFiles()
    .filter((f) => !seen.has(f))
    .map((f) => ({ file: rel(f), msg: `${read(f).split('\n').length} خط، از هیچ‌جا import نمی‌شود` }))
}

// ── R2: exportِ استفاده‌نشده ─────────────────────────────────────────────────
function unusedExports() {
  const files = sourceFiles()
  const all = files.map((f) => ({ file: f, text: read(f) }))
  const problems = []
  for (const { file, text } of all) {
    // فایلِ ورودیِ اپ و تایپ‌ها استثنا؛ تایپ‌ها ممکن است فقط در امضا استفاده شوند.
    if (file.endsWith('types.ts')) continue
    for (const m of text.matchAll(/^export (?:const|function|class) (\w+)/gm)) {
      const name = m[1]
      const usedElsewhere = all.some(
        (o) => o.file !== file && new RegExp(`\\b${name}\\b`).test(o.text),
      )
      if (!usedElsewhere) {
        problems.push({ file: rel(file), msg: `«${name}» export شده ولی هیچ فایلِ دیگری استفاده‌اش نمی‌کند` })
      }
    }
  }
  return problems
}

// ── R3: ارقامِ فارسی ────────────────────────────────────────────────────────
function rawNumbers() {
  const problems = []
  for (const f of sourceFiles()) {
    if (!f.includes(`${path.sep}screens${path.sep}`) && !f.includes(`${path.sep}ui${path.sep}`)) continue
    read(f)
      .split('\n')
      .forEach((line, i) => {
        // toLocaleString بدونِ 'fa-IR' یعنی ارقامِ لاتین روی صفحه‌ی فارسی.
        if (/toLocaleString\(\s*\)/.test(line)) {
          problems.push({ file: rel(f), line: i + 1, msg: 'toLocaleString بدونِ fa-IR' })
        }
      })
  }
  return problems
}

// ── R4: ارتفاعِ ثابت روی کادرِ متن ──────────────────────────────────────────
/**
 * `height: <عدد>` روی استایلی که متن دارد.
 *
 * **چرا مهم است:** اندروید اجازه می‌دهد کاربر فونتِ سیستم را تا دو برابر بزرگ کند
 * و کاربرِ این اپ — صاحبِ کسب‌وکارِ میان‌سال — واقعاً این کار را می‌کند. کادری با
 * ارتفاعِ ثابت رشد نمی‌کند، پس متن از پایین بریده می‌شود؛ بدونِ خطا، بدونِ کرش.
 * روی فیلدِ شمارشِ انبارگردانی همین افتاد و عددی که سندِ تعدیلِ حسابداری از آن
 * ساخته می‌شود ناخوانا شد.
 *
 * `minHeight` درست است و علامت نمی‌خورد. کادرِ **مربعیِ** آیکون (`width` برابرِ
 * `height`) هم استثناست: آنجا ارتفاع تزئین است نه ظرفِ متن.
 */
function fixedTextHeights() {
  const problems = []
  for (const f of sourceFiles()) {
    const text = read(f)
    for (const m of text.matchAll(/(\w+):\s*\{([^{}]*)\}/g)) {
      const [, name, body] = m
      const h = body.match(/(?:^|[\s,])height:\s*(\d+)/)
      if (!h) continue
      const w = body.match(/(?:^|[\s,])width:\s*(\d+)/)
      if (w && w[1] === h[1]) continue
      if (!/color:|fontSize|textAlign|fontWeight/.test(body)) continue
      const line = text.slice(0, m.index).split('\n').length
      problems.push({
        file: rel(f),
        line,
        msg: `«${name}» ارتفاعِ ثابتِ ${h[1]} دارد و متن — با فونتِ بزرگِ سیستم بریده می‌شود (minHeight بگذار)`,
      })
    }
  }
  return problems
}

/**
 * R5 — کلاس‌های غیرمجاز در چیدمانِ ویجت.
 *
 * **چرا این قاعده لازم شد:** `RemoteViews` یک layout معمولی نیست. لانچر آن را در
 * پروسه‌ی خودش باد می‌کند و فقط فهرستِ محدودی از کلاس‌ها را می‌پذیرد (آن‌هایی که
 * `@RemoteView` دارند). یک `<View>`ِ ساده به‌عنوان فاصله‌گیر اضافه شد و کلِ ویجت
 * تبدیل شد به کارتِ سفیدِ «Can't load widget».
 *
 * و بدترین بخشش حالتِ شکست است: **نه استثنا، نه کرش، نه ردِ پشته‌ای که به فایل
 * اشاره کند** — فقط یک خطِ `W AppWidgetHostView: Error inflating RemoteViews` در
 * logcat. tsc نمی‌گیردش، jest نمی‌گیردش، بیلد سبز است و APK ساخته می‌شود.
 * تنها راهِ فهمیدنش نگاه‌کردن به صفحه‌ی خانه است.
 */
const REMOTE_VIEWS_ALLOWED = new Set([
  'FrameLayout', 'LinearLayout', 'RelativeLayout', 'GridLayout',
  'AnalogClock', 'Button', 'Chronometer', 'ImageButton', 'ImageView',
  'ProgressBar', 'TextView', 'ViewFlipper', 'ListView', 'GridView',
  'StackView', 'AdapterViewFlipper', 'ViewStub',
])

function widgetLayoutViews() {
  const dir = path.join(ROOT, 'widget/res/layout')
  if (!fs.existsSync(dir)) return []
  const found = []
  for (const name of fs.readdirSync(dir)) {
    if (!name.endsWith('.xml')) continue
    const file = path.join(dir, name)
    const lines = fs.readFileSync(file, 'utf8').split('\n')
    lines.forEach((line, i) => {
      const m = line.match(/^\s*<([A-Za-z][A-Za-z0-9_.]*)/)
      if (!m) return
      const tag = m[1]
      if (tag.startsWith('!') || tag === 'merge' || tag === 'requestFocus') return
      const cls = tag.includes('.') ? tag.split('.').pop() : tag
      if (!REMOTE_VIEWS_ALLOWED.has(cls)) {
        found.push({
          file: path.relative(ROOT, file).replace(/\\/g, '/'),
          line: i + 1,
          msg: `«${tag}» در RemoteViews مجاز نیست — ویجت «Can't load widget» می‌شود`,
        })
      }
    })
  }
  return found
}

const RULES = [
  { id: 'R1', level: 'error', title: 'کدِ مرده', check: deadFiles },
  { id: 'R2', level: 'warn', title: 'exportِ استفاده‌نشده', check: unusedExports },
  { id: 'R3', level: 'error', title: 'ارقامِ فارسی', check: rawNumbers },
  { id: 'R4', level: 'error', title: 'ارتفاعِ ثابتِ کادرِ متن', check: fixedTextHeights },
  { id: 'R5', level: 'error', title: 'کلاسِ غیرمجاز در چیدمانِ ویجت', check: widgetLayoutViews },
]

console.log(`ممیزِ موبایل — ${sourceFiles().length} فایلِ منبع\n`)
let errors = 0
let warnings = 0
for (const rule of RULES) {
  const found = rule.check()
  const tag = found.length === 0 ? 'OK  ' : rule.level === 'error' ? 'ERR ' : 'WARN'
  console.log(`[${tag}] ${rule.id} ${rule.title} — ${found.length}`)
  for (const p of found) {
    console.log(`        ${p.file}${p.line ? `:${p.line}` : ''}  ${p.msg}`)
  }
  if (found.length) (rule.level === 'error' ? (errors += found.length) : (warnings += found.length))
}

console.log(`\nجمع: ${errors} خطا، ${warnings} هشدار`)
process.exit(errors > 0 ? 1 : 0)
