import { useEffect, useRef, useState } from 'react'
import { Download, Laptop, RefreshCw } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { toFaDigits } from '../lib/jalali'
import { updateProblem, type UpdateStatus } from '../lib/updateStatus'

export function ClientUpdateCard() {
  const [status, setStatus] = useState<UpdateStatus>({ state: 'idle' })
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const bridge = window.cubitaUpdate
  useEffect(() => {
    if (!bridge) return
    let active = true
    // رویداد تازه بر پاسخ قدیمی status مقدم است.
    let received = false
    const stop = bridge.onStatus((next) => { received = true; if (active) setStatus(next) })
    void bridge.status().then((next) => { if (active && !received) setStatus(next) }).catch(() => {})
    return () => { active = false; stop() }
  }, [bridge])
  if (!bridge || window.cubitaConfig?.edition !== 'enterprise') return null
  const working = busy || ['checking', 'available', 'downloading', 'verifying'].includes(status.state)
  async function check() {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    try {
      if (!bridge?.check) throw new Error('این نسخه بررسی دستی ندارد؛ یک‌بار نصاب تازه را روی این رایانه اجرا کنید.')
      setStatus(await bridge.check())
    } catch (error) { setStatus({ state: 'error', message: updateProblem(error, true) }) }
    finally { busyRef.current = false; setBusy(false) }
  }
  async function install() {
    if (!window.confirm('کارهای در حال انجام را ذخیره کنید. این برنامه برای نصب آپدیت بسته و دوباره باز می‌شود. ادامه می‌دهید؟')) return
    try { await bridge?.installNow() }
    catch (error) { setStatus({ state: 'error', message: updateProblem(error, true) }) }
  }
  return (
    <SectionCard icon={Laptop} title="به‌روزرسانی این رایانه از سرور" description="دریافت از شبکه داخلی؛ اینترنتِ کلاینت لازم نیست."
      actions={<button type="button" className="btn-secondary" disabled={working || status.state === 'ready'} onClick={check}>
        <RefreshCw size={15} className={working ? 'spin' : ''} />{working ? 'در حال دریافت…' : 'بررسی آپدیت از سرور'}
      </button>}>
      <dl className="lic-facts">
        <dt>نسخه این رایانه</dt><dd dir="ltr">{toFaDigits(window.cubitaConfig.version ?? '—')}</dd>
        <dt>سرور دریافت فایل</dt><dd dir="ltr" className="client-update-server">{window.cubitaConfig.serverUrl ?? 'تنظیم نشده'}</dd>
      </dl>
      <div role="status" aria-live="polite">
        {status.state === 'idle' && <p className="muted">برای دریافت آخرین نسخه، بررسی آپدیت را بزنید.</p>}
        {status.state === 'checking' && <p className="muted">در حال بررسی نسخه روی سرور…</p>}
        {status.state === 'available' && <p className="muted">نسخه {toFaDigits(status.version)} در حال دریافت است…</p>}
        {status.state === 'downloading' && <p className="muted">دانلود: {toFaDigits(String(status.percent))}٪ <progress max={100} value={status.percent} aria-label="پیشرفت دانلود آپدیت" /></p>}
        {status.state === 'verifying' && <p className="muted">در حال بررسی امضا و سلامت فایل…</p>}
        {status.state === 'none' && <p className="success-text">این رایانه با آخرین نسخه ارائه‌شده توسط سرور به‌روز است.</p>}
        {status.state === 'error' && <p className="error">{status.message}</p>}
        {status.state === 'ready' && <p className="success-text">نسخه {toFaDigits(status.version)} آماده نصب است.</p>}
      </div>
      {status.state === 'ready' && <button type="button" className="btn-primary" onClick={install}><Download size={15} />نصب و راه‌اندازی مجدد</button>}
      <p className="muted lic-footnote">مدیر ابتدا سرور را به‌روز و نصاب هم‌نسخه را روی آن آماده می‌کند؛ سپس کلاینت‌ها فایل امضاشده را فقط از همین سرور می‌گیرند. پیش از بستن برنامه کارهای خود را ذخیره کنید.</p>
    </SectionCard>
  )
}
