import { useEffect, useMemo, useState } from 'react'
import { Armchair, Clock, ShieldCheck, UserCheck, UserPlus, UsersRound } from 'lucide-react'
import {
  changeMemberRole,
  fetchMembers,
  inviteMember,
  setMemberActive,
  type Member,
  type MemberList,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { Pager, usePagination } from '../components/Pager'
import { StatCard } from '../components/StatCard'

const STATUS_TONE: Record<Member['status'], 'success' | 'warning' | 'default'> = {
  active: 'success',
  invited: 'warning',
  disabled: 'default',
}

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

export function TeamPage({ token }: { token: string }) {
  const [data, setData] = useState<MemberList | null>(null)
  const pg = usePagination(data?.members ?? [], 10)
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

  const kpis = useMemo(() => {
    const members = data?.members ?? []
    return {
      total: members.length,
      active: members.filter((m) => m.status === 'active').length,
      invited: members.filter((m) => m.status === 'invited').length,
    }
  }, [data])

  return (
    <div className="page panels">
      <PageHeader
        icon={UsersRound}
        title="کاربران"
        description="همکارانتان را دعوت کنید، نقششان را تعیین کنید، و دسترسی‌ها را مدیریت کنید."
      />

      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard icon={<UsersRound size={18} />} label="کل کاربران" value={kpis.total.toLocaleString('fa-IR')} />
        <StatCard icon={<UserCheck size={18} />} label="کاربران فعال" value={kpis.active.toLocaleString('fa-IR')} tone="success" />
        <StatCard
          icon={<Clock size={18} />}
          label="دعوت‌های در انتظار"
          value={kpis.invited.toLocaleString('fa-IR')}
          tone={kpis.invited > 0 ? 'warning' : 'default'}
        />
        <StatCard
          icon={<Armchair size={18} />}
          label="صندلی‌های پلن"
          value={seats == null ? '—' : seats.limit == null ? 'نامحدود' : `${seats.used.toLocaleString('fa-IR')} از ${seats.limit.toLocaleString('fa-IR')}`}
        />
      </div>

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
          <div className="entity-table-wrap">
          <table className="entity-table">
            <thead>
              <tr>
                <th>کاربر</th>
                <th>نقش</th>
                <th>وضعیت</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {pg.pageItems.map((m) => (
                <tr key={m.id}>
                  <td>
                    <div className="entity-cell">
                      <div className="entity-avatar">{m.name.trim().charAt(0) || '؟'}</div>
                      <div>
                        <div className="entity-name">
                          {m.name}
                          {m.is_me && <span className="muted"> (شما)</span>}
                        </div>
                        <div className="entity-sub ltr-cell">{m.email}</div>
                      </div>
                    </div>
                  </td>
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
                  <td>
                    <span className={`status-badge tone-${STATUS_TONE[m.status]}`}>{STATUS_LABELS[m.status]}</span>
                  </td>
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
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}
