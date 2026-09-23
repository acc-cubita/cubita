// @vitest-environment jsdom
/**
 * سندِ ۳۰۰ ردیفی در DOM — سنجه‌ی تکرارپذیرِ **رندر** (§۲۴، §۵۰).
 *
 * `lib/journalPerf.test.ts` فقط منطقِ خالص را می‌سنجد و خودش نوشته که زمانِ رندر
 * آن‌جا نیست. این فایل همان کمبود است: سوارشدنِ گرید، تایپ در ردیفِ ۱۵۰، و Enter.
 *
 * **هیچ آستانه‌ای ادعا نمی‌شود** — همان سیاستِ `journalPerf`: پروژه SLA ندارد.
 * زمان‌ها چاپ می‌شوند تا پیش و پس از هر تغییر مقایسه شوند. jsdom مرورگر نیست و
 * عددِ مطلقش با کروم فرق دارد؛ ارزشش در **مقایسه‌ی نسبی** روی یک دستگاه است.
 * آنچه تست *می‌سنجد* درستی است: متنِ تایپ‌شده در ردیفِ درست نشست و فوکوس جلو رفت.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { Harness, latest, line } from '../test/journalGridHarness'

const ROWS = 300
const ROW = 149 // ردیفِ ۱۵۰ — وسطِ سند
const DESC = 1 // ستون‌ها: حساب(۰) · شرح(۱) · بدهکار(۲) · بستانکار(۳)

const bigDoc = () =>
  Array.from({ length: ROWS }, (_, i) =>
    line({
      accountId: i % 2 ? 'cust' : 'bank',
      debit: i % 2 ? '' : String((i + 1) * 1000),
      credit: i % 2 ? String(i * 1000) : '',
      description: `شرحِ ردیفِ ${i + 1}`,
    }),
  )

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const median = (xs: number[]) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)]
const input = (row: number, col: number) =>
  container.querySelector<HTMLInputElement>(`[data-cell="${row}-${col}"] input`)!
const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!

function mount() {
  const t0 = performance.now()
  act(() => root.render(createElement(Harness, { initial: bigDoc() })))
  return performance.now() - t0
}

describe('گریدِ ۳۰۰ ردیفی — رندر', () => {
  it('سوارشدن، تایپ در ردیفِ ۱۵۰، و Enter', () => {
    const mounts: number[] = []
    for (let i = 0; i < 3; i++) {
      if (i > 0) {
        act(() => root.unmount())
        root = createRoot(container)
      }
      mounts.push(mount())
    }
    expect(container.querySelectorAll('[data-cell$="-0"]')).toHaveLength(ROWS)

    //: شش کلید، هر کدام یک رویدادِ input — همان چیزی که کاربر تولید می‌کند.
    const el = input(ROW, DESC)
    act(() => el.focus())
    const perKey: number[] = []
    let typed = ''
    for (const ch of 'بابت ح') {
      typed += ch
      const t0 = performance.now()
      act(() => {
        setValue.call(el, typed)
        el.dispatchEvent(new Event('input', { bubbles: true }))
      })
      perKey.push(performance.now() - t0)
    }
    expect(latest[ROW].description).toBe('بابت ح')

    const enters: number[] = []
    for (let i = 0; i < 10; i++) {
      act(() => input(ROW, DESC).focus())
      const t0 = performance.now()
      act(() => {
        input(ROW, DESC).dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true, cancelable: true }))
      })
      enters.push(performance.now() - t0)
    }
    expect((document.activeElement as HTMLElement).closest('[data-cell]')?.getAttribute('data-cell')).toBe(`${ROW}-2`)

    console.log(
      `[bench] 300 rows (jsdom) — mount ${median(mounts).toFixed(0)}ms · ` +
        `per key ${median(perKey).toFixed(1)}ms · Enter ${median(enters).toFixed(1)}ms`,
    )
  })
})
