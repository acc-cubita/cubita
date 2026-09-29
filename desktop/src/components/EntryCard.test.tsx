// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { JournalEntryRecord } from '../api'
import { EntryCard } from './EntryCard'

const sample = (): JournalEntryRecord => ({
  id: 'entry', number: 2, atf_number: 102, sub_number: 'A-25', entry_date: '2026-09-29',
  description: 'انتقال از صندوق به بانک', source_type: 'manual', source: null, created_by_name: 'مریم احمدی',
  status: 'temporary', voided_at: null, reverses_entry_id: null,
  lines: [
    { id: '1', account_id: 'bank', account_code: '1102', account_name: 'بانک', debit: '10000000', credit: '0', description: 'دریافت وجه' },
    { id: '2', account_id: 'cash', account_code: '1101', account_name: 'صندوق', debit: '0', credit: '10000000', description: 'خروج وجه' },
  ],
})
let host: HTMLDivElement, root: Root
beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
})
afterEach(async () => { await act(() => root.unmount()); host.remove() })

describe('برگهٔ مشترکِ سند', () => {
  it('اطلاعات، نام حساب، جمعِ هم‌ستون، تاریخ شمسی و ترتیب ردیف‌ها را دارد', async () => {
    await act(() => root.render(<EntryCard entry={sample()} />))
    expect(host.textContent).toContain('۱۴۰۵/۰۷/۰۷')
    expect(host.textContent).toContain('سند شمارهٔ ۲')
    expect(host.textContent).toContain('۱۰۲')
    expect(host.textContent).toContain('A-۲۵')
    expect(host.querySelector('.entry-document-meta')?.textContent).toContain('ثبت‌کننده: مریم احمدی')
    expect([...host.querySelectorAll('.entry-account')].map((node) => node.textContent)).toEqual(['۱۱۰۲بانک', '۱۱۰۱صندوق'])
    expect(host.querySelector('tfoot')?.textContent).toContain('سند تراز است')
    expect(host.querySelectorAll('tfoot .num')).toHaveLength(2)
    expect(host.querySelectorAll('tbody .num')).toHaveLength(4)
    expect(host.querySelector('tfoot .num')?.textContent).toBe('۱۰٬۰۰۰٬۰۰۰')
    expect(host.querySelectorAll('td:not([data-label])')).toHaveLength(0)
    expect(host.querySelectorAll('thead th')).toHaveLength(5)
  })
  it('تفصیلی، مرکز، ارزِ دقیق و تاریخ پیگیری فقط وقتی لازم‌اند نمایش دارند', async () => {
    const entry = sample()
    Object.assign(entry.lines[0], { analytic_id: 'analytic', analytic_code: '31', analytic_name: 'قرارداد الف',
      cost_center_id: 'center', cost_center_name: 'شعبهٔ تهران', currency_code: 'USD', fx_amount: '12.3456', fx_rate: '81000.5', tracking_date: '2026-09-29' })
    await act(() => root.render(<EntryCard entry={entry} />))
    expect(host.querySelectorAll('thead th')).toHaveLength(8)
    for (const text of ['قرارداد الف', 'شعبهٔ تهران', '۱۲٫۳۴۵۶', '۸۱٬۰۰۰٫۵', 'USD']) expect(host.textContent).toContain(text)
    expect(host.querySelector('[data-label="پیگیری"]')?.textContent).toContain('۱۴۰۵/۰۷/۰۷')
    expect(host.querySelector('tfoot td')?.getAttribute('colspan')).toBe('6')
  })
  it('نام نبودن، سند خالی و اختلاف را پنهان نمی‌کند', async () => {
    const entry = sample(); entry.lines[0].account_name = null; entry.lines[0].debit = '9999999'
    await act(() => root.render(<EntryCard entry={entry} />))
    expect(host.textContent).toContain('نام حساب در دسترس نیست')
    expect(host.textContent).toContain('اختلاف بدهکار و بستانکار: ۱ ریال')
    await act(() => root.render(<EntryCard entry={{ ...entry, lines: [] }} />))
    expect(host.textContent).toContain('ردیفی برای این سند دریافت نشد')
    expect(host.textContent).not.toContain('سند تراز است')
  })
  it('نامِ ناموجود را حدس نمی‌زند و برای منشأ خودکار ثبت‌کنندهٔ دستی نشان نمی‌دهد', async () => {
    await act(() => root.render(<EntryCard entry={{ ...sample(), created_by_name: null }} />))
    expect(host.textContent).toContain('ثبت‌کننده: نام در دسترس نیست')
    await act(() => root.render(<EntryCard entry={{ ...sample(), source_type: 'sales_invoice' }} />))
    expect(host.textContent).not.toContain('ثبت‌کننده:')
  })
  it('وضعیت ابطال/برگشت و کنش واقعیِ منشأ محفوظ است', async () => {
    const open = vi.fn(), entry = { ...sample(), voided_at: '2026-09-29', reverses_entry_id: 'old' }
    await act(() => root.render(<EntryCard entry={entry} onOpenSource={open} />))
    expect(host.textContent).toContain('باطل')
    expect(host.textContent).toContain('سند برگشتی')
    await act(() => (host.querySelector('button') as HTMLButtonElement).click())
    expect(open).toHaveBeenCalledOnce()
  })
})
