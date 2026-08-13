import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ShieldCheck, RefreshCw, UserPlus, CalendarClock, Users, CheckCircle2,
  AlertTriangle, Ban, Play, KeyRound, Trash2, Clock, Activity, ChevronDown, ChevronUp, Gift,
} from 'lucide-react'
import {
  fetchAdminAccounts, createAdminAccount, extendAdminAccount, setAdminAccountStatus,
  resetAdminAccountPassword, deleteAdminAccount, setAdminAccountKind, type AdminAccount,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { EmptyState } from '../components/EmptyState'
import { formatJalali } from '../lib/jalali'

const fa = (n: number) => n.toLocaleString('fa-IR')

const SUB_LABEL: Record<string, string> = {
  active: 'فعال', grace: 'مهلت ارفاق', expired: 'منقضی', cancelled: 'لغوشده', none: 'بدون اشتراک',
}
const SUB_TONE: Record<string, string> = {
  active: 'success', grace: 'warning', expired: 'danger', cancelled: 'danger', none: 'default',
}
const STATUS_LABEL: Record<string, string> = {
  active: 'فعال', suspended: 'تعلیق‌شده', cancelled: 'لغوشده',
}
const EXTEND_PRESETS = [30, 90, 180, 365]

const KIND_LABEL: Record<string, string> = {
  standard: 'عادی', distributor: 'پخش‌کننده', retailer: 'فروشگاه',
}

const MEMBERSHIP_LABEL: Record<string, string> = {
  active: 'فعال', invited: 'دعوت‌شده', disabled: 'غیرفعال',
}

/** «۳ روز پیش» / «همین حالا» / «هرگز» — نمایشِ انسانیِ آخرین فعالیت. */
function relativeFa(iso: string | null): string {
  if (!iso) return 'هرگز وارد نشده'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return '—'
  const sec = Math.floor((Date.now() - then) / 1000)
  if (sec < 0) return 'همین حالا'
  if (sec < 90) return 'همین حالا'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${fa(min)} دقیقه پیش`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${fa(hr)} ساعت پیش`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${fa(day)} روز پیش`
  const month = Math.floor(day / 30)
  if (month < 12) return `${fa(month)} ماه پیش`
  return `${fa(Math.floor(day / 365))} سال پیش`
}

/** آخرین فعالیت به‌شکلِ «۳ روز پیش · ۱۴۰۴/۰۵/۰۸». */
function lastSeenText(iso: string | null): string {
  if (!iso) return 'هرگز وارد نشده'
  return `${relativeFa(iso)} · ${formatJalali(iso.slice(0, 10))}`
}

export function AccountsAdminPage({ token }: { token: string }) {
  const [accounts, setAccounts] = useState<AdminAccount[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [extendId, setExtendId] = useState<string | null>(null)
  const [usersId, setUsersId] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'trial' | 'paid'>('all')

  // فرم ساخت
  const [showCreate, setShowCreate] = useState(false)
  const [bizName, setBizName] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [days, setDays] = useState('365')
  const [kind, setKind] = useState('standard')

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setAccounts(await fetchAdminAccounts(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  const kpis = useMemo(() => {
    const a = accounts ?? []
    const weekAgo = Date.now() - 7 * 24 * 3600 * 1000
    return {
      total: a.length,
      active: a.filter((x) => !x.is_trial && x.subscription_status === 'active').length,
      trial: a.filter((x) => x.is_trial).length,
      expiring: a.filter((x) => (x.subscription_status === 'active' || x.subscription_status === 'grace') && x.days_left != null && x.days_left <= 14).length,
      trouble: a.filter((x) => x.subscription_status === 'expired' || x.status === 'suspended').length,
      activeWeek: a.filter((x) => x.last_activity_at != null && new Date(x.last_activity_at).getTime() >= weekAgo).length,
    }
  }, [accounts])

  // شمارشِ فیلترها و فهرستِ فیلترشده — «آزمایشی» همان درخواستِ کاربر برای دیدنِ حساب‌های ۱۴روزه است.
  const counts = useMemo(() => {
    const a = accounts ?? []
    return { all: a.length, trial: a.filter((x) => x.is_trial).length, paid: a.filter((x) => !x.is_trial).length }
  }, [accounts])
  const filtered = useMemo(() => {
    const a = accounts ?? []
    if (filter === 'trial') return a.filter((x) => x.is_trial)
    if (filter === 'paid') return a.filter((x) => !x.is_trial)
    return a
  }, [accounts, filter])

  async function run(id: string, fn: () => Promise<unknown>, ok: string) {
    setBusyId(id); setError(null); setMessage(null)
    try {
      await fn()
      setMessage(ok)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusyId(null)
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null); setMessage(null)
    try {
      const created = await createAdminAccount(token, {
        business_name: bizName, owner_name: ownerName, email, password, days: Number(days) || 0, kind,
      })
      setMessage(`اکانت «${created.name}» (${KIND_LABEL[created.kind] ?? created.kind}) ساخته شد. رمزِ اولیه را به مالک بدهید.`)
      setBizName(''); setOwnerName(''); setEmail(''); setPassword(''); setDays('365'); setKind('standard')
      setShowCreate(false)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  function doExtend(a: AdminAccount, d: number) {
    setExtendId(null)
    void run(a.tenant_id, () => extendAdminAccount(token, a.tenant_id, { days: d }), `اشتراکِ «${a.name}» ${fa(d)} روز تمدید شد.`)
  }

  function toggleStatus(a: AdminAccount) {
    const next = a.status === 'active' ? 'suspended' : 'active'
    if (next === 'suspended' && !window.confirm(`اکانت «${a.name}» تعلیق شود؟ مالک تا فعال‌سازیِ دوباره نمی‌تواند وارد شود.`)) return
    void run(a.tenant_id, () => setAdminAccountStatus(token, a.tenant_id, next),
      next === 'suspended' ? `«${a.name}» تعلیق شد.` : `«${a.name}» فعال شد.`)
  }

  function changeKind(a: AdminAccount, next: string) {
    if (next === a.kind) return
    void run(a.tenant_id, () => setAdminAccountKind(token, a.tenant_id, next), `نوعِ «${a.name}» به «${KIND_LABEL[next] ?? next}» تغییر کرد.`)
  }

  function resetPw(a: AdminAccount) {
    const pw = window.prompt(`رمزِ تازه برای مالکِ «${a.name}» (${a.owner_email})\nحداقل ۱۰ کاراکتر:`)
    if (pw === null) return
    if (pw.length < 10) { setError('رمز باید حداقل ۱۰ کاراکتر باشد.'); return }
    void run(a.tenant_id, () => resetAdminAccountPassword(token, a.tenant_id, pw), `رمزِ مالکِ «${a.name}» عوض شد. نشست‌های بازش هم بسته شد.`)
  }

  function doDelete(a: AdminAccount) {
    const typed = window.prompt(
      `⚠️ حذفِ کاملِ «${a.name}» غیرقابلِ‌بازگشت است و همه‌ی داده‌هایش پاک می‌شود.\n` +
      `برای تأیید، نامِ کسب‌وکار را دقیقاً تایپ کنید:`,
    )
    if (typed === null) return
    if (typed.trim() !== a.name) { setError('نامِ واردشده با نامِ اکانت یکی نیست؛ حذف انجام نشد.'); return }
    void run(a.tenant_id, () => deleteAdminAccount(token, a.tenant_id), `اکانت «${a.name}» برای همیشه حذف شد.`)
  }

  function daysText(a: AdminAccount): string {
    // حسابِ آزمایشی: روزهای ماندهٔ ترایال (نه اشتراک) را نشان بده — با منطقِ «۱۴روزه».
    if (a.is_trial) {
      if (a.trial_expired) return 'آزمایشی تمام شد'
      if (a.trial_days_left == null) return 'آزمایشیِ رایگان'
      return `${fa(a.trial_days_left)} روز از ۱۴ روزِ آزمایشی مانده`
    }
    if (a.subscription_status === 'none') return 'بدون اشتراک'
    if (a.days_left == null) return '—'
    if (a.days_left < 0) return `${fa(Math.abs(a.days_left))} روز از انقضا گذشته`
    return `${fa(a.days_left)} روز مانده`
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={ShieldCheck}
        title="مدیریت اکانت‌ها"
        description="همه‌ی اکانت‌های ساخته‌شده، زمانِ ماندهٔ اشتراک‌ها، و ساخت/مدیریتِ دستیِ اکانت. این بخش فقط برای شماست."
      />

      <div className="stat-grid">
        <StatCard icon={<Users size={18} />} label="کل اکانت‌ها" value={fa(kpis.total)} />
        <StatCard icon={<CheckCircle2 size={18} />} label="اشتراکِ فعال" value={fa(kpis.active)} tone="success" />
        <StatCard icon={<Gift size={18} />} label="آزمایشیِ رایگان (۱۴روزه)" value={fa(kpis.trial)} tone={kpis.trial ? 'warning' : undefined} />
        <StatCard icon={<Activity size={18} />} label="فعال در ۷ روزِ اخیر" value={fa(kpis.activeWeek)} tone={kpis.activeWeek ? 'success' : undefined} />
        <StatCard icon={<Clock size={18} />} label="رو به انقضا (≤۱۴ روز)" value={fa(kpis.expiring)} tone={kpis.expiring ? 'warning' : undefined} />
        <StatCard icon={<AlertTriangle size={18} />} label="منقضی/تعلیق" value={fa(kpis.trouble)} tone={kpis.trouble ? 'danger' : undefined} />
      </div>

      <SectionCard
        icon={UserPlus}
        title="ساخت اکانت جدید"
        actions={<button onClick={() => setShowCreate((s) => !s)}>{showCreate ? 'بستن' : 'ساخت اکانت'}</button>}
      >
        {showCreate ? (
          <form className="invoice-form" onSubmit={handleCreate}>
            <label>نام کسب‌وکار<input value={bizName} onChange={(e) => setBizName(e.target.value)} required /></label>
            <label>نام مالک<input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} required /></label>
            <label>ایمیل ورود<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
            <label>رمز اولیه (≥۱۰ کاراکتر)<input type="text" value={password} onChange={(e) => setPassword(e.target.value)} minLength={10} required /></label>
            <label>
              مدت اشتراک اولیه
              <select value={days} onChange={(e) => setDays(e.target.value)}>
                <option value="365">یک سال (۳۶۵ روز)</option>
                <option value="180">شش ماه (۱۸۰ روز)</option>
                <option value="90">سه ماه (۹۰ روز)</option>
                <option value="30">یک ماه (۳۰ روز)</option>
                <option value="0">بدون اشتراک</option>
              </select>
            </label>
            <label>
              نوعِ حساب (بازارِ عمده‌فروشی)
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="standard">عادی</option>
                <option value="distributor">پخش‌کننده (ماژولِ «پخشِ من»)</option>
                <option value="retailer">فروشگاه (ماژولِ «بازارِ خرید»)</option>
              </select>
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><UserPlus size={14} /> ساخت اکانت</button>
            </div>
          </form>
        ) : (
          <p className="hint">با ساختِ اکانت، یک کسب‌وکار + کاربرِ مالک با رمزِ اولیه ایجاد می‌شود؛ رمز را خودتان به شخص می‌دهید و او بعداً عوضش می‌کند.</p>
        )}
      </SectionCard>

      <SectionCard
        icon={CalendarClock}
        title="همه‌ی اکانت‌ها"
        description="مرتب بر اساسِ نزدیک‌ترین انقضا."
        actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
      >
        {error && <div className="error">{error}</div>}
        {message && <div className="hint">{message}</div>}

        {accounts != null && accounts.length > 0 && (
          <div className="account-filter" role="tablist" aria-label="فیلترِ اکانت‌ها">
            <button className={filter === 'all' ? 'is-active' : ''} onClick={() => setFilter('all')}>همه ({fa(counts.all)})</button>
            <button className={`filter-trial${filter === 'trial' ? ' is-active' : ''}`} onClick={() => setFilter('trial')}>آزمایشیِ رایگان ({fa(counts.trial)})</button>
            <button className={filter === 'paid' ? 'is-active' : ''} onClick={() => setFilter('paid')}>پولی ({fa(counts.paid)})</button>
          </div>
        )}

        {accounts == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : accounts.length === 0 ? (
          <EmptyState icon={Users} text="هنوز اکانتی ساخته نشده." />
        ) : filtered.length === 0 ? (
          <EmptyState icon={Gift} text={filter === 'trial' ? 'هنوز هیچ حسابِ آزمایشی‌ای ساخته نشده.' : 'اکانتی در این فیلتر نیست.'} />
        ) : (
          <div className="account-list">
            {filtered.map((a) => (
              <div key={a.tenant_id} className={`account-card${a.status !== 'active' ? ' account-card--suspended' : ''}`}>
                <div className="account-head">
                  <div>
                    <div className="account-name">{a.name}</div>
                    <div className="account-owner">{a.owner_name} · {a.owner_email}</div>
                  </div>
                  {a.is_trial ? (
                    <span className={`status-badge ${a.trial_expired ? 'tone-danger' : 'tone-trial'}`}>
                      <Gift size={12} /> {a.trial_expired ? 'آزمایشی منقضی' : 'آزمایشیِ رایگان'}
                    </span>
                  ) : (
                    <span className={`status-badge tone-${SUB_TONE[a.subscription_status] ?? 'default'}`}>
                      {SUB_LABEL[a.subscription_status] ?? a.subscription_status}
                    </span>
                  )}
                </div>

                <div className="account-meta">
                  <span><CalendarClock size={13} /> انقضا: {a.expires_at ? formatJalali(a.expires_at.slice(0, 10)) : '—'} <strong>({daysText(a)})</strong></span>
                  <span><Activity size={13} /> آخرین فعالیت: <strong>{lastSeenText(a.last_activity_at)}</strong></span>
                  <span>پلن: {a.plan_name || '—'}</span>
                  <span>نوع: <strong>{KIND_LABEL[a.kind] ?? a.kind}</strong></span>
                  <span><Users size={13} /> {fa(a.user_count)}{a.max_users != null ? ` / ${fa(a.max_users)}` : ''} کاربر</span>
                  <span>ساخت: {formatJalali(a.created_at.slice(0, 10))}</span>
                  {a.status !== 'active' && <span className="account-suspended-tag">{STATUS_LABEL[a.status] ?? a.status}</span>}
                </div>

                {usersId === a.tenant_id && (
                  <div className="account-users">
                    {a.users.map((u) => (
                      <div key={u.email} className="account-user-row">
                        <div className="account-user-id">
                          <span className="account-user-name">
                            {u.name}
                            {u.is_owner && <span className="account-user-owner">مالک</span>}
                            {u.status !== 'active' && <span className="account-user-tag">{MEMBERSHIP_LABEL[u.status] ?? u.status}</span>}
                          </span>
                          <span className="account-user-email">{u.email}</span>
                        </div>
                        <span className={`account-user-seen${u.last_login_at ? '' : ' is-never'}`}>
                          {u.last_login_at ? lastSeenText(u.last_login_at) : 'هرگز وارد نشده'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {extendId === a.tenant_id && (
                  <div className="account-extend">
                    <span className="hint">افزودن به اشتراک:</span>
                    {EXTEND_PRESETS.map((d) => (
                      <button key={d} type="button" disabled={busyId === a.tenant_id} onClick={() => doExtend(a, d)}>+{fa(d)} روز</button>
                    ))}
                    <button type="button" className="link-like" onClick={() => setExtendId(null)}>انصراف</button>
                  </div>
                )}

                <div className="account-actions">
                  <button type="button" onClick={() => setUsersId(usersId === a.tenant_id ? null : a.tenant_id)}>
                    <Users size={13} /> کاربرها ({fa(a.user_count)})
                    {usersId === a.tenant_id ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                  </button>
                  <button type="button" disabled={busyId === a.tenant_id} onClick={() => setExtendId(extendId === a.tenant_id ? null : a.tenant_id)}>
                    <CalendarClock size={13} /> تمدید
                  </button>
                  <button type="button" disabled={busyId === a.tenant_id} onClick={() => toggleStatus(a)}>
                    {a.status === 'active' ? <><Ban size={13} /> تعلیق</> : <><Play size={13} /> فعال‌سازی</>}
                  </button>
                  <button type="button" disabled={busyId === a.tenant_id} onClick={() => resetPw(a)}>
                    <KeyRound size={13} /> رمز جدید
                  </button>
                  <select
                    className="account-kind-select"
                    value={a.kind}
                    disabled={busyId === a.tenant_id}
                    onChange={(e) => changeKind(a, e.target.value)}
                    title="نوعِ حساب در بازارِ عمده‌فروشی"
                  >
                    <option value="standard">نوع: عادی</option>
                    <option value="distributor">نوع: پخش‌کننده</option>
                    <option value="retailer">نوع: فروشگاه</option>
                  </select>
                  <button type="button" className="icon-btn-danger" disabled={busyId === a.tenant_id} onClick={() => doDelete(a)}>
                    <Trash2 size={13} /> حذف
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  )
}
