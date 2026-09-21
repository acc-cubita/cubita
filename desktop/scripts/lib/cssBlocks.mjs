/**
 * تجزیه‌ی بلوک‌های یک برگه‌ی سبک — «هر `{` کجا باز شد، سرش چه بود، کدام‌ها بسته نشدند».
 *
 * چرا ماژولِ جدا و نه چند خط داخلِ ممیز: تنها راهِ سنجیدنش این است که به CSSِ
 * **معیوب** بدهیمش، و آن CSS نباید در `src/` بنشیند. جدا که باشد، تست مستقیم
 * صدایش می‌زند و شیوه‌نامه‌ی واقعی دست نمی‌خورد.
 *
 * شمردنِ خامِ `{` و `}` کافی نیست: توضیح‌های CSS و رشته‌ها هر دو می‌توانند آکولاد
 * داشته باشند — `content: "}"` ردیفی است که واقعاً در `App.css` هست.
 */
export function cssBlocks(text) {
  const events = []
  const stack = []
  let line = 1
  let i = 0
  let lastCut = 0 // متنِ «سرِ بلوک» از اینجا تا `{` خوانده می‌شود
  while (i < text.length) {
    const ch = text[i]
    if (ch === '\n') {
      line++
      i++
    } else if (ch === '/' && text[i + 1] === '*') {
      const end = text.indexOf('*/', i + 2)
      const stop = end === -1 ? text.length : end + 2
      for (let k = i; k < stop; k++) if (text[k] === '\n') line++
      i = stop
    } else if (ch === '"' || ch === "'") {
      i++
      while (i < text.length && text[i] !== ch) {
        if (text[i] === '\\') i++
        else if (text[i] === '\n') line++
        i++
      }
      i++
    } else if (ch === '{') {
      const head = text.slice(lastCut, i).split(/[\n;{}]/).pop().trim()
      stack.push({ line, head })
      events.push({ kind: 'open', line, head, depth: stack.length - 1 })
      lastCut = ++i
    } else if (ch === '}') {
      if (stack.length === 0) events.push({ kind: 'stray', line })
      else stack.pop()
      lastCut = ++i
    } else i++
  }
  return { events, unclosed: stack }
}

/** یافته‌های یک برگه‌ی سبک، به‌ترتیبِ خط. شکلِ هر یافته: `{ line, msg }`. */
export function cssBraceFindings(text) {
  const { events, unclosed } = cssBlocks(text)
  const found = []

  for (const u of unclosed)
    found.push({ line: u.line, msg: `بلوکِ «${u.head}» باز مانده و تا پایانِ فایل بسته نمی‌شود` })

  for (const e of events)
    if (e.kind === 'stray') found.push({ line: e.line, msg: '`}`ِ اضافه — بلوکی باز نیست که ببندد' })

  //: `@media`ِ تودرتو در این مخزن همیشه یعنی بلوکی پیش‌تر بسته نشده. اینجا نه
  //: `@supports` هست نه `@layer`، و `@keyframes` هیچ‌وقت `@media` تو نمی‌گیرد —
  //: پس این نشانه غلطِ مثبت ندارد، و برخلافِ «بسته‌نشده» که به پایانِ فایل اشاره
  //: می‌کند، به **اولین علامتِ** خرابی اشاره می‌کند.
  for (const e of events)
    if (e.kind === 'open' && e.depth > 0 && e.head.startsWith('@media'))
      found.push({ line: e.line, msg: `«${e.head}» در عمقِ ${e.depth} — یعنی بلوکی پیش از این بسته نشده` })

  return found.sort((a, b) => a.line - b.line)
}
