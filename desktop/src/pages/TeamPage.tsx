import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Armchair,
  CheckCircle2,
  Clock,
  Mail,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  UserCheck,
  UserPlus,
  UsersRound,
} from 'lucide-react'
import {
  changeMemberRole,
  fetchMembers,
  fetchPermissionModules,
  fetchRoles,
  inviteMember,
  resendInvite,
  setMemberActive,
  setMemberPermissions,
  type Member,
  type MemberList,
  type PermissionMap,
  type PermissionModule,
  type RoleInfo,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { Pager, usePagination } from '../components/Pager'
import { StatCard } from '../components/StatCard'

/**
 * کاربران و دسترسی‌ها.
 *
 * تغییرِ اصلی نسبت به نسخه‌ی قبل: **دسترسی دیگر فقط «نقش» نیست.** پیش‌تر تنها کاری که
 * می‌شد کرد انتخاب یکی از شش نقشِ سختِ‌کدشده در همین فایل بود؛ اگر می‌خواستی کسی
 * فاکتور بزند ولی حسابداری را نبیند، هیچ راهی نداشتی.
 *
 * حالا نقش «نقطه‌ی شروع» است: با انتخابِ نقش، جدولِ دسترسی با مجوزِ همان نقش پر
 * می‌شود و از آن‌جا می‌شود ماژول‌به‌ماژول و اکشن‌به‌اکشن دقیق‌ترش کرد. فهرستِ ماژول‌ها و
 * نقش‌ها هم دیگر حدس نیست: هر دو از بک‌اند می‌آیند.
 */

const STATUS_TONE: Record<Member['status'], 'success' | 'warning' | 'default'> = {
  active: 'success',
  invited: 'warning',
  disabled: 'default',
}

const STATUS_LABELS: Record<Member['status'], string> = {
  active: 'فعال',
  invited: 'در انتظار پذیرش دعوت',
  disabled: 'غیرفعال',
}

const fa = (n: number) => n.toLocaleString('fa-IR')

/** آیا این نقشه دسترسیِ کامل («*») می‌دهد؟ نقشِ مالک همین است. */
const isFullAccess = (p: PermissionMap) => Array.isArray(p['*'])

/** شمارِ اکشن‌های داده‌شده — برای خلاصه‌ی «۳ ماژول، ۷ اجازه». */
function summarize(p: PermissionMap): string {
  if (isFullAccess(p)) return 'دسترسی کامل'
  const modules = Object.keys(p).filter((k) => (p[k] ?? []).length > 0)
  if (modules.length === 0) return 'بدون دسترسی'
  const actions = modules.reduce((sum, k) => sum + (p[k]?.length ?? 0), 0)
  return `${fa(modules.length)} ماژول · ${fa(actions)} اجازه`
}

export function TeamPage({ token }: { token: string }) {
  const [data, setData] = useState<MemberList | null>(null)
  const [roles, setRoles] = useState<RoleInfo[]>([])
  const [modules, setModules] = useState<PermissionModule[]>([])
  const pg = usePagination(data?.members ?? [], 10)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [busy, setBusy] = useState(false)

  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [roleKey, setRoleKey] = useState('accountant')
  /** null = «همان مجوزِ نقش»؛ غیرِ null = دسترسیِ دستیِ این دعوت. */
  const [draft, setDraft] = useState<PermissionMap | null>(null)
  /** عضوی که جدولِ دسترسی‌اش باز است. */
  const [editing, setEditing] = useState<{ member: Member; perms: PermissionMap } | null>(null)

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
    // نقش‌ها و ماژول‌ها ثابت‌اند؛ یک بار کافی است.
    void fetchRoles(token).then(setRoles).catch(() => {})
    void fetchPermissionModules(token).then(setModules).catch(() => {})
    // فقط با تغییرِ توکن؛ بقیه‌ی به‌روزرسانی‌ها پس از هر عملیات دستی انجام می‌شود.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

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
      custom: members.filter((m) => m.custom_permissions).length,
    }
  }, [data])

  return (
    <div className="page panels">
      <PageHeader
        icon={UsersRound}
        title="کاربران و دسترسی‌ها"
        description="همکار تازه دعوت کنید و دقیقاً مشخص کنید به کدام ماژول و کدام عملیات دسترسی داشته باشد."
      />

      {error && <div className="fy-note fy-note--err"><AlertTriangle size={16} /><div>{error}</div></div>}
      {message && (
        <div className={`fy-note ${message.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {message.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{message.text}</div>
        </div>
      )}

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
        title="کاربر جدید"
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
            نقش (نقطه‌ی شروعِ دسترسی)
            <select
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
            </select>
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

      <SectionCard
        icon={ShieldCheck}
        title="کاربران کسب‌وکار"
        description={
          kpis.custom > 0
            ? `${fa(kpis.custom)} کاربر دسترسیِ اختصاصی دارد و از نقشش پیروی نمی‌کند.`
            : undefined
        }
      >
        {data == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr>
                  <th>کاربر</th>
                  <th>نقش</th>
                  <th>دسترسی</th>
                  <th>وضعیت</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((m) => (
                  <tr key={m.id}>
                    <td className="card-title">
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
                    <td data-label="نقش">
                      <select
                        value={m.role_key}
                        disabled={busy}
                        onChange={(e) =>
                          void run(() => changeMemberRole(token, m.id, e.target.value), `نقش ${m.name} تغییر کرد.`)
                        }
                      >
                        {roles.map((r) => (
                          <option key={r.key} value={r.key}>
                            {r.name}
                          </option>
                        ))}
                        {/* نقش سفارشی‌ای که در فهرست نیست نباید بی‌صدا به نقش دیگری تبدیل شود */}
                        {!roles.some((r) => r.key === m.role_key) && (
                          <option value={m.role_key}>{m.role_name}</option>
                        )}
                      </select>
                    </td>
                    <td data-label="دسترسی">
                      <span className="tm-perm-sum">
                        {summarize(m.permissions)}
                        {m.custom_permissions && <span className="fy-badge fy-badge--active">اختصاصی</span>}
                      </span>
                    </td>
                    <td data-label="وضعیت">
                      <span className={`status-badge tone-${STATUS_TONE[m.status]}`}>{STATUS_LABELS[m.status]}</span>
                    </td>
                    <td className="card-actions">
                      <div className="fy-actions">
                        {/* دسترسیِ خودِ کاربر عمداً از این‌جا قابلِ تغییر نیست؛ سرور هم
                            ۴۰۹ می‌دهد. یک کلیکِ اشتباه نباید مدیر را از پنل بیرون کند. */}
                        {!m.is_me && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => setEditing({ member: m, perms: m.permissions })}
                          >
                            <SlidersHorizontal size={13} /> دسترسی
                          </button>
                        )}
                        {m.status === 'invited' && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() =>
                              void run(async () => {
                                const r = await resendInvite(token, m.id)
                                if (!r.email_sent) throw new Error('ارسال ایمیل دعوت ناموفق بود.')
                              }, `دعوت دوباره برای ${m.name} ارسال شد.`)
                            }
                          >
                            <Mail size={13} /> ارسال دوباره
                          </button>
                        )}
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
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}
      </SectionCard>

      {editing && (
        <SectionCard
          icon={SlidersHorizontal}
          title={`دسترسیِ ${editing.member.name}`}
          description={
            editing.member.custom_permissions
              ? 'این کاربر دسترسیِ اختصاصی دارد؛ تغییرِ نقش روی آن اثری ندارد تا به مجوزِ نقش برگردانده شود.'
              : 'در حالِ حاضر از مجوزِ نقشش پیروی می‌کند. با ذخیره، دسترسیِ اختصاصی ساخته می‌شود.'
          }
          actions={
            <button type="button" onClick={() => setEditing(null)}>
              بستن
            </button>
          }
        >
          <PermissionMatrix
            modules={modules}
            value={editing.perms}
            readOnly={isFullAccess(editing.perms)}
            onChange={(perms) => setEditing({ ...editing, perms: perms ?? {} })}
            note={
              isFullAccess(editing.perms)
                ? 'این کاربر دسترسیِ کامل (نقشِ مالک) دارد. برای محدودکردن، ابتدا نقشش را عوض کنید.'
                : undefined
            }
          />
          <div className="invoice-form-footer tm-editor-footer">
            <button
              type="button"
              className="btn-primary"
              disabled={busy || isFullAccess(editing.perms)}
              onClick={() =>
                void run(async () => {
                  await setMemberPermissions(token, editing.member.id, editing.perms)
                  setEditing(null)
                }, `دسترسیِ ${editing.member.name} ذخیره شد.`)
              }
            >
              ذخیره‌ی دسترسی
            </button>
            {editing.member.custom_permissions && (
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    await setMemberPermissions(token, editing.member.id, null)
                    setEditing(null)
                  }, `دسترسیِ ${editing.member.name} به مجوزِ نقش برگشت.`)
                }
              >
                <RotateCcw size={13} /> بازگشت به مجوزِ نقش
              </button>
            )}
          </div>
        </SectionCard>
      )}
    </div>
  )
}

/**
 * جدولِ ماژول × اکشن.
 *
 * «مشاهده» ستونِ ویژه است: بدونِ آن هیچ اکشنِ دیگری معنا ندارد (کاربر اجازه‌ی ثبت
 * دارد ولی صفحه‌ای برای دیدنش نه). پس برداشتنِ «مشاهده» کلِ ماژول را پاک می‌کند و
 * زدنِ هر اکشنِ دیگر، «مشاهده» را هم روشن می‌کند — همان قاعده‌ای که سرور هم اعمال
 * می‌کند، تا آنچه می‌بینید همان چیزی باشد که ذخیره می‌شود.
 */
function PermissionMatrix({
  modules,
  value,
  onChange,
  onReset,
  readOnly,
  note,
}: {
  modules: PermissionModule[]
  value: PermissionMap
  onChange: (next: PermissionMap | null) => void
  onReset?: () => void
  readOnly?: boolean
  note?: string
}) {
  if (modules.length === 0) return null

  const has = (mod: string, action: string) => (value[mod] ?? []).includes(action)

  function toggle(mod: PermissionModule, action: string) {
    if (readOnly) return
    const current = new Set(value[mod.key] ?? [])
    if (action === 'view' && current.has('view')) {
      current.clear()
    } else if (current.has(action)) {
      current.delete(action)
    } else {
      current.add(action)
      current.add('view')
    }
    const next: PermissionMap = { ...value }
    if (current.size === 0) delete next[mod.key]
    else next[mod.key] = mod.actions.map((a) => a.key).filter((k) => current.has(k))
    onChange(next)
  }

  function toggleWholeModule(mod: PermissionModule) {
    if (readOnly) return
    const next: PermissionMap = { ...value }
    if ((value[mod.key] ?? []).length === mod.actions.length) delete next[mod.key]
    else next[mod.key] = mod.actions.map((a) => a.key)
    onChange(next)
  }

  return (
    <div className="tm-matrix">
      <div className="tm-matrix-head">
        <span>دسترسی به ماژول‌ها</span>
        <span className="tm-matrix-sum">{summarize(value)}</span>
        {onReset && (
          <button type="button" onClick={onReset}>
            <RotateCcw size={12} /> بازگشت به نقش
          </button>
        )}
      </div>
      {note && <p className="bk-hint tm-matrix-note">{note}</p>}
      <div className="table-scroll">
        <table className="tm-matrix-table">
          <thead>
            <tr>
              <th>ماژول</th>
              {['مشاهده', 'ثبت', 'ویرایش', 'حذف', 'تأیید', 'تحویل'].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {modules.map((mod) => {
              const granted = (value[mod.key] ?? []).length
              return (
                <tr key={mod.key} className={granted > 0 ? 'on' : ''}>
                  <th scope="row">
                    <button
                      type="button"
                      className="tm-mod-name"
                      onClick={() => toggleWholeModule(mod)}
                      disabled={readOnly}
                      title="روشن/خاموش‌کردنِ همه‌ی اجازه‌های این ماژول"
                    >
                      {mod.label}
                    </button>
                    {mod.hint && <span className="tm-mod-hint">{mod.hint}</span>}
                  </th>
                  {['view', 'create', 'update', 'delete', 'approve', 'deliver'].map((action) => {
                    const supported = mod.actions.some((a) => a.key === action)
                    return (
                      <td key={action}>
                        {supported ? (
                          <input
                            type="checkbox"
                            checked={has(mod.key, action)}
                            disabled={readOnly}
                            onChange={() => toggle(mod, action)}
                            aria-label={`${mod.label} — ${action}`}
                          />
                        ) : (
                          <span className="tm-na">—</span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
