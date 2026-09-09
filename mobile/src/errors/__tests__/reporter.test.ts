/**
 * تستِ گزارشگرِ کرش.
 *
 * **چرا مهم است:** این ماژول دقیقاً وقتی اجرا می‌شود که اپ در حالِ شکستن است. اگر
 * خودش خطا بدهد، کاربر به‌جای یک کرش، دو تا می‌بیند و ما هیچ‌کدام را نمی‌فهمیم.
 * پس آنچه اینجا سنجیده می‌شود «آیا کار می‌کند» نیست — «آیا در بدترین حالت هم
 * ساکت می‌ماند» است.
 */

// فایل‌سیستمِ درون‌حافظه‌ای به‌جای دیسکِ واقعی.
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
      mockDisk = mockDisk ?? '[]'
    }
    async text() {
      if (mockDisk === null) throw new Error('no such file')
      return mockDisk
    }
    write(content: string) {
      if (mockFailWrites) throw new Error('disk full')
      mockDisk = content
    }
  },
}))

jest.mock('expo-application', () => ({ nativeApplicationVersion: '1.7.0' }))
jest.mock('expo-device', () => ({ osVersion: '14', modelName: 'Pixel 7' }))

import { flush, report, setCurrentScreen } from '../reporter'

const queued = (): unknown[] => (mockDisk ? JSON.parse(mockDisk) : [])

let fetchMock: jest.Mock

beforeEach(() => {
  mockDisk = null
  mockFailWrites = false
  // پیش‌فرض «شبکه قطع» است: هم به واقعیتِ لحظه‌ی کرش نزدیک‌تر، هم صف را برای
  // سنجش باقی می‌گذارد. تست‌هایی که ارسالِ موفق را می‌خواهند خودشان ست می‌کنند.
  fetchMock = jest.fn().mockRejectedValue(new Error('offline'))
  global.fetch = fetchMock as unknown as typeof fetch
  setCurrentScreen(null)
})

describe('ثبت', () => {
  it('خطا را با متن و صفحه ثبت می‌کند', async () => {
    setCurrentScreen('Dashboard')
    await report(new Error('چیزی شکست'))

    const [first] = queued() as Array<Record<string, unknown>>
    expect(first).toMatchObject({
      name: 'Error',
      message: 'چیزی شکست',
      screen: 'Dashboard',
      app_version: '1.7.0',
      fatal: false,
    })
    expect(typeof first.stack === 'string' || first.stack === null).toBe(true)
  })

  it('چیزی که Error نیست هم پذیرفته می‌شود', async () => {
    // throw 'رشته' در جاوااسکریپت قانونی است و واقعاً اتفاق می‌افتد.
    await report('یک رشته‌ی خام')
    expect((queued()[0] as { message: string }).message).toBe('یک رشته‌ی خام')
  })

  it('fatal را جدا علامت می‌زند', async () => {
    await report(new Error('مرگبار'), true)
    expect((queued()[0] as { fatal: boolean }).fatal).toBe(true)
  })
})

describe('مقاومت — هیچ‌کدام نباید throw کنند', () => {
  it('اگر دیسک پر باشد بی‌صدا رد می‌شود', async () => {
    mockFailWrites = true
    await expect(report(new Error('x'))).resolves.toBeUndefined()
  })

  it('اگر فایلِ صف خراب باشد، از صفر شروع می‌کند', async () => {
    mockDisk = 'این JSON نیست {{{'
    await expect(report(new Error('x'))).resolves.toBeUndefined()
    expect(queued()).toHaveLength(1)
  })

  it('اگر شبکه قطع باشد گزارش را نگه می‌دارد', async () => {
    await report(new Error('x'))
    // نرفت، پس باید هنوز روی دیسک باشد تا دفعه‌ی بعد.
    expect(queued()).toHaveLength(1)
  })

  it('۴۰۴ (اندپوینتِ هنوز مستقرنشده) گزارش را دور نمی‌ریزد', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 404 })
    await report(new Error('x'))
    expect(queued()).toHaveLength(1)
  })
})

describe('سقفِ صف', () => {
  it('بیش از ۵۰ گزارش نگه نمی‌دارد و تازه‌ترین‌ها را حفظ می‌کند', async () => {
    // یک حلقه‌ی خطا می‌تواند هزاران گزارش بسازد؛ بدونِ سقف حافظه‌ی گوشی پر می‌شود.
    for (let i = 0; i < 60; i += 1) await report(new Error(`e${i}`))

    const q = queued() as Array<{ message: string }>
    expect(q).toHaveLength(50)
    expect(q[q.length - 1].message).toBe('e59')
    expect(q[0].message).toBe('e10')
  })
})

describe('ارسال', () => {
  it('بعد از ارسالِ موفق صف را خالی می‌کند', async () => {
    await report(new Error('x'))
    expect(queued()).toHaveLength(1)

    fetchMock.mockResolvedValue({ ok: true })
    await flush()
    expect(queued()).toHaveLength(0)
  })

  it('توکنِ احراز نمی‌فرستد — گزارش نباید کاربر را لاگ‌اوت کند', async () => {
    fetchMock.mockResolvedValue({ ok: true })
    await report(new Error('x'))
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
  })

  it('وقتی صف خالی است اصلاً درخواستی نمی‌زند', async () => {
    await flush()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
