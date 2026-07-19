import { useEffect, useState } from 'react'
import { KeyRound, Save, ShieldCheck, UserPlus, UsersRound } from 'lucide-react'
import {
  changeMemberRole,
  changePassword,
  fetchMembers,
  inviteMember,
  setMemberActive,
  type Member,
  type MemberList,
  type MeResponse,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'

/** نقش‌های پیش‌فرضی که هر کسب‌وکار موقع ساخته شدن می‌گیرد. */
const ROLES = [
  { key: 'owner', label: 'مدیر/مالک' },
  { key: 'accountant', label: 'حسابدار' },
  { key: 'salesperson', label: 'فروشنده/صندوق‌دار' },
  { key: 'warehouse_keeper', label: 'انباردار' },
  { key: 'payroll_officer', label: 'مسئول حقوق و دستمزد' },
]

const STATUS_LABELS: Record<Member['status'], string> = {
  active: 'فعال',
  invited: 'در انتظار پذیرش دعوت',
  disabled: 'غیرفعال',
}

export function TeamPage({ token, me }: { token: string; me: MeResponse }) {
  const [data, setData] = useState<MemberList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [roleKey, setRoleKey] = useState('accountant')

  async function refresh() {
    try {
      setData(await fetchMembers(token))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  /** هر عملیات از یک مسیر رد می‌شود تا پیام خطای سرور همیشه دیده شود.
   *
   * سقف کاربران و گارد آخرین مالک هر دو ۴۰۹ با پیام فارسی برمی‌گردانند؛ بلعیدن
   * آن پیام یعنی کاربر فقط می‌بیند «چیزی کار نکرد» بدون اینکه بفهمد چرا.
   */
  async function run(operation: () => Promise<unknown>, successMessage: string) {
    setBusy(true)
    setMessage(null)
    try {
      await operation()
      setMessage(successMessage)
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  const seats = data?.seats
  const seatsFull = seats != null && seats.limit != null && seats.used >= seats.limit

  return (
    <div className="page">
      <PageHeader
        icon={UsersRound}
        title="کاربران"
        description="همکارانتان را دعوت کنید، نقششان را تعیین کنید، و دسترسی‌ها را مدیریت کنید."
      />

      {error && <div className="error">{error}</div>}

      <SectionCard
        icon={UserPlus}
        title="دعوت همکار"
        description={
          seats == null
            ? undefined
            : seats.limit == null
              ? `${seats.used} کاربر — پلن شما محدودیت تعداد کاربر ندارد.`
              : `${seats.used} از ${seats.limit} کاربر مجاز پلن شما استفاده شده است.`
        }
      >
        <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void run(async () => {
              const res = await inviteMember(token, { email, name, role_key: roleKey })
              setEmail('')
              setName('')
              if (!res.email_sent) {
                throw new Error('کاربر اضافه شد ولی ارسال ایمیل دعوت ناموفق بود — تنظیمات SMTP را بررسی کنید.')
              }
            }, 'دعوت ارسال شد. کاربر با کلیک روی لینک ایمیل، رمز خودش را می‌سازد.')
          }}
        >
          <label>
            ایمیل
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colleague@example.com"
              required
            />
          </label>
          <label>
            نام
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="نام و نام خانوادگی"
              required
            />
          </label>
          <label>
            نقش
            <select value={roleKey} onChange={(e) => setRoleKey(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || seatsFull}>
              <UserPlus size={14} /> ارسال دعوت
            </button>
          </div>
          {seatsFull && (
            <div className="hint">
              سقف کاربران پلن شما تکمیل است. برای افزودن کاربر تازه، یکی از کاربران را غیرفعال کنید یا پلن را ارتقا دهید.
            </div>
          )}
          {message && <div className="hint">{message}</div>}
        </form>
      </SectionCard>

      <SectionCard icon={ShieldCheck} title="کاربران کسب‌وکار">
        {data == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>نام</th>
                <th>ایمیل</th>
                <th>نقش</th>
                <th>وضعیت</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {data.members.map((m) => (
                <tr key={m.id}>
                  <td>
                    {m.name}
                    {m.is_me && <span className="muted"> (شما)</span>}
                  </td>
                  <td>{m.email}</td>
                  <td>
                    <select
                      value={m.role_key}
                      disabled={busy}
                      onChange={(e) =>
                        void run(() => changeMemberRole(token, m.id, e.target.value), `نقش ${m.name} تغییر کرد.`)
                      }
                    >
                      {ROLES.map((r) => (
                        <option key={r.key} value={r.key}>
                          {r.label}
                        </option>
                      ))}
                      {/* نقش سفارشی‌ای که در فهرست پیش‌فرض نیست نباید بی‌صدا به نقش دیگری تبدیل شود */}
                      {!ROLES.some((r) => r.key === m.role_key) && (
                        <option value={m.role_key}>{m.role_name}</option>
                      )}
                    </select>
                  </td>
                  <td>{STATUS_LABELS[m.status]}</td>
                  <td>
                    {!m.is_me && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void run(
                            () => setMemberActive(token, m.id, m.status === 'disabled'),
                            m.status === 'disabled' ? `${m.name} دوباره فعال شد.` : `دسترسی ${m.name} قطع شد.`,
                          )
                        }
                      >
                        {m.status === 'disabled' ? 'فعال‌سازی' : 'غیرفعال‌سازی'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <ChangePasswordCard token={token} me={me} />
    </div>
  )
}

function ChangePasswordCard({ token, me }: { token: string; me: MeResponse }) {
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
      <form className="invoice-form" onSubmit={handleSubmit}>
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
