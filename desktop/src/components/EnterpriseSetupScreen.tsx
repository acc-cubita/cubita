import { useState } from 'react'
import { ArrowLeft, Building2, Eye, EyeOff, Factory, Lock, Mail, Server, User, UserCog } from 'lucide-react'
import { enterpriseSetup, fetchMe, type MeResponse } from '../api'
import { SearchSelect } from './SearchSelect'
import { INDUSTRIES } from '../lib/industries'

const MIN_PASSWORD_LENGTH = 10

/**
 * «کوبیتا سازمانی» — راه‌اندازیِ سرورِ تازه‌نصب: کسب‌وکار و حسابِ مالک.
 *
 * فقط وقتی دیده می‌شود که سرور هنوز هیچ کسب‌وکاری ندارد؛ سرور خودش هم همین را زیرِ
 * قفل می‌سنجد، پس دومین کسی که هم‌زمان این صفحه را پر کند ۴۰۹ می‌گیرد. کدِ تأییدِ
 * ایمیلی ندارد چون سرورِ شرکت اغلب اینترنت ندارد — ایمیل فقط نامِ کاربریِ ورود است.
 */
export function EnterpriseSetupScreen({ onDone }: { onDone: (token: string, me: MeResponse) => void }) {
  const [businessName, setBusinessName] = useState('')
  const [industry, setIndustry] = useState('general')
  const [ownerName, setOwnerName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`رمز عبور باید حداقل ${MIN_PASSWORD_LENGTH.toLocaleString('fa-IR')} کاراکتر باشد.`)
      return
    }
    setLoading(true)
    try {
      const { access_token: t, refresh_token } = await enterpriseSetup({
        businessName: businessName.trim(),
        ownerName: ownerName.trim(),
        email: email.trim(),
        password,
        industry,
      })
      const me = await fetchMe(t)
      if (refresh_token) await window.cubita?.persistSession(t, refresh_token, me)
      else await window.cubita?.setAuthToken(t)
      onDone(t, me)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
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
          <p className="login-brand-tagline">سرور آماده است؛ فقط یک قدم مانده</p>
          <ul className="login-brand-features">
            <li>
              <span className="login-brand-feature-icon">
                <Server size={16} />
              </span>
              این کار فقط یک‌بار، روی سرورِ تازه‌نصب انجام می‌شود
            </li>
            <li>
              <span className="login-brand-feature-icon">
                <UserCog size={16} />
              </span>
              حسابی که می‌سازید مالکِ دفتر است و بقیه‌ی حسابداران را دعوت می‌کند
            </li>
          </ul>
        </div>
      </div>

      <div className="login-form-panel">
        <form className="login-card" onSubmit={handleSubmit}>
          <h1>راه‌اندازیِ سرور</h1>
          <p className="login-card-subtitle">مشخصاتِ شرکت و حسابِ مالک را وارد کنید.</p>

          <label>
            نامِ شرکت یا سازمان
            <div className="input-with-icon">
              <Building2 size={16} className="input-icon" />
              <input
                type="text"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="مثلاً شرکت پارس"
                autoFocus
                required
              />
            </div>
          </label>

          <label>
            نوعِ فعالیت
            <div className="input-with-icon">
              <Factory size={16} className="input-icon" />
              <SearchSelect value={industry} onChange={(e) => setIndustry(e.target.value)}>
                {INDUSTRIES.map((it) => (
                  <option key={it.key} value={it.key}>
                    {it.label}
                  </option>
                ))}
              </SearchSelect>
            </div>
            <span className="field-hint">ماژول‌های پنل بر اساسِ آن تنظیم می‌شوند و بعداً قابلِ تغییر است.</span>
          </label>

          <label>
            نام و نام خانوادگیِ مالک
            <div className="input-with-icon">
              <User size={16} className="input-icon" />
              <input type="text" value={ownerName} onChange={(e) => setOwnerName(e.target.value)} required />
            </div>
          </label>

          <label>
            ایمیل (نامِ کاربریِ ورود)
            <div className="input-with-icon">
              <Mail size={16} className="input-icon" />
              <input
                type="email"
                dir="ltr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
            <span className="field-hint">فقط برای ورود است؛ ایمیلی به آن فرستاده نمی‌شود.</span>
          </label>

          <label>
            رمز عبور
            <div className="input-with-icon">
              <Lock size={16} className="input-icon" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={MIN_PASSWORD_LENGTH}
                required
              />
              <button
                type="button"
                className="input-icon-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'پنهان‌کردن رمز' : 'نمایش رمز'}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <span className="field-hint">
              حداقل {MIN_PASSWORD_LENGTH.toLocaleString('fa-IR')} کاراکتر. آن را جای امنی نگه دارید.
            </span>
          </label>

          {error && <div className="error">{error}</div>}

          <button type="submit" className="btn-primary login-submit" disabled={loading}>
            {loading ? 'در حال راه‌اندازی…' : 'راه‌اندازی و ورود'}
            {!loading && <ArrowLeft size={15} />}
          </button>
        </form>
      </div>
    </div>
  )
}
