#!/usr/bin/env node
/**
 * ممیزِ ایستای صفحه‌ها — «آیا این صفحه قراردادِ طراحیِ کوبیتا را رعایت می‌کند؟»
 *
 * چرا اسکریپت و نه بازبینیِ چشمی: قراردادِ صفحه‌ها ده‌ها قاعده‌ی ریز دارد
 * (پوسته‌ی کارتی، سرصفحه، جدولِ کارت‌شونده در موبایل، سقفِ صفحه‌بندی…) و ۸۰+ صفحه.
 * چشم این را یکدست نگه نمی‌دارد؛ یک ممیزِ قابلِ اجرا نگه می‌دارد. هر قاعده اینجا از
 * یک خرابیِ واقعی آمده، نه از سلیقه — توضیحش کنارِ خودش است.
 *
 *   node scripts/audit-pages.mjs            # گزارشِ کامل
 *   node scripts/audit-pages.mjs --json     # خروجیِ ماشین‌خوان
 *   node scripts/audit-pages.mjs --rule R3  # فقط یک قاعده
 *
 * خروجِ ناصفر یعنی دستِ‌کم یک خطا (error) هست. هشدارها (warn) خروج را نمی‌شکنند.
 */
import fs from 'node:fs'
import path from 'node:path'
import { navTargets } from './lib/navTargets.mjs'
import { deadFiles } from './find-dead-code.mjs'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SRC = path.join(ROOT, 'src')

const args = process.argv.slice(2)
const asJson = args.includes('--json')
const ruleFlag = args.findIndex((a) => a === '--rule' || a.startsWith('--rule='))
const onlyRule =
  ruleFlag === -1 ? null : args[ruleFlag].includes('=') ? args[ruleFlag].split('=')[1] : args[ruleFlag + 1]

// ── جمع‌آوریِ فایل‌ها ────────────────────────────────────────────────────────

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full, out)
    else if (entry.name.endsWith('.tsx')) out.push(full)
  }
  return out
}

const rel = (f) => path.relative(ROOT, f).replace(/\\/g, '/')

/** فایل‌هایی که «صفحه» به حساب می‌آیند: هرچه در pages/ است، به‌علاوه‌ی پنل‌های
 *  سطح‌بالای components/ که خودشان یک صفحه‌ی کامل رندر می‌کنند. */
const pageFiles = walk(path.join(SRC, 'pages'))
const componentFiles = walk(path.join(SRC, 'components'))

// ── قاعده‌ها ────────────────────────────────────────────────────────────────
//
// هر قاعده: { id, level, title, why, check(file) → [پیام‌ها] }

const lines = (text) => text.split(/\r?\n/)

/** شماره‌ی خطِ یک ایندکسِ کاراکتری. */
const lineOf = (text, index) => text.slice(0, index).split(/\r?\n/).length

