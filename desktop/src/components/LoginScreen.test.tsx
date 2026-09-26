// @vitest-environment jsdom
/**
 * صفحه‌ی ورود — «نام کاربری را به خاطر بسپار».
 *
 * با تیک، ایمیل بعد از **ورودِ موفق** ذخیره می‌شود (هرگز رمز)؛ دفعه‌ی بعد از پیش پر است، تیک خورده و مکان‌نما روی رمز؛
 * ورودِ موفقِ بی‌تیک ایمیلِ ذخیره‌شده را پاک می‌کند؛ ورودِ ناموفق چیزی ذخیره نمی‌کند.
 */
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LoginScreen } from './LoginScreen'

let container: HTMLDivElement
let root: Root
let loginOk: boolean

beforeEach(() => {
  ;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true
  document.documentElement.dir = 'rtl'
  localStorage.clear()
  loginOk = true
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      const url = new URL(input, 'http://x')
      const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status })
      if (url.pathname === '/api/auth/login')
        return loginOk ? json({ access_token: 't', refresh_token: 'r' }) : json({ detail: 'ایمیل یا رمز اشتباه است' }, 401)
      if (url.pathname === '/api/auth/me') return json({ id: 'u', email: 'a@b.ir' })
      return json({})
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

const settle = () =>
  act(async () => {
    await new Promise((r) => setTimeout(r, 0))
  })
function render(onLoggedIn = vi.fn()) {
  act(() => root.render(createElement(LoginScreen, { onLoggedIn })))
  return onLoggedIn
}
const emailInput = () => container.querySelector<HTMLInputElement>('input[type="email"]')!
const passwordInput = () => container.querySelector<HTMLInputElement>('input[autocomplete="current-password"]')!
const box = () => container.querySelector<HTMLInputElement>('.login-remember input')!
function type(el: HTMLInputElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(el, value)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
async function submit() {
  await act(async () => container.querySelector<HTMLFormElement>('form')!.requestSubmit())
  await settle()
}

describe('ورود — نام کاربریِ به‌خاطرسپرده', () => {
  it('بارِ اول خالی و بی‌تیک؛ با تیک و ورودِ موفق فقط ایمیل ذخیره می‌شود', async () => {
    const onLoggedIn = render()
    expect(emailInput().value).toBe('')
    expect(box().checked).toBe(false)
    type(emailInput(), 'a@b.ir')
    type(passwordInput(), 'secret-pass')
    act(() => box().click())
    await submit()
    expect(onLoggedIn).toHaveBeenCalled()
    expect(localStorage.getItem('cubita.login.email')).toBe('a@b.ir')
    expect(JSON.stringify({ ...localStorage })).not.toContain('secret-pass')
  })

  it('دفعه‌ی بعد ایمیل از پیش پر است، تیک خورده و مکان‌نما روی رمز', () => {
    localStorage.setItem('cubita.login.email', 'a@b.ir')
    render()
    expect(emailInput().value).toBe('a@b.ir')
    expect(box().checked).toBe(true)
    expect(document.activeElement).toBe(passwordInput())
  })

  it('ورودِ موفقِ بی‌تیک ایمیلِ ذخیره‌شده را پاک می‌کند', async () => {
    localStorage.setItem('cubita.login.email', 'a@b.ir')
    render()
    act(() => box().click())
    type(passwordInput(), 'secret-pass')
    await submit()
    expect(localStorage.getItem('cubita.login.email')).toBeNull()
  })

  it('ورودِ ناموفق چیزی ذخیره نمی‌کند', async () => {
    loginOk = false
    render()
    type(emailInput(), 'wrong@b.ir')
    type(passwordInput(), 'x')
    act(() => box().click())
    await submit()
    expect(container.querySelector('.error')).not.toBeNull()
    expect(localStorage.getItem('cubita.login.email')).toBeNull()
  })
})
