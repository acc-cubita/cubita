/**
 * تشخیصِ آفلاین.
 *
 * سنجه‌ی اصلی «آیا درست تشخیص می‌دهد» نیست — «آیا زیادی حساس نیست» است. اگر یک
 * درخواستِ بدشانس اپ را آفلاین اعلام کند، کاربر بنرِ آفلاین می‌بیند در حالی که
 * شبکه سالم است، و بعد از چند بار دیگر به بنر اعتماد نمی‌کند.
 */
import { onlineManager } from '@tanstack/react-query'

import { reportNetworkResult, resetNetworkState } from '../network'

beforeEach(() => {
  jest.useFakeTimers()
  global.fetch = jest.fn().mockResolvedValue({ ok: true }) as unknown as typeof fetch
  resetNetworkState()
})

afterEach(() => {
  resetNetworkState()
  jest.useRealTimers()
})

describe('حساسیت', () => {
  it('یک شکستِ تکی آفلاین اعلام نمی‌کند', () => {
    // یک درخواستِ بدشانس الگو نیست.
    reportNetworkResult(true)
    expect(onlineManager.isOnline()).toBe(true)
  })

  it('دو شکستِ پیاپی آفلاین اعلام می‌کند', () => {
    reportNetworkResult(true)
    reportNetworkResult(true)
    expect(onlineManager.isOnline()).toBe(false)
  })

  it('یک موفقیتِ میانی شمارنده را صفر می‌کند', () => {
    reportNetworkResult(true)
    reportNetworkResult(false)
    reportNetworkResult(true)
    // دو شکست بوده ولی پیاپی نبوده.
    expect(onlineManager.isOnline()).toBe(true)
  })
})

describe('بازگشت', () => {
  it('اولین درخواستِ موفق فوراً به آنلاین برمی‌گرداند', () => {
    reportNetworkResult(true)
    reportNetworkResult(true)
    expect(onlineManager.isOnline()).toBe(false)

    reportNetworkResult(false)
    expect(onlineManager.isOnline()).toBe(true)
  })

  it('وقتی هیچ درخواستی نمی‌آید، خودش سرور را می‌سنجد', async () => {
    // بدونِ این، کاربری که اپ را باز گذاشته تا وقتی دستی کاری نکند در حالتِ
    // آفلاین گیر می‌کند — حتی اگر شبکه ده دقیقه پیش برگشته باشد.
    reportNetworkResult(true)
    reportNetworkResult(true)
    expect(onlineManager.isOnline()).toBe(false)

    await jest.advanceTimersByTimeAsync(15_000)
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/health'),
      expect.objectContaining({ method: 'GET' }),
    )
    expect(onlineManager.isOnline()).toBe(true)
  })

  it('اگر سنجش هم شکست بخورد آفلاین می‌ماند', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('still offline')) as unknown as typeof fetch
    reportNetworkResult(true)
    reportNetworkResult(true)

    await jest.advanceTimersByTimeAsync(15_000)
    expect(onlineManager.isOnline()).toBe(false)
  })
})
