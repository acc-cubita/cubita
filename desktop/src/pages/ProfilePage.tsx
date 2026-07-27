import { useState } from 'react'
import { Building2, Save, UserCircle } from 'lucide-react'
import { updateBusinessName, updateProfile, type MeResponse, type ProfileUpdate } from '../api'
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
            تلفن
            <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="اختیاری" />
          </label>
          <label>
            نقش
            <input type="text" value={me.role_name} disabled />
          </label>
        </div>
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
