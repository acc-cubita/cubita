import { beforeEach, describe, expect, it, vi } from 'vitest'

import { loadStoredToken, storeToken } from './session'

const store = new Map<string, string>()

beforeEach(() => {
  store.clear()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  })
})

describe('نشستِ ستاد', () => {
  it('کلید با اپِ مشتری فرق دارد', () => {
    //: روی localhost هر دو اپ یک مبدأ دارند؛ کلیدِ مشترک یعنی توکنِ همدیگر را
    //: بازنویسی می‌کردند و توسعه‌دهنده مدام از یکی بیرون می‌افتاد.
    storeToken('t1')
    expect(store.has('cubita.admin.token')).toBe(true)
    expect(store.has('cubita.auth.token')).toBe(false)
  })

  it('رفت‌وبرگشت و پاک‌کردن', () => {
    storeToken('t1')
    expect(loadStoredToken()).toBe('t1')
    storeToken(null)
    expect(loadStoredToken()).toBeNull()
  })

  it('ذخیره‌سازیِ مسدود اپ را نمی‌شکند', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
      removeItem: () => {
        throw new Error('blocked')
      },
    })
    expect(loadStoredToken()).toBeNull()
    expect(() => storeToken('t')).not.toThrow()
  })
})
