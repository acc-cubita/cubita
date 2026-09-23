// @vitest-environment jsdom
/**
 * نگهبانِ فوکوسِ `SearchSelect` — تنها تستِ DOMِ این مخزن، و دلیلش مشخص است.
 *
 * پاپ‌آورِ این کامپوننت با portal روی `document.body` می‌نشیند. وقتی بسته
 * می‌شد، فوکوس روی `<body>` می‌افتاد؛ و گریدِ سند سلولِ جاری را از
 * `[data-cell]`ِ عنصرِ فوکوس‌دار پیدا می‌کند، پس از آن لحظه **هیچ کلیدی کار
 * نمی‌کرد** تا کاربر با ماوس جایی کلیک کند. یعنی اولین انتخابِ حساب، کلِ
 * رابطِ صفحه‌کلیدیِ حالتِ حسابدار را می‌کُشت. این به تولید رسید.
 *
 * هیچ تستِ محیطِ `node`ای نمی‌توانست بگیردش، چون `document.activeElement`
 * بدونِ DOM وجود ندارد — به همین دلیل این فایل `jsdom` می‌خواهد.
 *
 * **چرا `openAndFocus` منتظرِ rAF می‌ماند.** نسخه‌ی اولِ این پرونده بعد از باز
 * کردن، مستقیم روی گزینه `click()` می‌زد و **با باگِ برگردانده‌شده هم سبز
 * می‌ماند**: در jsdom کلیک فوکوس را جابه‌جا نمی‌کند، پس فوکوس هنوز روی دکمه
 * بود و «برنگشتن» به چشم نمی‌آمد. خودِ کامپوننت فوکوس را داخلِ
 * `requestAnimationFrame` به کادرِ جست‌وجو می‌برد؛ تا آن اتفاق نیفتد، این
 * تست چیزی را نمی‌سنجد. هر تغییری در این پرونده باید با برگرداندنِ
 * `close(true)` به `setOpen(false)` **قرمز** شود.
 */
import { act, createElement, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SearchSelect } from './SearchSelect'

//: `<option>`های کافی تا از آستانه‌ی جست‌وجو رد شویم؛ زیرش `<select>`ِ بومی
//: رندر می‌شود که اصلاً پاپ‌آور ندارد و این تست بی‌معنا می‌شد.
const OPTIONS = Array.from({ length: 20 }, (_, i) => ({
  id: `a${i}`,
  label: i === 3 ? 'بانک ملت' : `حساب ${i}`,
}))

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

const trigger = () => document.querySelector<HTMLButtonElement>('.item-picker-trigger')!
const popover = () => document.querySelector('.item-picker-pop')
const search = () => document.querySelector<HTMLInputElement>('.item-picker-search input')
const options = () => [...document.querySelectorAll<HTMLElement>('.item-picker-opt')]

function render(children: ReactNode[], props: Record<string, unknown> = {}) {
  act(() => {
    root.render(createElement(SearchSelect, { value: '', 'aria-label': 'حساب', ...props }, children))
  })
}

const plainOptions = OPTIONS.map((o) =>
  createElement('option', { key: o.id, value: o.id }, o.label),
)

/** باز کردن + انتظار تا فوکوس واقعاً داخلِ پاپ‌آور برود (همان rAFِ کامپوننت). */
async function openAndFocus() {
  await act(async () => {
    trigger().click()
  })
  await act(async () => {
    await new Promise((r) => requestAnimationFrame(() => r(null)))
  })
}

describe('بازگرداندنِ فوکوس پس از بسته‌شدن', () => {
  it('باز که می‌شود، فوکوس داخلِ کادرِ جست‌وجوست — پیش‌شرطِ دو تستِ بعدی', async () => {
    render(plainOptions, { onChange: vi.fn() })
    trigger().focus()
    await openAndFocus()

    expect(popover()).not.toBeNull()
    expect(document.activeElement).toBe(search())
  })

  it('پس از **انتخاب**، فوکوس به دکمه برمی‌گردد و روی `<body>` نمی‌افتد', async () => {
    const onChange = vi.fn()
    render(plainOptions, { onChange })
    trigger().focus()
    await openAndFocus()

    await act(async () => {
      options()[3].click()
    })

    expect(popover()).toBeNull()
    expect(onChange).toHaveBeenCalledWith({ target: { value: 'a3' } })
    expect(document.activeElement).toBe(trigger())
    expect(document.activeElement).not.toBe(document.body)
  })

  it('پس از **Escape** هم فوکوس به دکمه برمی‌گردد', async () => {
    render(plainOptions, { onChange: vi.fn() })
    trigger().focus()
    await openAndFocus()

    await act(async () => {
      search()!.dispatchEvent(
        new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
      )
    })

    expect(popover()).toBeNull()
    expect(document.activeElement).toBe(trigger())
  })

  it('کلیکِ بیرون عمداً فوکوس را **نمی‌دزدد** از مقصدِ کلیک', async () => {
    render(plainOptions, { onChange: vi.fn() })
    const other = document.createElement('button')
    document.body.appendChild(other)
    trigger().focus()
    await openAndFocus()

    await act(async () => {
      document.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true }))
    })
    other.focus()

    expect(popover()).toBeNull()
    //: اگر این مسیر هم فوکوس را به دکمه برمی‌گرداند، کاربر هرگز نمی‌توانست با
    //: ماوس جای دیگری برود — پس عمداً برنمی‌گرداند.
    expect(document.activeElement).toBe(other)
    other.remove()
  })
})

describe('برچسبِ گزینه‌ها', () => {
  it('گزینه‌ی انتخاب‌شده بدونِ ویرگولِ اضافه نشان داده می‌شود', () => {
    //: `<option>{code} — {name}</option>` فرزندِ آرایه‌ای می‌سازد و `String()`
    //: رویش ویرگول می‌گذاشت: «۱۰۰۳, — ,بانک ملت». اینجا در DOMِ واقعی سنجیده
    //: می‌شود، نه فقط در واحدِ `flatten`.
    render(
      OPTIONS.map((o, i) =>
        createElement('option', { key: o.id, value: o.id }, String(1000 + i), ' — ', o.label),
      ),
      { value: 'a3', onChange: vi.fn() },
    )
    expect(trigger().textContent).toContain('1003 — بانک ملت')
    expect(trigger().textContent).not.toContain(',')
  })
})
