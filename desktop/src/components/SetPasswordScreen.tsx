import { useState } from 'react'
import { Lock, Eye, EyeOff, ArrowLeft, KeyRound, User } from 'lucide-react'
import { acceptInvite, fetchMe, redeemCode, resetPassword, type MeResponse } from '../api'
import { PRODUCT_NAME } from '../platform'

const MIN_PASSWORD_LENGTH = 10

/**
 * صفحه‌ی «رمز تازه بگذارید» برای دو جریان: بازیابی رمز و پذیرش دعوت.
 *
 * هر دو یک شکل دارند (توکن از لینک ایمیل + یک رمز تازه) و تفاوتشان فقط در متن و
 * اندپوینت است، پس یک کامپوننت با یک پارامتر ساده‌تر از دو کامپوننت تقریباً یکسان
 * است که کم‌کم از هم واگرا می‌شوند.
 *
 * سومی، `redeem-code`، مالِ کوبیتا سازمانی است: سرورِ شرکت ایمیل ندارد، پس کارمند به‌جای
 * لینک یک کدِ ۱۶ نویسه‌ای از مالک (یا مالک از `cubita-server` روی خودِ سرور) می‌گیرد و
 * این‌جا واردش می‌کند. کارمند لازم نیست بداند کدِ دعوت است یا بازنشانی؛ سرور می‌داند.
 */
export function SetPasswordScreen({
  action,
  token,
  onDone,
  onCancel,
}: {
  action: 'reset-password' | 'accept-invite' | 'redeem-code'
  /** برای `redeem-code` خالی است: کد را کاربر همین‌جا وارد می‌کند. */
  token: string
  onDone: (token: string, me: MeResponse) => void
  onCancel: () => void
}) {
  const isInvite = action === 'accept-invite'
  const isCode = action === 'redeem-code'
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password !== confirm) {
      setError('دو رمز وارد‌شده یکسان نیستند')
      return
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`رمز عبور باید حداقل ${MIN_PASSWORD_LENGTH} کاراکتر باشد`)
      return
    }

    setError(null)
    setLoading(true)
    try {
      const res = isCode
        ? await redeemCode(code.trim(), password, name.trim() || undefined)
        : isInvite
          ? await acceptInvite(token, password)
          : await resetPassword(token, password)
      const accessToken = res.access_token
      await window.cubita?.setAuthToken(accessToken)
      onDone(accessToken, await fetchMe(accessToken))
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
          <h2 className="login-brand-title">{PRODUCT_NAME}</h2>
          <p className="login-brand-tagline">
            {isCode
              ? 'کدی که از مدیرِ سیستم گرفته‌اید را وارد کنید و رمزِ خودتان را بسازید'
              : isInvite
              ? 'یک رمز عبور انتخاب کنید تا حسابتان فعال شود'
              : 'یک رمز تازه انتخاب کنید تا دوباره وارد شوید'}
          </p>
        </div>
      </div>

      <div className="login-form-panel">
        <form className="login-card" onSubmit={handleSubmit}>
          <h1>{isCode ? 'ورود با کد' : isInvite ? 'فعال‌سازی حساب' : 'انتخاب رمز تازه'}</h1>
          <p className="login-card-subtitle">
            {isCode
              ? 'کدِ دعوت یا بازنشانی را از مدیرِ سیستم بگیرید. رمزی که این‌جا می‌سازید را هیچ‌کس جز خودتان نمی‌داند.'
              : isInvite
              ? 'شما به یک کسب‌وکار در کوبیتا دعوت شده‌اید. برای ورود رمز عبور خود را بسازید.'
              : 'رمز تازه‌ای بگذارید. با ثبت آن، همه‌ی نشست‌های باز دیگر بسته می‌شوند.'}
          </p>

          {isCode && (
            <>
              <label>
                کد
                <div className="input-with-icon">
                  <KeyRound size={16} className="input-icon" />
                  <input
                    dir="ltr"
                    className="lic-activation"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    autoComplete="one-time-code"
                    autoFocus
                    required
                  />
                </div>
                <span className="field-hint">۱۶ نویسه، مثلِ XXXX-XXXX-XXXX-XXXX؛ خط‌تیره و حروفِ کوچک مهم نیست.</span>
              </label>
              <label>
                نامِ شما (اختیاری)
                <div className="input-with-icon">
                  <User size={16} className="input-icon" />
                  <input value={name} onChange={(e) => setName(e.target.value)} placeholder="برای کدِ دعوت" />
                </div>
              </label>
            </>
          )}

          <label>
            رمز عبور تازه
            <div className="input-with-icon">
              <Lock size={16} className="input-icon" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="حداقل ۱۰ کاراکتر"
                autoFocus={!isCode}
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

          <label>
            تکرار رمز عبور
            <div className="input-with-icon">
              <Lock size={16} className="input-icon" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
          </label>

          {error && <div className="error">{error}</div>}

          <button type="submit" className="btn-primary login-submit" disabled={loading}>
            {loading ? 'در حال ثبت...' : isInvite || isCode ? 'فعال‌سازی و ورود' : 'ثبت رمز و ورود'}
            {!loading && <ArrowLeft size={15} />}
          </button>

          <button type="button" className="link-button" onClick={onCancel}>
            بازگشت به صفحه‌ی ورود
          </button>
        </form>
      </div>
    </div>
  )
}
