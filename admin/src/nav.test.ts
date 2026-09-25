import { describe, expect, it } from 'vitest'

import type { StaffMe } from './api'
import { NAV, PAGE_TITLES, visibleNav } from './nav'

function me(role: StaffMe['role'], permissions: Record<string, string[]>): StaffMe {
  return {
    id: 'a',
    user_id: 'u',
    name: 'کارمند',
    email: 'x@staff.cubita.ir',
    role,
    role_label: role,
    permissions,
    last_login_at: null,
    via: 'staff',
  }
}

describe('منویِ ستاد', () => {
  it('مالک همه‌چیز را می‌بیند', () => {
    const keys = visibleNav(me('owner', { '*': ['*'] })).map((i) => i.key)
    expect(keys).toEqual(NAV.map((i) => i.key))
  })

  it('«کاربران ستاد» فقط برای مالک است — حتی با وایلدکاردِ مجوز', () => {
    //: گاردِ واقعی سرور است (`require_staff(role="owner")`)؛ این فقط نمی‌گذارد
    //: منویی نشان داده شود که کلیکش ۴۰۳ می‌گیرد.
    const keys = visibleNav(me('admin', { '*': ['*'] })).map((i) => i.key)
    expect(keys).not.toContain('staff')
  })

  it('پشتیبانی کمیسیون و خریدها را نمی‌بیند', () => {
    const keys = visibleNav(
      me('support', { accounts: ['view'], assurance: ['view'], errors: ['view'] }),
    ).map((i) => i.key)
    expect(keys).toContain('accounts')
    expect(keys).toContain('errors')
    expect(keys).not.toContain('commissions')
    expect(keys).not.toContain('purchases')
  })

  it('مالی اکانت‌ها را فقط می‌بیند ولی کمیسیون را دارد', () => {
    const keys = visibleNav(
      me('finance', { accounts: ['view'], billing: ['*'], commissions: ['*'] }),
    ).map((i) => i.key)
    expect(keys).toEqual(['accounts', 'commissions', 'purchases'])
  })

  it('پشتیبانی «مجوزهای سازمانی» را می‌بیند (برای صدورِ آفلاین)', () => {
    const keys = visibleNav(me('support', { licenses: ['view', 'issue'] })).map((i) => i.key)
    expect(keys).toEqual(['licenses'])
  })

  it('«درخواست‌های خرید» برای پشتیبانی (پیگیریِ تماس) و مالی (فقط دیدن)', () => {
    expect(visibleNav(me('support', { sales: ['view', 'edit'] })).map((i) => i.key)).toEqual(['sales'])
    expect(visibleNav(me('finance', { sales: ['view'] })).map((i) => i.key)).toEqual(['sales'])
  })

  it('مجوزِ خالی یعنی هیچ منویی — بسته می‌شکند، نه باز', () => {
    expect(visibleNav(me('support', {}))).toEqual([])
  })

  it('هر آیتمِ منو عنوان دارد', () => {
    for (const item of NAV) expect(PAGE_TITLES[item.key]).toBeTruthy()
  })
})
