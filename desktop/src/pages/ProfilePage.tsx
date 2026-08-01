import { useEffect, useState } from 'react'
import { Building2, MessageSquare, Save, ShieldCheck, UserCircle } from 'lucide-react'
import {
  sendPhoneCode,
  updateBusinessName,
  updateProfile,
  verifyPhoneCode,
  type MeResponse,
  type ProfileUpdate,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { ChangePasswordCard } from '../components/ChangePasswordCard'

export function ProfilePage({
  token,
  me,
  onMeUpdated,
}: {
  token: string
  me: MeResponse
  /** بعد از ذخیره، `me`ی لایه‌ی بالا تازه می‌شود تا نام/ایمیل در ساید‌بار هم عوض شود. */
  onMeUpdated: (me: MeResponse) => void
}) {
  const isOwner = Boolean(me.permissions['*'])

  return (
    <div className="page">
      <PageHeader
        icon={UserCircle}
        title="پروفایل من"
        description="نام، ایمیل و اطلاعات تماسِ حسابتان را ویرایش کنید و رمز عبور را عوض کنید."
      />

      <div className="workspace-split">
        <UserInfoCard token={token} me={me} onMeUpdated={onMeUpdated} />
        <div className="profile-side">
          {isOwner && <BusinessCard token={token} me={me} onMeUpdated={onMeUpdated} />}
          <ChangePasswordCard token={token} me={me} />
        </div>
      </div>
    </div>
  )
}

function UserInfoCard({
  token,
  me,
  onMeUpdated,
}: {
  token: string
  me: MeResponse
  onMeUpdated: (me: MeResponse) => void
}) {
  const [name, setName] = useState(me.name)
  const [phone, setPhone] = useState(me.phone ?? '')
  const [email, setEmail] = useState(me.email)
  const [currentPassword, setCurrentPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const emailChanged = email.trim().toLowerCase() !== me.email

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)

    const patch: ProfileUpdate = {}
    if (name.trim() !== me.name) patch.name = name.trim()
    if ((phone ?? '') !== (me.phone ?? '')) patch.phone = phone // خالی = پاک‌کردنِ تلفن
    if (emailChanged) {
      if (!currentPassword) {
        setMessage('برای تغییر ایمیل، رمز فعلی را وارد کنید.')
        return
      }
      patch.email = email.trim()
      patch.current_password = currentPassword
    }

    if (Object.keys(patch).length === 0) {
      setMessage('تغییری برای ذخیره نیست.')
      return
    }

    setBusy(true)
    try {
      const updated = await updateProfile(token, patch)
      onMeUpdated(updated)
      setCurrentPassword('')
      setMessage('اطلاعات حساب به‌روزرسانی شد.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard icon={UserCircle} title="اطلاعات کاربری" description="نام، تلفن و ایمیلِ حسابِ شما.">
      <form className="invoice-form form-full" onSubmit={handleSubmit}>
        <label>
          نام و نام خانوادگی
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <div className="field-row">
          <label>
            تلفن همراه
            <input
              type="text"
              inputMode="tel"
              dir="ltr"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="۰۹۱۲..."
            />
          </label>
          <label>
            نقش
            <input type="text" value={me.role_name} disabled />
          </label>
        </div>
        <PhoneVerification
          token={token}
          phone={phone}
          verified={me.phone_verified}
          savedPhone={me.phone}
          onVerified={(updated) => {
            setPhone(updated.phone ?? '')
            onMeUpdated(updated)
          }}
        />
        <label>
          ایمیل (نامِ کاربریِ ورود)
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        {emailChanged && (
          <label>
            رمز فعلی (برای تأییدِ تغییرِ ایمیل)
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="رمز عبور فعلی"
            />
          </label>
        )}
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={busy}>
            <Save size={14} /> ذخیره تغییرات
          </button>
        </div>
        {message && <div className="hint">{message}</div>}
      </form>
    </SectionCard>
  )
}

function BusinessCard({
  token,
  me,
  onMeUpdated,
}: {
  token: string
  me: MeResponse
  onMeUpdated: (me: MeResponse) => void
}) {
  const [name, setName] = useState(me.tenant_name)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!name.trim()) {
      setMessage('نام کسب‌وکار نمی‌تواند خالی باشد.')
      return
    }
    if (name.trim() === me.tenant_name) {
      setMessage('تغییری برای ذخیره نیست.')
      return
    }
    setBusy(true)
    try {
      const updated = await updateBusinessName(token, name.trim())
      onMeUpdated(updated)
      setMessage('نام کسب‌وکار به‌روزرسانی شد.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard icon={Building2} title="اطلاعات کسب‌وکار" description="نامی که در فاکتورها و گزارش‌ها نمایش داده می‌شود.">
      <form className="invoice-form form-full" onSubmit={handleSubmit}>
        <label>
          نام کسب‌وکار
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={busy}>
            <Save size={14} /> ذخیره
          </button>
        </div>
        {message && <div className="hint">{message}</div>}
      </form>
    </SectionCard>
  )
}

/**
 * تأییدِ شماره‌ی موبایل با کدِ پیامکی — درست زیرِ فیلدِ تلفن.
 *
 * دکمه‌ها همه `type="button"`اند و Enter در ورودیِ کد جلوگیری می‌شود، وگرنه داخلِ
 * همان فرمِ پروفایل، تأییدِ کد به‌اشتباه فرمِ نام/ایمیل را submit می‌کرد.
 */
function PhoneVerification({
  token,
  phone,
  verified,
  savedPhone,
  onVerified,
}: {
  token: string
  phone: string
  verified: boolean
  savedPhone: string | null
  onVerified: (me: MeResponse) => void
}) {
  const [stage, setStage] = useState<'idle' | 'sent'>('idle')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)

  // شمارشِ معکوسِ «ارسال دوباره»
  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  // اگر شماره را عوض کرد، جریانِ کد را از نو شروع کن (کدِ قبلی به شماره‌ی دیگری رفته بود)
  useEffect(() => {
    setStage('idle')
    setCode('')
    setMsg(null)
  }, [phone])

  const digits = phone.replace(/\D/g, '')
  const looksValid = /^0?9\d{9}$/.test(digits)
  const alreadyVerified = verified && phone.trim() === (savedPhone ?? '').trim()

  async function send() {
    setMsg(null)
    setBusy(true)
    try {
      const res = await sendPhoneCode(token, phone)
      if (res.sent) {
        setStage('sent')
        setCooldown(60)
        setMsg({ text: `کد به ${res.phone} پیامک شد`, kind: 'ok' })
      } else {
        setMsg({ text: 'ارسالِ کد ناموفق بود؛ کمی بعد دوباره تلاش کنید.', kind: 'err' })
      }
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function verify() {
    if (code.length < 4) return
    setMsg(null)
    setBusy(true)
    try {
      const updated = await verifyPhoneCode(token, code)
      onVerified(updated)
      setStage('idle')
      setCode('')
      setMsg({ text: 'شماره با موفقیت تأیید شد.', kind: 'ok' })
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'کد نادرست است', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  if (alreadyVerified) {
    return (
      <div className="phone-verify">
        <span className="phone-verify-badge">
          <ShieldCheck size={15} /> شماره‌ی موبایل تأیید شده است
        </span>
      </div>
    )
  }

  return (
    <div className="phone-verify">
      {stage === 'idle' ? (
        <button
          type="button"
          className="phone-verify-btn"
          onClick={send}
          disabled={busy || !looksValid}
          title={!looksValid ? 'ابتدا یک شماره‌ی موبایلِ معتبر وارد کنید' : undefined}
        >
          <MessageSquare size={14} /> {busy ? 'در حال ارسال…' : 'تأیید شماره با پیامک'}
        </button>
      ) : (
        <div className="phone-verify-code">
          <input
            type="text"
            inputMode="numeric"
            dir="ltr"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                verify()
              }
            }}
            placeholder="کدِ ۶ رقمی"
            className="phone-code-input"
            autoFocus
          />
          <button type="button" className="btn-primary" onClick={verify} disabled={busy || code.length < 4}>
            {busy ? '…' : 'تأیید'}
          </button>
          <button type="button" className="link-button" onClick={send} disabled={busy || cooldown > 0}>
            {cooldown > 0 ? `ارسال دوباره (${cooldown})` : 'ارسال دوباره'}
          </button>
        </div>
      )}
      {msg && <div className={`phone-verify-hint ${msg.kind}`}>{msg.text}</div>}
    </div>
  )
}
