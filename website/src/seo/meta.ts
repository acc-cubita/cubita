/**
 * فرادادهٔ هر صفحه — عنوان، توضیح، canonical، Open Graph و دادهٔ ساخت‌یافته.
 *
 * **یک منبع برای سه مصرف:** پیش‌رندر (`scripts/prerender.mjs`) همین را در `<head>` هر فایلِ HTML
 * می‌نویسد، نقشهٔ سایت از همین ساخته می‌شود، و در مرورگر `applyMeta` همان را روی سند می‌گذارد. پس
 * عنوانی که گوگل می‌بیند و عنوانی که کاربر در زبانه می‌بیند هرگز دو چیز نمی‌شوند.
 *
 * عنوان و توضیح عمداً بی‌کسرهٔ اضافه‌اند («نرم‌افزار حسابداری»، نه «نرم‌افزارِ حسابداری»): همان
 * چیزی است که مردم جست‌وجو می‌کنند.
 */

export const SITE_URL = 'https://cubita.ir'
export const SITE_NAME = 'کوبیتا'
const OG_IMAGE = `${SITE_URL}/og-image.jpg`

export type JsonLd = Record<string, unknown>

export interface Crumb {
  name: string
  path: string
}

export interface PageMeta {
  path: string
  title: string
  description: string
  /** صفحه‌ی تراکنشی یا تکراری — در نقشهٔ سایت نمی‌آید و `noindex` می‌گیرد. */
  noindex?: boolean
  /** canonicalِ دیگر (مثلاً `/concept` که همان صفحهٔ اصلی است). */
  canonical?: string
  priority?: number
  changefreq?: 'weekly' | 'monthly' | 'yearly'
  /** مسیرِ صفحه بی «کوبیتا»ی اول؛ خالی یعنی صفحهٔ اصلی. */
  breadcrumb?: Crumb[]
  jsonLd?: JsonLd[]
}

export const absolute = (path: string) => (path === '/' ? `${SITE_URL}/` : `${SITE_URL}${path}`)

export function breadcrumbLd(crumbs: Crumb[]): JsonLd {
  const all = [{ name: SITE_NAME, path: '/' }, ...crumbs]
  return {
    '@type': 'BreadcrumbList',
    itemListElement: all.map((c, i) => ({ '@type': 'ListItem', position: i + 1, name: c.name, item: absolute(c.path) })),
  }
}

export function faqLd(items: { q: string; a: string }[]): JsonLd {
  return {
    '@type': 'FAQPage',
    mainEntity: items.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
  }
}

export const ORGANIZATION_LD: JsonLd = {
  '@type': 'Organization',
  '@id': `${SITE_URL}/#org`,
  name: SITE_NAME,
  url: `${SITE_URL}/`,
  logo: `${SITE_URL}/favicon.svg`,
  email: 'acc.cubita@gmail.com',
}

function graph(meta: PageMeta): JsonLd | null {
  const items = [...(meta.jsonLd ?? [])]
  if (meta.breadcrumb?.length) items.push(breadcrumbLd(meta.breadcrumb))
  return items.length ? { '@context': 'https://schema.org', '@graph': items } : null
}

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/** تگ‌های `<head>` برای پیش‌رندر. JSON-LD با `<\/` امن می‌شود تا متنی `</script>` آن را نشکند. */
//: صفحه‌ی noindex (۴۰۴، نتیجه‌ی پرداخت) canonical نمی‌گیرد، مگر صریح داده شده باشد (`/concept` ← `/`).
const canonicalOf = (meta: PageMeta) => (meta.canonical ? absolute(meta.canonical) : meta.noindex ? null : absolute(meta.path))

export function headTags(meta: PageMeta): string {
  const canonical = canonicalOf(meta)
  const url = canonical ?? absolute(meta.path)
  const lines = [
    `<title>${esc(meta.title)}</title>`,
    `<meta name="description" content="${esc(meta.description)}" />`,
    ...(canonical ? [`<link rel="canonical" href="${canonical}" />`] : []),
    meta.noindex ? '<meta name="robots" content="noindex, follow" />' : '<meta name="robots" content="index, follow, max-image-preview:large" />',
    '<meta property="og:type" content="website" />',
    `<meta property="og:site_name" content="${SITE_NAME}" />`,
    '<meta property="og:locale" content="fa_IR" />',
    `<meta property="og:url" content="${url}" />`,
    `<meta property="og:title" content="${esc(meta.title)}" />`,
    `<meta property="og:description" content="${esc(meta.description)}" />`,
    `<meta property="og:image" content="${OG_IMAGE}" />`,
    '<meta property="og:image:width" content="1200" />',
    '<meta property="og:image:height" content="630" />',
    '<meta name="twitter:card" content="summary_large_image" />',
    `<meta name="twitter:title" content="${esc(meta.title)}" />`,
    `<meta name="twitter:description" content="${esc(meta.description)}" />`,
    `<meta name="twitter:image" content="${OG_IMAGE}" />`,
  ]
  const ld = graph(meta)
  if (ld) lines.push(`<script type="application/ld+json">${JSON.stringify(ld).replace(/</g, '\\u003c')}</script>`)
  return lines.join('\n    ')
}

function setMeta(selector: string, attr: 'name' | 'property', key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(selector)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.content = content
}

/** در مرورگر: همان عنوان و توضیحِ پیش‌رندر — برای توسعه (بی پیش‌رندر) و ناوبریِ درون‌برنامه‌ای. */
export function applyMeta(meta: PageMeta): void {
  document.title = meta.title
  setMeta('meta[name="description"]', 'name', 'description', meta.description)
  setMeta('meta[name="robots"]', 'name', 'robots', meta.noindex ? 'noindex, follow' : 'index, follow, max-image-preview:large')
  const canonical = canonicalOf(meta)
  let link = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!canonical) {
    link?.remove()
    return
  }
  if (!link) {
    link = document.createElement('link')
    link.rel = 'canonical'
    document.head.appendChild(link)
  }
  link.href = canonical
}
