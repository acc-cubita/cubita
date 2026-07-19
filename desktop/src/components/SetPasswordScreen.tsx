import { useState } from 'react'
import { Lock, Eye, EyeOff, ArrowLeft } from 'lucide-react'
import { acceptInvite, fetchMe, resetPassword, type MeResponse } from '../api'

const MIN_PASSWORD_LENGTH = 10

/**
 * صفحه‌ی «رمز تازه بگذارید» برای دو جریان: بازیابی رمز و پذیرش دعوت.
 *
 * هر دو یک شکل دارند (توکن از لینک ایمیل + یک رمز تازه) و تفاوتشان فقط در متن و
 * اندپوینت است، پس یک کامپوننت با یک پارامتر ساده‌تر از دو کامپوننت تقریباً یکسان
 * است که کم‌کم از هم واگرا می‌شوند.
 */
export function SetPasswordScreen({
  action,
  token,
  onDone,
  onCancel,
}: {
  action: 'reset-password' | 'accept-invite'
  token: string
  onDone: (token: string, me: MeResponse) => void
  onCancel: () => void
}) {
  const isInvite = action === 'accept-invite'
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
      const res = isInvite ? await acceptInvite(token, password) : await resetPassword(token, password)
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
          <h2 className="login-brand-title">کوبیتا</h2>
          <p className="login-brand-tagline">
            {isInvite
              ? 'یک رمز عبور انتخاب کنید تا حسابتان فعال شود'
              : 'یک رمز تازه انتخاب کنید تا دوباره وارد شوید'}
          </p>
        </div>
      </div>

      <div className="login-form-panel">
        <form className="login-card" onSubmit={handleSubmit}>
          <h1>{isInvite ? 'فعال‌سازی حساب' : 'انتخاب رمز تازه'}</h1>
          <p className="login-card-subtitle">
            {isInvite
              ? 'شما به یک کسب‌وکار در کوبیتا دعوت شده‌اید. برای ورود رمز عبور خود را بسازید.'
              : 'رمز تازه‌ای بگذارید. با ثبت آن، همه‌ی نشست‌های باز دیگر بسته می‌شوند.'}
          </p>

          <label>
            رمز عبور تازه
            <div className="input-with-icon">
              <Lock size={16} className="input-icon" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="حداقل ۱۰ کاراکتر"
                autoFocus
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
            {loading ? 'در حال ثبت...' : isInvite ? 'فعال‌سازی و ورود' : 'ثبت رمز و ورود'}
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
