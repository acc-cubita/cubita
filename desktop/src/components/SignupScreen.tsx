import { useEffect, useRef, useState } from 'react'
import { Mail, Lock, Eye, EyeOff, ArrowLeft, ArrowRight, Building2, User, Gift, MailCheck, RefreshCw } from 'lucide-react'
import { requestSignupCode, signup, fetchMe, type MeResponse } from '../api'

const MIN_PASSWORD_LENGTH = 10
const CODE_LENGTH = 6
const RESEND_SECONDS = 60

/**
 * ثبت‌نامِ «۱۴ روز رایگان» با تأییدِ ایمیل — verify-before-create.
 *
 * دو گام: (۱) کاربر مشخصاتش را می‌دهد و کد به ایمیلش می‌رود؛ (۲) کد را وارد می‌کند و تازه
 * حساب ساخته و مستقیم وارد می‌شود. هیچ حسابی با ایمیلِ تأییدنشده به‌وجود نمی‌آید.
 */
export function SignupScreen({
  onDone,
  onBackToLogin,
}: {
  onDone: (token: string, me: MeResponse) => void
  onBackToLogin: () => void
}) {
  const [step, setStep] = useState<'details' | 'code'>('details')
  const [businessName, setBusinessName] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [code, setCode] = useState('')
  const [maskedEmail, setMaskedEmail] = useState('')
  const [deliveryWarning, setDeliveryWarning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [resendIn, setResendIn] = useState(0)
  const codeInputRef = useRef<HTMLInputElement>(null)

  // شمارشِ معکوسِ «ارسال دوباره».
  useEffect(() => {
    if (resendIn <= 0) return
    const t = setInterval(() => setResendIn((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [resendIn])

  // با ورود به گامِ کد، فوکوس روی ورودیِ کد.
  useEffect(() => {
    if (step === 'code') codeInputRef.current?.focus()
  }, [step])

  async function handleRequestCode(e: React.FormEvent) {
    e.preventDefault()
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`رمز عبور باید حداقل ${MIN_PASSWORD_LENGTH} کاراکتر باشد`)
      return
    }
    setError(null)
    setLoading(true)
    try {
      const res = await requestSignupCode(email.trim())
      setMaskedEmail(res.email)
      setDeliveryWarning(!res.sent)
      setCode('')
      setStep('code')
      setResendIn(RESEND_SECONDS)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    if (resendIn > 0 || loading) return
    setError(null)
    setLoading(true)
    try {
      const res = await requestSignupCode(email.trim())
      setMaskedEmail(res.email)
      setDeliveryWarning(!res.sent)
      setResendIn(RESEND_SECONDS)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerifyAndCreate(e: React.FormEvent) {
    e.preventDefault()
    if (code.trim().length !== CODE_LENGTH) {
      setError(`کد تأیید ${CODE_LENGTH} رقمی است`)
      return
    }
    setError(null)
    setLoading(true)
    try {
      const t = await signup(businessName.trim(), ownerName.trim(), email.trim(), password, code.trim())
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
        {step === 'details' ? (
          <form className="login-card" onSubmit={handleRequestCode}>
            <h1>شروعِ رایگان</h1>
            <p className="login-card-subtitle">اطلاعات را کامل کنید؛ یک کدِ تأیید به ایمیلتان می‌فرستیم.</p>

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
              <span className="field-hint">کدِ تأیید به همین ایمیل می‌رود، پس باید واقعی و در دسترس باشد.</span>
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
              {loading ? 'در حال ارسال کد...' : 'ارسال کد تأیید به ایمیل'}
              {!loading && <ArrowLeft size={15} />}
            </button>

            <button type="button" className="link-button" onClick={onBackToLogin}>
              قبلاً حساب دارید؟ وارد شوید
            </button>
          </form>
        ) : (
          <form className="login-card" onSubmit={handleVerifyAndCreate}>
            <div className="signup-code-badge" aria-hidden="true">
              <MailCheck size={26} />
            </div>
            <h1>کد تأیید را وارد کنید</h1>
            <p className="login-card-subtitle">
              کدِ {CODE_LENGTH} رقمی به <bdi className="signup-code-email">{maskedEmail}</bdi> فرستادیم. اگر در
              «صندوق ورودی» نبود، پوشه‌ی هرزنامه (Spam) را هم ببینید.
            </p>

            {deliveryWarning && (
              <div className="hint signup-code-warn">
                ممکن است ایمیل با کمی تأخیر برسد. اگر نرسید، از «ارسال دوباره» استفاده کنید.
              </div>
            )}

            <label>
              کد تأیید ایمیل
              <input
                ref={codeInputRef}
                className="signup-code-input"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={CODE_LENGTH}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, CODE_LENGTH))}
                placeholder="------"
                dir="ltr"
                required
              />
            </label>

            {error && <div className="error">{error}</div>}

            <button type="submit" className="btn-primary login-submit" disabled={loading || code.length !== CODE_LENGTH}>
              {loading ? 'در حال ساخت حساب...' : 'تأیید و ساخت حساب'}
              {!loading && <ArrowLeft size={15} />}
            </button>

            <div className="signup-code-actions">
              <button
                type="button"
                className="link-button"
                onClick={handleResend}
                disabled={resendIn > 0 || loading}
              >
                <RefreshCw size={13} />
                {resendIn > 0 ? `ارسال دوباره تا ${resendIn.toLocaleString('fa-IR')} ثانیه` : 'ارسال دوباره‌ی کد'}
              </button>
              <button
                type="button"
                className="link-button"
                onClick={() => {
                  setStep('details')
                  setError(null)
                }}
              >
                <ArrowRight size={13} /> ویرایش اطلاعات
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
