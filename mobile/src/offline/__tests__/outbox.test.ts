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

import { clearOutbox, drain, discard, enqueue, listOutbox, retryItem } from '../outbox'
import { setTokens } from '../../api/client'
import { resetNetworkState } from '../network'
import type { SalesInvoiceIn, TreasuryTxnIn } from '../../api/types'

// **بدنه‌های واقعی، نه شیءِ دلخواه.** `enqueue` تایپ‌دار است تا نامِ فیلدِ اشتباه
// سرِ کامپایل قرمز شود نه سرِ مشتری با ۴۲۲.
const invoice = (): SalesInvoiceIn => ({
  invoice_date: '2026-09-10',
  warehouse_id: 'wh-1',
  lines: [{ item_id: 'it-1', qty: '1', unit_price: '1000' }],
})
const txn = (amount = '1000'): TreasuryTxnIn => ({
  transaction_date: '2026-09-10',
  contact_id: 'c-1',
  amount,
  method: 'cash',
})

// صف حالا از `apiPost`ِ مشترک رد می‌شود، پس پاسخ باید `json()` داشته باشد —
// همان‌جا که کلاینت `detail`ِ فارسیِ خطا را بیرون می‌کشد.
const ok = { ok: true, status: 201, json: async () => ({ id: 'x', number: 12 }) }
const fail = (status: number, detail?: string) => ({
  ok: false,
  status,
  json: async () => (detail ? { detail } : {}),
})

let fetchMock: jest.Mock

beforeEach(async () => {
  mockDisk = null
  fetchMock = jest.fn().mockResolvedValue(ok)
  global.fetch = fetchMock as unknown as typeof fetch
  onlineManager.setOnline(true)
  // صف حالا از کلاینتِ مشترک رد می‌شود، و آن کلاینت لایه‌ی تشخیصِ آفلاین را
  // تغذیه می‌کند: بعد از دو شکستِ پیاپی یک `setInterval` هر ۱۵ ثانیه می‌سازد.
  // بدونِ این پاک‌سازی، jest تمام نمی‌شود.
  resetNetworkState()
  setTokens(null, null)
  await clearOutbox()
})

afterEach(() => {
  resetNetworkState()
  setTokens(null, null)
})

describe('کلیدِ idempotency', () => {
  it('در تلاش‌های پیاپی عوض نمی‌شود', async () => {
    // قلبِ ایمنیِ صف. کلیدِ تازه در تلاشِ دوم = فاکتورِ دوم.
    fetchMock.mockRejectedValue(new Error('offline'))
    await enqueue('salesInvoice', invoice())

    onlineManager.setOnline(true)
    await drain()
    await drain()

    const keys = fetchMock.mock.calls.map((c) => c[1].headers['Idempotency-Key'])
    expect(keys.length).toBeGreaterThanOrEqual(2)
    expect(new Set(keys).size).toBe(1)
  })

  it('دو کارِ متفاوت کلیدهای متفاوت می‌گیرند', async () => {
    fetchMock.mockRejectedValue(new Error('offline'))
    await enqueue('receipt', txn())
    await enqueue('receipt', txn())

    const items = await listOutbox()
    expect(items).toHaveLength(2)
    expect(items[0].key).not.toBe(items[1].key)
  })
})

describe('صف‌کردن', () => {
  it('وقتی آفلاین است کار را نگه می‌دارد', async () => {
    onlineManager.setOnline(false)
    await enqueue('salesInvoice', invoice())

    expect(fetchMock).not.toHaveBeenCalled()
    expect(await listOutbox()).toHaveLength(1)
  })

  it('وقتی آنلاین است فوراً می‌فرستد و از صف پاک می‌کند', async () => {
    await enqueue('salesInvoice', invoice())
    expect(await listOutbox()).toHaveLength(0)
  })

  it('هدرِ replay را می‌فرستد تا سقفِ اعتبار سرِ همگام‌سازی نگیرد', async () => {
    // آن فروش قبلاً انجام شده و کالایش رفته؛ ردّش یعنی نابودکردنِ کارِ فروشنده.
    await enqueue('salesInvoice', invoice())
    expect(fetchMock.mock.calls[0][1].headers['X-Cubita-Offline-Replay']).toBe('1')
  })
})

