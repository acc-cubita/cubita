import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Copy,
  Eye,
  EyeOff,
  KeyRound,
  LifeBuoy,
  Save,
  ShieldCheck,
  Wand2,
  X,
} from 'lucide-react'
import { changePassword, type MeResponse } from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'

/**
 * تغییر کلمه عبور — صفحه‌ی مستقل (پیش‌تر یک کارتِ کوچک در «پروفایل من» بود).
 *
 * سه چیز این‌جا را از یک فرمِ سه‌فیلدی جدا می‌کند:
 *  ۱. **سنجه‌ی زنده‌ی رمز** با همان قاعده‌ای که سرور اعمال می‌کند (حداقل ۱۰ کاراکتر)
 *     به‌علاوه‌ی معیارهایی که رمز را واقعاً قوی می‌کنند — و ردکردنِ رمزی که نامِ کاربر
 *     یا ایمیلش را در خود دارد.
 *  ۲. **نشستِ زنده می‌ماند.** سرور پس از تغییرِ رمز توکنِ تازه برمی‌گرداند؛ آن را در
 *     همین‌جا جایگزین می‌کنیم تا کاربر بیرون نیفتد. دستگاه‌های دیگر همچنان باطل
 *     می‌شوند، چون `token_version` بالا می‌رود.
 *  ۳. **هشدارِ Caps Lock**، که شایع‌ترین دلیلِ «رمز فعلی نادرست است» است.
 */

/** حداقلِ طولِ رمز — دقیقاً همان عددی که بک‌اند اعمال می‌کند. */
const MIN_LENGTH = 10

const fa = (n: number) => n.toLocaleString('fa-IR')

interface Rule {
  key: string
  label: string
  ok: boolean
}

/** قاعده‌های رمز. اولی الزامِ سرور است؛ بقیه کیفیت را می‌سنجند. */
function buildRules(next: string, current: string, me: MeResponse): Rule[] {
  const lower = next.toLowerCase()
  const localPart = me.email.split('@')[0]?.toLowerCase() ?? ''
  const nameParts = me.name
    .toLowerCase()
    .split(/\s+/)
    .filter((p) => p.length >= 3)
  const containsIdentity =
    (localPart.length >= 3 && lower.includes(localPart)) || nameParts.some((p) => lower.includes(p))

  return [
    { key: 'len', label: `حداقل ${fa(MIN_LENGTH)} کاراکتر`, ok: next.length >= MIN_LENGTH },
    { key: 'letter', label: 'شاملِ حرف', ok: /[A-Za-z؀-ۿ]/.test(next) },
    { key: 'digit', label: 'شاملِ رقم', ok: /[0-9]/.test(next) },
    { key: 'symbol', label: 'شاملِ نشانه (مثل ! یا @)', ok: /[^A-Za-z0-9؀-ۿ]/.test(next) },
    { key: 'identity', label: 'بدونِ نام یا ایمیلِ شما', ok: next.length > 0 && !containsIdentity },
    { key: 'differs', label: 'متفاوت با رمزِ فعلی', ok: next.length > 0 && next !== current },
  ]
}

/** امتیازِ ۰..۴ از روی قاعده‌های برآورده‌شده و طول. */
function strengthOf(next: string, rules: Rule[]): { score: number; label: string } {
  if (!next) return { score: 0, label: '—' }
  const passed = rules.filter((r) => r.ok).length
  let score = Math.max(0, passed - 2)
  if (next.length >= 16 && passed === rules.length) score = 4
  const labels = ['بسیار ضعیف', 'ضعیف', 'متوسط', 'قوی', 'بسیار قوی']
  return { score: Math.min(score, 4), label: labels[Math.min(score, 4)] }
}

/** رمزِ تصادفیِ خوانا — از crypto، نه Math.random. */
function generatePassword(): string {
  const alphabet = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*-_=+'
  const bytes = new Uint32Array(18)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join('')
}

