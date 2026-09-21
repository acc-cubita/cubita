/**
 * مدیریت اکانت‌ها — دفترِ مشتریانِ کوبیتا.
 *
 * بازنویسیِ `desktop/src/pages/AccountsAdminPage.tsx` با سه تفاوتِ عمدی:
 *
 * ۱. فیلتر و جست‌وجو روی همه‌ی ستون‌های معنادار، نه فقط «آزمایشی/پولی».
 * ۲. کشوی جزئیات به‌جای بازشدنِ ردیف — کنش‌ها جایی جمع می‌شوند که کاربر
 *    کسب‌وکار را دیده باشد، نه وسطِ فهرست.
 * ۳. حذف سه گارد دارد (نقشِ مالک، تایپِ شناسه، دلیل) و ردِ ستادی می‌نویسد.
 */
import { useMemo, useState } from 'react'
import { Plus, RefreshCw, Search, ShieldCheck, Trash2 } from 'lucide-react'

import {
  createAccount,
  deleteAccount,
  extendAccount,
  fetchAccounts,
  resetAccountPassword,
  setAccountStatus,
  type Account,
  type StaffMe,
} from '../api'
import { textMatches } from '../lib/faText'
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
  RowAction,
  Stat,
  TableScroll,
  faInt,
  useAsync,
} from '../ui/kit'

type Filter = 'all' | 'trial' | 'paid' | 'expiring' | 'suspended'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'همه' },
  { key: 'trial', label: 'آزمایشی' },
  { key: 'paid', label: 'پولی' },
  { key: 'expiring', label: 'رو به انقضا' },
  { key: 'suspended', label: 'تعلیق‌شده' },
]

/** «۳ روز پیش» — عددِ خام برای «آخرین فعالیت» خوانا نیست. */
function relativeFa(iso: string | null): string {
  if (!iso) return 'هرگز'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'امروز'
  if (days === 1) return 'دیروز'
  if (days < 30) return `${faInt(days)} روز پیش`
  if (days < 365) return `${faInt(Math.floor(days / 30))} ماه پیش`
  return `${faInt(Math.floor(days / 365))} سال پیش`
}

function statusTone(a: Account): 'ok' | 'warn' | 'bad' | 'mute' {
  if (a.status !== 'active') return 'bad'
  if (a.subscription_status === 'expired') return 'bad'
  if (a.days_left != null && a.days_left <= 14) return 'warn'
  if (a.is_trial) return 'warn'
  return 'ok'
}

function statusText(a: Account): string {
  if (a.status !== 'active') return 'تعلیق‌شده'
  if (a.is_trial) return `آزمایشی — ${faInt(a.trial_days_left)} روز`
  if (a.subscription_status === 'expired') return 'منقضی'
  if (a.days_left != null) return `${faInt(a.days_left)} روز مانده`
  return 'بدونِ اشتراک'
}

