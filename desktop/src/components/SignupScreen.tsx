import { useState } from 'react'
import { Mail, Lock, Eye, EyeOff, ArrowLeft, Building2, User, Gift } from 'lucide-react'
import { signup, fetchMe, type MeResponse } from '../api'

const MIN_PASSWORD_LENGTH = 10

/**
 * ثبت‌نامِ «۱۴ روز رایگان» — تنها راهِ ورودِ خودسرویس به محصول.
 *
 * موفقیت مستقیم کاربر را وارد می‌کند (توکن برمی‌گردد)، چون کسی که همین حالا حساب
 * ساخته نباید بلافاصله دوباره لاگین کند. حسابِ ساخته‌شده آزمایشیِ ۱۴روزه است؛ خودِ
 * سرور این را ست می‌کند و اینجا فقط جشنش را می‌گیریم.
 */
export function SignupScreen({
  onDone,
  onBackToLogin,
}: {
  onDone: (token: string, me: MeResponse) => void
  onBackToLogin: () => void
}) {
  const [businessName, setBusinessName] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`رمز عبور باید حداقل ${MIN_PASSWORD_LENGTH} کاراکتر باشد`)
      return
    }
    setError(null)
    setLoading(true)
    try {
      const t = await signup(businessName.trim(), ownerName.trim(), email.trim(), password)
      await window.cubita?.setAuthToken(t)
      onDone(t, await fetchMe(t))
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
          <h2 className="login-brand-title">کوبیتا</h2>
          <p className="login-brand-tagline">۱۴ روز رایگان امتحان کنید — بدون کارت بانکی</p>
          <ul className="login-brand-features">
            <li>
              <span className="login-brand-feature-icon">
                <Gift size={16} />
              </span>
              همه‌ی امکاناتِ حسابداری، انبار و فروش، رایگان تا ۱۴ روز
            </li>
            <li>
              <span className="login-brand-feature-icon">
                <Building2 size={16} />
              </span>
              فضای کاریِ اختصاصیِ خودتان، از همین حالا
            </li>
            <li>
              <span className="login-brand-feature-icon">
                <Lock size={16} />
              </span>
              با تهیه‌ی پلن، همین اطلاعات حفظ می‌شود
            </li>
          </ul>
        </div>
      </div>

      <div className="login-form-panel">
        <form className="login-card" onSubmit={handleSubmit}>
          <h1>شروعِ رایگان</h1>
          <p className="login-card-subtitle">حساب بسازید و بلافاصله وارد شوید — ۱۴ روز رایگان.</p>

          <label>
            نام کسب‌وکار
            <div className="input-with-icon">
              <Building2 size={16} className="input-icon" />
              <input
                type="text"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="مثلاً فروشگاه پارس"
                autoFocus
                required
              />
            </div>
          </label>

          <label>
            نام و نام خانوادگی
            <div className="input-with-icon">
              <User size={16} className="input-icon" />
              <input
                type="text"
                value={ownerName}
                onChange={(e) => setOwnerName(e.target.value)}
                placeholder="نام شما"
                required
              />
            </div>
          </label>

          <label>
            ایمیل (نامِ کاربریِ ورود)
            <div className="input-with-icon">
              <Mail size={16} className="input-icon" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
          </label>

          <label>
            رمز عبور
            <div className="input-with-icon">
              <Lock size={16} className="input-icon" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="حداقل ۱۰ کاراکتر"
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
          </label>

          {error && <div className="error">{error}</div>}

          <button type="submit" className="btn-primary login-submit" disabled={loading}>
            {loading ? 'در حال ساخت حساب...' : 'ساختِ حساب و شروعِ رایگان'}
            {!loading && <ArrowLeft size={15} />}
          </button>

          <button type="button" className="link-button" onClick={onBackToLogin}>
            قبلاً حساب دارید؟ وارد شوید
          </button>
        </form>
      </div>
    </div>
  )
}
