// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { loadRememberedEmail, rememberEmail } from './rememberedLogin'

beforeEach(() => localStorage.clear())

describe('نام کاربریِ به‌خاطرسپرده', () => {
  it('با تیک ذخیره می‌شود و بی‌تیک پاک', () => {
    rememberEmail(null, '  a@b.ir ', true)
    expect(loadRememberedEmail()).toBe('a@b.ir')
    rememberEmail(null, 'a@b.ir', false)
    expect(loadRememberedEmail()).toBeNull()
  })

  it('فقط ایمیل؛ هیچ کلیدِ دیگری نوشته نمی‌شود', () => {
    rememberEmail(null, 'a@b.ir', true)
    expect(Object.keys(localStorage)).toEqual(['cubita.login.email'])
  })

  it('در نسخه‌ی سازمانی هر سرور ایمیلِ خودش را دارد', () => {
    rememberEmail('http://srv-a:8420', 'a@co.ir', true)
    rememberEmail('http://srv-b:8420', 'b@co.ir', true)
    expect(loadRememberedEmail('http://srv-a:8420')).toBe('a@co.ir')
    expect(loadRememberedEmail('http://srv-b:8420')).toBe('b@co.ir')
    expect(loadRememberedEmail()).toBeNull()
  })

  it('localStorageِ در دسترس‌نبوده خطا نمی‌دهد', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(loadRememberedEmail()).toBeNull()
    spy.mockRestore()
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(() => rememberEmail(null, 'a@b.ir', true)).not.toThrow()
    vi.restoreAllMocks()
  })
})