export default function AccountsPage({
  token,
  me,
  onUnauthorized,
}: {
  token: string
  me: StaffMe
  onUnauthorized: (e: unknown) => void
}) {
  const { data, loading, error, reload } = useAsync(() => fetchAccounts(token), [token])
  const [filter, setFilter] = useState<Filter>('all')
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<Account | null>(null)
  const [creating, setCreating] = useState(false)
  const [msg, setMsg] = useState<{ kind: 'ok' | 'bad'; text: string } | null>(null)

  const rows = data ?? []

  const kpis = useMemo(() => {
    const active = rows.filter((r) => r.status === 'active')
    return {
      total: rows.length,
      trial: rows.filter((r) => r.is_trial).length,
      paid: active.filter((r) => !r.is_trial && r.subscription_status === 'active').length,
      expiring: active.filter((r) => r.days_left != null && r.days_left <= 14 && r.days_left >= 0)
        .length,
      dead: rows.filter((r) => r.status !== 'active' || r.subscription_status === 'expired').length,
    }
  }, [rows])

  const shown = useMemo(
    () =>
      rows.filter((r) => {
        if (filter === 'trial' && !r.is_trial) return false
        if (filter === 'paid' && (r.is_trial || r.subscription_status !== 'active')) return false
        if (filter === 'expiring' && !(r.days_left != null && r.days_left <= 14 && r.days_left >= 0))
          return false
        if (filter === 'suspended' && r.status === 'active') return false
        //: `textMatches` و نه `includes`: «طرف حساب» با فاصله‌ی معمولی باید
        //: «طرف‌حساب» با نیم‌فاصله را هم پیدا کند، و «ي/ك»ِ عربی را هم.
        return textMatches(
          [r.name, r.slug, r.owner_email, r.owner_name].filter(Boolean).join(' '),
          q,
        )
      }),
    [rows, filter, q],
  )

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
        icon={ShieldCheck}
        title="مدیریت اکانت‌ها"
        description="همه‌ی کسب‌وکارهای کوبیتا، وضعیتِ اشتراک و کنش‌های مدیریتی."
        actions={
          <>
            <button type="button" className="ad-btn" onClick={reload}>
              <RefreshCw size={15} /> تازه‌سازی
            </button>
            <button type="button" className="ad-btn primary" onClick={() => setCreating(true)}>
              <Plus size={15} /> اکانت تازه
            </button>
          </>
        }
      />

      <section className="ad-stats">
        <Stat label="کلِ اکانت‌ها" value={faInt(kpis.total)} />
        <Stat label="اشتراکِ فعال" value={faInt(kpis.paid)} tone="ok" />
        <Stat label="آزمایشی" value={faInt(kpis.trial)} tone="warn" />
        <Stat label="انقضا تا ۱۴ روز" value={faInt(kpis.expiring)} tone="warn" />
        <Stat label="منقضی یا تعلیق" value={faInt(kpis.dead)} tone="bad" />
      </section>

      <Note msg={msg} />

      <Card>
        <div className="ad-toolbar">
          <div className="ad-search">
            <Search size={15} />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="نام، شناسه یا ایمیلِ مالک"
              aria-label="جست‌وجو"
            />
          </div>
          <div className="ad-segments">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                className={`ad-segment${filter === f.key ? ' active' : ''}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
          <span className="ad-count">{faInt(shown.length)} مورد</span>
        </div>

        <AsyncBlock
          loading={loading}
          error={error}
          empty={shown.length === 0}
          emptyText="اکانتی با این شرایط پیدا نشد. فیلتر یا جست‌وجو را عوض کنید."
        >
          <TableScroll>
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>کسب‌وکار</th>
                  <th>مالک</th>
                  <th>وضعیت</th>
                  <th>انقضا</th>
                  <th>کاربران</th>
                  <th>آخرین فعالیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shown.map((a) => (
                  <tr key={a.tenant_id}>
                    <td className="card-title" data-label="کسب‌وکار">
                      {a.name}
                      <span className="ad-sub" dir="ltr">
                        {a.slug}
                      </span>
                    </td>
                    <td data-label="مالک">
                      {a.owner_name ?? '—'}
                      <span className="ad-sub" dir="ltr">
                        {a.owner_email ?? '—'}
                      </span>
                    </td>
                    <td data-label="وضعیت">
                      <Chip text={statusText(a)} tone={statusTone(a)} />
                    </td>
                    <td data-label="انقضا">{formatJalali(a.expires_at)}</td>
                    <td className="num" data-label="کاربران">
                      {faInt(a.user_count)}
                      {a.max_users ? ` / ${faInt(a.max_users)}` : ''}
                    </td>
                    <td data-label="آخرین فعالیت">{relativeFa(a.last_activity_at)}</td>
                    <td className="card-actions">
                      <button type="button" className="ad-btn small" onClick={() => setOpen(a)}>
                        جزئیات
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        </AsyncBlock>
      </Card>

      {open ? (
        <AccountDrawer
          account={open}
          me={me}
          onClose={() => setOpen(null)}
          onAct={act}
          token={token}
        />
      ) : null}

      {creating ? (
        <CreateDialog token={token} onClose={() => setCreating(false)} onAct={act} />
      ) : null}
    </>
  )
}

function AccountDrawer({
  account,
  me,
  token,
  onClose,
  onAct,
}: {
  account: Account
  me: StaffMe
  token: string
  onClose: () => void
  onAct: (fn: () => Promise<unknown>, ok: string) => Promise<void>
}) {
  const [confirming, setConfirming] = useState(false)

  return (
    <Dialog title={account.name} onClose={onClose}>
      <dl className="ad-dl">
        <div>
          <dt>شناسه</dt>
          <dd dir="ltr">{account.slug}</dd>
        </div>
        <div>
          <dt>مالک</dt>
          <dd dir="ltr">{account.owner_email ?? '—'}</dd>
        </div>
        <div>
          <dt>پلن</dt>
          <dd>{account.plan_name ?? '—'}</dd>
        </div>
        <div>
          <dt>ساخته شده</dt>
          <dd>{formatJalali(account.created_at)}</dd>
        </div>
        <div>
          <dt>انقضا</dt>
          <dd>{formatJalali(account.expires_at)}</dd>
        </div>
        <div>
          <dt>صنف</dt>
          <dd>{account.industry ?? '—'}</dd>
        </div>
      </dl>

      <h4 className="ad-h4">تمدیدِ اشتراک</h4>
      <div className="ad-btn-row">
        {[30, 90, 180, 365].map((d) => (
          <button
            key={d}
            type="button"
            className="ad-btn small"
            onClick={() =>
              onAct(
                () => extendAccount(token, account.tenant_id, d),
                `اشتراکِ «${account.name}» ${faInt(d)} روز تمدید شد.`,
              )
            }
          >
            + {faInt(d)} روز
          </button>
        ))}
      </div>

      <h4 className="ad-h4">کاربرانِ این کسب‌وکار</h4>
      <TableScroll>
        <table className="cards-on-mobile">
          <thead>
            <tr>
              <th>نام</th>
              <th>ایمیل</th>
              <th>آخرین ورود</th>
            </tr>
          </thead>
          <tbody>
            {account.users.map((u) => (
              <tr key={u.email}>
                <td className="card-title" data-label="نام">
                  {u.name}
                  {u.is_owner ? <Chip text="مالک" tone="mute" /> : null}
                </td>
                <td data-label="ایمیل" dir="ltr">
                  {u.email}
                </td>
                <td data-label="آخرین ورود">{relativeFa(u.last_login_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>

      <h4 className="ad-h4">کنش‌های مدیریتی</h4>
      <div className="ad-btn-row">
        <button
          type="button"
          className="ad-btn small"
          onClick={() =>
            onAct(
              () =>
                setAccountStatus(
                  token,
                  account.tenant_id,
                  account.status === 'active' ? 'suspended' : 'active',
                ),
              account.status === 'active' ? 'اکانت تعلیق شد.' : 'اکانت فعال شد.',
            )
          }
        >
          {account.status === 'active' ? 'تعلیقِ اکانت' : 'فعال‌سازیِ اکانت'}
        </button>

        <button
          type="button"
          className="ad-btn small"
          onClick={() => {
            const pw = window.prompt('رمزِ تازه‌ی مالک (دستِ‌کم ۱۰ نویسه):')
            if (pw) {
              onAct(
                () => resetAccountPassword(token, account.tenant_id, pw),
                'رمزِ مالک بازنشانی شد و نشست‌های بازش باطل شدند.',
              )
            }
          }}
        >
          بازنشانیِ رمزِ مالک
        </button>

        {me.role === 'owner' ? (
          <RowAction
            icon={Trash2}
            label="حذفِ کاملِ اکانت"
            danger
            onClick={() => setConfirming(true)}
          />
        ) : null}
      </div>

      {confirming ? (
        <DeleteConfirm
          account={account}
          token={token}
          onAct={onAct}
          onDone={() => {
            setConfirming(false)
            onClose()
          }}
          onCancel={() => setConfirming(false)}
        />
      ) : null}
    </Dialog>
  )
}

function DeleteConfirm({
  account,
  token,
  onAct,
  onDone,
  onCancel,
}: {
  account: Account
  token: string
  onAct: (fn: () => Promise<unknown>, ok: string) => Promise<void>
  onDone: () => void
  onCancel: () => void
}) {
  const [slug, setSlug] = useState('')
  const [reason, setReason] = useState('')
  const ready = slug === account.slug && reason.trim().length >= 10

  return (
    <div className="ad-danger">
      <p>
        این کار <strong>برگشت‌ناپذیر</strong> است: کلِ دفتر، فاکتورها، کاربران و
        پشتیبان‌های «{account.name}» پاک می‌شوند.
      </p>
      <FieldGrid>
        <Field label="برای تأیید، شناسه‌ی کسب‌وکار را تایپ کنید" hint={`باید دقیقاً ${account.slug} باشد`}>
          <input dir="ltr" value={slug} onChange={(e) => setSlug(e.target.value)} />
        </Field>
        <Field label="دلیلِ حذف" hint="در ردِ کارهای ستاد ثبت می‌شود — دستِ‌کم ۱۰ نویسه">
          <input value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
      </FieldGrid>
      <div className="ad-btn-row">
        <button
          type="button"
          className="ad-btn danger"
          disabled={!ready}
          onClick={() =>
            onAct(
              () => deleteAccount(token, account.tenant_id, slug, reason.trim()),
              `اکانتِ «${account.name}» کاملاً حذف شد.`,
            ).then(onDone)
          }
        >
          حذفِ همیشگی
        </button>
        <button type="button" className="ad-btn small" onClick={onCancel}>
          انصراف
        </button>
      </div>
      {!ready ? (
        <p className="ad-field-hint">
          {slug !== account.slug ? 'شناسه هنوز دقیق وارد نشده.' : 'دلیل باید دستِ‌کم ۱۰ نویسه باشد.'}
        </p>
      ) : null}
    </div>
  )
}

function CreateDialog({
  token,
  onClose,
  onAct,
}: {
  token: string
  onClose: () => void
  onAct: (fn: () => Promise<unknown>, ok: string) => Promise<void>
}) {
  const [form, setForm] = useState({
    business_name: '',
    owner_name: '',
    email: '',
    password: '',
    days: 365,
  })
  const missing = !form.business_name
    ? 'نامِ کسب‌وکار'
    : !form.owner_name
      ? 'نامِ مالک'
      : !form.email
        ? 'ایمیل'
        : form.password.length < 10
          ? 'رمزِ دستِ‌کم ۱۰ نویسه‌ای'
          : null

  return (
    <Dialog
      title="اکانتِ تازه"
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            className="ad-btn primary"
            disabled={!!missing}
            onClick={() =>
              onAct(
                () => createAccount(token, form),
                `اکانتِ «${form.business_name}» ساخته شد.`,
              ).then(onClose)
            }
          >
            ساختِ اکانت
          </button>
          {missing ? <span className="ad-field-hint">{missing} لازم است</span> : null}
        </>
      }
    >
      <FieldGrid>
        <Field label="نامِ کسب‌وکار">
          <input
            value={form.business_name}
            onChange={(e) => setForm({ ...form, business_name: e.target.value })}
          />
        </Field>
        <Field label="نامِ مالک">
          <input
            value={form.owner_name}
            onChange={(e) => setForm({ ...form, owner_name: e.target.value })}
          />
        </Field>
        <Field label="ایمیلِ مالک">
          <input
            type="email"
            dir="ltr"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </Field>
        <Field label="رمزِ اولیه" hint="دستِ‌کم ۱۰ نویسه؛ مالک بعداً عوضش می‌کند">
          <input
            dir="ltr"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </Field>
        <Field label="طولِ اشتراکِ اولیه (روز)" hint="صفر یعنی بدونِ اشتراک">
          <input
            type="number"
            dir="ltr"
            value={form.days}
            onChange={(e) => setForm({ ...form, days: Number(e.target.value) || 0 })}
          />
        </Field>
      </FieldGrid>
      <p className="ad-field-hint">
        کسب‌وکار، کاربرِ مالک و دفترِ حساب‌ها یک‌جا ساخته می‌شوند. مالک بلافاصله
        می‌تواند در acc.cubita.ir وارد شود.
      </p>
    </Dialog>
  )
}
