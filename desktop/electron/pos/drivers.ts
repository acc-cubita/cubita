import net from 'node:net'

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
      return networkTcpDriver(profile)
    case 'serial':
      return unimplementedDriver('سریال/USB')
    case 'sdk':
      return unimplementedDriver('SDK اختصاصی')
    default:
      return unimplementedDriver('نامشخص')
  }
}
