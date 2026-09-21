import { describe, expect, it } from 'vitest'

import { cssBraceFindings, cssBlocks } from './cssBlocks.mjs'

/**
 * این تست دو کار می‌کند و هر دو لازم‌اند:
 *
 * ۱. سنجه **می‌گیرد** — همان خرابی‌ای که واقعاً پیش آمد.
 * ۲. سنجه **غلطِ مثبت نمی‌دهد** — که مهم‌تر است. ممیزی که سرِ CSSِ سالم داد
 *    بزند، چند روز بعد با `--rule` کنار گذاشته می‌شود و آن‌وقت هیچ است.
 */
describe('cssBraceFindings', () => {
  it('بلوکِ بسته‌نشده را با خطِ خودش گزارش می‌کند', () => {
    const css = ['@media (max-width: 760px) {', '  .a { color: red; }', ''].join('\n')
    const hits = cssBraceFindings(css)
    expect(hits).toHaveLength(1)
    expect(hits[0].line).toBe(1)
    expect(hits[0].msg).toContain('باز مانده')
  })

  it('`}`ِ اضافه را می‌گیرد', () => {
    const hits = cssBraceFindings('.a { color: red; }\n}\n')
    expect(hits).toHaveLength(1)
    expect(hits[0].line).toBe(2)
  })

  it('`@media`ِ تودرتو را به‌عنوانِ اولین علامتِ خرابی گزارش می‌کند', () => {
    //: شکلِ دقیقِ خرابیِ واقعی: یک `@media` بسته نمی‌شود، پس `@media`ِ بعدی
    //: به عمقِ ۱ می‌افتد. «بسته‌نشده» به خطِ ۱ اشاره می‌کند و این یکی به خطِ ۴ —
    //: و در فایلی با ۱۲ هزار خط، همین دومی است که آدم را سرِ جای درست می‌برد.
    const css = [
      '@media (max-width: 760px) {',
      '  .a { color: red; }',
      '',
      '@media (max-width: 640px) {',
      '  .b { color: blue; }',
      '}',
    ].join('\n')
    const hits = cssBraceFindings(css)
    expect(hits.map((h) => h.line)).toEqual([1, 4])
    expect(hits[1].msg).toContain('عمقِ 1')
  })

  //: سه حالتی که یک شمارنده‌ی ساده‌ی `{`/`}` را می‌شکنند. `content: "}"` فرضی
  //: نیست — در `App.css` هست.
  it.each([
    ['آکولاد داخلِ رشته', '.x::after { content: "}"; }\n.y::before { content: "{"; }\n'],
    ['آکولاد داخلِ توضیح', '/* } } }\n   { { { */\n.x { color: red; }\n'],
    ['گریزِ رشته', '.x::after { content: "\\"}"; }\n'],
    ['@keyframes تودرتو', '@keyframes spin { from { opacity: 0 } to { opacity: 1 } }\n'],
    ['@font-face', "@font-face { font-family: 'Vazir'; src: url(a.woff2); }\n"],
  ])('%s را خرابی نمی‌شمارد', (_name, css) => {
    expect(cssBraceFindings(css)).toEqual([])
  })

  it('سرِ بلوک را برای پیام نگه می‌دارد', () => {
    const { events } = cssBlocks('.page.panels > * {\n  background: red;\n}\n')
    expect(events[0].head).toBe('.page.panels > *')
  })
})
