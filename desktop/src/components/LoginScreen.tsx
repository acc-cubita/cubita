import { useState } from 'react'
import { Mail, Lock, Eye, EyeOff, ArrowLeft, ShoppingCart, BookOpen, Landmark } from 'lucide-react'
import { login, fetchMe, requestPasswordReset, type MeResponse } from '../api'

const FEATURES = [
  { icon: ShoppingCart, text: 'فروش، خرید و انبارداری یکپارچه' },
  { icon: BookOpen, text: 'حسابداری دوطرفه با گزارش‌های زنده' },
  { icon: Landmark, text: 'چک، بانک، حقوق و دستمزد در یک‌جا' },
]

export function LoginScreen({
  onLoggedIn,
  onSignup,
}: {
  onLoggedIn: (token: string, me: MeResponse) => void
  onSignup?: () => void
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<'login' | 'forgot'>('login')
  const [notice, setNotice] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const t = await login(email, password)
      await window.cubita?.setAuthToken(t)
      const meRes = await fetchMe(t)
      onLoggedIn(t, meRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  async function handleForgot(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await requestPasswordReset(email)
      // پیام سرور عمداً نمی‌گوید ایمیل وجود داشت یا نه؛ همان را نشان می‌دهیم تا
      // رابط کاربری چیزی را لو ندهد که خودِ اندپوینت پنهانش کرده.
      setNotice(res.detail)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  if (mode === 'forgot') {
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
            <p className="login-brand-tagline">لینک بازیابی را برایتان ایمیل می‌کنیم</p>
          </div>
        </div>

        <div className="login-form-panel">
          <form className="login-card" onSubmit={handleForgot}>
            <h1>بازیابی رمز عبور</h1>
            <p className="login-card-subtitle">
              ایمیل حسابتان را وارد کنید. لینک بازیابی تا یک ساعت معتبر است.
            </p>

            <label>
              ایمیل
              <div className="input-with-icon">
                <Mail size={16} className="input-icon" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoFocus
                  required
                />
              </div>
            </label>

            {error && <div className="error">{error}</div>}
            {notice && <div className="notice">{notice}</div>}

            <button type="submit" className="btn-primary login-submit" disabled={loading}>
              {loading ? 'در حال ارسال...' : 'ارسال لینک بازیابی'}
              {!loading && <ArrowLeft size={15} />}
            </button>

            <button
              type="button"
              className="link-button"
              onClick={() => {
                setMode('login')
                setError(null)
                setNotice(null)
              }}
            >
              بازگشت به صفحه‌ی ورود
            </button>
          </form>
        </div>
      </div>
    )
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
          <p className="login-brand-tagline">سامانه‌ی یکپارچه‌ی حسابداری، انبار و فروش — آفلاین و آنلاین</p>
          <ul className="login-brand-features">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text}>
                <span className="login-brand-feature-icon">
                  <Icon size={16} />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="login-form-panel">
        <form className="login-card" onSubmit={handleSubmit}>
          <h1>ورود به حساب کاربری</h1>
          <p className="login-card-subtitle">برای ادامه، اطلاعات ورود خود را وارد کنید</p>

          <label>
            ایمیل
            <div className="input-with-icon">
              <Mail size={16} className="input-icon" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoFocus
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
                placeholder="••••••••"
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
            {loading ? 'در حال ورود...' : 'ورود'}
            {!loading && <ArrowLeft size={15} />}
          </button>

          <button
            type="button"
            className="link-button"
            onClick={() => {
              setMode('forgot')
              setError(null)
            }}
          >
            رمز عبور را فراموش کرده‌ام
          </button>

          {onSignup && (
            <div className="login-signup-cta">
              <span>حساب ندارید؟</span>
              <button type="button" className="link-button login-signup-link" onClick={onSignup}>
                ۱۴ روز رایگان امتحان کنید
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
