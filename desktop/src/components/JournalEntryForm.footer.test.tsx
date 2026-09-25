// @vitest-environment jsdom
/**
 * نوارِ پایینِ سند و راهنمای میان‌برها.
 *
 * * رنگِ توازن روی کلِ نوار (`jf-foot--empty|ok|err`)، نه فقط روی عدد.
 * * Ctrl+S از **هر جای** فرمِ حسابدار ثبت می‌کند — و فقط یک بار، چون گرید همان کلید را
 *   زودتر می‌گیرد و فرم نباید دوباره بفرستد. شمارشِ درخواست‌های POST همین را می‌سنجد.
 * * راهنمای میان‌برها پنجره است: با دکمه‌ی سرِ کارت یا Ctrl+/ باز، با Esc یا Ctrl+/ بسته، و
 *   فوکوس بعد از بستن به همان خانه برمی‌گردد.
 *
 * هوکِ واقعیِ `useJournalEntryDraft`؛ پیش‌نویس از `localStorage` (همان کلیدِ ماندگارِ وب)
 * پُر می‌شود تا تست به تایپ در گرید وابسته نباشد.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { JournalEntryForm } from './JournalEntryForm'
import { __resetExperienceForTests, setExperience } from '../lib/experienceMode'
import { line } from '../test/journalGridHarness'
import type { JournalDraftLine } from '../lib/journalEntryDraft'
import type { AccountCache } from '../electron.d'

const ACCOUNTS: AccountCache[] = [
  { id: 'bank', code: '1101', name: 'بانک ملی', type: 'asset', is_group: 0, parent_id: null },
  { id: 'cust', code: '1301', name: 'طرف حساب', type: 'asset', is_group: 0, parent_id: null },
]

let container: HTMLDivElement
let root: Root
let posts: number

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  localStorage.clear()
  __resetExperienceForTests() // پیش‌فرض: حسابدار
  posts = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        posts++
        return new Response(JSON.stringify({ id: 'je1' }), { status: 201 })
      }
      const path = new URL(url).pathname
      return new Response(JSON.stringify(path === '/api/accounts/tafsili-mode' ? { mode: 'optional' } : []), { status: 200 })
    }),
  )
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

function seed(lines: JournalDraftLine[]) {
  localStorage.setItem('cubita.draft.journal.lines', JSON.stringify(lines))
}

const BALANCED = [line({ accountId: 'bank', debit: '100' }), line({ accountId: 'cust', credit: '100' })]

async function render() {
  await act(async () => {
    root.render(createElement(JournalEntryForm, { token: 't', accounts: ACCOUNTS, onQueued: () => {} }))
  })
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
}

async function press(el: HTMLElement, code: string, opts: KeyboardEventInit = {}) {
  act(() => el.focus())
  await act(async () => {
    el.dispatchEvent(new KeyboardEvent('keydown', { key: code, code, bubbles: true, cancelable: true, ...opts }))
    await new Promise((r) => setTimeout(r, 0))
  })
}

const foot = () => container.querySelector<HTMLElement>('.jf-foot')!
const dialog = () => document.querySelector<HTMLElement>('[role="dialog"]')
const trigger = () => container.querySelector<HTMLButtonElement>('.jk-trigger')
const headerInput = () => container.querySelector<HTMLInputElement>('.jh-bar input')!

describe('نوارِ پایین', () => {
  it('رنگِ توازن روی کلِ نوار: خالی، اختلاف، متوازن', async () => {
    await render()
    expect(foot().className).toContain('jf-foot--empty')

    act(() => root.unmount())
    root = createRoot(container)
    seed([line({ accountId: 'bank', debit: '100' }), line({ accountId: 'cust', credit: '40' })])
    await render()
    expect(foot().className).toContain('jf-foot--err')
    expect(foot().textContent).toContain('بدهکار بیشتر')

    act(() => root.unmount())
    root = createRoot(container)
    seed(BALANCED)
    await render()
    expect(foot().className).toContain('jf-foot--ok')
  })

  it('حالتِ حسابدار «ثبت سند (Ctrl+S)»؛ حالتِ ساده فقط «ثبت سند» — و یک دکمه‌ی ثبت', async () => {
    await render()
    const submits = container.querySelectorAll<HTMLButtonElement>('button[type=submit]')
    expect(submits).toHaveLength(1)
    expect(submits[0].textContent).toBe('ثبت سند(Ctrl+S)')
    expect(submits[0].getAttribute('aria-keyshortcuts')).toBe('Control+S')

    act(() => setExperience('simple'))
    const simple = container.querySelector<HTMLButtonElement>('button[type=submit]')!
    expect(simple.textContent).toBe('ثبت سند')
    expect(trigger()).toBeNull()
    expect(foot()).not.toBeNull()
  })

  it('راست دکمه، چپ جمع‌ها: ترتیبِ DOM (= ترتیبِ خواندنِ راست‌به‌چپ)', async () => {
    await render()
    const kids = [...foot().children].map((c) => c.className)
    expect(kids[0]).toContain('jf-submit')
    expect(kids[kids.length - 1]).toContain('jb-sum')
  })
})

describe('Ctrl+S', () => {
  it('از سربرگ هم ثبت می‌کند — یک بار', async () => {
    seed(BALANCED)
    await render()
    await press(headerInput(), 'KeyS', { ctrlKey: true })
    expect(posts).toBe(1)
  })

  it('از خانه‌ی گرید یک بار، نه دو بار (گرید و فرم هر دو گوش می‌دهند)', async () => {
    seed(BALANCED)
    await render()
    const cell = container.querySelector<HTMLElement>('[data-cell="0-1"] input')!
    await press(cell, 'KeyS', { ctrlKey: true })
    expect(posts).toBe(1)
  })
})

describe('پنجره‌ی میان‌برها', () => {
  it('زیرِ گرید چیزی نیست؛ Ctrl+/ باز می‌کند، Esc می‌بندد و فوکوس به همان خانه برمی‌گردد', async () => {
    await render()
    expect(container.querySelector('.jg-keys, .jg-legend')).toBeNull()
    expect(dialog()).toBeNull()

    const from = headerInput()
    await press(from, 'Slash', { ctrlKey: true })
    expect(dialog()).not.toBeNull()
    expect(dialog()!.contains(document.activeElement)).toBe(true)

    await press(document.activeElement as HTMLElement, 'Escape')
    expect(dialog()).toBeNull()
    expect(document.activeElement).toBe(from)
  })

  it('دکمه‌ی سرِ کارت باز می‌کند و Ctrl+/ از داخلِ پنجره می‌بندد', async () => {
    await render()
    act(() => trigger()!.click())
    expect(dialog()).not.toBeNull()
    await press(document.activeElement as HTMLElement, 'Slash', { ctrlKey: true })
    expect(dialog()).toBeNull()
  })

  it('Ctrl+S از داخلِ پنجره سند نمی‌فرستد', async () => {
    seed(BALANCED)
    await render()
    act(() => trigger()!.click())
    await press(document.activeElement as HTMLElement, 'KeyS', { ctrlKey: true })
    expect(posts).toBe(0)
  })

  it('همه‌ی میان‌برهای گرید در پنجره هست — از جمله کپی از ردیفِ قبل', async () => {
    await render()
    act(() => trigger()!.click())
    const keys = [...dialog()!.querySelectorAll('kbd')].map((k) => k.textContent)
    expect(keys).toEqual(
      expect.arrayContaining(['Enter', 'Tab', 'F2', 'F4', 'Alt+↓', 'Ctrl+Enter', 'Ctrl+D', 'Ctrl+Shift+C', 'Ctrl+Delete', 'Ctrl+G', 'Ctrl+S', 'Ctrl+/']),
    )
    act(() => dialog()!.querySelector<HTMLButtonElement>('[aria-label="بستن"]')!.click())
  })
})
