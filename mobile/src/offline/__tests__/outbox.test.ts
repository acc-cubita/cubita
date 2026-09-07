/**
 * صفِ نوشتنِ آفلاین.
 *
 * مهم‌ترین چیزی که اینجا سنجیده می‌شود **کلیدِ ثابت** است. اگر تلاشِ دوم کلیدِ
 * تازه بگیرد، محافظتِ idempotencyِ بک‌اند بی‌اثر می‌شود و همان فاکتور دو بار
 * ثبت می‌شود — بدونِ هیچ خطایی، فقط دفترِ غلط.
 */
let mockDisk: string | null = null

jest.mock('expo-file-system', () => ({
  Paths: { document: '/doc' },
  File: class {
    get exists() {
      return mockDisk !== null
    }
    create() {
      mockDisk = mockDisk ?? ''
    }
    async text() {
      if (mockDisk === null) throw new Error('missing')
      return mockDisk
    }
    write(content: string) {
      mockDisk = content
    }
    delete() {
      mockDisk = null
    }
  },
}))

import { onlineManager } from '@tanstack/react-query'

import { clearOutbox, drain, discard, enqueue, listOutbox } from '../outbox'

const ok = { ok: true, status: 201 }
const fail = (status: number) => ({ ok: false, status })

let fetchMock: jest.Mock

beforeEach(async () => {
  mockDisk = null
  fetchMock = jest.fn().mockResolvedValue(ok)
  global.fetch = fetchMock as unknown as typeof fetch
  onlineManager.setOnline(true)
  await clearOutbox()
})

describe('کلیدِ idempotency', () => {
  it('در تلاش‌های پیاپی عوض نمی‌شود', async () => {
    // قلبِ ایمنیِ صف. کلیدِ تازه در تلاشِ دوم = فاکتورِ دوم.
    fetchMock.mockRejectedValue(new Error('offline'))
    await enqueue('salesInvoice', { total: 100 })

    onlineManager.setOnline(true)
    await drain()
    await drain()

    const keys = fetchMock.mock.calls.map((c) => c[1].headers['Idempotency-Key'])
    expect(keys.length).toBeGreaterThanOrEqual(2)
    expect(new Set(keys).size).toBe(1)
  })

  it('دو کارِ متفاوت کلیدهای متفاوت می‌گیرند', async () => {
    fetchMock.mockRejectedValue(new Error('offline'))
    await enqueue('receipt', { amount: 1 })
    await enqueue('receipt', { amount: 2 })

    const items = await listOutbox()
    expect(items).toHaveLength(2)
    expect(items[0].key).not.toBe(items[1].key)
  })
})

describe('صف‌کردن', () => {
  it('وقتی آفلاین است کار را نگه می‌دارد', async () => {
    onlineManager.setOnline(false)
    await enqueue('salesInvoice', { total: 500 })

    expect(fetchMock).not.toHaveBeenCalled()
    expect(await listOutbox()).toHaveLength(1)
  })

  it('وقتی آنلاین است فوراً می‌فرستد و از صف پاک می‌کند', async () => {
    await enqueue('salesInvoice', { total: 500 })
    expect(await listOutbox()).toHaveLength(0)
  })

  it('هدرِ replay را می‌فرستد تا سقفِ اعتبار سرِ همگام‌سازی نگیرد', async () => {
    // آن فروش قبلاً انجام شده و کالایش رفته؛ ردّش یعنی نابودکردنِ کارِ فروشنده.
    await enqueue('salesInvoice', { total: 1 })
    expect(fetchMock.mock.calls[0][1].headers['X-Cubita-Offline-Replay']).toBe('1')
  })
})

describe('رفتار در برابرِ خطا', () => {
  it('خطای شبکه یعنی بماند و بعداً دوباره', async () => {
    fetchMock.mockRejectedValue(new Error('offline'))
    await enqueue('receipt', { amount: 10 })

    const items = await listOutbox()
    expect(items).toHaveLength(1)
    expect(items[0].attempts).toBe(1)
    expect(items[0].rejectedReason).toBeUndefined()
  })

  it('۵۰۰ هم یعنی بماند — مشکل سمتِ سرور است نه کار', async () => {
    fetchMock.mockResolvedValue(fail(500))
    await enqueue('payment', { amount: 10 })
    expect((await listOutbox())[0].rejectedReason).toBeUndefined()
  })

  it('۴۰۱ یعنی بماند — نشست خراب است نه کار', async () => {
    // اگر اینجا دور می‌ریختیم، کارِ کاربر به‌خاطر انقضای توکن نابود می‌شد.
    fetchMock.mockResolvedValue(fail(401))
    await enqueue('receipt', { amount: 10 })
    const items = await listOutbox()
    expect(items).toHaveLength(1)
    expect(items[0].rejectedReason).toBeUndefined()
  })

  it('۴۲۲ یعنی سرور نمی‌پذیرد — علامت می‌خورد ولی حذف نمی‌شود', async () => {
    // حذفِ خودکار یعنی کارِ کاربر بی‌صدا ناپدید شود. علامت می‌خورد تا ببیند.
    fetchMock.mockResolvedValue(fail(422))
    await enqueue('salesInvoice', { total: -5 })

    const items = await listOutbox()
    expect(items).toHaveLength(1)
    expect(items[0].rejectedReason).toBeTruthy()
  })

  it('آیتمِ ردشده در تلاش‌های بعدی دوباره فرستاده نمی‌شود', async () => {
    fetchMock.mockResolvedValue(fail(422))
    await enqueue('salesInvoice', { total: -5 })
    fetchMock.mockClear()

    await drain()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('ترتیب', () => {
  it('روی اولین شکستِ شبکه متوقف می‌شود', async () => {
    // ادامه‌دادن فقط شمارنده‌ی تلاشِ بقیه را بی‌دلیل بالا می‌برد.
    onlineManager.setOnline(false)
    await enqueue('receipt', { amount: 1 })
    await enqueue('receipt', { amount: 2 })
    await enqueue('receipt', { amount: 3 })

    onlineManager.setOnline(true)
    fetchMock.mockRejectedValue(new Error('offline'))
    await drain()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const items = await listOutbox()
    expect(items.map((i) => i.attempts)).toEqual([1, 0, 0])
  })

  it('وقتی آفلاین است اصلاً تلاش نمی‌کند', async () => {
    onlineManager.setOnline(false)
    await enqueue('receipt', { amount: 1 })
    fetchMock.mockClear()

    await drain()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('حذفِ دستی', () => {
  it('کاربر می‌تواند آیتمِ ردشده را دور بیندازد', async () => {
    fetchMock.mockResolvedValue(fail(422))
    await enqueue('salesInvoice', { total: -5 })
    const [item] = await listOutbox()

    await discard(item.key)
    expect(await listOutbox()).toHaveLength(0)
  })
})
