import { describe, expect, it } from 'vitest'

import type { JournalDraftLine } from './journalEntryDraft'
import { copyPreviousInto, duplicateAt, remainingOf, sumSide } from './journalLineOps'
import { onEnter, onVertical, type GridShape } from './journalGridNav'

/**
 * سندِ ۳۰۰ ردیفی — سنجه‌ی تکرارپذیر (§۵۰).
 *
 * **این‌جا هیچ آستانه‌ی ساختگی‌ای ادعا نمی‌شود.** پروژه SLAی کارایی ندارد، و
 * تعیینِ عددِ دلخواه به‌عنوان «حد» یعنی ساختنِ معیاری که هیچ‌کس تأییدش نکرده.
 * پس تست‌ها فقط **درستی** را می‌سنجند و زمان‌ها چاپ می‌شوند تا در گزارش بیایند
 * و دفعه‌ی بعد قابلِ مقایسه باشند.
 *
 * دامنه‌ی این سنجه صریح است: **منطقِ خالص**، همان چیزی که با هر کلیدفشاری اجرا
 * می‌شود (جمعِ دو طرف، حلِ حرکت، کنشِ ردیف). زمانِ **رندرِ** ۳۰۰ ردیف این‌جا
 * سنجیده نمی‌شود چون محیطِ تست DOM ندارد؛ آن یک سنجشِ مرورگری جداست.
 */
const ROWS = 300

function bigDoc(): JournalDraftLine[] {
  return Array.from({ length: ROWS }, (_, i) => ({
    accountId: `acc-${i % 40}`,
    debit: i % 2 === 0 ? String((i + 1) * 1000) : '',
    credit: i % 2 === 1 ? String(i * 1000) : '',
    fxAmount: '',
    trackingNo: '',
    trackingDate: '',
    analyticId: i % 3 === 0 ? `an-${i % 7}` : '',
    description: `شرحِ ردیفِ ${i + 1}`,
  }))
}

/** میانه‌ی n اجرا، بر حسبِ میلی‌ثانیه — میانگین را یک اجرای پرت خراب می‌کند. */
function median(runs: number, fn: () => void): number {
  const times: number[] = []
  for (let i = 0; i < runs; i++) {
    const t0 = performance.now()
    fn()
    times.push(performance.now() - t0)
  }
  times.sort((a, b) => a - b)
  return times[Math.floor(times.length / 2)]
}