const RULES = [
  {
    id: 'R1',
    level: 'error',
    title: 'پوسته‌ی کارتیِ صفحه',
    why:
      'هر صفحه باید ریشه‌اش `<div className="page panels">` باشد یا از `OpsPage` بیاید. ' +
      'بدونِ آن محتوا روی پس‌زمینه‌ی برنامه شناور می‌ماند و کارتِ سفید زیرش نیست.',
    scope: 'pages',
    check(text) {
      if (!/export function [A-Z]/.test(text)) return []
      const found = []
      // هر کامپوننتِ صادرشده‌ای که «Page» در نامش دارد باید یکی از دو الگو را داشته باشد.
      const re = /export function ([A-Z][A-Za-z0-9]*Page)\b/g
      let m
      while ((m = re.exec(text))) {
        const name = m[1]
        const body = text.slice(m.index, nextExportIndex(text, m.index))
        // استثنای عمدی: داشبورد بومِ ویجت است نه صفحه‌ی کارتی، پس پوسته‌ی خودش را دارد.
        const ok =
          /className="page panels"/.test(body) ||
          /<OpsPage\b/.test(body) ||
          /className="page dash"|guided-dash/.test(body) ||
          /<[A-Z][A-Za-z0-9]*Page\b/.test(body)
        if (!ok) found.push({ line: lineOf(text, m.index), msg: `${name}: نه \`page panels\` دارد نه \`OpsPage\`` })
      }
      return found
    },
  },
  {
    id: 'R2',
    level: 'error',
    title: 'جدولِ کارت‌شونده در موبایل',
    why:
      'هر `<table>` باید کلاسِ `cards-on-mobile` بگیرد. بدونِ آن جدول روی نمایشگرِ ' +
      'باریک افقی می‌لغزد و ستون‌ها بریده می‌شوند.',
    check(text) {
      const found = []
      const re = /<table\b([^>]*)>/g
      let m
      while ((m = re.exec(text))) {
        if (!/cards-on-mobile|table-plain/.test(m[1])) {
          found.push({ line: lineOf(text, m.index), msg: 'جدول بدونِ `cards-on-mobile`' })
        }
      }
      return found
    },
  },
  {
    id: 'R3',
    level: 'error',
    title: 'برچسبِ سلول برای نمای کارتی',
    why:
      'در نمای کارتیِ موبایل، سرستون‌ها ناپدید می‌شوند و هر سلول با `data-label` خودش ' +
      'شناخته می‌شود. سلولِ بدونِ برچسب در موبایل یک مقدارِ بی‌عنوان است.',
    check(text) {
      const found = []
      const re = /<td\b/g
      let m
      while ((m = re.exec(text))) {
        const close = tagEnd(text, m.index)
        if (close === -1) break
        const attrs = text.slice(m.index + 3, close)
        re.lastIndex = close
        // جدولی که عمداً «ساده» است (رسیدِ چاپی، ماتریسِ مجوز) کارتی نمی‌شود.
        if (inPlainTable(text, m.index)) continue
        // سلولِ کنش/خالی برچسب نمی‌خواهد.
        if (/data-label/.test(attrs)) continue
        // قراردادِ نمای کارتی (App.css): سرِ کارت و سلولِ پنهان برچسب نمی‌گیرند،
        // و سلولِ دکمه/تیک هم عنوانِ ستون ندارد.
        if (/card-actions|card-title|card-hide|acc-row-actions|mdn-check-col/.test(attrs)) continue
        // سلولی که کلِ عرضِ جدول را می‌گیرد (ردیفِ بازشونده) ستونِ خودش را ندارد.
        if (/colSpan/.test(attrs)) continue
        // HTMLِ رشته‌ایِ پنجره‌ی چاپ (داخلِ template literal) جدولِ React نیست.
        if (lineTextAt(text, m.index).includes('`')) continue
        const after = text.slice(m.index, m.index + 400)
        if (/^<td[^>]*\/>/.test(after) || /^<td[^>]*><\/td>/.test(after)) continue
        found.push({ line: lineOf(text, m.index), msg: 'سلولِ جدول بدونِ `data-label`' })
      }
      return found
    },
  },
  {
    id: 'R4',
    level: 'warn',
    title: 'ظرفِ لغزشِ جدول',
    why:
      'جدولِ پهن باید داخلِ `.table-scroll` بنشیند تا خودش بلغزد، نه اینکه کلِ صفحه ' +
      'را پهن‌تر از نمایشگر کند.',
    check(text) {
      const found = []
      const re = /<table([^>]*)>/g
      let m
      while ((m = re.exec(text))) {
        if (/table-plain/.test(m[1])) continue
        const before = text.slice(Math.max(0, m.index - 600), m.index)
        if (!/table-scroll/.test(before)) {
          found.push({ line: lineOf(text, m.index), msg: 'جدول بیرون از `.table-scroll`' })
        }
      }
      return found
    },
  },
  {
    id: 'R5',
    level: 'error',
    title: 'سقفِ صفحه‌بندیِ سرور',
    why:
      'سرور در هر درخواست حداکثر ۲۰۰ ردیف می‌دهد (`MAX_LIMIT`) و عددِ بزرگ‌تر ۴۲۲ ' +
      'برمی‌گرداند — یعنی صفحه بی‌صدا خالی می‌شود. برای بیش از ۲۰۰ ردیف باید با کرسر صفحه گرفت.',
    check(text) {
      const found = []
      const re = /limit:\s*(\d+)/g
      let m
      while ((m = re.exec(text))) {
        if (Number(m[1]) > 200 && !/fetchJournalEntriesFiltered/.test(text.slice(Math.max(0, m.index - 300), m.index)))
          found.push({ line: lineOf(text, m.index), msg: `limit=${m[1]} از سقفِ ۲۰۰ سرور بیشتر است` })
      }
      return found
    },
  },
  {
    id: 'R6',
    level: 'error',
    title: 'متنِ فارسی داخلِ فیلدِ LTR',
    why:
      'فیلدی که `dir="ltr"` دارد متنِ فارسیِ placeholder را وارونه نشان می‌دهد ' +
      '(«۱۳ رقم — اختیاری» می‌شود «رقم — اختیاری ۱۳»). راهنما را زیرِ فیلد بگذارید.',
    check(text) {
      const found = []
      const re = /<(input|textarea)\b[^>]*>/gs
      let m
      while ((m = re.exec(text))) {
        const tag = m[0]
        if (!/dir="ltr"/.test(tag)) continue
        const ph = /placeholder=(?:"([^"]*)"|\{`([^`]*)`\})/.exec(tag)
        const value = ph?.[1] ?? ph?.[2] ?? ''
        if (/[؀-ۿ]/.test(value)) {
          found.push({ line: lineOf(text, m.index), msg: 'placeholderِ فارسی روی فیلدِ `dir="ltr"`' })
        }
      }
      return found
    },
  },
  {
    id: 'R7',
    level: 'warn',
    title: 'ارقامِ فارسی',
    why:
      'همه‌ی اعداد باید با `toLocaleString(\'fa-IR\')` یا کمکی‌های `lib/jalali` فارسی شوند. ' +
      '`toLocaleString()` بدونِ زبان به زبانِ سیستم می‌افتد و روی ویندوزِ انگلیسی رقمِ لاتین می‌دهد.',
    check(text) {
      const found = []
      const re = /toLocaleString\(\s*\)/g
      let m
      while ((m = re.exec(text))) found.push({ line: lineOf(text, m.index), msg: '`toLocaleString()` بدونِ زبان' })
      return found
    },
  },
  {
    id: 'R8',
    level: 'warn',
    title: 'تاریخِ شمسی',
    why:
      'تاریخ باید با `formatJalali` نشان داده شود. `toLocaleDateString` یا برش‌زدنِ ' +
      'رشته‌ی ISO تاریخِ میلادی می‌دهد که کاربرِ ایرانی نمی‌خواند.',
    check(text) {
      const found = []
      const re = /toLocaleDateString\(/g
      let m
      while ((m = re.exec(text))) found.push({ line: lineOf(text, m.index), msg: '`toLocaleDateString` به‌جای `formatJalali`' })
      return found
    },
  },
  {
    id: 'R9',
    level: 'warn',
    title: 'حالتِ خالی',
    why:
      'فهرستِ خالی باید `EmptyState` (یا `AsyncBlock` با `empty`) نشان دهد، نه یک جدولِ ' +
      'بی‌ردیف که کاربر نمی‌داند خالی است یا هنوز بارگذاری نشده.',
    check(text, file) {
      if (!/<table\b/.test(text)) return []
      // جدولِ ردیف‌های یک فرم (اقلامِ فاکتور، ردیف‌های سند) همیشه دستِ‌کم یک ردیف
      // جدولِ چاپی/ماتریسی حالتِ خالی ندارد.
      if (/table-plain/.test(text)) return []
      // دارد و به‌جای «خالی است» دکمه‌ی «افزودن ردیف» می‌گیرد — قاعده شاملش نیست.
      if (/افزودن ردیف|افزودن قلم|addLine|addRow|setLines\(/.test(text)) return []
      // جدولی که **ساختاراً** نمی‌تواند خالی باشد (ردیف‌های یک سندِ دوطرفه، پلکانِ
      // فرم با دکمه‌ی افزودن). نشانه‌ی `audit-r9-exempt` صریح است و کنارش باید
      // دلیل نوشته شود — همان الگوی `table-plain`: تصمیم، نه فراموشی.
      if (/audit-r9-exempt/.test(text)) return []
      if (/EmptyState|AsyncBlock|mod-list-empty/.test(text)) return []
      // گاردِ دستی — الگویی که بیشترِ کدِ موجود واقعاً استفاده می‌کند:
      // `list.length === 0 ? <p className="muted">…` یا `if (…length === 0) {`
      // یا `list.length > 0 && <table…`. قاعده تا امروز فقط سه کامپوننت را
      // می‌شناخت، پس سیزده فایلی که **از قبل** حالتِ خالی داشتند هشدار
      // می‌گرفتند — و هشدارِ کاذب باعث می‌شود کلِ قاعده نادیده گرفته شود.
      //
      // عمداً فقط شکل‌هایی که **رندر را گیت می‌کنند** پذیرفته می‌شوند؛
      // `if (x.length === 0) setX(...)` (بارگذاریِ تنبل) شامل نمی‌شود.
      if (/\.length === 0\s*\?|\.length === 0\)\s*(return|\{)|\.length > 0\s*&&|\.length \? /.test(text)) return []
      return [{ line: 1, msg: `${path.basename(file)}: جدول دارد ولی حالتِ خالی ندارد` }]
    },
  },
  {
    id: 'R10',
    level: 'warn',
    title: 'سرصفحه‌ی صفحه',
    why:
      'هر صفحه باید `PageHeader` داشته باشد (یا از `OpsPage` بگیرد): عنوان و یک‌خط ' +
      'توضیحِ «این صفحه برای چیست». در پوسته‌ی «راهنما» پنهان می‌شود ولی در بقیه‌ی پوسته‌ها دیده می‌شود.',
    scope: 'pages',
    check(text) {
      if (!/export function [A-Z][A-Za-z0-9]*Page\b/.test(text)) return []
      // داشبورد سرصفحه‌ی خودش را دارد (`page-welcome`)، نه PageHeader.
      if (/<PageHeader\b|<OpsPage\b|page-welcome/.test(text)) return []
      return [{ line: 1, msg: 'فایلِ صفحه بدونِ `PageHeader`/`OpsPage`' }]
    },
  },
  {
    id: 'R11',
    level: 'error',
    title: 'فهرستِ نظیرِ عملیات',
    why:
      'قاعده‌ی نظیر: هر منوی عملیاتی که رکورد ثبت می‌کند باید در کارتِ «فهرست»ِ همان ' +
      'ماژول دفترِ خودش را داشته باشد. هر منوی عملیات باید در `OPS_LIST_MAP` یک ردیف ' +
      'داشته باشد — یا کلیدِ فهرستش، یا دلیلِ استثنا (state/view/none). بدونِ این، ' +
      'منوی تازه بی‌سروصدا بدونِ فهرست می‌ماند.',
    scope: 'nav',
    check() {
      const nav = fs.readFileSync(path.join(SRC, 'lib', 'navModel.tsx'), 'utf8')
      const lists = fs.readFileSync(path.join(SRC, 'components', 'moduleLists.tsx'), 'utf8')
      const mapBody = lists.slice(lists.indexOf('OPS_LIST_MAP'), lists.indexOf('export interface ListDef'))
      const mapped = new Set([...mapBody.matchAll(/^\s{2}([a-zA-Z]+):/gm)].map((m) => m[1]))
      const listKeys = new Set([...lists.matchAll(/key: '([a-zA-Z]+)', label:/g)].map((m) => m[1]))

      const navBody = nav.slice(nav.indexOf('export const NAV_GROUPS'), nav.indexOf('const PAGE_MODULE_KEY'))
      const found = []
      //: همان پارسر که `verify-pages.mjs` هم از آن می‌خواند — یک منبع، نه دو
      //: تا که دیر یا زود واگرا شوند.
      for (const { key, label } of navTargets()) {
        if (!mapped.has(key)) {
          found.push({ line: 1, msg: `منوی «${label}» (${key}) در OPS_LIST_MAP ردیف ندارد` })
          continue
        }
        const target = new RegExp(`^\s{2}${key}:\s*'([a-zA-Z]+)'`, 'm').exec(mapBody)?.[1]
        if (!target || ['state', 'view', 'none'].includes(target)) continue
        // مقصد باید یک صفحه‌ی واقعی باشد: یا منوی فهرست، یا منوی عملیاتِ دیگری
        // (دفترِ چک‌ها عمداً «جستجوی چک» است که در کارتِ عملیات نشسته).
        const navKeys = new Set([...navBody.matchAll(/key: '([a-zA-Z]+)'/g)].map((x) => x[1]))
        if (!listKeys.has(target) && !navKeys.has(target)) {
          found.push({ line: 1, msg: `منوی «${label}» به فهرستِ ناموجودِ «${target}» اشاره می‌کند` })
        }
      }
      return found
    },
  },
  {
    id: 'R12',
    level: 'error',
    title: 'کدِ مرده',
    why:
      'فایلی که از `main.tsx` به آن نمی‌رسیم مرده است: نه `tsc` می‌گیردش (فایلِ ' +
      'بی‌مصرف خطا نیست)، نه چشمِ بازبین. سه بازسازیِ ماژول نُه فایلِ بی‌ارجاع جا ' +
      'گذاشتند و هیچ‌کدام دیده نشدند تا وقتی این قاعده نوشته شد.',
    scope: 'nav',
    check() {
      //: `file` را خودش می‌دهد تا گزارش به فایلِ مرده اشاره کند، نه به navModel
      //: که پیش‌فرضِ قاعده‌های `scope: 'nav'` است.
      return deadFiles().map((d) => ({
        file: `src/${d.file}`,
        line: 1,
        msg: `${d.lines} خط، از هیچ‌جا import نمی‌شود`,
      }))
    },
  },
  {
    id: 'R13',
    level: 'error',
    title: 'تبِ بی‌راه',
    why:
      'گروهی که `LIST_MENUS` یا `OPS_MENUS` دارد، منوی گروه را نشان می‌دهد و ' +
      '`sectionLists`/`ops`ِ خودِ صفحه اصلاً رندر نمی‌شوند (`ModulePanels`). بالای ' +
      '۱۰۲۴px نوارِ تبِ درون‌صفحه و کشوی موبایل هم پنهان‌اند — پس تبی که در منوی ' +
      'گروه ردیف ندارد **هیچ راهِ ورودی ندارد**. سه تبِ «طرف حساب‌ها»، «سنین ' +
      'مطالبات» و «بخش‌بندی» دقیقاً همین‌طور گم شدند: نه tsc دیدشان (کلیدها رشته‌اند) ' +
      'و نه ممیز، چون خودشان درست اعلام شده بودند.',
    scope: 'nav',
    check() {
      const lists = fs.readFileSync(path.join(SRC, 'components', 'moduleLists.tsx'), 'utf8')
      const secSrc = fs.readFileSync(path.join(SRC, 'components', 'moduleSections.tsx'), 'utf8')

      /** ورودی‌های `{ key, section }`ِ یک نگاشتِ گروهی، به تفکیکِ گروه. */
      const menusOf = (name) => {
        const start = lists.indexOf(`export const ${name}`)
        if (start === -1) return {}
        const body = lists.slice(start, lists.indexOf('\n}\n', start))
        const out = {}
        let heading = null
        for (const m of body.matchAll(
          /^\s{2}'([^']+)': \[|key: '([a-zA-Z]+)'(?:, section: '([a-z0-9-]+)')?, label:/gm,
        )) {
          if (m[1] !== undefined) out[(heading = m[1])] = new Set()
          else if (heading) out[heading].add(`${m[2]}:${m[3] ?? ''}`)
        }
        return out
      }
      const listMenus = menusOf('LIST_MENUS')
      const opsMenus = menusOf('OPS_MENUS')

      //: بخش‌های هر صفحه، با همان تفکیکِ عملیات/فهرست که `ModulePanels` می‌کند.
      const secBody = secSrc.slice(secSrc.indexOf('export const MODULE_SECTIONS'))
      const sections = {}
      for (const m of secBody.matchAll(/\n {2}([a-zA-Z]+): \[([\s\S]*?)\n {2}\]/g)) {
        sections[m[1]] = [...m[2].matchAll(/key: '([a-z0-9-]+)', label: '([^']+)'([^\n]*)/g)].map((x) => ({
          key: x[1],
          label: x[2],
          isList: /kind: 'list'/.test(x[3]),
        }))
      }

      const groupOf = Object.fromEntries(navTargets().map((t) => [t.key, t.heading]))
      const found = []
      for (const [page, secs] of Object.entries(sections)) {
        const heading = groupOf[page]
        if (!heading) continue
        //: منوی گروه فقط همان ستون را می‌بلعد که خودش می‌سازد.
        for (const [menu, kind, want] of [
          [listMenus[heading], 'فهرست', true],
          [opsMenus[heading], 'عملیات', false],
        ]) {
          if (!menu) continue
          for (const s of secs.filter((x) => x.isList === want)) {
            if (!menu.has(`${page}:${s.key}`)) {
              found.push({
                line: 1,
                msg: `تبِ «${s.label}» (${page}/${s.key}) در منوی «${kind}»ِ گروهِ «${heading}» ردیف ندارد — بالای ۱۰۲۴px باز نمی‌شود`,
              })
            }
          }
        }
      }
      return found
    },
  },
]

