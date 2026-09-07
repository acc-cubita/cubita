/**
 * وضعیتِ آنلاین/آفلاین — بدونِ کتابخانه‌ی جانبی.
 *
 * **چرا NetInfo نصب نشد:** آنچه واقعاً اهمیت دارد «آیا گوشی وای‌فای دارد» نیست،
 * «آیا بک‌اندِ ما جواب می‌دهد» است. این دو یکی نیستند: وای‌فای هتل که پشتِ صفحه‌ی
 * ورود گیر کرده «متصل» گزارش می‌شود، و اینترنتِ موبایلِ ضعیف هم همین‌طور. کلاینتِ
 * API از قبل دقیقاً همان چیزی را که می‌خواهیم می‌داند: خطای `status: 0` یعنی
 * درخواست اصلاً به سرور نرسید.
 *
 * پس به‌جای افزودنِ یک ماژولِ نیتیو، همان سیگنالِ موجود را به `onlineManager`
 * وصل می‌کنیم — که react-query خودش برای توقفِ retry و ازسرگیریِ خودکار از آن
 * استفاده می‌کند.
 */
import { onlineManager } from '@tanstack/react-query'

import { API_BASE_URL } from '../api/config'

/** بعد از چند شکستِ پیاپیِ شبکه، آفلاین اعلام می‌کنیم. */
const FAILURES_BEFORE_OFFLINE = 2

/** فاصله‌ی تلاش برای فهمیدنِ بازگشتِ شبکه. */
const PROBE_INTERVAL_MS = 15_000

let consecutiveFailures = 0
let probe: ReturnType<typeof setInterval> | null = null

/**
 * یک درخواستِ سبک به health برای فهمیدنِ اینکه شبکه برگشته یا نه.
 *
 * عمداً `/api/health` است نه یک اندپوینتِ داده‌ای: احراز نمی‌خواهد، پاسخش کوچک
 * است، و اگر کاربر خارج شده باشد هم کار می‌کند.
 */
async function reachable(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`, { method: 'GET' })
    return res.ok
  } catch {
    return false
  }
}

function stopProbing(): void {
  if (probe) {
    clearInterval(probe)
    probe = null
  }
}

function startProbing(): void {
  if (probe) return
  probe = setInterval(async () => {
    if (await reachable()) {
      consecutiveFailures = 0
      onlineManager.setOnline(true)
      stopProbing()
    }
  }, PROBE_INTERVAL_MS)
}

/** کلاینتِ API بعد از هر درخواست این را صدا می‌زند. */
export function reportNetworkResult(failed: boolean): void {
  if (!failed) {
    consecutiveFailures = 0
    if (!onlineManager.isOnline()) {
      onlineManager.setOnline(true)
      stopProbing()
    }
    return
  }

  consecutiveFailures += 1
  // یک شکستِ تکی می‌تواند صرفاً یک درخواستِ بدشانس باشد؛ دوتای پیاپی الگوست.
  if (consecutiveFailures >= FAILURES_BEFORE_OFFLINE && onlineManager.isOnline()) {
    onlineManager.setOnline(false)
    startProbing()
  }
}

/** فقط برای تست — وضعیت را به حالتِ اولیه برمی‌گرداند. */
export function resetNetworkState(): void {
  consecutiveFailures = 0
  stopProbing()
  onlineManager.setOnline(true)
}
