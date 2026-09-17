import net from 'node:net'

import { buildPnaMessage, parsePnaResponse } from './pna.js'
import type { PayResult, PosStatus, PosTerminalDriver, PosTerminalProfile } from './types.js'

function nowIso(): string {
  return new Date().toISOString()
}

function randomDigits(len: number): string {
  let s = ''
  for (let i = 0; i < len; i++) s += Math.floor(Math.random() * 10)
  return s
}

// ── شبیه‌ساز: بدونِ سخت‌افزار، برای توسعه/دمو ─────────────────────────────────────
// تأخیرِ کوتاه (مثلِ کشیدنِ واقعیِ کارت) و سپس تأیید/رد بر اساسِ پروفایل. RRN تصادفیِ
// یکتا می‌سازد تا مسیرِ کاملِ ثبتِ حسابداری + idempotency واقعاً تمرین شود.
function simulatorDriver(profile: PosTerminalProfile): PosTerminalDriver {
  return {
    async pay(amountRial, refId): Promise<PayResult> {
      const delay = profile.simulateDelayMs ?? 1200
      await new Promise((r) => setTimeout(r, delay))
      if (profile.simulateOutcome === 'decline') {
        return { approved: false, message: 'تراکنش رد شد (شبیه‌ساز)', psp: 'simulator', datetime: nowIso() }
      }
      return {
        approved: true,
        rrn: `SIM${randomDigits(9)}`,
        traceNo: randomDigits(6),
        cardMask: `6037****${randomDigits(4)}`,
        terminalNo: profile.host || 'SIM-TERMINAL',
        datetime: nowIso(),
        psp: 'simulator',
        raw: { simulated: true, amountRial, refId },
      }
    },
    async status(): Promise<PosStatus> {
      return { online: true, message: 'شبیه‌ساز فعال است' }
    },
  }
}

// ── تحت‌شبکه (TCP): اسکلتِ عمومیِ «کارتخوانِ متصل به رایانه» ───────────────────────
// status اتصالِ TCP را واقعاً می‌آزماید (برای دکمه‌ی «تستِ اتصال»). pay هنوز پروتکلِ
// واقعیِ PSP را ندارد — نقطه‌ی وصلِ درایورِ اختصاصی؛ تا آن زمان با پیامِ روشن رد می‌کند
// تا هرگز بایتِ نامفهوم به دستگاهِ واقعی نفرستد.
function networkTcpDriver(profile: PosTerminalProfile): PosTerminalDriver {
  const host = profile.host || ''
  const port = profile.port || 0

  function connectTest(timeoutMs: number): Promise<PosStatus> {
    return new Promise((resolve) => {
      if (!host || !port) {
        resolve({ online: false, message: 'آدرس یا پورتِ دستگاه تنظیم نشده است' })
        return
      }
      const socket = new net.Socket()
      let settled = false
      const done = (s: PosStatus) => {
        if (settled) return
        settled = true
        socket.destroy()
        resolve(s)
      }
      socket.setTimeout(timeoutMs)
      socket.once('connect', () => done({ online: true, message: `اتصال به ${host}:${port} برقرار شد` }))
      socket.once('timeout', () => done({ online: false, message: 'مهلتِ اتصال تمام شد' }))
      socket.once('error', (err) => done({ online: false, message: `اتصال ناموفق: ${err.message}` }))
      socket.connect(port, host)
    })
  }

  return {
    async pay(): Promise<PayResult> {
      return {
        approved: false,
        message:
          'درایورِ واقعیِ این کارتخوان هنوز فعال نشده است؛ برای اتصالِ واقعی به مستنداتِ پروتکلِ PSP نیاز است. فعلاً «شبیه‌ساز» را انتخاب کنید.',
        psp: profile.psp || 'network',
        datetime: nowIso(),
      }
    },
    status(): Promise<PosStatus> {
      return connectTest(4000)
    },
  }
}

// ── پرداخت نوین آرین (PNA) ────────────────────────────────────────────────────────
// قالبِ پیام از خروجیِ ابزارِ رسمیِ خودِ PNA استخراج شد و `scripts/verify-pna.mjs`
// نگهبانش است. جزئیات در `pna.ts`.
//
// **این درایور عمداً تراکنش را «تأییدشده» اعلام نمی‌کند** — قالبِ پاسخ هنوز دیده
// نشده. دلیلش در `parsePnaResponse` نوشته شده و خلاصه‌اش این است: گفتنِ «رد شد»
// به تراکنشی که شاید تأیید شده، کاربر را به کشیدنِ دوباره‌ی کارت می‌کشانَد.

//: `psp` روی فرم متنِ آزاد است، پس تطبیق مقاوم انجام می‌شود. وقتی PSP دوم اضافه
//: شد، این باید فهرستِ صریح شود نه تطبیقِ متنی.
const PNA_MARKERS = ['pna', 'پرداخت نوین', 'نوین آرین', 'fanap', 'فناپ']

