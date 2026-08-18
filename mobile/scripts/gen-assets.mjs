import { writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'

// sharp از node_modulesِ desktop لود می‌شود (mobile خودش sharp ندارد).
const require = createRequire('d:/hesabdari/desktop/')
const sharp = require('sharp')

// ساختِ آیکون/اسپلشِ برندِ کوبیتا از SVG. از پوشه‌ی desktop اجرا می‌شود (sharp آنجاست):
//   cd d:/hesabdari/desktop && node d:/hesabdari/mobile/scripts/gen-assets.mjs
const OUT = 'd:/hesabdari/mobile/assets'
const BG = '#0b0b0d'

// نشانِ برند در مختصاتِ ۴۸‌واحدی (منطبق بر BrandMark.tsx).
function mark(mono = false) {
  const barFill = mono ? '#ffffff' : '#1a1400'
  const sq = mono ? 'none' : 'url(#g)'
  const dot = mono ? '#ffffff' : '#a78bfa'
  return `
    ${mono ? '' : '<rect x="1.5" y="1.5" width="45" height="45" rx="10.5" fill="' + sq + '"/>'}
    <rect x="12" y="26" width="6.5" height="10" rx="2" fill="${barFill}"/>
    <rect x="20.75" y="20" width="6.5" height="16" rx="2" fill="${barFill}"/>
    <rect x="29.5" y="14" width="6.5" height="22" rx="2" fill="${barFill}"/>
    <circle cx="33" cy="13" r="4.5" fill="${dot}"/>`
}

function canvas({ size = 1024, frac = 0.62, bg = null, mono = false } = {}) {
  const markPx = size * frac
  const scale = markPx / 48
  const t = (size - markPx) / 2
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffe6a6"/><stop offset="1" stop-color="#ef9f10"/>
    </linearGradient></defs>
    ${bg ? `<rect width="${size}" height="${size}" rx="${size * 0.22}" fill="${bg}"/>` : ''}
    <g transform="translate(${t},${t}) scale(${scale})">${mark(mono)}</g>
  </svg>`
}

const png = (svg) => sharp(Buffer.from(svg)).png().toBuffer()

const jobs = [
  // آیکونِ اصلی (iOS/عمومی): پس‌زمینه‌ی نزدیک‌مشکی + نشانِ طلاییِ درشت
  ['icon.png', canvas({ frac: 0.68, bg: BG })],
  // فورگراندِ adaptive (اندروید): نشانِ طلایی روی شفاف، در ناحیه‌ی امن
  ['android-icon-foreground.png', canvas({ frac: 0.58 })],
  // پس‌زمینه‌ی adaptive: تختِ نزدیک‌مشکی
  ['android-icon-background.png', `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024"><rect width="1024" height="1024" fill="${BG}"/></svg>`],
  // مونوکروم (تمِ پویا): موتیفِ سفید روی شفاف
  ['android-icon-monochrome.png', canvas({ frac: 0.58, mono: true })],
  // اسپلش: نشانِ طلایی، پس‌زمینه از config
  ['splash-icon.png', canvas({ frac: 0.42 })],
  // فاوآیکونِ وب
  ['favicon.png', canvas({ size: 96, frac: 0.9 })],
]

for (const [name, svg] of jobs) {
  await writeFile(`${OUT}/${name}`, await png(svg))
  console.log('wrote', name)
}
console.log('done')
