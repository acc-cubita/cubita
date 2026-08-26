import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Mail, RotateCcw, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import {
  changeMemberRole,
  fetchMembers,
  fetchPermissionModules,
  fetchRoles,
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
import { PermissionMatrix, isFullAccess, summarize } from '../components/PermissionMatrix'

/**
 * فهرستِ کاربران — نیمه‌ی «دیدن و مدیریت‌کردن».
 *
 * صفحه‌ی «کاربر جدید» فقط دعوت می‌کند؛ کارِ روی کاربرِ موجود (نقش، دسترسی، فعال/غیرفعال،
 * ارسالِ دوباره‌ی دعوت) این‌جاست، چون هر کنش به یک ردیفِ مشخص گره خورده و بدونِ دیدنِ
 * ردیف معنا ندارد.
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

export function UserListPage({ token }: { token: string }) {
  const [data, setData] = useState<MemberList | null>(null)
  const [roles, setRoles] = useState<RoleInfo[]>([])
  const [modules, setModules] = useState<PermissionModule[]>([])
  const [message, setMessage] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<{ member: Member; perms: PermissionMap } | null>(null)
  const pg = usePagination(data?.members ?? [], 12)

  async function refresh() {
    try {
      setData(await fetchMembers(token))
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    void fetchRoles(token).then(setRoles).catch(() => {})
    void fetchPermissionModules(token).then(setModules).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  /** پیامِ خطای سرور (سقفِ کاربران، گاردِ آخرین مالک) همیشه باید دیده شود. */
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

  const custom = (data?.members ?? []).filter((m) => m.custom_permissions).length

  return (
    <div className="page panels">
      <PageHeader
        icon={ShieldCheck}
        title="کاربران"
        description="کاربرانِ این کسب‌وکار: نقش، دسترسی و وضعیتِ هرکدام."
      />

      {message && (
        <div className={`fy-note ${message.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {message.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{message.text}</div>
        </div>
      )}

      <SectionCard
        icon={ShieldCheck}
        title="کاربران کسب‌وکار"
        description={
          custom > 0
            ? `${fa(custom)} کاربر دسترسیِ اختصاصی دارد و از نقشش پیروی نمی‌کند.`
            : 'همه‌ی کاربران از مجوزِ نقششان پیروی می‌کنند.'
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
                        {/* نقشِ سفارشی‌ای که در فهرست نیست نباید بی‌صدا به نقشِ دیگری تبدیل شود */}
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
                      <span className={`status-badge tone-${STATUS_TONE[m.status]}`}>
                        {STATUS_LABELS[m.status]}
                      </span>
                    </td>
                    <td className="card-actions">
                      <div className="fy-actions">
                        {/* دسترسیِ خودِ کاربر عمداً این‌جا قابلِ تغییر نیست؛ سرور هم ۴۰۹
                            می‌دهد. یک کلیکِ اشتباه نباید مدیر را از پنل بیرون کند. */}
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
