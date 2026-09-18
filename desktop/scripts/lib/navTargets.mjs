import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'src')

/**
 * فهرستِ صفحه‌های ناوبری، خوانده‌شده از `navModel.tsx`.
 *
 * **چرا با regex و نه import:** `navModel.tsx` آیکنِ JSX دارد، و این اسکریپت‌ها
 * با `node` خام اجرا می‌شوند بدونِ ترنسفورمِ TypeScript. همین منطق از قبل در
 * `audit-pages.mjs` بود و کار می‌کرد؛ این‌جا فقط بیرون کشیده شده تا دو اسکریپت
 * یک پارسر داشته باشند نه دو تا — وگرنه دیر یا زود واگرا می‌شدند.
 *
 * **چرا این فایل وجود دارد:** فهرستِ صفحه‌های `verify-pages.mjs` دستی بود و
 * موردی رشد کرده بود — «دریافت و پرداخت» ۱۸ صفحه داشت و «حسابداری» ۳ تا، با
 * ۲۲ منو. صفحه‌ی «گزارش ترازها» در فهرست نبود و دقیقاً همان صفحه بود که با
 * خطای رندر سفید می‌شد و به تولید رسید. فهرستِ دستی یعنی پوششی که به یادِ آدم‌ها
 * بند است.
 *
 * @returns {{ key: string, label: string, heading: string }[]}
 */
export function navTargets() {
  const nav = fs.readFileSync(path.join(SRC, 'lib', 'navModel.tsx'), 'utf8')
  //: همان برشِ `audit-pages.mjs` — فقط بدنه‌ی NAV_GROUPS، تا تعریف‌های بعدی
  //: (که `key:` دارند ولی منو نیستند) وارد نشوند.
  const body = nav.slice(nav.indexOf('export const NAV_GROUPS'), nav.indexOf('const PAGE_MODULE_KEY'))

  const out = []
  let heading = ''
  //: یک گذر از بالا به پایین: هر `heading` گروهِ جاری را عوض می‌کند و هر
  //: `key/label` به همان گروه نسبت می‌خورد. ترتیبِ متنِ فایل همان ترتیبِ
  //: ساختار است، پس همین کافی است.
  for (const m of body.matchAll(/heading: '([^']+)'|key: '([a-zA-Z]+)', label: '([^']+)'/g)) {
    if (m[1] !== undefined) heading = m[1]
    else out.push({ key: m[2], label: m[3], heading })
  }
  return out
}

/**
 * ورودی‌های منوی گروه‌هایی که «عملیات»شان کار‌به‌کار است نه صفحه‌به‌صفحه (`OPS_MENUS`)
 * — به‌همراهِ همه‌ی ورودی‌های «فهرست»ِ همان گروه‌ها (`LIST_MENUS`).
 *
 * **چرا:** در این گروه‌ها («تامین‌کنندگان و انبار») ردیفی با نامِ صفحه («انبار») در
 * منو نیست؛ هر ردیف تبی از یک صفحه است. بدونِ این فهرست، `verify-pages` صفحه‌ی «انبار»
 * را با زیررشته‌ی «رسید انبار» باز می‌کرد — که تبِ صفحه‌ی خرید است — و خودِ انبار
 * هرگز سنجیده نمی‌شد.
 *
 * @returns {{ key: string, section: string | null, label: string, heading: string }[]}
 */
export function groupMenuTargets() {
  const lists = fs.readFileSync(path.join(SRC, 'components', 'moduleLists.tsx'), 'utf8')
  const block = (name) => {
    const start = lists.indexOf(`export const ${name}`)
    return start === -1 ? '' : lists.slice(start, lists.indexOf('\n}\n', start))
  }
  const parse = (body) => {
    const out = []
    let heading = ''
    for (const m of body.matchAll(/^\s{2}'([^']+)': \[|key: '([a-zA-Z]+)'(?:, section: '([a-z-]+)')?, label: '([^']+)'/gm)) {
      if (m[1] !== undefined) heading = m[1]
      else out.push({ key: m[2], section: m[3] ?? null, label: m[4], heading })
    }
    return out
  }
  const ops = parse(block('OPS_MENUS'))
  const headings = new Set(ops.map((t) => t.heading))
  return [...ops, ...parse(block('LIST_MENUS')).filter((t) => headings.has(t.heading))]
}