/** پایانِ یک تگِ باز — با احترام به `{}`، `()` و رشته‌ها، چون attributeهای JSX
 *  خودشان `>` دارند (`className={x >= 0 ? …}`، `onClick={(e) => …}`). */
function tagEnd(text, start) {
  let i = start
  let curly = 0
  let paren = 0
  let quote = null
  while (i < text.length) {
    const ch = text[i]
    if (quote) {
      if (ch === quote) quote = null
    } else if (ch === '"' || ch === "'" || ch === '`') quote = ch
    else if (ch === '{') curly++
    else if (ch === '}') curly--
    else if (ch === '(') paren++
    else if (ch === ')') paren--
    else if (ch === '>' && curly === 0 && paren === 0) return i
    i++
  }
  return -1
}

/** متنِ خطی که این ایندکس در آن است. */
function lineTextAt(text, index) {
  const start = text.lastIndexOf(String.fromCharCode(10), index) + 1
  const end = text.indexOf(String.fromCharCode(10), index)
  return text.slice(start, end === -1 ? text.length : end)
}

/** آیا این ایندکس داخلِ جدولی است که `table-plain` علامت خورده؟ */
function inPlainTable(text, index) {
  const open = text.lastIndexOf('<table', index)
  if (open === -1) return false
  const close = text.lastIndexOf('</table>', index)
  if (close > open) return false
  const tag = text.slice(open, text.indexOf('>', open) + 1)
  return /table-plain/.test(tag)
}

