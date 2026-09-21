/**
 * کاربرانِ ستاد — فقط مالکِ سامانه.
 *
 * صفحه‌ای که قبلاً اصلاً وجود نداشت، چون «کارمندِ ستاد» هم وجود نداشت: تا امروز
 * دسترسیِ مدیریتی یک ایمیل در متغیرِ محیطی بود و عوض‌کردنش یعنی ویرایشِ `.env` و
 * ری‌استارتِ سرویس.
 *
 * **قاعده‌ی ضدِقفل:** سرور نمی‌گذارد آخرین مالکِ فعال برداشته یا تنزل داده شود.
 * صفحه همین را جلوتر هم می‌گوید تا کاربر با ۴۰۹ غافلگیر نشود.
 */
import { useState } from 'react'
import { KeyRound, Plus, RefreshCw, Users } from 'lucide-react'

import {
  createStaff,
  fetchStaff,
  resetStaffPassword,
  setStaffRole,
  setStaffStatus,
  type StaffMe,
} from '../api'
import { formatJalali } from '../lib/jalali'
import {
  AsyncBlock,
  Card,
  Chip,
  Dialog,
  Field,
  FieldGrid,
  Note,
  PageHeader,
  TableScroll,
  faInt,
  useAsync,
} from '../ui/kit'

const ROLES: { key: string; label: string; hint: string }[] = [
  { key: 'owner', label: 'مالکِ سامانه', hint: 'همه‌چیز، از جمله حذفِ اکانت و مدیریتِ ستاد' },
  { key: 'admin', label: 'مدیر', hint: 'اکانت‌ها، حسابرسی، مالی و پشتیبانی — بدونِ حذفِ اکانت' },
  { key: 'finance', label: 'مالی', hint: 'خریدها، کمیسیون و پلن‌ها؛ اکانت‌ها فقط خواندنی' },
  { key: 'support', label: 'پشتیبانی', hint: 'دیدنِ اکانت‌ها و خطاها؛ بدونِ تغییر' },
]

