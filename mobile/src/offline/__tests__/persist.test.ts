/**
 * ماندگاریِ کشِ خواندنی.
 *
 * دو چیز اینجا از بقیه مهم‌ترند، چون شکستنشان *بی‌صدا* داده‌ی غلط نشان می‌دهد:
 * کشِ کهنه که تازه به‌نظر برسد، و کشی که بعد از خروج نرود.
 */
let mockDisk: string | null = null
let mockFailWrites = false

jest.mock('expo-file-system', () => ({
  Paths: { document: '/doc' },
  File: class {
    get exists() {
      return mockDisk !== null
    }
    create() {
      if (mockFailWrites) throw new Error('disk full')
      mockDisk = mockDisk ?? ''
    }
    async text() {
      if (mockDisk === null) throw new Error('missing')
      return mockDisk
    }
    write(content: string) {
      if (mockFailWrites) throw new Error('disk full')
      mockDisk = content
    }
    delete() {
      mockDisk = null
    }
  },
}))

import { QueryClient } from '@tanstack/react-query'

import { clearCache, loadCache, startPersisting } from '../persist'

const DAY = 24 * 60 * 60 * 1000

/** یک اسنپ‌شاتِ دستی با سنِ دلخواه. */
function seed(ageMs: number, data: unknown = { cash: 12345 }) {
  mockDisk = JSON.stringify({
    savedAt: Date.now() - ageMs,
    state: {
      mutations: [],
      queries: [
        {
          queryKey: ['dashboard'],
          queryHash: '["dashboard"]',
          state: { data, dataUpdatedAt: Date.now() - ageMs, status: 'success', fetchStatus: 'idle' },
        },
      ],
    },
  })
}

let client: QueryClient

beforeEach(() => {
  mockDisk = null
  mockFailWrites = false
  client = new QueryClient({ defaultOptions: { queries: { gcTime: DAY } } })
})

afterEach(() => {
  client.clear()
})

describe('بازیابی', () => {
  it('کشِ تازه را برمی‌گرداند', async () => {
    seed(60_000)
    await expect(loadCache(client)).resolves.toBe(true)
    expect(client.getQueryData(['dashboard'])).toEqual({ cash: 12345 })
  })

  it('کشِ کهنه‌تر از ۲۴ ساعت را دور می‌ریزد', async () => {
    // مهم‌ترین تستِ این فایل: عددِ هفته‌ی پیش که «امروزی» به‌نظر برسد، برای
    // نرم‌افزارِ حسابداری از نبودِ عدد بدتر است.
    seed(DAY + 60_000)
    await expect(loadCache(client)).resolves.toBe(false)
    expect(client.getQueryData(['dashboard'])).toBeUndefined()
    expect(mockDisk).toBeNull() // پاک هم شده باشد
  })

  it('وقتی هیچ کشی نیست بی‌صدا رد می‌شود', async () => {
    await expect(loadCache(client)).resolves.toBe(false)
  })

  it('فایلِ خراب اپ را نمی‌شکند و خودش را پاک می‌کند', async () => {
    mockDisk = 'این JSON نیست {{{'
    await expect(loadCache(client)).resolves.toBe(false)
    expect(mockDisk).toBeNull()
  })

  it('اسنپ‌شاتِ بدونِ savedAt را نامعتبر می‌داند', async () => {
    // نسخه‌ی قدیمیِ ساختار یا فایلِ نصفه‌نوشته.
    mockDisk = JSON.stringify({ state: { queries: [] } })
    await expect(loadCache(client)).resolves.toBe(false)
  })
})

describe('ذخیره', () => {
  it('تغییرِ کش را بعد از مکث روی دیسک می‌نویسد', async () => {
    jest.useFakeTimers()
    const stop = startPersisting(client)

    client.setQueryData(['dashboard'], { cash: 999 })
    expect(mockDisk).toBeNull() // هنوز نه — throttle

    jest.advanceTimersByTime(3_000)
    expect(mockDisk).not.toBeNull()
    expect(JSON.parse(mockDisk as string).state.queries).toHaveLength(1)

    stop()
    jest.useRealTimers()
  })

  it('چند تغییرِ پیاپی فقط یک نوشتن می‌سازد', async () => {
    jest.useFakeTimers()
    const stop = startPersisting(client)

    client.setQueryData(['a'], 1)
    client.setQueryData(['b'], 2)
    client.setQueryData(['c'], 3)
    jest.advanceTimersByTime(3_000)

    // هر سه در یک نوشتن باشند، نه سه نوشتنِ دیسک.
    expect(JSON.parse(mockDisk as string).state.queries).toHaveLength(3)

    stop()
    jest.useRealTimers()
  })

  it('دیسکِ پر اپ را نمی‌شکند', async () => {
    jest.useFakeTimers()
    mockFailWrites = true
    const stop = startPersisting(client)

    client.setQueryData(['dashboard'], { cash: 1 })
    expect(() => jest.advanceTimersByTime(3_000)).not.toThrow()

    stop()
    jest.useRealTimers()
  })

  it('بعد از قطعِ اشتراک دیگر نمی‌نویسد', async () => {
    jest.useFakeTimers()
    const stop = startPersisting(client)
    stop()

    client.setQueryData(['dashboard'], { cash: 1 })
    jest.advanceTimersByTime(10_000)
    expect(mockDisk).toBeNull()

    jest.useRealTimers()
  })
})

describe('خروج از حساب', () => {
  it('کش را پاک می‌کند', () => {
    // روی گوشیِ مشترک، بدونِ این، کاربرِ بعدی اعدادِ کسب‌وکارِ قبلی را می‌بیند.
    seed(60_000)
    clearCache()
    expect(mockDisk).toBeNull()
  })

  it('وقتی کشی نیست هم بی‌خطر است', () => {
    expect(() => clearCache()).not.toThrow()
  })
})
