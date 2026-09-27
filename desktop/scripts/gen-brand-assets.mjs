// ساختِ همه‌ی دارایی‌های نشانِ کوبیتا («خانه‌ها») از یک هندسه، با کرومیومِ playwright (بی‌وابستگیِ دیگر):
//   فاوآیکونِ SVGِ وب‌اپ، ادمین و سایت · build/icon.ico · تصویرهای کنار و سرِ نصاب (BMP) · آیکون‌ها و اسپلشِ اپِ موبایل
//
// اجرا از پوشه‌ی desktop:
//   node scripts/gen-brand-assets.mjs
//
// نشان: هشت خانه‌ی جدول که حرفِ C را می‌سازند؛ خانه‌ی بنفشِ بالا «خانه‌ی فعالِ برگه» است. هندسه در
// کاشیِ ۱۲۰واحدی است و با desktop/src/components/BrandMark.tsx، website/src/concept/SiteChrome.tsx و
// mobile/src/ui/BrandMark.tsx یکی است — تغییرش یعنی تغییرِ هر چهار.
import { readFile, writeFile } from 'node:fs/promises'
import { chromium } from 'playwright'

const ROOT = new URL('../../', import.meta.url)
const INK = '#17130C'
const GOLD = '#FFC72C'
const VIOLET = '#A592E9'
//: زمینه‌ی تیره‌ی اپِ موبایل (app.json: splash و adaptiveIcon) — همان که بود.
const MOBILE_BG = '#0b0b0d'
const CELLS = [
  [24, 24],
  [50, 24],
  [24, 50],
  [24, 76],
  [50, 76],
  [76, 76],
]
const ACTIVE = [76, 24]

const cellRects = (fill) => CELLS.map(([x, y]) => `<rect x="${x}" y="${y}" width="20" height="20" rx="5" fill="${fill}" />`)

function tileSvg(size) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 120 120" fill="none">
  <rect width="120" height="120" rx="28" fill="${INK}" />
  <g fill="${GOLD}">
${CELLS.map(([x, y]) => `    <rect x="${x}" y="${y}" width="20" height="20" rx="5" />`).join('\n')}
  </g>
  <rect x="${ACTIVE[0]}" y="${ACTIVE[1]}" width="20" height="20" rx="5" fill="${VIOLET}" />
</svg>
`
}

// فقط خانه‌ها، بی کاشی؛ `frac` = پهنای شبکه‌ی خانه‌ها نسبت به بوم.
function cellsSvg(size, frac, { mono = false, bg = null } = {}) {
  const v = 72 / frac
  const o = 60 - v / 2
  const fill = mono ? '#ffffff' : GOLD
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="${o} ${o} ${v} ${v}">
    ${bg ? `<rect x="${o}" y="${o}" width="${v}" height="${v}" fill="${bg}" />` : ''}
    ${cellRects(fill).join('')}
    <rect x="${ACTIVE[0]}" y="${ACTIVE[1]}" width="20" height="20" rx="5" fill="${mono ? '#ffffff' : VIOLET}" ${mono ? 'fill-opacity="0.55"' : ''} />
  </svg>`
}

// ICO با ورودی‌های PNG (از ویستا به بعد؛ icon.icoِ پیشین هم همین قالب بود و نصابِ NSIS آن را می‌خورد).
function ico(entries) {
  const head = Buffer.alloc(6 + 16 * entries.length)
  head.writeUInt16LE(1, 2)
  head.writeUInt16LE(entries.length, 4)
  let offset = head.length
  entries.forEach(({ size, data }, i) => {
    const o = 6 + 16 * i
    head.writeUInt8(size >= 256 ? 0 : size, o)
    head.writeUInt8(size >= 256 ? 0 : size, o + 1)
    head.writeUInt16LE(1, o + 4)
    head.writeUInt16LE(32, o + 6)
    head.writeUInt32LE(data.length, o + 8)
    head.writeUInt32LE(offset, o + 12)
    offset += data.length
  })
  return Buffer.concat([head, ...entries.map((e) => e.data)])
}

// BMPِ ۲۴بیتیِ پایین‌به‌بالا — قالبی که NSIS برای تصویرهای نصاب می‌خواهد. `rgba` پیکسل‌های ردیف‌به‌ردیف است.
function bmp(rgba, w, h) {
  const row = Math.ceil((w * 3) / 4) * 4
  const out = Buffer.alloc(54 + row * h)
  out.write('BM', 0)
  out.writeUInt32LE(out.length, 2)
  out.writeUInt32LE(54, 10)
  out.writeUInt32LE(40, 14)
  out.writeInt32LE(w, 18)
  out.writeInt32LE(h, 22)
  out.writeUInt16LE(1, 26)
  out.writeUInt16LE(24, 28)
  out.writeUInt32LE(row * h, 34)
  for (let y = 0; y < h; y++) {
    const dst = 54 + (h - 1 - y) * row
    for (let x = 0; x < w; x++) {
      const s = (y * w + x) * 4
      out[dst + x * 3] = rgba[s + 2]
      out[dst + x * 3 + 1] = rgba[s + 1]
      out[dst + x * 3 + 2] = rgba[s]
    }
  }
  return out
}

async function fontFace(weight, file) {
  const b64 = (await readFile(new URL(`website/public/fonts/${file}`, ROOT))).toString('base64')
  return `@font-face{font-family:V;font-weight:${weight};src:url(data:font/woff2;base64,${b64}) format('woff2')}`
}

const browser = await chromium.launch()