export function ChangePasswordPage({
  token,
  me,
  onTokenRenewed,
}: {
  token: string
  me: MeResponse
  /** توکنِ تازه‌ی سرور را در نشستِ برنامه می‌نشاند تا کاربر بیرون نیفتد. */
  onTokenRenewed?: (token: string) => void
}) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNext, setShowNext] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [copied, setCopied] = useState(false)

  const rules = useMemo(() => buildRules(next, current, me), [next, current, me])
  const strength = strengthOf(next, rules)
  const required = rules.find((r) => r.key === 'len')?.ok ?? false
  const identityOk = rules.find((r) => r.key === 'identity')?.ok ?? false
  const differsOk = rules.find((r) => r.key === 'differs')?.ok ?? false
  const matches = confirm.length > 0 && confirm === next
  // فقط چیزهایی که سرور یا امنیت واقعاً لازم دارند جلوی ثبت را می‌گیرند؛ بقیه‌ی
  // قاعده‌ها راهنمای کیفیت‌اند، نه مانع.
  const canSubmit = Boolean(current) && required && identityOk && differsOk && matches && !busy

  function trackCaps(e: React.KeyboardEvent<HTMLInputElement>) {
    setCapsLock(e.getModifierState?.('CapsLock') ?? false)
  }

  function fillGenerated() {
    const generated = generatePassword()
    setNext(generated)
    setConfirm(generated)
    setShowNext(true)
    setCopied(false)
    void navigator.clipboard
      ?.writeText(generated)
      .then(() => setCopied(true))
      // کپی در محیط‌های بدونِ دسترسی به کلیپ‌بورد شکست می‌خورد؛ رمز روی صفحه هست،
      // پس تنها چیزی که از دست می‌رود راحتیِ کپی است.
      .catch(() => setCopied(false))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const res = await changePassword(token, current, next)
      setCurrent('')
      setNext('')
      setConfirm('')
      setDone(true)
      // بدونِ این، توکنِ فعلی همین حالا باطل شده و اولین کلیکِ بعدی ۴۰۱ می‌گرفت.
      onTokenRenewed?.(res.access_token)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={KeyRound}
        title="تغییر کلمه عبور"
        description={`رمزِ ورودِ حسابِ ${me.email}. برای تأیید، رمزِ فعلی هم پرسیده می‌شود.`}
      />

      {done && (
        <div className="fy-note fy-note--ok">
          <CheckCircle2 size={16} />
          <div>
            <strong>رمز عبور عوض شد.</strong>
            <p>
              نشستِ همین دستگاه فعال ماند، ولی همه‌ی دستگاه‌های دیگر — از جمله اپِ موبایل — بیرون
              رفتند و باید دوباره با رمزِ تازه وارد شوند.
            </p>
          </div>
        </div>
      )}
      {error && (
        <div className="fy-note fy-note--err">
          <AlertTriangle size={16} />
          <div>{error}</div>
        </div>
      )}

      <div className="workspace-split">
        <SectionCard
          icon={KeyRound}
          title="رمز تازه"
          description="رمز باید دستِ‌کم ۱۰ کاراکتر باشد و نامِ حسابتان را در خود نداشته باشد."
          actions={
            <button type="button" onClick={fillGenerated} disabled={busy}>
              <Wand2 size={13} /> ساختِ رمزِ قوی
            </button>
          }
        >
          <form className="invoice-form form-full" onSubmit={handleSubmit}>
            <label>
              رمز فعلی
              <span className="pw-field">
                <input
                  type={showCurrent ? 'text' : 'password'}
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  onKeyUp={trackCaps}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="pw-eye"
                  onClick={() => setShowCurrent((v) => !v)}
                  aria-label={showCurrent ? 'پنهان‌کردن رمز' : 'نمایش رمز'}
                >
                  {showCurrent ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </span>
            </label>

            <label>
              رمز تازه
              <span className="pw-field">
                <input
                  type={showNext ? 'text' : 'password'}
                  value={next}
                  onChange={(e) => {
                    setNext(e.target.value)
                    setCopied(false)
                  }}
                  onKeyUp={trackCaps}
                  autoComplete="new-password"
                  required
                />
                <button
                  type="button"
                  className="pw-eye"
                  onClick={() => setShowNext((v) => !v)}
                  aria-label={showNext ? 'پنهان‌کردن رمز' : 'نمایش رمز'}
                >
                  {showNext ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </span>
            </label>

            <label>
              تکرار رمز تازه
              <span className="pw-field">
                <input
                  type={showNext ? 'text' : 'password'}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  onKeyUp={trackCaps}
                  autoComplete="new-password"
                  required
                />
              </span>
              {confirm.length > 0 && (
                <span className={`pw-match ${matches ? 'ok' : 'bad'}`}>
                  {matches ? <Check size={12} /> : <X size={12} />}
                  {matches ? 'یکسان است' : 'با رمز تازه یکی نیست'}
                </span>
              )}
            </label>

            <div className="field-full">
              <div className="pw-strength">
                <div className="pw-bars" data-score={strength.score}>
                  {[0, 1, 2, 3].map((i) => (
                    <span key={i} className={i < strength.score ? 'on' : ''} />
                  ))}
                </div>
                <span className="pw-strength-label">قدرت: {strength.label}</span>
              </div>

              <ul className="pw-rules">
                {rules.map((r) => (
                  <li key={r.key} className={r.ok ? 'ok' : ''}>
                    {r.ok ? <Check size={12} /> : <X size={12} />}
                    {r.label}
                  </li>
                ))}
              </ul>

              {capsLock && (
                <p className="pw-caps">
                  <AlertTriangle size={13} /> Caps Lock روشن است.
                </p>
              )}
              {copied && (
                <p className="pw-caps pw-caps--ok">
                  <Copy size={13} /> رمزِ ساخته‌شده در کلیپ‌بورد کپی شد — پیش از ثبت جایی امن ذخیره‌اش کنید.
                </p>
              )}
            </div>

            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={!canSubmit}>
                <Save size={14} /> ثبت رمز تازه
              </button>
            </div>
          </form>
        </SectionCard>

        <div className="profile-side">
        <SectionCard
          icon={LifeBuoy}
          title="راه‌های بازیابیِ حساب"
          description="اگر روزی رمز را فراموش کنید، فقط از این راه‌ها می‌شود دوباره وارد شد."
        >
          <ul className="pw-recovery">
            <li className={me.email_verified ? 'ok' : 'warn'}>
              {me.email_verified ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
              <span>
                <strong>ایمیل</strong>
                <span className="pw-recovery-value">{me.email}</span>
              </span>
              <span className="pw-recovery-state">
                {me.email_verified ? 'تأییدشده' : 'تأیید نشده'}
              </span>
            </li>
            <li className={me.phone_verified ? 'ok' : 'warn'}>
              {me.phone_verified ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
              <span>
                <strong>موبایل</strong>
                <span className="pw-recovery-value">{me.phone || 'ثبت نشده'}</span>
              </span>
              <span className="pw-recovery-state">
                {me.phone_verified ? 'تأییدشده' : me.phone ? 'تأیید نشده' : '—'}
              </span>
            </li>
          </ul>
          {!me.email_verified && !me.phone_verified && (
            <p className="pw-caps">
              <AlertTriangle size={13} /> هیچ راهِ تأییدشده‌ای برای بازیابی ندارید. در «پروفایل من»
              ایمیل یا موبایلتان را تأیید کنید.
            </p>
          )}
        </SectionCard>

        <SectionCard
          icon={ShieldCheck}
          title="پس از تغییر چه می‌شود"
          description="تغییرِ رمز یک اقدامِ امنیتی است، نه یک ویرایشِ ساده‌ی پروفایل."
        >
          <ul className="pw-facts">
            <li>
              <strong>این دستگاه وارد می‌ماند.</strong> نشستِ همین پنجره با کلیدِ تازه ادامه پیدا
              می‌کند و بیرون نمی‌افتید.
            </li>
            <li>
              <strong>بقیه‌ی دستگاه‌ها بیرون می‌روند.</strong> هر مرورگر یا اپِ موبایلی که با این
              حساب وارد شده باشد باید دوباره وارد شود — همین ابزارِ شماست وقتی نگرانِ لو رفتنِ رمز
              هستید.
            </li>
            <li>
              <strong>رمزِ فعلی لازم است.</strong> بدونِ آن، هر کسی که به لپ‌تاپِ بازِ شما برسد
              می‌توانست حساب را برای همیشه از دستتان بگیرد.
            </li>
            <li>
              <strong>رمز را جایی امن نگه دارید.</strong> کوبیتا رمز را به‌صورتِ هش ذخیره می‌کند و
              هیچ‌کس — از جمله پشتیبانی — نمی‌تواند آن را بازیابی کند؛ فقط می‌شود رمزِ تازه ساخت.
            </li>
          </ul>
        </SectionCard>
        </div>
      </div>
    </div>
  )
}
