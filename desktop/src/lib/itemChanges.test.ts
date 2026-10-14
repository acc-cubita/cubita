// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { subscribeItemChanges, withItemChange } from './itemChanges'
import { createItemLive, deleteItemLive, importItems, updateItemLive } from '../api'

afterEach(() => vi.unstubAllGlobals())

describe('تازه‌سازی فهرست پس از تغییر موفق کالا', () => {
  it('ثبت سریع، ویرایش، حذف و ورود گروهی از مسیر واقعی API اعلان می‌دهند', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200 })))
    const refresh = vi.fn().mockResolvedValue(undefined)
    const stop = subscribeItemChanges(refresh, vi.fn())
    try {
      await createItemLive('token', { name: 'کالای تازه', sku: 'NEW', unit: 'عدد' })
      await updateItemLive('token', 'new', { name: 'نام تازه' })
      await deleteItemLive('token', 'new')
      await importItems('token', [])
      await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(4))
    } finally { stop() }
  })

  it('ثبت ردشده فهرست را عوض نمی‌کند و خطای سرور حفظ می‌شود', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'کد تکراری است' }), { status: 409 })))
    const refresh = vi.fn()
    const stop = subscribeItemChanges(refresh, vi.fn())
    try {
      await expect(createItemLive('token', { name: 'کالا', sku: 'OLD', unit: 'عدد' })).rejects.toThrow('کد تکراری')
      expect(refresh).not.toHaveBeenCalled()
    } finally { stop() }
  })

  it('تغییر دوم حین دریافت گم نمی‌شود و درخواست‌های خواندن همزمان نمی‌شوند', async () => {
    let finish!: () => void
    const first = new Promise<void>((resolve) => { finish = resolve })
    const refresh = vi.fn().mockReturnValueOnce(first).mockResolvedValue(undefined)
    const stop = subscribeItemChanges(refresh, vi.fn())
    try {
      await withItemChange(Promise.resolve('first'))
      await withItemChange(Promise.resolve('second'))
      expect(refresh).toHaveBeenCalledTimes(1)
      finish()
      await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(2))
    } finally { stop() }
  })

  it('شکست خواندن ثبت موفق را شکست نشان نمی‌دهد؛ تغییر بعدی قابل تلاش است', async () => {
    const error = new Error('offline')
    const refresh = vi.fn().mockRejectedValueOnce(error).mockResolvedValue(undefined)
    const onError = vi.fn()
    const stop = subscribeItemChanges(refresh, onError)
    try {
      await expect(withItemChange(Promise.resolve('saved'))).resolves.toBe('saved')
      await vi.waitFor(() => expect(onError).toHaveBeenCalledWith(error))
      await withItemChange(Promise.resolve('saved again'))
      await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(2))
      stop()
      await withItemChange(Promise.resolve('after unmount'))
      expect(refresh).toHaveBeenCalledTimes(2)
    } finally { stop() }
  })
})