describe('رفتار در برابرِ خطا', () => {
  it('خطای شبکه یعنی بماند و بعداً دوباره', async () => {
    fetchMock.mockRejectedValue(new Error('offline'))
    await enqueue('receipt', txn())

    const items = await listOutbox()
    expect(items).toHaveLength(1)
    expect(items[0].attempts).toBe(1)
    expect(items[0].rejectedReason).toBeUndefined()
  })

  it('۵۰۰ هم یعنی بماند — مشکل سمتِ سرور است نه کار', async () => {
    fetchMock.mockResolvedValue(fail(500))
    await enqueue('payment', txn())
    expect((await listOutbox())[0].rejectedReason).toBeUndefined()
  })

  it('۴۰۱ یعنی بماند — نشست خراب است نه کار', async () => {
    // اگر اینجا دور می‌ریختیم، کارِ کاربر به‌خاطر انقضای توکن نابود می‌شد.
    fetchMock.mockResolvedValue(fail(401))
    await enqueue('receipt', txn())
    const items = await listOutbox()
    expect(items).toHaveLength(1)
    expect(items[0].rejectedReason).toBeUndefined()
  })

  it('ردِ سرور سرِ ثبت پرتاب می‌شود و در صف نمی‌ماند', async () => {
    // کاربر همین حالا جلوی گوشی ایستاده و می‌تواند اشکال را درست کند. پارک‌کردنش
    // یعنی فرم بسته شود و کار به فهرستی برود که باید بعداً کشفش کند.
    fetchMock.mockResolvedValue(fail(422, 'سقفِ اعتبارِ این مشتری پر است'))

    await expect(enqueue('salesInvoice', invoice())).rejects.toMatchObject({
      message: 'سقفِ اعتبارِ این مشتری پر است',
    })
    expect(await listOutbox()).toHaveLength(0)
  })

  it('ردِ حینِ drain پارک می‌شود — با پیامِ خودِ سرور', async () => {
    // اینجا کاربر نیست، پس کار نباید بی‌صدا ناپدید شود. و پیام باید همان چیزی
    // باشد که سرور گفت: «موجودیِ انبار کافی نیست» از «حساب بسته است» باید قابلِ
    // تشخیص باشد، وگرنه کاربر می‌داند چیزی ثبت نشده ولی نه اینکه چرا.
    onlineManager.setOnline(false)
    await enqueue('salesInvoice', invoice())
    onlineManager.setOnline(true)

    fetchMock.mockResolvedValue(fail(422, 'موجودیِ انبار کافی نیست'))
    await drain()

    const items = await listOutbox()
    expect(items).toHaveLength(1)
    expect(items[0].rejectedReason).toBe('موجودیِ انبار کافی نیست')
  })

  it('آیتمِ ردشده در تلاش‌های بعدی دوباره فرستاده نمی‌شود', async () => {
    onlineManager.setOnline(false)
    await enqueue('salesInvoice', invoice())
    onlineManager.setOnline(true)
    fetchMock.mockResolvedValue(fail(422, 'رد شد'))
    await drain()
    fetchMock.mockClear()

    await drain()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('صف توکن را خودش تزریق می‌کند — drain پارامتر نمی‌گیرد', async () => {
    // باگِ واقعی: `App.tsx` سرِ بازگشتِ شبکه `drain()` را بدونِ توکن صدا می‌زد و
    // هر تلاشِ خودکار ۴۰۱ می‌گرفت؛ کار تا ابد در صف می‌ماند.
    setTokens('tok-123', null)
    onlineManager.setOnline(false)
    await enqueue('receipt', txn())
    onlineManager.setOnline(true)

    await drain()
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer tok-123')
  })
})

describe('ترتیب', () => {
  it('روی اولین شکستِ شبکه متوقف می‌شود', async () => {
    // ادامه‌دادن فقط شمارنده‌ی تلاشِ بقیه را بی‌دلیل بالا می‌برد.
    onlineManager.setOnline(false)
    await enqueue('receipt', txn())
    await enqueue('receipt', txn())
    await enqueue('receipt', txn())

    onlineManager.setOnline(true)
    fetchMock.mockRejectedValue(new Error('offline'))
    await drain()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const items = await listOutbox()
    expect(items.map((i) => i.attempts)).toEqual([1, 0, 0])
  })

  it('وقتی آفلاین است اصلاً تلاش نمی‌کند', async () => {
    onlineManager.setOnline(false)
    await enqueue('receipt', txn())
    fetchMock.mockClear()

    await drain()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('حذفِ دستی', () => {
  it('کاربر می‌تواند آیتمِ ردشده را دور بیندازد', async () => {
    // رد سرِ ثبت پرتاب می‌شود، پس موردِ پارک‌شده از مسیرِ `drain` می‌آید.
    onlineManager.setOnline(false)
    await enqueue('salesInvoice', invoice())
    onlineManager.setOnline(true)
    fetchMock.mockResolvedValue(fail(422, 'رد شد'))
    await drain()

    const [item] = await listOutbox()
    expect(item.rejectedReason).toBe('رد شد')

    await discard(item.key)
    expect(await listOutbox()).toHaveLength(0)
  })
})

describe('تلاشِ دوباره‌ی دستی', () => {
  /** یک موردِ ردشده می‌سازد (رد فقط حینِ drain پارک می‌شود). */
  async function parkRejected(): Promise<string> {
    onlineManager.setOnline(false)
    await enqueue('salesInvoice', invoice())
    onlineManager.setOnline(true)
    fetchMock.mockResolvedValue(fail(422, 'موجودیِ انبار کافی نیست'))
    await drain()
    return (await listOutbox())[0].key
  }

  it('موردِ ردشده را دوباره می‌فرستد و در موفقیت پاک می‌کند', async () => {
    // علتِ رد اغلب بیرونِ سند است و درست می‌شود: انبار شارژ شد، سقفِ اعتبار بالا
    // رفت. بدونِ این، تنها راهِ باقی‌مانده حذف بود — یعنی دور ریختنِ کارِ کاربر.
    const key = await parkRejected()
    fetchMock.mockResolvedValue(ok)

    expect(await retryItem(key)).toBe('sent')
    expect(await listOutbox()).toHaveLength(0)
  })

  it('اگر باز هم رد شد، پیامِ تازه می‌نشیند', async () => {
    const key = await parkRejected()
    fetchMock.mockResolvedValue(fail(422, 'حسابِ این شخص بسته است'))

    expect(await retryItem(key)).toBe('rejected')
    expect((await listOutbox())[0].rejectedReason).toBe('حسابِ این شخص بسته است')
  })

  it('اگر فقط شبکه بود، علامتِ رد برداشته می‌شود تا drain دوباره سراغش برود', async () => {
    // وگرنه یک قطعیِ لحظه‌ای، کار را برای همیشه از چرخه‌ی خودکار بیرون می‌گذاشت.
    const key = await parkRejected()
    fetchMock.mockRejectedValue(new Error('offline'))

    expect(await retryItem(key)).toBe('retry')
    expect((await listOutbox())[0].rejectedReason).toBeUndefined()
  })

  it('کلیدِ idempotency در تلاشِ دستی هم عوض نمی‌شود', async () => {
    // اگر عوض می‌شد، «تلاشِ دوباره» روی کاری که سرور *گرفته* بود یعنی سندِ دوم.
    const key = await parkRejected()
    fetchMock.mockClear()
    fetchMock.mockResolvedValue(ok)
    await retryItem(key)

    expect(fetchMock.mock.calls[0][1].headers['Idempotency-Key']).toBe(key)
  })
})