export function isPna(psp: string | undefined): boolean {
  const v = (psp || '').trim().toLowerCase()
  return v !== '' && PNA_MARKERS.some((m) => v.includes(m.toLowerCase()))
}

function tcpRoundTrip(host: string, port: number, payload: string, timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const socket = new net.Socket()
    let out = ''
    let settled = false
    const done = (err: Error | null) => {
      if (settled) return
      settled = true
      socket.destroy()
      err ? reject(err) : resolve(out)
    }
    socket.setTimeout(timeoutMs)
    socket.once('connect', () => socket.write(payload))
    socket.on('data', (chunk) => {
      out += chunk.toString('utf8')
      //: کشیدنِ کارت طول می‌کشد؛ دستگاه ممکن است پاسخ را تکه‌تکه بفرستد. تا
      //: بسته‌شدنِ اتصال یا مهلت صبر می‌کنیم، نه تا اولین تکه.
    })
    socket.once('timeout', () => done(out ? null : new Error('مهلتِ پاسخِ دستگاه تمام شد')))
    socket.once('error', (e) => done(new Error(`ارتباط با دستگاه برقرار نشد: ${e.message}`)))
    socket.once('close', () => done(null))
    socket.connect(port, host)
  })
}

function pnaDriver(profile: PosTerminalProfile): PosTerminalDriver {
  const host = profile.host || ''
  const port = profile.port || 0

  return {
    async pay(amountRial, refId): Promise<PayResult> {
      if (!host || !port) {
        return { approved: false, message: 'آدرس یا پورتِ دستگاه تنظیم نشده است', psp: 'pna', datetime: nowIso() }
      }
      let message: string
      try {
        //: `refId` کلیدِ یکتاییِ ماست نه شماره‌ی قبض؛ در «داده‌ی اضافی» می‌رود تا
        //: اگر روی رسیدِ دستگاه چاپ شد، تطبیقِ دستی ممکن باشد.
        message = buildPnaMessage({
          amount: String(Math.round(amountRial)),
          additionalData: refId.slice(0, 99),
        })
      } catch (e) {
        return {
          approved: false,
          message: e instanceof Error ? e.message : 'ساختِ پیامِ کارتخوان ممکن نشد',
          psp: 'pna',
          datetime: nowIso(),
        }
      }

      let raw: string
      try {
        //: مهلت بلند است چون کاربر باید کارت بکشد و رمز بزند.
        raw = await tcpRoundTrip(host, port, message, 120000)
      } catch (e) {
        return {
          approved: false,
          message: e instanceof Error ? e.message : 'خطا در ارتباط با کارتخوان',
          psp: 'pna',
          datetime: nowIso(),
          raw: { sent: message },
        }
      }

      const parsed = parsePnaResponse(raw)
      return {
        approved: parsed.outcome === 'approved',
        message: parsed.message,
        psp: 'pna',
        datetime: nowIso(),
        raw: { sent: message, received: parsed.raw, fields: parsed.fields },
      }
    },

    status(): Promise<PosStatus> {
      return new Promise((resolve) => {
        if (!host || !port) {
          resolve({ online: false, message: 'آدرس یا پورتِ دستگاه تنظیم نشده است' })
          return
        }
        const socket = new net.Socket()
        let settled = false
        const done = (s: PosStatus) => {
          if (settled) return
          settled = true
          socket.destroy()
          resolve(s)
        }
        socket.setTimeout(4000)
        socket.once('connect', () => done({ online: true, message: `اتصال به ${host}:${port} برقرار شد` }))
        socket.once('timeout', () => done({ online: false, message: 'مهلتِ اتصال تمام شد' }))
        socket.once('error', (err) => done({ online: false, message: `اتصال ناموفق: ${err.message}` }))
        socket.connect(port, host)
      })
    },
  }
}

// ── استاب‌های سریال و SDK: تا زمانِ مشخص‌شدنِ دستگاه ─────────────────────────────
function unimplementedDriver(kind: string): PosTerminalDriver {
  const message = `اتصالِ «${kind}» هنوز پیاده‌سازی نشده است؛ فعلاً از «شبیه‌ساز» یا «تحت‌شبکه» استفاده کنید.`
  return {
    async pay(): Promise<PayResult> {
      return { approved: false, message, datetime: nowIso() }
    },
    async status(): Promise<PosStatus> {
      return { online: false, message }
    },
  }
}

export function driverFor(profile: PosTerminalProfile): PosTerminalDriver {
  switch (profile.transport) {
    case 'simulator':
      return simulatorDriver(profile)
    case 'network':
      //: PSPِ شناخته‌شده درایورِ خودش را می‌گیرد؛ بقیه به اسکلتِ عمومی می‌افتند
      //: که صادقانه رد می‌کند. پیش‌فرض = رفتارِ دیروز.
      return isPna(profile.psp) ? pnaDriver(profile) : networkTcpDriver(profile)
    case 'serial':
      return unimplementedDriver('سریال/USB')
    case 'sdk':
      return unimplementedDriver('SDK اختصاصی')
    default:
      return unimplementedDriver('نامشخص')
  }
}
