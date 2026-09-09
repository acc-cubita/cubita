/**
 * دروازه‌ی ضدِ اسکنِ تکراری.
 *
 * **مسئله:** `onBarcodeScanned` مادامی که بارکد در کادر است پشتِ‌سرِ هم شلیک
 * می‌کند — ده‌ها بار در ثانیه. بدونِ دروازه، یک بار گرفتنِ گوشی جلوی جعبه یعنی
 * «۳۰ عدد شمرده شد». هیچ خطایی هم نمی‌دهد؛ فقط انبارگردانیِ غلط.
 *
 * دو مهلت، چون دو رفتارِ متفاوت‌اند:
 * - `anyScanMs` — بعد از هر اسکنِ پذیرفته‌شده، لحظه‌ای همه‌چیز بسته است تا کاربر
 *   بازخوردِ روی صفحه را ببیند.
 * - `sameCodeMs` — *همان* بارکد مهلتِ بلندتری دارد. کاربر معمولاً گوشی را چند
 *   ثانیه جلوی جعبه نگه می‌دارد؛ در آن بازه یک کالای دیگر می‌تواند عمداً اسکن
 *   شود، ولی همین یکی نه.
 *
 * جدا از کامپوننت است تا بشود تستش کرد — دقیقاً همان چیزی که روی دستگاه
 * سخت دیده می‌شود ولی در دفتر خیلی گران تمام می‌شود.
 */
export interface ScanGateOptions {
  /** مهلتِ عمومی پس از هر اسکنِ پذیرفته‌شده (میلی‌ثانیه). */
  anyScanMs?: number
  /** مهلتِ همان بارکد (میلی‌ثانیه). */
  sameCodeMs?: number
}

export interface ScanGate {
  /** آیا این اسکن باید شمرده شود؟ `now` تزریق می‌شود تا تست به ساعتِ واقعی وابسته نباشد. */
  accept: (code: string, now?: number) => boolean
  /** فراموش‌کردنِ تاریخچه — مثلاً وقتی کاربر عمداً می‌خواهد همان کالا را دوباره بزند. */
  reset: () => void
}

export function createScanGate({ anyScanMs = 700, sameCodeMs = 2_500 }: ScanGateOptions = {}): ScanGate {
  // «هرگز» است، نه «لحظه‌ی صفر». با ۰ اولین اسکن در نزدیکیِ مبدأ زمان رد می‌شد —
  // با ساعتِ واقعی هرگز دیده نمی‌شد، ولی حالتِ اولیه‌ی غلطی است.
  let lastCode: string | null = null
  let lastCodeAt = -Infinity
  let lastAnyAt = -Infinity

  return {
    accept(code, now = Date.now()) {
      if (!code) return false
      if (now - lastAnyAt < anyScanMs) return false
      if (code === lastCode && now - lastCodeAt < sameCodeMs) return false
      lastCode = code
      lastCodeAt = now
      lastAnyAt = now
      return true
    },
    reset() {
      lastCode = null
      lastCodeAt = -Infinity
      lastAnyAt = -Infinity
    },
  }
}
