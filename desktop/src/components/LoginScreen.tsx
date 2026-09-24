import { useState } from 'react'
import { Mail, Lock, Eye, EyeOff, ArrowLeft, ShoppingCart, BookOpen, Landmark, Smartphone, Phone, KeyRound } from 'lucide-react'
import {
  login,
  fetchMe,
  requestPasswordReset,
  requestPasswordResetSms,
  resetPasswordSms,
  type MeResponse,
} from '../api'

const FEATURES = [
  { icon: ShoppingCart, text: 'فروش، خرید و انبارداری یکپارچه' },
  { icon: BookOpen, text: 'حسابداری دوطرفه با گزارش‌های زنده' },
  { icon: Landmark, text: 'چک، بانک، حقوق و دستمزد در یک‌جا' },
]

export function LoginScreen({
  onLoggedIn,
  onSignup,
  enterprise,
}: {
  onLoggedIn: (token: string, me: MeResponse) => void
  onSignup?: () => void
  /** کوبیتا سازمانی: نشانیِ سرورِ فعلی و راهِ تغییرش. بازیابیِ رمز با ایمیل/پیامک
   *  آنجا نیست (سرورِ شرکت SMTP و خطِ پیامک ندارد) — رمزِ فراموش‌شده را مالک بازنشانی می‌کند. */
  enterprise?: { serverUrl: string; onChangeServer: () => void }
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<'login' | 'forgot'>('login')
  const [notice, setNotice] = useState<string | null>(null)
  // بازیابیِ رمز دو راه دارد: ایمیل (لینک) یا پیامک (کدِ درون‌برنامه‌ای). فلوی پیامکی
  // خودش دو گام است: گرفتنِ شماره، سپس کد + رمزِ تازه.
  const [forgotMethod, setForgotMethod] = useState<'email' | 'sms'>('email')
  const [phone, setPhone] = useState('')
  const [smsStep, setSmsStep] = useState<'phone' | 'code'>('phone')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [showNewPassword, setShowNewPassword] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const { access_token: t, refresh_token } = await login(email, password)
      const meRes = await fetchMe(t)
      // دسکتاپ: نشستِ کامل (توکن‌ها + me) روی دیسک — بارِ اولِ یوزر/پسورد کافی
      // است تا اپ از این پس خودش وارد بماند، آنلاین یا آفلاین. رفرش همیشه از
      // سرور می‌آید (login آن را صادر می‌کند)؛ نال‌بودنش فقط نوعاً ممکن است.
      if (refresh_token) await window.cubita?.persistSession(t, refresh_token, meRes)
      else await window.cubita?.setAuthToken(t)
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

  // گامِ اولِ پیامکی: شماره را می‌فرستد؛ پاسخ یکنواخت است (وجودِ شماره را لو نمی‌دهد)،
  // پس در هر حال به گامِ کد می‌رویم تا رابط چیزی را که اندپوینت پنهان کرده فاش نکند.
  async function handleRequestSms(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await requestPasswordResetSms(phone)
      setNotice(res.detail)
      setSmsStep('code')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  // گامِ دومِ پیامکی: کد + رمزِ تازه؛ در صورتِ موفقیت توکن می‌گیریم و مستقیم وارد می‌شویم.
  async function handleResetSms(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const { access_token } = await resetPasswordSms(phone, code, newPassword)
      await window.cubita?.setAuthToken(access_token)
      const meRes = await fetchMe(access_token)
      onLoggedIn(access_token, meRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  if (mode === 'forgot') {
    // با تعویضِ روش یا بازگشت، حالتِ گذرا پاک می‌شود تا پیام/کدِ قبلی نماند.
    const clearTransient = () => {
      setError(null)
      setNotice(null)
      setCode('')
      setNewPassword('')
    }
    const switchMethod = (m: 'email' | 'sms') => {
      setForgotMethod(m)
      setSmsStep('phone')
      clearTransient()
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
            <p className="login-brand-tagline">
              {forgotMethod === 'email'
                ? 'لینک بازیابی را برایتان ایمیل می‌کنیم'
                : 'کد بازیابی را برایتان پیامک می‌کنیم'}
            </p>
          </div>
        </div>

        <div className="login-form-panel">
          <div className="login-card">
            <h1>بازیابی رمز عبور</h1>

            <div className="seg-toggle login-method-toggle">
              <button
                type="button"
                className={forgotMethod === 'email' ? 'active' : ''}
                onClick={() => switchMethod('email')}
              >
                <Mail size={14} /> ایمیل
              </button>
              <button
                type="button"
                className={forgotMethod === 'sms' ? 'active' : ''}
                onClick={() => switchMethod('sms')}
              >
                <Smartphone size={14} /> پیامک
              </button>
            </div>

            {forgotMethod === 'email' && (
              <form onSubmit={handleForgot} className="login-card-form">
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
              </form>
            )}

            {forgotMethod === 'sms' && smsStep === 'phone' && (
              <form onSubmit={handleRequestSms} className="login-card-form">
                <p className="login-card-subtitle">
                  شماره‌ی موبایلی که قبلاً در پروفایل «تأیید» کرده‌اید را وارد کنید. کد تا ۵ دقیقه معتبر است.
                </p>
                <label>
                  شماره موبایل
                  <div className="input-with-icon">
                    <Phone size={16} className="input-icon" />
                    <input
                      type="tel"
                      inputMode="numeric"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                      autoFocus
                      required
                    />
                  </div>
                </label>
                {error && <div className="error">{error}</div>}
                <button type="submit" className="btn-primary login-submit" disabled={loading}>
                  {loading ? 'در حال ارسال...' : 'ارسال کد'}
                  {!loading && <ArrowLeft size={15} />}
                </button>
              </form>
            )}

            {forgotMethod === 'sms' && smsStep === 'code' && (
              <form onSubmit={handleResetSms} className="login-card-form">
                {notice && <div className="notice">{notice}</div>}
                <label>
                  کد پیامک‌شده
                  <div className="input-with-icon">
                    <KeyRound size={16} className="input-icon" />
                    <input
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      value={code}
                      onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                      placeholder="۶ رقم"
                      autoFocus
                      required
                    />
                  </div>
                </label>
                <label>
                  رمز عبور تازه
                  <div className="input-with-icon">
                    <Lock size={16} className="input-icon" />
                    <input
                      type={showNewPassword ? 'text' : 'password'}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="حداقل ۱۰ کاراکتر"
                      minLength={10}
                      required
                    />
                    <button
                      type="button"
                      className="input-icon-toggle"
                      onClick={() => setShowNewPassword((v) => !v)}
                      aria-label={showNewPassword ? 'پنهان‌کردن رمز' : 'نمایش رمز'}
                      tabIndex={-1}
                    >
                      {showNewPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </label>
                {error && <div className="error">{error}</div>}
                <button type="submit" className="btn-primary login-submit" disabled={loading}>
                  {loading ? 'در حال ثبت...' : 'ثبت رمز تازه و ورود'}
                  {!loading && <ArrowLeft size={15} />}
                </button>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => {
                    setSmsStep('phone')
                    clearTransient()
                  }}
                >
                  شماره را اشتباه زدم / ارسال دوباره‌ی کد
                </button>
              </form>
            )}

            <button
              type="button"
              className="link-button"
              onClick={() => {
                setMode('login')
                setSmsStep('phone')
                clearTransient()
              }}
            >
              بازگشت به صفحه‌ی ورود
            </button>
          </div>
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
          <h2 className="login-brand-title">{enterprise ? 'کوبیتا سازمانی' : 'کوبیتا'}</h2>
          <p className="login-brand-tagline">
            {enterprise
              ? 'حسابداریِ شرکت، روی سرورِ خودِ شرکت'
              : 'سامانه‌ی یکپارچه‌ی حسابداری، انبار و فروش — آفلاین و آنلاین'}
          </p>
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

          {enterprise ? (
            <p className="login-server-line">
              سرور: <span dir="ltr">{enterprise.serverUrl}</span>
              <button type="button" className="link-button" onClick={enterprise.onChangeServer}>
                تغییرِ سرور
              </button>
            </p>
          ) : (
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
          )}

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
