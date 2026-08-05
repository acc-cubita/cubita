import { useEffect, useMemo, useState } from 'react'
import {
  UserPlus,
  Users,
  Target,
  Trophy,
  Gift,
  Save,
  Phone,
  CalendarClock,
  UserCheck,
  Trash2,
  ArrowRightLeft,
  CheckCircle2,
  Circle,
  History,
  AlertTriangle,
} from 'lucide-react'
import {
  addLoyaltyTxn,
  fetchLoyaltySettings,
  setLoyaltySettings,
  convertLead,
  createCrmActivity,
  createLead,
  deleteCrmActivity,
  deleteLead,
  fetchContacts,
  fetchCrmActivities,
  fetchLeads,
  fetchLoyaltyBalances,
  updateCrmActivity,
  updateLead,
  type ActivityKind,
  type ContactRecord,
  type CrmActivityRecord,
  type LeadRecord,
  type LeadStatus,
  type LoyaltyBalance,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { NumberInput } from '../components/NumberInput'
import { SectionCard } from '../components/SectionCard'
import { StatCard } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import { EmptyState } from '../components/EmptyState'
import { Pager, usePagination } from '../components/Pager'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { LoyaltyHistoryDrawer } from '../components/LoyaltyHistoryDrawer'
import { formatJalali, todayIso } from '../lib/jalali'

const fa = (n: number) => n.toLocaleString('fa-IR')
const isOverdue = (d: string | null | undefined) => !!d && d < todayIso()

const LEAD_STATUS: Record<LeadStatus, { label: string; tone: string }> = {
  new: { label: 'جدید', tone: 'default' },
  contacted: { label: 'تماس‌گرفته', tone: 'warning' },
  qualified: { label: 'واجد شرایط', tone: 'success' },
  won: { label: 'موفق', tone: 'success' },
  lost: { label: 'ناموفق', tone: 'danger' },
}
const STATUS_ORDER: LeadStatus[] = ['new', 'contacted', 'qualified', 'won', 'lost']

const KIND_LABELS: Record<ActivityKind, string> = {
  call: 'تماس',
  meeting: 'جلسه',
  note: 'یادداشت',
  task: 'کار',
}

export function CrmPage({ token }: { token: string }) {
  const [leads, setLeads] = useState<LeadRecord[]>([])
  const [activities, setActivities] = useState<CrmActivityRecord[]>([])
  const [balances, setBalances] = useState<LoyaltyBalance[]>([])
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setError(null)
    try {
      const [ls, acts, bals, cs] = await Promise.all([
        fetchLeads(token),
        fetchCrmActivities(token),
        fetchLoyaltyBalances(token),
        fetchContacts(token),
      ])
      setLeads(ls)
      setActivities(acts)
      setBalances(bals)
      setContacts(cs.filter((c) => c.type !== 'supplier'))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  // به‌روزرسانیِ خوش‌بینانه‌ی مانده‌ی امتیاز: مقدار دقیقاً همان delta است، پس بلافاصله
  // در جدول اعمالش می‌کنیم تا کاربر منتظرِ رفت‌وبرگشتِ شبکه (onChanged) نماند.
  function applyLoyaltyDelta(contactId: string, delta: number, contactName: string) {
    setBalances((prev) =>
      prev.some((b) => b.contact_id === contactId)
        ? prev.map((b) => (b.contact_id === contactId ? { ...b, balance: b.balance + delta } : b))
        : [...prev, { contact_id: contactId, contact_name: contactName, balance: delta }],
    )
  }

  useEffect(() => {
    void refresh()
  }, [])

  const kpis = useMemo(() => {
    const open = leads.filter((l) => ['new', 'contacted', 'qualified'].includes(l.status)).length
    const won = leads.filter((l) => l.status === 'won').length
    const points = balances.reduce((s, b) => s + b.balance, 0)
    const pendingFollowups = activities.filter((a) => !a.done).length
    return { total: leads.length, open, won, points, pendingFollowups }
  }, [leads, balances, activities])

  return (
    <div className="page">
      <PageHeader
        icon={Users}
        title="باشگاه مشتریان (CRM)"
        description="سرنخ‌های فروش را در قیف مدیریت کنید، پیگیری‌ها را ثبت کنید و به مشتریان وفادار امتیاز بدهید."
      />

      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard icon={<Target size={18} />} label="کل سرنخ‌ها" value={fa(kpis.total)} />
        <StatCard icon={<UserPlus size={18} />} label="سرنخ‌های باز" value={fa(kpis.open)} tone={kpis.open > 0 ? 'warning' : 'default'} hint="در حال پیگیری" />
        <StatCard icon={<Trophy size={18} />} label="تبدیل‌شده به مشتری" value={fa(kpis.won)} tone="success" />
        <StatCard icon={<Gift size={18} />} label="مجموع امتیاز فعال" value={fa(kpis.points)} hint={`${fa(kpis.pendingFollowups)} پیگیریِ باز`} />
      </div>

      <Tabs
        syncPage="crm"
        tabs={[
          { key: 'leads', label: 'سرنخ‌ها', icon: Target, content: <LeadsTab token={token} leads={leads} onChanged={refresh} /> },
          { key: 'activities', label: 'پیگیری‌ها', icon: CalendarClock, content: <ActivitiesTab token={token} activities={activities} leads={leads} contacts={contacts} onChanged={refresh} /> },
          { key: 'loyalty', label: 'باشگاه مشتریان', icon: Gift, content: <LoyaltyTab token={token} balances={balances} contacts={contacts} onChanged={refresh} onApplyDelta={applyLoyaltyDelta} /> },
        ]}
      />
    </div>
  )
}

// ── تبِ سرنخ‌ها ─────────────────────────────────────────
function LeadsTab({ token, leads, onChanged }: { token: string; leads: LeadRecord[]; onChanged: () => Promise<void> }) {
  const EMPTY = { name: '', phone: '', company: '', source: '', estimated_value: '', status: 'new' as LeadStatus, next_action_date: '', notes: '' }
  const [form, setForm] = useState(EMPTY)
  const [filter, setFilter] = useState<'all' | 'open' | 'won' | 'lost'>('all')
  const [msg, setMsg] = useState<string | null>(null)

  const filtered = useMemo(() => {
    return leads.filter((l) => {
      if (filter === 'open') return ['new', 'contacted', 'qualified'].includes(l.status)
      if (filter === 'won') return l.status === 'won'
      if (filter === 'lost') return l.status === 'lost'
      return true
    })
  }, [leads, filter])
  const leadsPg = usePagination(filtered, 10, filter)

  // قیفِ فروش: تعداد و ارزشِ تخمینیِ هر مرحله
  const funnel = useMemo(() => STATUS_ORDER.map((s) => {
    const inStage = leads.filter((l) => l.status === s)
    return {
      status: s,
      count: inStage.length,
      value: inStage.reduce((sum, l) => sum + Number(l.estimated_value || 0), 0),
    }
  }), [leads])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!form.name.trim()) {
      setMsg('نام سرنخ الزامی است.')
      return
    }
    try {
      await createLead(token, {
        name: form.name,
        phone: form.phone || undefined,
        company: form.company || undefined,
        source: form.source || undefined,
        status: form.status,
        estimated_value: Number(form.estimated_value) || 0,
        next_action_date: form.next_action_date || null,
        notes: form.notes || undefined,
      })
      setForm(EMPTY)
      setMsg('سرنخ ثبت شد.')
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function changeStatus(id: string, status: LeadStatus) {
    await updateLead(token, id, { status })
    await onChanged()
  }
  async function convert(id: string) {
    await convertLead(token, id)
    await onChanged()
  }
  async function remove(id: string) {
    await deleteLead(token, id)
    await onChanged()
  }

  return (
    <>
    <div className="crm-funnel">
      {funnel.map((f) => (
        <div key={f.status} className={`crm-funnel-stage tone-${LEAD_STATUS[f.status].tone}`}>
          <div className="crm-funnel-label">{LEAD_STATUS[f.status].label}</div>
          <div className="crm-funnel-count">{fa(f.count)}</div>
          <div className="crm-funnel-value">{f.value > 0 ? `${fa(f.value)} ریال` : '—'}</div>
        </div>
      ))}
    </div>
    <div className="workspace-split">
      <SectionCard icon={UserPlus} title="سرنخ جدید" description="یک مشتریِ بالقوه را وارد قیفِ فروش کنید.">
        <form className="invoice-form form-full" onSubmit={submit}>
          <label>
            نام
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="نام شخص یا شرکت" required />
          </label>
          <div className="field-row">
            <label>
              تلفن
              <input type="text" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </label>
            <label>
              شرکت
              <input type="text" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
            </label>
          </div>
          <div className="field-row">
            <label>
              منبع
              <input type="text" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} placeholder="اینستاگرام، معرفی، ..." />
            </label>
            <label>
              ارزش تخمینی (ریال)
              <NumberInput value={form.estimated_value} onChange={(v) => setForm({ ...form, estimated_value: v })} />
            </label>
          </div>
          <div className="field-row">
            <label>
              وضعیت
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as LeadStatus })}>
                {STATUS_ORDER.map((s) => (
                  <option key={s} value={s}>{LEAD_STATUS[s].label}</option>
                ))}
              </select>
            </label>
            <label>
              پیگیری بعدی
              <JalaliDatePicker value={form.next_action_date || todayIso()} onChange={(v) => setForm({ ...form, next_action_date: v })} />
            </label>
          </div>
          <label>
            یادداشت
            <input type="text" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><Save size={14} /> ثبت سرنخ</button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </form>
      </SectionCard>

      <SectionCard
        icon={Target}
        title="قیف فروش"
        description={`${fa(filtered.length)} سرنخ`}
        actions={
          <div className="check-actions">
            <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
              <option value="all">همه</option>
              <option value="open">در حال پیگیری</option>
              <option value="won">موفق</option>
              <option value="lost">ناموفق</option>
            </select>
          </div>
        }
      >
        {filtered.length === 0 ? (
          <EmptyState icon={Target} text="سرنخی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table leads-table">
              <thead>
                <tr>
                  <th>سرنخ</th>
                  <th>وضعیت</th>
                  <th>ارزش تخمینی</th>
                  <th>پیگیری بعدی</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {leadsPg.pageItems.map((l) => {
                  const open = ['new', 'contacted', 'qualified'].includes(l.status)
                  const overdue = open && isOverdue(l.next_action_date)
                  return (
                  <tr key={l.id}>
                    <td data-label="سرنخ">
                      <div className="entity-cell">
                        <div className="entity-avatar tone-customer">{l.name.trim().charAt(0) || '؟'}</div>
                        <div>
                          <div className="entity-name">{l.name}</div>
                          <div className="entity-sub">{[l.company, l.phone, l.source].filter(Boolean).join(' · ') || '—'}</div>
                        </div>
                      </div>
                    </td>
                    <td data-label="وضعیت">
                      <select className="status-select" value={l.status} onChange={(e) => void changeStatus(l.id, e.target.value as LeadStatus)}>
                        {STATUS_ORDER.map((s) => (
                          <option key={s} value={s}>{LEAD_STATUS[s].label}</option>
                        ))}
                      </select>
                    </td>
                    <td data-label="ارزش تخمینی" className="money-cell">{Number(l.estimated_value) > 0 ? fa(Number(l.estimated_value)) : '—'}</td>
                    <td data-label="پیگیری بعدی">
                      {l.next_action_date ? formatJalali(l.next_action_date) : '—'}
                      {overdue && <span className="status-badge tone-danger crm-overdue"><AlertTriangle size={11} /> عقب‌افتاده</span>}
                    </td>
                    <td className="crm-actions-cell">
                      <div className="row-actions">
                        {l.converted_contact_id ? (
                          <span className="status-badge tone-success"><UserCheck size={12} /> مشتری شد</span>
                        ) : (
                          <button type="button" onClick={() => void convert(l.id)} title="تبدیل به مشتری">
                            <ArrowRightLeft size={13} /> تبدیل به مشتری
                          </button>
                        )}
                        <button type="button" className="icon-btn-danger" onClick={() => void remove(l.id)} aria-label="حذف">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
            <Pager page={leadsPg.page} pageCount={leadsPg.pageCount} onChange={leadsPg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
    </>
  )
}

// ── تبِ پیگیری‌ها ───────────────────────────────────────
function ActivitiesTab({
  token,
  activities,
  leads,
  contacts,
  onChanged,
}: {
  token: string
  activities: CrmActivityRecord[]
  leads: LeadRecord[]
  contacts: ContactRecord[]
  onChanged: () => Promise<void>
}) {
  const [kind, setKind] = useState<ActivityKind>('call')
  const [subject, setSubject] = useState('')
  const [date, setDate] = useState(todayIso())
  const [targetType, setTargetType] = useState<'lead' | 'contact'>('lead')
  const [targetId, setTargetId] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [filter, setFilter] = useState<'open' | 'overdue' | 'all'>('open')

  const leadName = useMemo(() => new Map(leads.map((l) => [l.id, l.name])), [leads])
  const contactName = useMemo(() => new Map(contacts.map((c) => [c.id, c.name])), [contacts])
  const filteredActivities = useMemo(() => activities.filter((a) => {
    if (filter === 'open') return !a.done
    if (filter === 'overdue') return !a.done && isOverdue(a.activity_date)
    return true
  }), [activities, filter])
  const actPg = usePagination(filteredActivities, 10, filter)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!subject.trim()) {
      setMsg('موضوع الزامی است.')
      return
    }
    if (!targetId) {
      setMsg('یک سرنخ یا مشتری انتخاب کنید.')
      return
    }
    try {
      await createCrmActivity(token, {
        kind,
        subject,
        activity_date: date,
        lead_id: targetType === 'lead' ? targetId : null,
        contact_id: targetType === 'contact' ? targetId : null,
      })
      setSubject('')
      setMsg('پیگیری ثبت شد.')
      await onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function toggleDone(a: CrmActivityRecord) {
    await updateCrmActivity(token, a.id, { done: !a.done })
    await onChanged()
  }
  async function remove(id: string) {
    await deleteCrmActivity(token, id)
    await onChanged()
  }

  const targets = targetType === 'lead' ? leads.filter((l) => !l.converted_contact_id) : contacts

  return (
    <div className="workspace-split">
      <SectionCard icon={CalendarClock} title="ثبت پیگیری" description="تماس، جلسه یا یادآوریِ مرتبط با یک سرنخ یا مشتری.">
        <form className="invoice-form form-full" onSubmit={submit}>
          <div className="field-row">
            <label>
              نوع
              <select value={kind} onChange={(e) => setKind(e.target.value as ActivityKind)}>
                {(Object.keys(KIND_LABELS) as ActivityKind[]).map((k) => (
                  <option key={k} value={k}>{KIND_LABELS[k]}</option>
                ))}
              </select>
            </label>
            <label>
              تاریخ
              <JalaliDatePicker value={date} onChange={setDate} />
            </label>
          </div>
          <div className="field-row">
            <label>
              مرتبط با
              <select value={targetType} onChange={(e) => { setTargetType(e.target.value as 'lead' | 'contact'); setTargetId('') }}>
                <option value="lead">سرنخ</option>
                <option value="contact">مشتری</option>
              </select>
            </label>
            <label>
              {targetType === 'lead' ? 'سرنخ' : 'مشتری'}
              <select value={targetId} onChange={(e) => setTargetId(e.target.value)}>
                <option value="">— انتخاب —</option>
                {targets.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            موضوع
            <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="مثلاً: تماس پیگیری سفارش" required />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><Phone size={14} /> ثبت پیگیری</button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </form>
      </SectionCard>

      <SectionCard
        icon={CalendarClock}
        title="پیگیری‌ها"
        description={`${fa(filteredActivities.length)} مورد`}
        actions={
          <div className="seg-toggle">
            <button type="button" className={filter === 'open' ? 'active' : ''} onClick={() => setFilter('open')}>باز</button>
            <button type="button" className={filter === 'overdue' ? 'active' : ''} onClick={() => setFilter('overdue')}>عقب‌افتاده</button>
            <button type="button" className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>همه</button>
          </div>
        }
      >
        {filteredActivities.length === 0 ? (
          <EmptyState icon={CalendarClock} text="پیگیری‌ای با این فیلتر نیست." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table activities-table">
              <thead>
                <tr>
                  <th>موضوع</th>
                  <th>نوع</th>
                  <th>مرتبط با</th>
                  <th>تاریخ</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {actPg.pageItems.map((a) => {
                  const overdue = !a.done && isOverdue(a.activity_date)
                  return (
                  <tr key={a.id} className={a.done ? 'row-muted' : ''}>
                    <td data-label="موضوع" className="entity-name">{a.subject}</td>
                    <td data-label="نوع"><span className="status-badge tone-default">{KIND_LABELS[a.kind]}</span></td>
                    <td data-label="مرتبط با">{a.lead_id ? (leadName.get(a.lead_id) ?? 'سرنخ') : a.contact_id ? (contactName.get(a.contact_id) ?? 'مشتری') : '—'}</td>
                    <td data-label="تاریخ">
                      {formatJalali(a.activity_date)}
                      {overdue && <span className="status-badge tone-danger crm-overdue"><AlertTriangle size={11} /> عقب‌افتاده</span>}
                    </td>
                    <td className="crm-actions-cell">
                      <div className="row-actions">
                        <button type="button" onClick={() => void toggleDone(a)} title={a.done ? 'بازکردن' : 'انجام شد'}>
                          {a.done ? <CheckCircle2 size={14} /> : <Circle size={14} />} {a.done ? 'انجام‌شده' : 'باز'}
                        </button>
                        <button type="button" className="icon-btn-danger" onClick={() => void remove(a.id)} aria-label="حذف">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
            <Pager page={actPg.page} pageCount={actPg.pageCount} onChange={actPg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}

// ── تبِ باشگاه مشتریان (امتیاز) ────────────────────────
function LoyaltyTab({
  token,
  balances,
  contacts,
  onChanged,
  onApplyDelta,
}: {
  token: string
  balances: LoyaltyBalance[]
  contacts: ContactRecord[]
  onChanged: () => Promise<void>
  onApplyDelta: (contactId: string, delta: number, contactName: string) => void
}) {
  const [contactId, setContactId] = useState('')
  const [mode, setMode] = useState<'earn' | 'redeem'>('earn')
  const [points, setPoints] = useState('')
  const [reason, setReason] = useState('')
  const [date, setDate] = useState(todayIso())
  const [msg, setMsg] = useState<string | null>(null)
  const [historyContact, setHistoryContact] = useState<{ id: string; name: string } | null>(null)
  const loyaltyPg = usePagination(balances, 10)

  // تنظیماتِ کسبِ خودکارِ امتیاز هنگامِ فروش
  const [autoEnabled, setAutoEnabled] = useState(false)
  const [perPoint, setPerPoint] = useState('')
  const [setMsg2, setSetMsg2] = useState<string | null>(null)

  useEffect(() => {
    fetchLoyaltySettings(token)
      .then((s) => {
        setAutoEnabled(s.is_enabled)
        setPerPoint(Number(s.amount_per_point) ? String(Number(s.amount_per_point)) : '')
      })
      .catch(() => {})
  }, [token])

  async function saveSettings() {
    setSetMsg2(null)
    try {
      await setLoyaltySettings(token, { is_enabled: autoEnabled, amount_per_point: Number(perPoint) || 0 })
      setSetMsg2('تنظیماتِ کسبِ خودکار ذخیره شد.')
    } catch (err) {
      setSetMsg2(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    const p = Number(points)
    if (!contactId || !(p > 0)) {
      setMsg('مشتری و امتیاز (بزرگ‌تر از صفر) الزامی است.')
      return
    }
    try {
      const delta = mode === 'earn' ? p : -p
      await addLoyaltyTxn(token, {
        contact_id: contactId,
        points: delta,
        reason: reason || (mode === 'earn' ? 'کسب امتیاز' : 'استفاده از امتیاز'),
        txn_date: date,
      })
      // مانده را همان لحظه در جدول اصلاح کن (delta دقیق است)، بعد در پس‌زمینه با سرور تطبیق بده.
      onApplyDelta(contactId, delta, contacts.find((c) => c.id === contactId)?.name ?? '')
      setPoints('')
      setReason('')
      setMsg(mode === 'earn' ? 'امتیاز به مشتری اضافه شد.' : 'امتیاز از مشتری کسر شد.')
      void onChanged()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <>
      <SectionCard icon={Gift} title="کسبِ خودکارِ امتیاز هنگامِ فروش" description="با فعال‌سازی، هر فروش به یک مشتری خودکار امتیاز می‌دهد.">
        <div className="benefit-toolbar">
          <label className="cal-check-inline">
            <input type="checkbox" checked={autoEnabled} onChange={(e) => setAutoEnabled(e.target.checked)} />
            کسبِ خودکار فعال باشد
          </label>
          <label>
            به‌ازای هر چند ریال خرید، ۱ امتیاز؟
            <NumberInput value={perPoint} onChange={setPerPoint} placeholder="مثلاً ۱۰۰۰۰" style={{ width: 140 }} disabled={!autoEnabled} />
          </label>
          <button type="button" className="btn-primary" onClick={() => void saveSettings()}><Save size={13} /> ذخیره</button>
          {setMsg2 && <span className="hint">{setMsg2}</span>}
        </div>
      </SectionCard>

      <div className="workspace-split">
      <SectionCard icon={Gift} title="ثبت امتیاز" description="به مشتریانِ وفادار امتیاز بدهید یا امتیازشان را خرج کنید.">
        <form className="invoice-form form-full" onSubmit={submit}>
          <label>
            مشتری
            <select value={contactId} onChange={(e) => setContactId(e.target.value)} required>
              <option value="">— انتخاب —</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          <div className="field-row">
            <label>
              نوع
              <select value={mode} onChange={(e) => setMode(e.target.value as 'earn' | 'redeem')}>
                <option value="earn">افزودن امتیاز</option>
                <option value="redeem">استفاده از امتیاز</option>
              </select>
            </label>
            <label>
              امتیاز
              <NumberInput value={points} onChange={setPoints} required />
            </label>
          </div>
          <div className="field-row">
            <label>
              بابت
              <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="خرید، تولد، ..." />
            </label>
            <label>
              تاریخ
              <JalaliDatePicker value={date} onChange={setDate} />
            </label>
          </div>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary"><Gift size={14} /> ثبت امتیاز</button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </form>
      </SectionCard>

      <SectionCard icon={Trophy} title="مانده امتیازِ مشتریان" description={`${fa(balances.length)} مشتری`}>
        {balances.length === 0 ? (
          <EmptyState icon={Gift} text="هنوز امتیازی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table loyalty-table">
              <thead>
                <tr>
                  <th>مشتری</th>
                  <th>امتیاز فعال</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {loyaltyPg.pageItems.map((b) => (
                  <tr key={b.contact_id}>
                    <td data-label="مشتری">
                      <div className="entity-cell">
                        <div className="entity-avatar tone-customer">{b.contact_name.trim().charAt(0) || '؟'}</div>
                        <div className="entity-name">{b.contact_name}</div>
                      </div>
                    </td>
                    <td data-label="امتیاز فعال" className="money-cell"><strong>{fa(b.balance)}</strong></td>
                    <td className="loyalty-action">
                      <button type="button" onClick={() => setHistoryContact({ id: b.contact_id, name: b.contact_name })}>
                        <History size={13} /> تاریخچه
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={loyaltyPg.page} pageCount={loyaltyPg.pageCount} onChange={loyaltyPg.setPage} />
          </div>
        )}
      </SectionCard>
      </div>

      {historyContact && <LoyaltyHistoryDrawer token={token} contact={historyContact} onClose={() => setHistoryContact(null)} />}
    </>
  )
}
