// پیش‌رندرِ سایتِ معرفی: برای هر صفحه‌ی `ALL_PAGES` یک فایلِ HTMLِ کامل (متن + head) می‌سازد،
// به‌اضافه‌ی `404.html` و `sitemap.xml`. پس از `vite build` (کلاینت) و `vite build --ssr` اجرا می‌شود.
//
// چرا: سایت SPA بود و خزنده فقط `<div id="root"></div>` می‌دید؛ هر نشانی هم با ۲۰۰ همان صفحه را
// می‌داد. حالا هر صفحه متن و عنوان و توضیحِ خودش را دارد و nginx نشانیِ ناشناخته را با ۴۰۴ جواب می‌دهد.
//
// نگهبان‌ها (build را می‌شکنند، نه فقط هشدار): `style`ِ درون‌خطی (CSPِ سایت `style-src 'self'` است و
// آن را دور می‌ریزد)، و تعدادِ h1ِ هر صفحه‌ی ایندکس‌شدنی که باید دقیقاً یکی باشد.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DIST = path.join(ROOT, 'dist')
const SSR = path.join(ROOT, 'dist-ssr')
const SITE = 'https://cubita.ir'

const template = fs.readFileSync(path.join(DIST, 'index.html'), 'utf8')
if (!template.includes('<!--app-head-->') || !template.includes('<!--app-html-->')) {
  throw new Error('index.html نشانگرهای <!--app-head--> و <!--app-html--> را ندارد.')
}
const entry = fs.readdirSync(SSR).find((f) => /^entry-server\.m?js$/.test(f))
if (!entry) throw new Error(`entry-server در ${SSR} پیدا نشد؛ اول vite build --ssr را اجرا کنید.`)
const { render, headTags, ALL_PAGES, NOT_FOUND_META } = await import(pathToFileURL(path.join(SSR, entry)).href)

const errors = []
const warnings = []

function build(meta, url) {
  const html = render(url)
  if (/<[^>]+\sstyle="/.test(html)) errors.push(`${url}: صفتِ style در HTML — CSP آن را رد می‌کند؛ به کلاسِ CSS ببرید.`)
  const h1 = (html.match(/<h1[\s>]/g) ?? []).length
  if (h1 !== 1) errors.push(`${url}: ${h1} تیترِ h1 (باید دقیقاً یکی باشد).`)
  if (!meta.noindex) {
    if (meta.title.length > 75) warnings.push(`${url}: عنوان ${meta.title.length} نویسه است (گوگل حدودِ ۶۰ تا ۷۰ را نشان می‌دهد).`)
    if (meta.description.length < 70 || meta.description.length > 200) {
      warnings.push(`${url}: توضیح ${meta.description.length} نویسه است (بهتر ۱۲۰ تا ۱۶۰).`)
    }
  }
  return template.replace('<!--app-head-->', headTags(meta)).replace('<!--app-html-->', html)
}

function write(file, content) {
  const target = path.join(DIST, file)
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, content)
}

const seen = new Set()
for (const meta of ALL_PAGES) {
  if (seen.has(meta.path)) errors.push(`مسیرِ تکراری در ALL_PAGES: ${meta.path}`)
  seen.add(meta.path)
  write(meta.path === '/' ? 'index.html' : path.join(meta.path.slice(1), 'index.html'), build(meta, meta.path))
}
write('404.html', build(NOT_FOUND_META, '/__not-found__'))

const today = new Date().toISOString().slice(0, 10)
const urls = ALL_PAGES.filter((m) => !m.noindex)
  .map((m) => {
    const loc = m.path === '/' ? `${SITE}/` : `${SITE}${m.path}`
    const extra = [
      m.changefreq ? `    <changefreq>${m.changefreq}</changefreq>` : null,
      m.priority != null ? `    <priority>${m.priority.toFixed(1)}</priority>` : null,
    ].filter(Boolean)
    return ['  <url>', `    <loc>${loc}</loc>`, `    <lastmod>${today}</lastmod>`, ...extra, '  </url>'].join('\n')
  })
  .join('\n')
write('sitemap.xml', `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`)

fs.rmSync(SSR, { recursive: true, force: true })

for (const w of warnings) console.warn(`هشدار: ${w}`)
if (errors.length) {
  for (const e of errors) console.error(`خطا: ${e}`)
  process.exit(1)
}
console.log(`پیش‌رندر: ${ALL_PAGES.length} صفحه + 404.html، نقشهٔ سایت با ${urls.split('<url>').length - 1} نشانی.`)
