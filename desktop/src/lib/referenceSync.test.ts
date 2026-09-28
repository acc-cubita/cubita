import { describe, expect, it, vi } from 'vitest'
import { referenceAllowed, referenceSyncMessage, runReferenceSync } from './referenceSync'

describe('همگام‌سازی مستقلِ مرجع‌ها', () => {
  it('حسابدار بدون انبار فقط حساب‌ها و بانکِ مجاز را می‌گیرد', async () => {
    const accounts = vi.fn().mockResolvedValue(undefined)
    const items = vi.fn().mockResolvedValue(undefined)
    const clear = vi.fn()
    const banks = vi.fn().mockResolvedValue(undefined)
    const result = await runReferenceSync([
      { key: 'accounts', run: accounts }, { key: 'items', run: items, onSkipped: clear },
      { key: 'bankAccounts', run: banks },
    ], { accounting: ['view'], checks_bank: ['view'] })
    expect(result).toEqual({ pulled: ['accounts', 'bankAccounts'], skipped: ['items'], failed: [] })
    expect(accounts).toHaveBeenCalledOnce()
    expect(banks).toHaveBeenCalledOnce()
    expect(items).not.toHaveBeenCalled()
    expect(clear).toHaveBeenCalledOnce()
  })

  it('۴۰۳ِ واقعی با نقشهٔ مجوز کهنه هم جلوی بخش موفق را نمی‌گیرد', async () => {
    const clear = vi.fn()
    const result = await runReferenceSync([
      { key: 'accounts', run: async () => {} },
      { key: 'warehouses', run: async () => { throw Object.assign(new Error('مجاز نیست'), { status: 403 }) }, onSkipped: clear },
    ], { '*': ['*'] })
    expect(result).toEqual({ pulled: ['accounts'], skipped: ['warehouses'], failed: [] })
    expect(clear).toHaveBeenCalledOnce()
  })

  it.each([401, 402, 404, 500])('خطای %i به‌جای خطای مجوز پنهان نمی‌شود', async (status) => {
    const result = await runReferenceSync([
      { key: 'accounts', run: async () => { throw Object.assign(new Error('پاسخ ناموفق'), { status }) } },
      { key: 'items', run: async () => {} },
    ])
    expect(result.pulled).toEqual(['items'])
    expect(result.skipped).toEqual([])
    expect(result.failed).toEqual([{ key: 'accounts', message: 'پاسخ ناموفق' }])
  })

  it('خطای شبکه خواناست و بخش‌های موفق حفظ می‌شوند', async () => {
    const result = await runReferenceSync([
      { key: 'accounts', run: async () => {} },
      { key: 'items', run: async () => { throw new TypeError('fetch failed') } },
    ])
    expect(result.failed[0].message).toContain('اتصال شبکه')
    expect(referenceSyncMessage(result, { pushed: 1, failed: 2 })).toContain('ناموفق: ۲')
    expect(referenceSyncMessage(result)).not.toContain('کامل شد')
  })

  it('اکشنِ ساخت/تأیید به‌تنهایی خواندن نمی‌دهد، *ِ ماژول و مالک خواندن می‌دهند', () => {
    expect(referenceAllowed({ accounting: ['create', 'approve'] }, 'accounts')).toBe(false)
    expect(referenceAllowed({ accounting: ['*'] }, 'accounts')).toBe(true)
    expect(referenceAllowed({ '*': ['view'] }, 'accounts')).toBe(true)
    expect(referenceAllowed({ '*': ['*'] }, 'items')).toBe(true)
    expect(referenceAllowed({}, 'accounts')).toBe(false)
    expect(referenceAllowed(undefined, 'accounts')).toBe(true)
  })

  it('خطای پاک‌کردنِ کش هم پنهان نمی‌شود', async () => {
    const result = await runReferenceSync([
      { key: 'items', run: async () => {}, onSkipped: () => { throw new Error('کش خواندنی نیست') } },
    ], {})
    expect(result.failed).toEqual([{ key: 'items', message: 'کش خواندنی نیست' }])
  })
})
