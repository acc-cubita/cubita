import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Armchair,
  CheckCircle2,
  Clock,
  Mail,
  UserCheck,
  UserPlus,
  UsersRound,
} from 'lucide-react'
import {
  fetchMembers,
  fetchPermissionModules,
  fetchRoles,
  inviteMember,
  type MemberList,
  type PermissionMap,
  type PermissionModule,
  type RoleInfo,
} from '../api'
import { AccessCodeCard, type IssuedCode } from '../components/AccessCodeCard'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { PermissionMatrix, isFullAccess, summarize } from '../components/PermissionMatrix'
import { SearchSelect } from '../components/SearchSelect'
import { isEnterprise } from '../platform'

/**
 * کاربر جدید — نیمه‌ی «ساختن».
 *
 * فقط دعوت و تعیینِ دسترسیِ اولیه. کارِ روی کاربرِ موجود (نقش، دسترسی، فعال/غیرفعال)
 * در صفحه‌ی «کاربران» است، چون هر کنش به یک ردیفِ مشخص گره خورده و بدونِ دیدنِ آن
 * ردیف معنا ندارد.
 *
 * نقش این‌جا «نقطه‌ی شروع» است نه قفس: با انتخابِ نقش، جدولِ دسترسی با مجوزِ همان نقش
 * پر می‌شود و از آن‌جا می‌شود ماژول‌به‌ماژول دقیق‌ترش کرد. فهرستِ نقش‌ها و ماژول‌ها هم
 * از بک‌اند می‌آید نه از یک فهرستِ سختِ‌کدشده.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')

export function TeamPage({ token }: { token: string }) {
  const [data, setData] = useState<MemberList | null>(null)
  const [roles, setRoles] = useState<RoleInfo[]>([])
  const [modules, setModules] = useState<PermissionModule[]>([])
  const [message, setMessage] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [busy, setBusy] = useState(false)
  const [issued, setIssued] = useState<IssuedCode | null>(null)

  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [roleKey, setRoleKey] = useState('accountant')
  /** null = «همان مجوزِ نقش»؛ غیرِ null = دسترسیِ دستیِ این دعوت. */
  const [draft, setDraft] = useState<PermissionMap | null>(null)

  async function refresh() {
    try {
      setData(await fetchMembers(token))
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    // نقش‌ها و ماژول‌ها ثابت‌اند؛ یک بار کافی است.
    void fetchRoles(token).then(setRoles).catch(() => {})
    void fetchPermissionModules(token).then(setModules).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  /** پیامِ خطای سرور (سقفِ کاربران، ایمیلِ تکراری) همیشه باید دیده شود. */
  async function run(operation: () => Promise<unknown>, successMessage: string) {
    setBusy(true)
    setMessage(null)
    try {
      await operation()
      setMessage({ text: successMessage, kind: 'ok' })
      await refresh()
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const seats = data?.seats
  const seatsFull = seats != null && seats.limit != null && seats.used >= seats.limit
  const selectedRole = roles.find((r) => r.key === roleKey) ?? null
  // جدولِ دعوت: تا وقتی دست نخورده، آینه‌ی مجوزِ نقش است.
  const invitePerms = draft ?? selectedRole?.permissions ?? {}

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
        icon={UserPlus}
        title="کاربر جدید"
        description="همکار تازه دعوت کنید و دقیقاً مشخص کنید به کدام ماژول و کدام عملیات دسترسی داشته باشد."
      />

      {message && (
        <div className={`fy-note ${message.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {message.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{message.text}</div>
        </div>
      )}

      {issued && <AccessCodeCard issued={issued} onClose={() => setIssued(null)} />}

      <div className="stat-grid">
        <StatCard icon={<UsersRound size={18} />} label="کل کاربران" value={fa(kpis.total)} />
        <StatCard icon={<UserCheck size={18} />} label="کاربران فعال" value={fa(kpis.active)} tone="success" />
        <StatCard
          icon={<Clock size={18} />}
          label="دعوت‌های در انتظار"
          value={fa(kpis.invited)}
          tone={kpis.invited > 0 ? 'warning' : 'default'}
        />
        <StatCard
          icon={<Armchair size={18} />}
          label="صندلی‌های پلن"
          value={
            seats == null
              ? '—'
              : seats.limit == null
                ? 'نامحدود'
                : `${fa(seats.used)} از ${fa(seats.limit)}`
          }
        />
      </div>

      <SectionCard
        icon={UserPlus}
        title="دعوت همکار"
        description={
          seats == null
            ? undefined
            : seats.limit == null
              ? `${fa(seats.used)} کاربر — پلن شما محدودیت تعداد کاربر ندارد.`
              : `${fa(seats.used)} از ${fa(seats.limit)} کاربر مجاز پلن شما استفاده شده است.`
        }
      >
        <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void run(async () => {
              const res = await inviteMember(token, {
                email,
                name,
                role_key: roleKey,
                permissions: draft,
              })
              setEmail('')
              setName('')
              setDraft(null)
              if (res.code) {
                // سازمانی: ایمیلی نیست؛ کد یک‌بار نشان داده می‌شود و مالک دستی می‌دهدش.
                setIssued({ kind: 'invite', name: res.member.name, code: res.code, hours: 7 * 24 })
                return
              }
              if (!res.email_sent) {
                throw new Error('کاربر اضافه شد ولی ارسال ایمیل دعوت ناموفق بود — تنظیمات SMTP را بررسی کنید.')
              }
            }, isEnterprise
              ? 'کاربر اضافه شد. کدِ دعوت را پایین‌تر ببینید و به او بدهید.'
              : 'دعوت ارسال شد. کاربر با کلیک روی لینک ایمیل، رمز خودش را می‌سازد.')
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
            نقش (نقطه‌ی شروعِ دسترسی)
            <SearchSelect
              value={roleKey}
              onChange={(e) => {
                setRoleKey(e.target.value)
                // تغییرِ نقش یعنی «از این مجوز شروع کن»؛ ویرایشِ دستیِ قبلی کنار می‌رود.
                setDraft(null)
              }}
            >
              {roles.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.name}
                </option>
              ))}
            </SearchSelect>
            <span className="bk-hint">{selectedRole ? summarize(selectedRole.permissions) : ''}</span>
          </label>

          <div className="field-full">
            <PermissionMatrix
              modules={modules}
              value={invitePerms}
              readOnly={selectedRole != null && isFullAccess(selectedRole.permissions) && draft == null}
              onChange={setDraft}
              onReset={draft ? () => setDraft(null) : undefined}
              note={
                selectedRole && isFullAccess(selectedRole.permissions) && draft == null
                  ? 'نقشِ مالک دسترسیِ کامل دارد. برای محدودکردن، نقشِ دیگری انتخاب کنید.'
                  : draft
                    ? 'دسترسی دستی تنظیم شده و دیگر از نقش پیروی نمی‌کند.'
                    : 'همان مجوزِ نقش. با زدنِ هر تیک، دسترسیِ اختصاصی ساخته می‌شود.'
              }
            />
          </div>

          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || seatsFull}>
              <Mail size={14} /> ارسال دعوت
            </button>
          </div>
          {seatsFull && (
            <div className="hint">
              سقف کاربران پلن شما تکمیل است. برای افزودن کاربر تازه، یکی از کاربران را غیرفعال کنید یا پلن را ارتقا دهید.
            </div>
          )}
        </form>
      </SectionCard>
    </div>
  )
}