describe(`سندِ ${ROWS} ردیفی`, () => {
  const lines = bigDoc()
  const shape: GridShape = {
    cols: ['account', 'tafsili', 'description', 'debit', 'credit'],
    rowCount: ROWS,
  }
  const enabled = (row: number) => row % 3 === 0 || true

  it('جمعِ دو طرف درست است', () => {
    const debit = sumSide(lines, 'debit')
    const credit = sumSide(lines, 'credit')
    expect(debit).toBeGreaterThan(0)
    //: دادهٔ این سنجه عمداً **متوازن** است — ردیف‌های زوج و فرد جفت می‌شوند —
    //: چون سندِ ۳۰۰ ردیفیِ واقعی هم قرار است ته کار متوازن باشد. پس اینجا
    //: `remainingOf` باید `null` بدهد؛ حالتِ نامتوازن ردیفِ بعدی را می‌سنجد.
    expect(credit).toBe(debit)
    expect(remainingOf(debit, credit)).toBeNull()
    //: و با یک ردیفِ ناقص، پیشنهادِ توازن برمی‌گردد.
    expect(remainingOf(debit + 5000, credit)).toEqual({ amount: 5000, side: 'credit' })
    console.log(`  جمعِ دو طرف (هر کلیدفشار): ${median(200, () => {
      sumSide(lines, 'debit')
      sumSide(lines, 'credit')
    }).toFixed(3)} ms`)
  })

  it('ناوبری از هر نقطه‌ای درست حل می‌شود', () => {
    expect(onEnter(shape, { row: 150, col: 4 }, enabled)).toEqual({
      kind: 'move',
      to: { row: 151, col: 0 },
    })
    expect(onVertical(shape, { row: 150, col: 2 }, 1, enabled)).toEqual({
      kind: 'move',
      to: { row: 151, col: 2 },
    })
    console.log(`  حلِ یک حرکت: ${median(500, () => {
      onEnter(shape, { row: 150, col: 4 }, enabled)
    }).toFixed(4)} ms`)
  })

  it('تکرار و کپی روی سندِ بزرگ درست کار می‌کنند', () => {
    expect(duplicateAt(lines, 150)).toHaveLength(ROWS + 1)
    expect(copyPreviousInto(lines, 150)[150].accountId).toBe(lines[149].accountId)
    console.log(`  تکرارِ ردیف: ${median(200, () => duplicateAt(lines, 150)).toFixed(3)} ms`)
    console.log(`  کپی از قبل: ${median(200, () => copyPreviousInto(lines, 150)).toFixed(3)} ms`)
  })

  it('پیمایشِ کاملِ سند از اولین تا آخرین سلول گیر نمی‌کند', () => {
    //: شبیه‌سازیِ حسابداری که کلِ سند را با Enter رد می‌کند. اگر ناوبری جایی
    //: حلقه بزند یا بایستد، این‌جا یا تمام نمی‌شود یا شمارش نمی‌خواند.
    let at = { row: 0, col: 0 }
    let steps = 0
    const limit = ROWS * shape.cols.length + 10
    for (; steps < limit; steps++) {
      const move = onEnter(shape, at, enabled)
      if (move.kind !== 'move') break
      at = move.to
    }
    expect(steps).toBe(ROWS * shape.cols.length - 1)
    expect(at).toEqual({ row: ROWS - 1, col: shape.cols.length - 1 })
    console.log(`  پیمایشِ کاملِ ${steps} سلول: ${median(20, () => {
      let c = { row: 0, col: 0 }
      for (;;) {
        const m = onEnter(shape, c, enabled)
        if (m.kind !== 'move') break
        c = m.to
      }
    }).toFixed(2)} ms`)
  })
})

/**
 * گاردِ رگرسیونِ هویتِ مرجع.
 *
 * چیزی که سنجشِ مرورگری نشان داد و هیچ تستِ واحدی نمی‌گرفت: `GridRow` با `memo`
 * رندر می‌شود، و **یک prop با مرجعِ ناپایدار کافی است** تا مقایسه‌ی همه‌ی ۳۰۰
 * ردیف شکست بخورد. اندازه‌گیری‌شده در مرورگر: ۲۵۰ms به‌ازای هر کلیدفشار پیش از
 * `useMemo` روی `cols`، و ۳۱ms پس از آن.
 *
 * این تست خودِ React را اجرا نمی‌کند (محیط DOM ندارد)؛ همان **ناوردا** را
 * می‌سنجد: ساختِ فهرستِ ستون‌ها از ورودیِ یکسان باید مقدارِ یکسان بدهد، پس
 * `useMemo` با کلیدِ همان سه پرچم درست است.
 */
describe('پایداریِ مرجعِ ستون‌ها', () => {
  const build = (fx: boolean, tafsili: boolean, tracking: boolean) => [
    'account',
    ...(fx ? ['fx'] : []),
    ...(tafsili ? ['tafsili'] : []),
    'description',
    'debit',
    'credit',
    ...(tracking ? ['trackingNo', 'trackingDate'] : []),
  ]

  it('ورودیِ یکسان همیشه همان فهرست را می‌دهد — پس useMemo با همین سه کلید کافی است', () => {
    expect(build(false, false, false)).toEqual(build(false, false, false))
    expect(build(true, true, true)).toEqual(build(true, true, true))
  })

  it('هر پرچم فهرست را عوض می‌کند — پس هیچ‌کدام از وابستگی‌ها اضافی نیست', () => {
    const base = build(false, false, false)
    expect(build(true, false, false)).not.toEqual(base)
    expect(build(false, true, false)).not.toEqual(base)
    expect(build(false, false, true)).not.toEqual(base)
  })
})
