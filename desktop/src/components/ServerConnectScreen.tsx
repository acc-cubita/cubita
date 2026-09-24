import { useState } from 'react'
import { ArrowLeft, CheckCircle2, Network, Server, ShieldCheck, Users } from 'lucide-react'

/**
 * «کوبیتا سازمانی» — اتصالِ این رایانه به سرورِ شرکت.
 *
 * اولین صفحه‌ی کلاینتِ تازه‌نصب، و از صفحه‌ی ورود هم با «تغییرِ سرور» باز می‌شود.
 * آزمایشِ اتصال در main انجام می‌شود (نه fetch از همین‌جا) تا پیش از هر تنظیمِ CORS
 * هم جواب بدهد و بسنجد طرفِ مقابل واقعاً سرورِ کوبیتا سازمانی است. پس از ذخیره،
 * صفحه دوباره بار می‌شود تا همه‌ی درخواست‌ها از نشانیِ تازه شروع شوند.
 */
export function ServerConnectScreen({
  currentUrl,
  onCancel,
}: {
  currentUrl: string | null
  onCancel?: () => void
}) {
  const [address, setAddress] = useState(currentUrl ?? '')
  const [busy, setBusy] = useState<'probe' | 'save' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [verified, setVerified] = useState<string | null>(null)

  async function probe(e?: React.FormEvent) {
    e?.preventDefault()
    setError(null)
    setVerified(null)
    setBusy('probe')
    try {
      const r = await window.cubita.serverProbe!(address)
      if (r.ok) setVerified(r.url)
      else setError(r.error)
    } finally {
      setBusy(null)
    }
  }

  async function save() {
    if (!verified) return
    setError(null)
    setBusy('save')
    try {
      const r = await window.cubita.serverSave!(verified)
      if (r.ok) window.location.reload()
      else setError(r.error)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="login-shell">
      <div className="login-brand">
        <div className="login-brand-blobs" aria-hidden="true">
          <span className="blob blob-1" />
          <span className="blob blob-2" />
          <span className="blob blob-3" />
        </div>
        <div className="login-brand-content">
          <div className="login-brand-mark">C</div>
          <h2 className="login-brand-title">کوبیتا سازمانی</h2>
          <p className="login-brand-tagline">حسابداریِ شرکت، روی سرورِ خودِ شرکت</p>
          <ul className="login-brand-features">
            <li>
              <span className="login-brand-feature-icon">
                <Server size={16} />
              </span>
              داده روی سرورِ شرکت می‌ماند و از شبکه‌ی داخلی بیرون نمی‌رود
            </li>
            <li>
              <span className="login-brand-feature-icon">
                <Users size={16} />
              </span>
              چند حسابدار، همزمان روی یک دفتر
            </li>
            <li>
              <span className="login-brand-feature-icon">
                <ShieldCheck size={16} />
              </span>
              بدونِ نیاز به اینترنت برای کارِ روزانه
            </li>
          </ul>
        </div>
      </div>

      <div className="login-form-panel">
        <form className="login-card" onSubmit={probe}>
          <h1>اتصال به سرور</h1>
          <p className="login-card-subtitle">
            نامِ رایانه‌ی سرور یا نشانیِ IPِ آن را وارد کنید. مدیرِ شبکه‌ی شرکت آن را می‌داند.
          </p>

          <label>
            نشانیِ سرور
            <div className="input-with-icon">
              <Network size={16} className="input-icon" />
              <input
                type="text"
                dir="ltr"
                value={address}
                onChange={(e) => {
                  setAddress(e.target.value)
                  setVerified(null)
                }}
                placeholder="acc-server"
                autoFocus
                required
                spellCheck={false}
              />
            </div>
            <span className="field-hint">
              نامِ رایانه بهتر از IP است؛ IP ممکن است با روشن‌وخاموش‌شدنِ مودم عوض شود.
            </span>
          </label>

          {error && <div className="error">{error}</div>}
          {verified && (
            <div className="notice">
              <CheckCircle2 size={15} /> سرور پیدا شد: <span dir="ltr">{verified}</span>
            </div>
          )}

          {verified ? (
            <button type="button" className="btn-primary login-submit" onClick={save} disabled={busy !== null}>
              {busy === 'save' ? 'در حال اتصال…' : 'اتصال به این سرور'}
              {busy === null && <ArrowLeft size={15} />}
            </button>
          ) : (
            <button type="submit" className="btn-primary login-submit" disabled={busy !== null}>
              {busy === 'probe' ? 'در حال آزمایش…' : 'آزمایشِ اتصال'}
              {busy === null && <ArrowLeft size={15} />}
            </button>
          )}

          {onCancel && (
            <button type="button" className="link-button" onClick={onCancel}>
              بازگشت به صفحه‌ی ورود
            </button>
          )}
        </form>
      </div>
    </div>
  )
}