export default function StaffPage({
  token,
  me,
  onUnauthorized,
}: {
  token: string
  me: StaffMe
  onUnauthorized: (e: unknown) => void
}) {
  const { data, loading, error, reload } = useAsync(() => fetchStaff(token), [token])
  const [creating, setCreating] = useState(false)
  const [msg, setMsg] = useState<{ kind: 'ok' | 'bad'; text: string } | null>(null)

  const rows = data ?? []
  const activeOwners = rows.filter((r) => r.role === 'owner' && r.is_active).length

  async function act(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn()
      setMsg({ kind: 'ok', text: ok })
      reload()
    } catch (e) {
      onUnauthorized(e)
      setMsg({ kind: 'bad', text: e instanceof Error ? e.message : 'انجام نشد' })
    }
  }

  return (
    <>
      <PageHeader
        icon={Users}
        title="کاربران ستاد"
        description="چه کسی به پنلِ مدیریت دسترسی دارد و با چه نقشی."
        actions={
          <>
            <button type="button" className="ad-btn" onClick={reload}>
              <RefreshCw size={15} /> تازه‌سازی
            </button>
            <button type="button" className="ad-btn primary" onClick={() => setCreating(true)}>
              <Plus size={15} /> کاربرِ تازه
            </button>
          </>
        }
      />

      {activeOwners < 2 ? (
        <p className="ad-note tone-warn">
          فقط {faInt(activeOwners)} مالکِ فعال دارید. بازیابیِ رمزِ ستاد خودکار نیست،
          پس اگر رمزِ همین حساب گم شود راهِ برگشت فقط SSH است — یک مالکِ دوم بسازید.
        </p>
      ) : null}

      <Note msg={msg} />

      <Card>
        <AsyncBlock loading={loading} error={error} empty={rows.length === 0} emptyText="کاربرِ ستادی ثبت نشده.">
          <TableScroll>
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>ایمیل</th>
                  <th>نقش</th>
                  <th>وضعیت</th>
                  <th>آخرین ورود</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id}>
                    <td className="card-title" data-label="نام">
                      {s.name}
                      {s.user_id === me.user_id ? <Chip text="شما" tone="mute" /> : null}
                    </td>
                    <td data-label="ایمیل" dir="ltr">
                      {s.email}
                    </td>
                    <td data-label="نقش">
                      <select
                        className="ad-select"
                        value={s.role}
                        onChange={(e) =>
                          act(
                            () => setStaffRole(token, s.id, e.target.value),
                            `نقشِ ${s.email} عوض شد.`,
                          )
                        }
                        aria-label={`نقشِ ${s.name}`}
                      >
                        {ROLES.map((r) => (
                          <option key={r.key} value={r.key}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td data-label="وضعیت">
                      {s.is_active ? (
                        <Chip text="فعال" tone="ok" />
                      ) : (
                        <Chip text="غیرفعال" tone="mute" />
                      )}
                    </td>
                    <td data-label="آخرین ورود">{formatJalali(s.last_login_at)}</td>
                    <td className="card-actions">
                      <button
                        type="button"
                        className="ad-btn small"
                        onClick={() =>
                          act(
                            () => setStaffStatus(token, s.id, !s.is_active),
                            s.is_active ? 'کاربر غیرفعال شد.' : 'کاربر فعال شد.',
                          )
                        }
                      >
                        {s.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}
                      </button>
                      <button
                        type="button"
                        className="ad-btn small"
                        onClick={() => {
                          const pw = window.prompt(`رمزِ تازه برای ${s.email} (دستِ‌کم ۱۰ نویسه):`)
                          if (pw) {
                            act(
                              () => resetStaffPassword(token, s.id, pw),
                              'رمز بازنشانی شد و نشست‌های بازش باطل شدند.',
                            )
                          }
                        }}
                      >
                        <KeyRound size={14} /> رمزِ تازه
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        </AsyncBlock>
      </Card>

      <Card title="نقش‌ها چه می‌توانند">
        <TableScroll>
          <table className="cards-on-mobile">
            <thead>
              <tr>
                <th>نقش</th>
                <th>دسترسی</th>
              </tr>
            </thead>
            <tbody>
              {ROLES.map((r) => (
                <tr key={r.key}>
                  <td className="card-title" data-label="نقش">
                    {r.label}
                  </td>
                  <td data-label="دسترسی">{r.hint}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
      </Card>

      {creating ? (
        <CreateStaffDialog
          onClose={() => setCreating(false)}
          onSubmit={(form) =>
            act(() => createStaff(token, form), `کاربرِ ستادِ «${form.name}» ساخته شد.`).then(() =>
              setCreating(false),
            )
          }
        />
      ) : null}
    </>
  )
}

function CreateStaffDialog({
  onClose,
  onSubmit,
}: {
  onClose: () => void
  onSubmit: (form: { name: string; email: string; password: string; role: string }) => void
}) {
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'support' })
  const missing = !form.name
    ? 'نام'
    : !form.email
      ? 'ایمیل'
      : form.password.length < 10
        ? 'رمزِ دستِ‌کم ۱۰ نویسه‌ای'
        : null

  return (
    <Dialog
      title="کاربرِ ستادِ تازه"
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            className="ad-btn primary"
            disabled={!!missing}
            onClick={() => onSubmit(form)}
          >
            ساختِ کاربر
          </button>
          {missing ? <span className="ad-field-hint">{missing} لازم است</span> : null}
        </>
      }
    >
      <p className="ad-field-hint">
        اگر این ایمیل از قبل کاربرِ کوبیتا باشد، همان حساب کارمندِ ستاد می‌شود و رمزِ
        خودش را نگه می‌دارد.
      </p>
      <FieldGrid>
        <Field label="نام">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="ایمیل">
          <input
            type="email"
            dir="ltr"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </Field>
        <Field label="رمزِ اولیه" hint="دستِ‌کم ۱۰ نویسه">
          <input
            dir="ltr"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </Field>
        <Field label="نقش" hint={ROLES.find((r) => r.key === form.role)?.hint}>
          <select
            className="ad-select"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
          >
            {ROLES.map((r) => (
              <option key={r.key} value={r.key}>
                {r.label}
              </option>
            ))}
          </select>
        </Field>
      </FieldGrid>
    </Dialog>
  )
}
