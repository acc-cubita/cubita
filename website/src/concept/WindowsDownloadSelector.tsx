import { useEffect, useRef, useState } from 'react'
import { Download } from 'lucide-react'
import { suggestWindows, windowsPackage, type WindowsBits, type WindowsHints, type WindowsVersion } from './windowsDownload'

type HintNavigator = Navigator & { userAgentData?: { getHighEntropyValues: (names: string[]) => Promise<WindowsHints> } }

export function WindowsDownloadSelector() {
  const [version, setVersion] = useState<WindowsVersion>('')
  const [bits, setBits] = useState<WindowsBits>('')
  const [suggested, setSuggested] = useState(false)
  const edited = useRef(false)
  useEffect(() => {
    let active = true
    function apply(hints?: WindowsHints) {
      if (!active || edited.current) return
      const result = suggestWindows(navigator.userAgent, hints)
      setVersion(result.version)
      setBits(result.bits)
      setSuggested(Boolean(result.version || result.bits))
    }
    apply()
    const data = (navigator as HintNavigator).userAgentData
    if (data) void data.getHighEntropyValues(['architecture', 'bitness', 'wow64']).then(apply).catch(() => { /* Manual choice works when hints are unavailable. */ })
    return () => { active = false }
  }, [])
  const pkg = windowsPackage(version, bits)
  return (
    <section className="cc-section cc-section-alt" id="windows-download" aria-labelledby="windows-download-title">
      <div className="cc-section-head">
        <h2 id="windows-download-title">نسخهٔ مناسب ویندوز خود را انتخاب کنید</h2>
        <p>کوبیتا سازمانی؛ در همین نصاب می‌توانید نقش «سرور» یا «کلاینت» را انتخاب کنید.</p>
      </div>
      <div className="cc-card cc-windows-selector">
        <p>{suggested ? 'پیشنهاد بر اساس اطلاعات مرورگر است؛ پیش از دانلود، ویندوز و معماری سیستم مقصد را بررسی کنید.' : 'اگر برای رایانهٔ دیگری دانلود می‌کنید، مشخصات همان رایانه را انتخاب کنید.'}</p>
        <div className="cc-windows-fields">
          <label className="cc-field"><span>نسخهٔ ویندوز</span>
            <select value={version} onChange={e => { edited.current = true; setVersion(e.target.value as WindowsVersion) }}>
              <option value="">انتخاب ویندوز</option><option value="7">ویندوز ۷</option><option value="8">ویندوز ۸</option><option value="8.1">ویندوز ۸٫۱</option><option value="10-11">ویندوز ۱۰ و ۱۱</option>
            </select>
          </label>
          <label className="cc-field"><span>معماری ویندوز</span>
            <select value={bits} onChange={e => { edited.current = true; setBits(e.target.value as WindowsBits) }}>
              <option value="">انتخاب معماری</option><option value="32">۳۲ بیتی (x86)</option><option value="64">۶۴ بیتی (x64)</option>
            </select>
          </label>
        </div>
        <p className="cc-windows-result" role="status" aria-live="polite">{pkg.message}</p>
        {pkg.href && <a className="cc-btn cc-btn-primary" href={pkg.href} download><Download size={16} /> دانلود نصاب سازمانی {version === '8.1' ? 'ویندوز ۸٫۱' : 'ویندوز ۱۰ و ۱۱'} — ۶۴ بیتی</a>}
        <details className="cc-windows-help"><summary>از کجا بفهمم ویندوزم چند بیتی است؟</summary>
          <p>در تنظیمات ویندوز، بخش System و سپس About یا در Control Panel بخش System، مقدار «System type» را ببینید. 32-bit یعنی ۳۲ بیتی و64-bit یعنی ۶۴ بیتی. معماری مرورگر ممکن است با معماری ویندوز متفاوت باشد.</p>
          <p>نسخهٔ فعلی برای پردازنده‌های x86/x64 است؛ پشتیبانی از ARM تأیید نشده است.</p>
        </details>
        <p>پیش‌نیازهای لازم در نصاب بررسی و در صورت نیاز نصب می‌شوند. گزارش خطاهای نصب در پوشهٔ <bdi dir="ltr">C:\ProgramData\Cubita\logs</bdi> ثبت می‌شود؛ مسیر دقیق در پیام خطا نمایش داده می‌شود.</p>
      </div>
    </section>
  )
}
