// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { JalaliDatePicker } from './JalaliDatePicker'
import { jalaliToIso } from '../lib/jalali'

let root: Root
let host: HTMLDivElement
const change = vi.fn()
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  host = document.createElement('div'); document.body.append(host); root = createRoot(host); change.mockReset()
})
afterEach(() => { act(() => root.unmount()); host.remove() })
function render(value = '2026-09-28') { act(() => root.render(<JalaliDatePicker value={value} onChange={change} clearLabel="پاک کردن" />)) }
function click(selector: string) { act(() => host.querySelector<HTMLButtonElement>(selector)!.click()) }
function textButton(text: string) { act(() => Array.from(host.querySelectorAll('button')).find((button) => button.textContent === text)!.click()) }
describe('تقویم روز، ماه، سال', () => {
  it('سرعنوان یک پله بالا و انتخاب یک پله پایین می‌رود، بدون تغییر تاریخ تا انتخاب روز', () => {
    render(); click('.jalali-date-trigger'); click('[aria-label="انتخاب ماه"]')
    expect(host.querySelector('[aria-label="انتخاب سال"]')?.textContent).toBe('۱۴۰۵')
    expect(host.querySelectorAll('.jalali-date-grid--levels button')).toHaveLength(12)
    click('[aria-label="انتخاب سال"]'); textButton('۱۴۰۴'); textButton('اسفند')
    expect(change).not.toHaveBeenCalled()
    expect(host.querySelector('[aria-label="انتخاب ماه"]')?.textContent).toBe('اسفند ۱۴۰۴')
    click('[aria-label="۲۹ اسفند ۱۴۰۴"]')
    expect(change).toHaveBeenCalledExactlyOnceWith(jalaliToIso(1404, 12, 29))
    expect(host.querySelector('[role=dialog]')).toBeNull()
  })
  it('پیمایش سال‌ها ۱۲تایی، ماه‌ها سالانه و روزها ماهانه است', () => {
    render(); click('.jalali-date-trigger'); click('[aria-label="ماه قبل"]')
    expect(host.querySelector('.jalali-date-title')?.textContent).toBe('شهریور ۱۴۰۵')
    click('[aria-label="انتخاب ماه"]'); click('[aria-label="سال بعد"]')
    expect(host.querySelector('.jalali-date-title')?.textContent).toBe('۱۴۰۶')
    click('[aria-label="انتخاب سال"]')
    const first = host.querySelector('.jalali-date-grid--levels button')!.textContent
    click('[aria-label="سال‌های بعد"]')
    expect(host.querySelector('.jalali-date-grid--levels button')!.textContent).not.toBe(first)
    expect(change).not.toHaveBeenCalled()
  })
  it('Escape می‌بندد و بازکردن دوباره به روزهای تاریخ اصلی برمی‌گردد', () => {
    render(); click('.jalali-date-trigger'); click('[aria-label="انتخاب ماه"]')
    act(() => host.querySelector('[role=dialog]')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })))
    expect(host.querySelector('[role=dialog]')).toBeNull()
    click('.jalali-date-trigger')
    expect(host.querySelector('[aria-label="انتخاب ماه"]')).not.toBeNull()
    expect(host.querySelector('.jalali-date-title')?.textContent).toBe('مهر ۱۴۰۵')
  })
  it('اسفند کبیسه و غیرکبیسه و پاک‌کردن حفظ می‌شوند', () => {
    render(jalaliToIso(1403, 12, 1)); click('.jalali-date-trigger')
    expect(host.querySelector('[aria-label="۳۰ اسفند ۱۴۰۳"]')).not.toBeNull()
    click('[aria-label="انتخاب ماه"]'); click('[aria-label="سال بعد"]'); textButton('اسفند')
    expect(host.querySelector('[aria-label="۳۰ اسفند ۱۴۰۴"]')).toBeNull()
    textButton('پاک کردن'); expect(change).toHaveBeenCalledExactlyOnceWith('')
  })
})
