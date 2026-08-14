import { useState } from 'react'
import { KeyRound, Save } from 'lucide-react'
import { changePassword, type MeResponse } from '../api'
import { SectionCard } from './SectionCard'

/** تغییرِ رمزِ عبورِ کاربرِ واردشده. رمزِ فعلی پرسیده می‌شود و همه‌ی نشست‌های دیگر باطل می‌شوند. */
export function ChangePasswordCard({ token, me }: { token: string; me: MeResponse }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (next !== confirm) {
      setMessage('دو رمز تازه یکسان نیستند.')
      return
    }
    setBusy(true)
    try {
      await changePassword(token, current, next)
      setCurrent('')
      setNext('')
      setConfirm('')
      // توکنِ تازه‌ی سرور عمداً ذخیره نمی‌شود. نشستِ همین صفحه با توکن قدیمی کار
      // می‌کند و آن توکن همین حالا باطل شد، پس درخواست بعدی ۴۰۱ می‌گیرد. گفتنِ
      // صریحِ «دوباره وارد شوید» صادقانه‌تر از این است که کاربر با اولین کلیک به
      // خطای نامفهوم بخورد.
      setMessage('رمز عبور عوض شد و همه‌ی دستگاه‌های دیگر بیرون رفتند. برای ادامه، دوباره وارد شوید.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={KeyRound}
      title="تغییر رمز عبور"
      description={`رمز حساب ${me.email}. با تغییر آن، همه‌ی دستگاه‌های دیگری که با این حساب وارد شده‌اند بیرون می‌روند.`}
    >
      <form className="invoice-form form-full" onSubmit={handleSubmit}>
        <label>
          رمز فعلی
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
        </label>
        <label>
          رمز تازه
          <input
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            placeholder="حداقل ۱۰ کاراکتر"
            required
          />
        </label>
        <label>
          تکرار رمز تازه
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={busy}>
            <Save size={14} /> ثبت رمز تازه
          </button>
        </div>
        {message && <div className="hint">{message}</div>}
      </form>
    </SectionCard>
  )
}
