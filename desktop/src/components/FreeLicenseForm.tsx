import { useEffect, useState } from 'react'
import { Gift } from 'lucide-react'
import { activateFreeLicense, sendFreeLicenseCode, type LicenseInfo } from '../api'
import { FREE_SEATS } from '../lib/license'

const fa = (n: number) => n.toLocaleString('fa-IR')
const RESEND_SECONDS = 60
//: فقط شکل را می‌سنجد تا دکمه بی‌خود فعال نشود؛ سنجشِ واقعی (و یکدست‌کردنِ +۹۸ و ارقامِ فارسی) کارِ سرور است.
const digitsOf = (s: string) => s.replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d))).replace(/\D/g, '')

/**
 * ثبت‌نامِ رایگانِ «کوبیتا سازمانی» — نامِ سازمان و شماره‌ی همراه، کدِ پیامکی، و مجوزِ دائمیِ رایگان
 * (تا سه کاربر) روی همین سرور.
 *
 * خودِ سرور با ابر حرف می‌زند، نه این رایانه؛ پس اینترنتِ سرور لازم است و نبودنش پیامِ «کدِ درخواست»
 * را برمی‌گرداند. کد به همین سرور گره است: کدی که روی سرورِ دیگری وارد شود کار نمی‌کند.
 */
export function FreeLicenseForm({
  token,
  defaultOrg,
  disabled,
  onInstalled,
}: {
  token: string
  defaultOrg: string
  disabled: boolean
  onInstalled: (next: LicenseInfo) => Promise<void>
}) {
  const [org, setOrg] = useState(defaultOrg)
  const [phone, setPhone] = useState('')
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState<'send' | 'verify' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [wait, setWait] = useState(0)

  useEffect(() => {
    if (wait <= 0) return
    const t = window.setTimeout(() => setWait((w) => w - 1), 1000)
    return () => window.clearTimeout(t)
  }, [wait])

  const phoneOk = digitsOf(phone).length >= 10
  const codeOk = digitsOf(code).length === 6

  async function send() {
    setBusy('send')
    setError(null)
    try {
      const out = await sendFreeLicenseCode(token, phone.trim())
      setSentTo(out.phone)
      setCode('')
      setWait(RESEND_SECONDS)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'کدِ تأیید فرستاده نشد.')
    } finally {
      setBusy(null)
    }
  }

  async function verify() {
    setBusy('verify')
    setError(null)
    try {
      await onInstalled(await activateFreeLicense(token, phone.trim(), digitsOf(code), org.trim()))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'فعال‌سازیِ رایگان ناموفق بود.')
    } finally {
      setBusy(null)
    }
  }

  const locked = disabled || busy !== null

  return (
    <form
      className="lic-step"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        if (sentTo && codeOk && !locked) void verify()
        else if (!sentTo && phoneOk && !locked) void send()
      }}
    >
      <span className="lic-step-title">
        <Gift size={15} /> ثبت‌نامِ رایگان
      </span>
      <span className="field-hint">رایگان و بی‌انقضا، تا {fa(FREE_SEATS)} کاربر. فقط نامِ سازمان و شماره‌ی همراه لازم است.</span>
      <label className="lic-field">
        <span>نامِ سازمان</span>
        <input type="text" value={org} onChange={(e) => setOrg(e.target.value)} maxLength={200} disabled={locked} />
      </label>
      <label className="lic-field">
        <span>شماره‌ی همراه (مثلِ ۰۹۱۲۱۲۳۴۵۶۷)</span>
        <input
          type="tel"
          dir="ltr"
          inputMode="tel"
          autoComplete="tel"
          value={phone}
          onChange={(e) => {
            setPhone(e.target.value)
            //: شماره‌ی تازه کدِ تازه می‌خواهد؛ کدِ قبلی به شماره‌ی قبلی رفته بود.
            if (sentTo) setSentTo(null)
          }}
          maxLength={20}
          disabled={locked}
        />
      </label>

      {sentTo ? (
        <>
          <label className="lic-field">
            <span>کدِ تأیید</span>
            <input
              type="text"
              dir="ltr"
              inputMode="numeric"
              autoComplete="one-time-code"
              className="lic-activation lic-otp"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={8}
              disabled={locked}
              autoFocus
            />
          </label>
          <span className="field-hint">
            کدِ {fa(6)} رقمی به <bdi dir="ltr">{sentTo}</bdi> فرستاده شد.
          </span>
          <div className="lic-actions">
            <button type="submit" className="btn-primary" disabled={locked || !codeOk}>
              {busy === 'verify' ? 'در حال فعال‌سازی…' : 'فعال‌سازیِ رایگان'}
            </button>
            <button type="button" className="btn-secondary" onClick={send} disabled={locked || wait > 0 || !phoneOk}>
              {wait > 0 ? `ارسالِ دوباره (${fa(wait)})` : 'ارسالِ دوباره'}
            </button>
          </div>
        </>
      ) : (
        <button type="submit" className="btn-primary" disabled={locked || !phoneOk}>
          {busy === 'send' ? 'در حال ارسال…' : 'ارسالِ کدِ تأیید'}
        </button>
      )}

      {error && <p className="error lic-error">{error}</p>}
      <span className="field-hint">
        سرور فقط همین یک‌بار به اینترنت نیاز دارد. کاربرِ بیشتر یا سامانه‌ی مؤدیان با مجوزِ تجاری اضافه می‌شود.
      </span>
    </form>
  )
}