function nextExportIndex(text, from) {
  const next = text.indexOf('\nexport function ', from + 10)
  return next === -1 ? text.length : next
}

// ── اجرا ───────────────────────────────────────────────────────────────────

const results = []
for (const rule of RULES) {
  if (onlyRule && rule.id !== onlyRule) continue
  // قاعده‌ی `nav` به کلِ ناوبری نگاه می‌کند، نه فایل‌به‌فایل — یک‌بار اجرا می‌شود.
  if (rule.scope === 'nav') {
    for (const hit of rule.check('', ''))
      results.push({ rule: rule.id, level: rule.level, file: 'src/lib/navModel.tsx', ...hit })
    continue
  }
  const files = rule.scope === 'pages' ? pageFiles : [...pageFiles, ...componentFiles]
  for (const file of files) {
    const text = fs.readFileSync(file, 'utf8')
    for (const hit of rule.check(text, file)) {
      results.push({ rule: rule.id, level: rule.level, file: rel(file), ...hit })
    }
  }
}

if (asJson) {
  console.log(JSON.stringify({ results, rules: RULES.map(({ id, level, title }) => ({ id, level, title })) }, null, 1))
} else {
  const byRule = new Map()
  for (const r of results) {
    if (!byRule.has(r.rule)) byRule.set(r.rule, [])
    byRule.get(r.rule).push(r)
  }
  console.log(`\nممیزِ صفحه‌ها — ${pageFiles.length} فایلِ صفحه، ${componentFiles.length} کامپوننت\n`)
  for (const rule of RULES) {
    if (onlyRule && rule.id !== onlyRule) continue
    const hits = byRule.get(rule.id) ?? []
    const mark = hits.length === 0 ? 'OK  ' : rule.level === 'error' ? 'FAIL' : 'WARN'
    console.log(`[${mark}] ${rule.id} ${rule.title} — ${hits.length}`)
    for (const h of hits.slice(0, 40)) console.log(`        ${h.file}:${h.line}  ${h.msg}`)
    if (hits.length > 40) console.log(`        … و ${hits.length - 40} مورد دیگر`)
  }
  const errors = results.filter((r) => r.level === 'error').length
  const warns = results.length - errors
  console.log(`\nجمع: ${errors} خطا، ${warns} هشدار\n`)
}

process.exit(results.some((r) => r.level === 'error') ? 1 : 0)
