// @vitest-environment jsdom
/**
 * ثبتِ سند در دو حالت — **همان پیش‌نویس، دو نما** (UI-01 §۲۸، §۲۹، §۳۵).
 *
 * * حالتِ ساده: فیلدهای حرفه‌ای پشتِ «گزینه‌های بیشتر»؛ حسابدار همه را یک‌جا.
 * * داده‌ی پُر هرگز پنهان نمی‌شود — پیش‌نویسِ ماندگار ممکن است از جلسه‌ی قبل مقدار بیاورد.
 * * عوض‌کردنِ حالت وسطِ ثبت، ردیف‌ها را پاک نمی‌کند.
 *
 * `fetch` شبیه‌سازی می‌شود فقط برای چهار داده‌ی کمکیِ فرم (حالتِ تفصیلی، مراکز هزینه،
 * تفصیلی‌ها، ارزها)؛ خودِ هوکِ `useJournalEntryDraft` و `usePersistentState` واقعی‌اند.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { JournalEntryForm } from './JournalEntryForm'
import { __resetExperienceForTests, setExperience } from '../lib/experienceMode'
import type { AccountCache } from '../electron.d'

const ACCOUNTS: AccountCache[] = [
  { id: 'bank', code: '1101', name: 'بانک ملی', type: 'asset', is_group: 0, parent_id: null },
  { id: 'cust', code: '1301', name: 'طرف حساب', type: 'asset', is_group: 0, parent_id: null },
]

const API: Record<string, unknown> = {
  '/api/accounts/tafsili-mode': { mode: 'optional' },
  '/api/cost-centers': [{ id: 'cc1', code: '10', name: 'پروژه الف', is_active: true }],
  '/api/accounting/analytics': [{ id: 'an1', code: '01', name: 'تفصیلی الف', is_active: true }],
  '/api/currencies': [{ id: 'usd', code: 'USD', name: 'دلار' }],
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  localStorage.clear()
  __resetExperienceForTests() // پیش‌فرض: حسابدار
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const path = new URL(url).pathname
      return new Response(JSON.stringify(API[path] ?? []), { status: 200 })
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

async function render() {
  await act(async () => {
    root.render(createElement(JournalEntryForm, { token: 't', accounts: ACCOUNTS, onQueued: () => {} }))
  })
  //: چهار درخواستِ کمکی برگردند.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
}

const labels = () => [...container.querySelectorAll('.ef-label label')].map((l) => l.textContent?.replace('*', '').trim())
const toggle = () => container.querySelector<HTMLButtonElement>('.ef-more-toggle')

describe('سربرگِ سند در هر حالت', () => {
  it('حسابدار: همه‌ی فیلدها یک‌جا، بی «گزینه‌های بیشتر»', async () => {
    await render()
    expect(toggle()).toBeNull()
    expect(labels()).toEqual(expect.arrayContaining(['شرح سند', 'تاریخ سند', 'وضعیت سند', 'شماره فرعی', 'مرکز هزینه / پروژه', 'تفصیلی سایر', 'ارز سند']))
  })

  it('ساده: فقط شرح و تاریخ؛ بقیه پشتِ «گزینه‌های بیشتر»', async () => {
    act(() => setExperience('simple'))
    await render()
    expect(labels()).toEqual(['شرح سند', 'تاریخ سند'])
    expect(toggle()?.getAttribute('aria-expanded')).toBe('false')
    expect(toggle()?.textContent).toContain('مرکز هزینه')

    act(() => toggle()!.click())
    expect(toggle()?.getAttribute('aria-expanded')).toBe('true')
    expect(labels()).toEqual(expect.arrayContaining(['وضعیت سند', 'شماره فرعی', 'مرکز هزینه / پروژه', 'تفصیلی سایر', 'ارز سند']))
  })

  it('**داده‌ی پُر پنهان نمی‌شود** — شماره فرعیِ ماندهٔ پیش‌نویس، بخش را باز و قفل نگه می‌دارد', async () => {
    localStorage.setItem('cubita.draft.journal.subNumber', JSON.stringify('پرونده ۷'))
    act(() => setExperience('simple'))
    await render()
    expect(toggle()?.getAttribute('aria-expanded')).toBe('true')
    expect(toggle()?.disabled).toBe(true)
    expect(labels()).toContain('شماره فرعی')
  })
})

describe('عوض‌کردنِ حالت وسطِ ثبت', () => {
  it('**ردیف‌ها و مبلغ‌ها می‌مانند** — ساده ← حسابدار ← ساده', async () => {
    localStorage.setItem(
      'cubita.draft.journal.lines',
      JSON.stringify([
        { accountId: 'bank', debit: '20000000', credit: '', fxAmount: '', trackingNo: '', trackingDate: '', analyticId: '', description: 'بابت اجاره' },
        { accountId: 'cust', debit: '', credit: '20000000', fxAmount: '', trackingNo: '', trackingDate: '', analyticId: '', description: '' },
      ]),
    )
    act(() => setExperience('simple'))
    await render()
    const amounts = () =>
      [...container.querySelectorAll<HTMLInputElement>('input[inputmode="numeric"], input[inputmode="decimal"]')]
        .map((i) => i.value)
        .filter(Boolean)
    const before = amounts()
    expect(before.length).toBeGreaterThanOrEqual(2)

    act(() => setExperience('accountant'))
    expect(container.querySelector('.jg-table')).not.toBeNull() // گرید آمد
    expect(amounts()).toEqual(before)
    expect([...container.querySelectorAll<HTMLInputElement>('input')].some((i) => i.value === 'بابت اجاره')).toBe(true)

    act(() => setExperience('simple'))
    expect(container.querySelector('.jg-table')).toBeNull()
    expect(amounts()).toEqual(before)
    //: شرحِ ردیف در حالتِ ساده ستونِ همیشگی نیست، ولی چون پُر است دیده می‌شود.
    expect([...container.querySelectorAll<HTMLInputElement>('input')].some((i) => i.value === 'بابت اجاره')).toBe(true)
  })
})

describe('خطای ردیفی با شماره‌ی گرید — در خودِ فرم (§۳۸)', () => {
  const L = (p: Record<string, string>) => ({
    accountId: '', debit: '', credit: '', fxAmount: '', trackingNo: '', trackingDate: '', analyticId: '', description: '', ...p,
  })
  const message = () => container.querySelector('.ef-status, [role="status"]')?.textContent ?? container.textContent ?? ''

  async function submit() {
    await act(async () => {
      container.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
      await new Promise((r) => setTimeout(r, 0))
    })
  }

  it('مبلغِ بی‌حساب: پیش از رفتن به سرور، «ردیفِ ۲»', async () => {
    localStorage.setItem('cubita.draft.journal.lines', JSON.stringify([
      L({ accountId: 'bank', debit: '100' }),
      L({ debit: '50' }),
      L({ accountId: 'cust', credit: '100' }),
    ]))
    await render()
    await submit()
    expect(message()).toContain('ردیفِ ۲: مبلغ دارد ولی حساب ندارد')
    const posts = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.filter(
      (c) => (c[1] as RequestInit | undefined)?.method === 'POST',
    )
    expect(posts).toHaveLength(0)
  })

  it('۴۲۲ِ سرور برای ردیفِ دومِ payload → «ردیفِ ۳» چون ردیفِ ۲ خالی است', async () => {
    localStorage.setItem('cubita.draft.journal.lines', JSON.stringify([
      L({ accountId: 'bank', debit: '100' }),
      L({}),
      L({ accountId: 'cust', credit: '100' }),
    ]))
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === 'POST') {
          return new Response(
            JSON.stringify({ detail: [{ loc: ['body', 'lines', 1, 'fx_rate'], msg: 'Value error, نرخِ ارز باید بزرگ‌تر از صفر باشد' }] }),
            { status: 422 },
          )
        }
        return new Response(JSON.stringify(API[new URL(url).pathname] ?? []), { status: 200 })
      }),
    )
    await render()
    await submit()
    expect(message()).toContain('ردیفِ ۳: نرخِ ارز باید بزرگ‌تر از صفر باشد')
    expect(message()).not.toContain('[object Object]')
  })

  it('۴۲۲ِ سطحِ سند (بی ردیف): متنِ خوانا، نه «[object Object]»', async () => {
    localStorage.setItem('cubita.draft.journal.lines', JSON.stringify([
      L({ accountId: 'bank', debit: '100' }),
      L({ accountId: 'cust', credit: '100' }),
    ]))
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === 'POST') {
          return new Response(JSON.stringify({ detail: [{ loc: ['body'], msg: 'Value error, مجموع سند نمی‌تواند صفر باشد' }] }), {
            status: 422,
          })
        }
        return new Response(JSON.stringify(API[new URL(url).pathname] ?? []), { status: 200 })
      }),
    )
    await render()
    await submit()
    expect(message()).toContain('مجموع سند نمی‌تواند صفر باشد')
    expect(message()).not.toContain('[object Object]')
    expect(message()).not.toContain('Value error')
  })
})
