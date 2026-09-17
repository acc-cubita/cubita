/**
 * گاردِ تعویضِ کسب‌وکار.
 *
 * قیدی که این فایل نگه می‌دارد: **تا وقتی صفِ آفلاین خالی نشده، تعویض ممکن
 * نیست.** اگر روزی کسی این شرط را بردارد بی‌آنکه کشِ محلی مستأجر‌محور شده باشد،
 * سندهای صف‌نشسته در کسب‌وکارِ اشتباه ثبت می‌شوند — و هیچ خطایی هم دیده نمی‌شود.
 */
import { describe, it, expect } from 'vitest'

import { canSwitchTenant } from './tenantSwitch'

const base = { currentTenantId: 'A', targetTenantId: 'B', pendingOutbox: 0, isDesktop: true }

describe('حالتِ عادی', () => {
  it('صفِ خالی → مجاز', () => {
    expect(canSwitchTenant(base).allowed).toBe(true)
  })

  it('همان کسب‌وکار → غیرمجاز، ولی این خطا نیست', () => {
    const d = canSwitchTenant({ ...base, targetTenantId: 'A' })
    expect(d.allowed).toBe(false)
    expect(d.allowed === false && d.reason).toBe('same')
  })
})

describe('صفِ آفلاین', () => {
  it('**هسته‌ی این گارد** — یک سندِ همگام‌نشده کافی است که تعویض بسته شود', () => {
    const d = canSwitchTenant({ ...base, pendingOutbox: 1 })
    expect(d.allowed).toBe(false)
    expect(d.allowed === false && d.reason).toBe('pending-outbox')
  })

  it('پیام تعدادِ سندها را می‌گوید و عاقبت را هشدار می‌دهد', () => {
    //: «نمی‌شود» بی‌دلیل، کاربر را به دورزدنِ گارد می‌کشاند.
    const d = canSwitchTenant({ ...base, pendingOutbox: 3 })
    expect(d.allowed === false && d.message).toMatch(/۳/)
    expect(d.allowed === false && d.message).toMatch(/کسب‌وکارِ تازه/)
  })

  it('در وب صفِ محلی وجود ندارد، پس گارد اعمال نمی‌شود', () => {
    expect(canSwitchTenant({ ...base, pendingOutbox: 5, isDesktop: false }).allowed).toBe(true)
  })
})

describe('ترتیبِ سنجش', () => {
  it('«همان کسب‌وکار» بر صفِ پر مقدم است — پیامِ گمراه‌کننده نمی‌دهد', () => {
    //: کلیک روی کسب‌وکارِ فعلی نباید بگوید «صفت پر است»؛ اصلاً کاری نمی‌خواست بکند.
    const d = canSwitchTenant({ ...base, targetTenantId: 'A', pendingOutbox: 9 })
    expect(d.allowed === false && d.reason).toBe('same')
  })
})