// یک صفحه‌ی HTML را دقیقاً در ابعادِ خودش عکس می‌گیرد (پس‌زمینه‌ی شفاف مگر آن‌که CSS رنگ بدهد).
async function shot(w, h, body, css = '') {
  const fonts = [await fontFace(400, 'Vazirmatn-UI-Regular.woff2'), await fontFace(800, 'Vazirmatn-UI-ExtraBold.woff2')]
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 })
  await page.setContent(`<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><style>
    ${fonts.join('\n')}
    html,body{margin:0;width:${w}px;height:${h}px;overflow:hidden;background:transparent;font-family:V,Tahoma,sans-serif}
    body>svg{display:block}
    ${css}
  </style></head><body>${body}</body></html>`)
  await page.evaluate(() => document.fonts.ready)
  const buf = await page.screenshot({ type: 'png', omitBackground: true })
  const rgba = await page.evaluate(async (b64) => {
    const img = new Image()
    img.src = `data:image/png;base64,${b64}`
    await img.decode()
    const c = document.createElement('canvas')
    c.width = img.width
    c.height = img.height
    const ctx = c.getContext('2d')
    ctx.drawImage(img, 0, 0)
    return Array.from(ctx.getImageData(0, 0, c.width, c.height).data)
  }, buf.toString('base64'))
  await page.close()
  return { png: buf, rgba }
}

const svgPng = async (svg, size) => (await shot(size, size, svg)).png

const SIDEBAR_CSS = `
  body{background:#0E0B07;color:#FFF7E0;display:flex;flex-direction:column;align-items:center;position:relative}
  .grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,199,44,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(255,199,44,.07) 1px,transparent 1px);background-size:14px 14px;background-position:-1px 6px;-webkit-mask:radial-gradient(120px 150px at 50% 30%,#000,transparent 75%)}
  .glow{position:absolute;left:50%;top:102px;width:170px;height:170px;transform:translate(-50%,-50%);background:radial-gradient(closest-side,rgba(255,199,44,.22),transparent)}
  .mark{position:relative;margin-top:60px;border-radius:20px;box-shadow:0 14px 30px -10px rgba(0,0,0,.8)}
  .mark svg{display:block}
  .name{position:relative;margin-top:22px;color:#FFC72C;font-weight:800;font-size:31px;line-height:1.3}
  .tag{position:relative;margin-top:6px;color:#BDB6A6;font-size:12px}
  .rule{position:relative;margin-top:16px;width:34px;height:2px;border-radius:2px;background:#FFC72C;opacity:.8}
  .site{position:absolute;bottom:22px;color:#FFC72C;font-weight:800;font-size:12px;letter-spacing:.04em;direction:ltr}`

const HEADER_CSS = `
  body{background:#FFFFFF;display:flex;align-items:center;gap:9px;padding:0 14px;box-sizing:border-box}
  body svg{display:block}
  .name{color:#17130C;font-weight:800;font-size:20px;line-height:1}`

try {
  const sidebar = await shot(
    164,
    314,
    `<div class="grid"></div><div class="glow"></div><div class="mark">${tileSvg(84)}</div>
     <div class="name">کوبیتا</div><div class="tag">نرم‌افزار حسابداری هوشمند</div><div class="rule"></div><div class="site">cubita.ir</div>`,
    SIDEBAR_CSS,
  )
  const sidebarBmp = bmp(sidebar.rgba, 164, 314)
  await writeFile(new URL('desktop/build/installerSidebar.bmp', ROOT), sidebarBmp)
  await writeFile(new URL('desktop/build/uninstallerSidebar.bmp', ROOT), sidebarBmp)
  const header = await shot(150, 57, `<div>${tileSvg(32)}</div><div class="name">کوبیتا</div>`, HEADER_CSS)
  await writeFile(new URL('desktop/build/installerHeader.bmp', ROOT), bmp(header.rgba, 150, 57))

  const entries = []
  for (const size of [16, 24, 32, 48, 64, 128, 256]) entries.push({ size, data: await svgPng(tileSvg(size), size) })
  await writeFile(new URL('desktop/build/icon.ico', ROOT), ico(entries))

  for (const p of ['desktop/public/favicon.svg', 'admin/public/favicon.svg', 'website/public/favicon.svg']) {
    await writeFile(new URL(p, ROOT), tileSvg(32))
  }

  const mobile = [
    // آیکونِ اصلی: خودِ کاشی
    ['icon.png', tileSvg(1024), 1024],
    // فورگراندِ adaptive (اندروید): فقط خانه‌ها، درونِ ناحیه‌ی امن؛ پس‌زمینه از app.json
    ['android-icon-foreground.png', cellsSvg(1024, 0.42), 1024],
    ['android-icon-background.png', `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024"><rect width="1024" height="1024" fill="${MOBILE_BG}"/></svg>`, 1024],
    // مونوکروم (تمِ پویا): خانه‌های سفید؛ خانه‌ی فعال کم‌رنگ‌تر تا از بقیه جدا بماند
    ['android-icon-monochrome.png', cellsSvg(1024, 0.42, { mono: true }), 1024],
    // اسپلش: خانه‌ها روی زمینه‌ی اسپلش (app.json)
    ['splash-icon.png', cellsSvg(1024, 0.62), 1024],
    // فاوآیکونِ وب
    ['favicon.png', tileSvg(96), 96],
  ]
  for (const [name, svg, size] of mobile) {
    await writeFile(new URL(`mobile/assets/${name}`, ROOT), await svgPng(svg, size))
  }
} finally {
  await browser.close()
}
console.log('done: icon.ico, installer bmps, 3 favicons, 6 mobile assets')
