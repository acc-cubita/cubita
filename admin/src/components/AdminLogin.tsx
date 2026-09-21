/**
 * ورود به ستاد.
 *
 * عمداً کپیِ `desktop/src/components/LoginScreen.tsx` نیست. آن ۳۹۱ خط شاخه‌ی
 * ثبت‌نام، بازیابیِ رمز، پیامک و Electron دارد — هیچ‌کدام اینجا معنا ندارند، و
 * «لینکِ ثبت‌نام» روی پنلِ ستاد یعنی دعوت به حدس‌زدن.
 *
 * بازیابیِ رمز در فازِ ۱ وجود ندارد (جریانِ موجود به اپِ مشتری ایمیل می‌زند و
 * آنجا عضویت می‌خواهد). راهش این است که یک مالکِ دیگر از صفحه‌ی «کاربران ستاد»
 * بازنشانی کند — و به همین دلیل سرور نمی‌گذارد آخرین مالک برداشته شود.
 */
import { useState, type FormEvent } from 'react'
import { LockKeyhole } from 'lucide-react'

import { login } from '../api'

export default function AdminLogin({ onToken }: { onToken: (token: string) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onToken(await login(email.trim(), password))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ورود ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ad-login">
      <form className="ad-login-card" onSubmit={submit}>
        <div className="ad-login-brand">
          <LockKeyhole size={22} />
          <div>
            <h1>ستادِ کوبیتا</h1>
            <p>پنلِ مدیریتِ سامانه</p>
          </div>
        </div>

        <label className="ad-field">
          <span className="ad-field-label">ایمیل</span>
          <input
            type="email"
            dir="ltr"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label className="ad-field">
          <span className="ad-field-label">رمز عبور</span>
          <input
            type="password"
            dir="ltr"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error ? <p className="ad-note tone-bad">{error}</p> : null}

        <button type="submit" className="ad-btn primary" disabled={busy || !email || !password}>
          {busy ? 'در حال ورود…' : 'ورود'}
        </button>

        <p className="ad-login-foot">
          این صفحه فقط برای کارکنانِ کوبیتاست. برای ورود به نرم‌افزارِ حسابداری به
          acc.cubita.ir بروید.
        </p>
      </form>
    </div>
  )
}
