import { Fragment, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Ban,
  CalendarClock,
  CheckCircle2,
  CircleDollarSign,
  Coins,
  HandCoins,
  Layers,
  Percent,
  Plus,
  Printer,
  Save,
  Search,
  ShieldCheck,
  TrendingDown,
  UserRound,
  Wallet,
  X,
} from 'lucide-react'
import {
  cancelInstallmentPlan,
  createInstallmentPlan,
  fetchContacts,
  fetchEarlySettlement,
  fetchInstallmentPlans,
  fetchInstallmentSummary,
  payInstallment,
  rescheduleInstallments,
  settleInstallments,
  type ContactRecord,
  type EarlySettlement,
  type Installment,
  type InstallmentPlan,
  type InstallmentSummary,
} from '../../api'
import type { BankAccountCache } from '../../electron.d'
import { PageHeader } from '../../components/PageHeader'
import { NumberInput } from '../../components/NumberInput'
import { SectionCard } from '../../components/SectionCard'
import {
  CountBadge,
  FormField,
  FormGrid,
  FormStatus,
  InputAffix,
} from '../../components/form/FormKit'
import { firstMissing } from '../../components/form/firstMissing'
import { EmptyState } from '../../components/EmptyState'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, toFaDigits, todayIso } from '../../lib/jalali'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * فروشِ اقساطی — قرارداد، زمان‌بندیِ وصول، و پرونده‌ی هر قرارداد.
 *
 * سه چیز این صفحه را از یک «جدولِ سررسید» جدا می‌کند:
 *
 * * **قیمتِ نقدی در برابر مبلغِ اقساطی.** فروشِ اقساطی یعنی همین تفاوت؛ بدونِ نشان‌دادنش
 *   قرارداد نمی‌گوید سودِ این معامله چقدر بوده.
 * * **وصول، نه فقط سررسید.** یک فیش معمولاً چند قسط را می‌بندد؛ تقسیمِ دستی‌اش کارِ
 *   کاربر نیست. «تسویه‌ی زودهنگام» هم مبلغش را خودِ سیستم با تخفیفِ سودِ وصول‌نشده می‌گوید.
 * * **زمان‌بندی چیزِ ثابتی نیست.** تعویق و تجمیعِ قسط در واقعیت پیش می‌آید؛ سرور فقط
 *   نمی‌گذارد جمعِ اقساط از مبلغِ قرارداد واگرا شود.
 */

const fa = (n: string | number) => Number(n || 0).toLocaleString('fa-IR')
const faInt = (n: number) => n.toLocaleString('fa-IR')

const PLAN_STATUS: Record<InstallmentPlan['status'], { label: string; tone: string }> = {
  active: { label: 'فعال', tone: 'warning' },
  completed: { label: 'تسویه‌شده', tone: 'success' },
  cancelled: { label: 'لغوشده', tone: 'muted' },
}
const INST_STATUS: Record<Installment['status'], { label: string; tone: string }> = {
  pending: { label: 'در انتظار', tone: 'muted' },
  partial: { label: 'پرداخت جزئی', tone: 'warning' },
  paid: { label: 'پرداخت‌شده', tone: 'success' },
  overdue: { label: 'معوق', tone: 'danger' },
}

type PlanFilter = 'all' | 'active' | 'overdue' | 'completed' | 'cancelled'
type Tab = 'schedule' | 'payments' | 'reschedule'
type Msg = { text: string; kind: 'ok' | 'err' } | null

const FILTERS: { key: PlanFilter; label: string }[] = [
  { key: 'all', label: 'همه' },
  { key: 'active', label: 'فعال' },
  { key: 'overdue', label: 'دارای معوق' },
  { key: 'completed', label: 'تسویه‌شده' },
  { key: 'cancelled', label: 'لغوشده' },
]

function errText(err: unknown) {
  return err instanceof Error ? err.message : 'خطای ناشناخته'
}

function Note({ msg }: { msg: Msg }) {
  if (!msg) return null
  return (
    <div className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
      {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      <div>{msg.text}</div>
    </div>
  )
}

function Metric({
  icon,
  label,
  value,
  hint,
  tone = 'plain',
}: {
  icon: React.ReactNode
  label: string
  value: string
  hint?: string
  tone?: 'in' | 'out' | 'plain'
}) {
  return (
    <div className="cc-metric">
      <span className="cc-metric-label">
        {icon}
        {label}
      </span>
      <span className={`cc-metric-value ${tone === 'plain' ? '' : tone === 'in' ? 'pos-in' : 'pos-out'}`}>
        {value}
      </span>
      {hint && <span className="cc-metric-hint">{hint}</span>}
    </div>
  )
}

/** نوارِ پیشرفتِ وصول (پرداخت‌شده ÷ تسهیم‌شده) */
function ProgressBar({ paid, scheduled }: { paid: number; scheduled: number }) {
  const pct = scheduled > 0 ? Math.min(100, Math.round((paid / scheduled) * 100)) : 0
  return (
    <div className="inst-progress" title={`${toFaDigits(pct)}٪ وصول‌شده`}>
      <div className="inst-progress-fill" style={{ width: `${pct}%` }} />
      <span className="inst-progress-label">{toFaDigits(pct)}٪</span>
    </div>
  )
}

/**
 * سنِّ معوق در یک نوار. سطل‌ها ترتیبِ معناداری دارند (سررسیدنشده → بیش از ۹۰ روز)
 * پس یک نوارِ پیوسته درست‌تر از چهار عددِ جدا است: نسبت‌ها با هم دیده می‌شوند.
 */
function AgingBar({ summary }: { summary: InstallmentSummary }) {
  const total = summary.buckets.reduce((s, b) => s + Number(b.amount), 0)
  if (total <= 0) return <p className="hint">قسطِ بازی در سبد نیست.</p>
  return (
    <div className="inst-aging">
      <div className="inst-aging-bar">
        {summary.buckets.map((b, i) => {
          const w = (Number(b.amount) / total) * 100
          if (w <= 0) return null
          return (
            <span
              key={b.key}
              className={`inst-aging-seg inst-aging-seg--${i}`}
              style={{ width: `${w}%` }}
              title={`${b.label}: ${fa(b.amount)}`}
            />
          )
        })}
      </div>
      <ul className="inst-aging-legend">
        {summary.buckets.map((b, i) => (
          <li key={b.key}>
            <span className={`inst-aging-dot inst-aging-seg--${i}`} />
            <span className="inst-aging-label">{b.label}</span>
            <span className="inst-aging-amount">{fa(b.amount)}</span>
            <span className="inst-aging-count">{faInt(b.count)} قسط</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function printSchedule(plan: InstallmentPlan) {
  const win = window.open('', '_blank', 'width=840,height=1000')
  if (!win) return
  const rows = plan.installments
    .map(
      (i) =>
        `<tr><td>${toFaDigits(i.seq)}</td><td>${formatJalali(i.due_date)}</td><td class="num">${fa(i.amount)}</td><td class="num">${fa(i.paid_amount)}</td><td class="num">${fa(i.remaining)}</td><td>${INST_STATUS[i.status].label}</td></tr>`,
    )
    .join('')
  const guarantor = plan.guarantor_name
    ? `<div>ضامن: <strong>${plan.guarantor_name}</strong>${plan.guarantor_phone ? ` — ${plan.guarantor_phone}` : ''}</div>`
    : ''
  win.document.write(`<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>جدولِ اقساط ${plan.number ?? ''} — ${plan.contact_name}</title>
<style>
  *{box-sizing:border-box}
  body{font-family:Vazirmatn,Tahoma,sans-serif;margin:28px;color:#1f2937}
  h1{font-size:20px;margin:0 0 4px}
  .muted{color:#6b7280;font-size:13px}
  .head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #111827;padding-bottom:12px;margin-bottom:16px}
  .meta{text-align:left;font-size:13px;line-height:1.9}
  .summary{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px;font-size:13px}
  .summary div{border:1px solid #e5e7eb;border-radius:8px;padding:8px 14px}
  table{width:100%;border-collapse:collapse;margin-bottom:16px}
  th{text-align:right;background:#f3f4f6;font-size:13px;padding:8px 10px;border:1px solid #e5e7eb}
  td{padding:8px 10px;border:1px solid #e5e7eb;font-size:13.5px}
  td.num{text-align:left;font-variant-numeric:tabular-nums}
  .foot{margin-top:26px;color:#6b7280;font-size:11.5px;line-height:1.8}
</style></head><body>
  <div class="head">
    <div><h1>جدولِ اقساط</h1><div class="muted">${plan.title || 'فروش اقساطی'}</div></div>
    <div class="meta">
      <div>مشتری: <strong>${plan.contact_name}</strong></div>
      ${guarantor}
      <div>قرارداد شماره: ${plan.number != null ? toFaDigits(plan.number) : '—'}</div>
      <div>تاریخِ شروع: ${formatJalali(plan.start_date)}</div>
    </div>
  </div>
  <div class="summary">
    <div>قیمت نقدی: <strong>${fa(plan.cash_price)}</strong></div>
    <div>سود اقساط: <strong>${fa(plan.profit_amount)}</strong></div>
    <div>مبلغ کل: <strong>${fa(plan.total_amount)}</strong></div>
    <div>پیش‌پرداخت: <strong>${fa(plan.down_payment)}</strong></div>
    <div>پرداخت‌شده: <strong>${fa(plan.total_paid)}</strong></div>
    <div>مانده: <strong>${fa(plan.total_remaining)}</strong></div>
  </div>
  <table class="table-plain">
    <thead><tr><th>قسط</th><th>سررسید</th><th class="num">مبلغ</th><th class="num">پرداخت‌شده</th><th class="num">مانده</th><th>وضعیت</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <div class="foot">این جدول از سیستمِ حسابداری صادر شده است. هر پرداخت به‌صورتِ دریافت از مشتری در خزانه ثبت می‌شود.</div>
  <script>window.onload=function(){window.print()}</script>
</body></html>`)
  win.document.close()
}

// ── فرمِ قرارداد ─────────────────────────────────────────────────────────────

const EMPTY_FORM = {
  contactId: '',
  title: '',
  cash: '',
  profit: '',
  down: '',
  count: '6',
  interval: '1',
  startDate: todayIso(),
  penalty: '',
  guarantorName: '',
  guarantorPhone: '',
  guarantorId: '',
}

function PlanForm({
  contacts,
  onSubmit,
  onCancel,
  msg,
}: {
  contacts: ContactRecord[]
  onSubmit: (form: typeof EMPTY_FORM, total: number) => Promise<void>
  onCancel: () => void
  msg: Msg
}) {
  //: پیامِ اعتبارسنجیِ خودِ فرم؛ پیامِ سرور از بیرون (`msg`) می‌آید و اولویت دارد.
  const [localMsg, setLocalMsg] = useState<Msg>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const set = (patch: Partial<typeof EMPTY_FORM>) => setForm({ ...form, ...patch })

  // پیش‌نمایشِ تسهیم — همان منطقِ سرور: financed = کل − پیش، قسط = کف(financed÷n)،
  // باقی‌مانده به قسط آخر. نشان‌دادنش پیش از ثبت، بیشترِ اشتباه‌های ورودی را می‌گیرد.
  const preview = useMemo(() => {
    const cash = Number(form.cash) || 0
    const profit = Number(form.profit) || 0
    const total = cash + profit
    const d = Number(form.down) || 0
    const n = Number(form.count) || 0
    if (!(cash > 0) || n < 1 || d < 0 || d >= total) return null
    const financed = total - d
    const base = Math.floor(financed / n)
    return { total, financed, base, last: base + (financed - base * n), n, profit, cash }
  }, [form.cash, form.profit, form.down, form.count])

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        const missing = firstMissing([
          [form.contactId, 'inst-contact', 'مشتری را انتخاب کنید.'],
          [form.cash, 'inst-cash', 'قیمتِ نقدی را وارد کنید.'],
          [form.count, 'inst-count', 'تعدادِ اقساط را وارد کنید.'],
        ])
        if (missing) {
          setLocalMsg({ text: missing, kind: 'err' })
          return
        }
        void onSubmit(form, preview?.total ?? 0)
      }}
    >
      <FormGrid>
        <FormField id="inst-contact" label="مشتری" required>
          {(id) => (
            <SearchSelect id={id} value={form.contactId} onChange={(e) => set({ contactId: e.target.value })}>
              <option value="">— انتخاب مشتری —</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </SearchSelect>
          )}
        </FormField>
        <FormField label="عنوان قرارداد" optional>
          {(id) => (
            <input
              id={id}
              value={form.title}
              onChange={(e) => set({ title: e.target.value })}
              placeholder="مثلاً خرید یخچال"
            />
          )}
        </FormField>
        <FormField id="inst-cash" label="قیمت نقدی" required>
          {(id) => (
            <InputAffix unit="ریال">
              <NumberInput id={id} value={form.cash} onChange={(v) => set({ cash: v })} />
            </InputAffix>
          )}
        </FormField>
        <FormField label="سود فروش اقساطی" optional>
          {(id) => (
            <InputAffix unit="ریال">
              <NumberInput id={id} value={form.profit} onChange={(v) => set({ profit: v })} placeholder="۰" />
            </InputAffix>
          )}
        </FormField>
        <FormField label="پیش‌پرداخت" optional>
          {(id) => (
            <InputAffix unit="ریال">
              <NumberInput id={id} value={form.down} onChange={(v) => set({ down: v })} placeholder="۰" />
            </InputAffix>
          )}
        </FormField>
        <FormField id="inst-count" label="تعداد اقساط" required>
          {(id) => <NumberInput id={id} value={form.count} onChange={(v) => set({ count: v })} group={false} />}
        </FormField>
        <FormField label="فاصله" tip="فاصله‌ی سررسیدها به ماه؛ ۱ یعنی ماهانه.">
          {(id) => (
            <InputAffix unit="ماه">
              <NumberInput id={id} value={form.interval} onChange={(v) => set({ interval: v })} group={false} />
            </InputAffix>
          )}
        </FormField>
        <FormField label="تاریخِ اولین قسط" required>
          {(id) => (
            <JalaliDatePicker id={id} value={form.startDate} onChange={(iso) => set({ startDate: iso })} />
          )}
        </FormField>
        <FormField label="جریمه‌ی دیرکرد" optional tip="درصدِ ماهانه روی قسطِ معوق؛ فقط برآورد می‌شود و سند نمی‌خورد.">
          {(id) => (
            <InputAffix unit="٪">
              <NumberInput
                id={id}
                value={form.penalty}
                onChange={(v) => set({ penalty: v })}
                allowDecimal
                placeholder="۰"
              />
            </InputAffix>
          )}
        </FormField>
        <FormField label="نام ضامن" optional>
          {(id) => (
            <input id={id} value={form.guarantorName} onChange={(e) => set({ guarantorName: e.target.value })} />
          )}
        </FormField>
        <FormField label="تلفن ضامن" optional>
          {(id) => (
            <input
              id={id}
              value={form.guarantorPhone}
              onChange={(e) => set({ guarantorPhone: e.target.value })}
              dir="ltr"
            />
          )}
        </FormField>
        <FormField label="کد ملی ضامن" optional>
          {(id) => (
            <input
              id={id}
              value={form.guarantorId}
              onChange={(e) => set({ guarantorId: e.target.value })}
              dir="ltr"
            />
          )}
        </FormField>
      </FormGrid>

      {preview && (
        <div className="pos-summary inst-preview">
          <div className="pos-row">
            <span>مبلغ کل قرارداد (نقدی + سود)</span>
            <strong>{fa(preview.total)}</strong>
          </div>
          <div className="pos-row">
            <span>مبلغِ تسهیم‌شده (کل − پیش‌پرداخت)</span>
            <strong>{fa(preview.financed)}</strong>
          </div>
          <div className="pos-row">
            <span>هر قسط</span>
            <strong>{fa(preview.base)}</strong>
          </div>
          {preview.last !== preview.base && (
            <div className="pos-row">
              <span>قسط آخر (با گِردکردن)</span>
              <strong>{fa(preview.last)}</strong>
            </div>
          )}
          <div className="pos-row pos-total">
            <span>
              {toFaDigits(preview.n)} قسط، هر {toFaDigits(Number(form.interval) || 1)} ماه
              {preview.profit > 0 && ` · سود ${toFaDigits(Math.round((preview.profit / preview.cash) * 1000) / 10)}٪`}
            </span>
            <strong>{fa(preview.financed)}</strong>
          </div>
        </div>
      )}

      <div className="ef-card-foot">
        <FormStatus msg={msg ?? localMsg} />
        <button type="button" className="ef-btn-secondary" onClick={onCancel}>
          <X size={15} /> انصراف
        </button>
        <button type="submit" className="btn-primary">
          <Save size={16} /> ثبت قرارداد
        </button>
      </div>
    </form>
  )
}

// ── ویرایشِ زمان‌بندی ─────────────────────────────────────────────────────────

function RescheduleEditor({
  plan,
  onApply,
  msg,
}: {
  plan: InstallmentPlan
  onApply: (lines: { installment_id: string; due_date: string; amount: number }[]) => Promise<void>
  msg: Msg
}) {
  const [draft, setDraft] = useState(() =>
    plan.installments.map((i) => ({ id: i.id, due: i.due_date, amount: String(Number(i.amount)) })),
  )
  useEffect(() => {
    setDraft(plan.installments.map((i) => ({ id: i.id, due: i.due_date, amount: String(Number(i.amount)) })))
  }, [plan.id, plan.installments])

  const sum = draft.reduce((s, d) => s + (Number(d.amount) || 0), 0)
  const target = Number(plan.financed)
  const diff = sum - target

  return (
    <div className="inst-reschedule">
      <p className="hint">
        سررسید و مبلغِ هر قسط را می‌توانید عوض کنید — تعویق، تجمیع، یا تقسیمِ دوباره. تنها قیدِ سرور این است که
        جمعِ اقساط برابرِ مبلغِ تسهیم‌شده بماند و هیچ قسطی کمتر از مبلغِ وصول‌شده‌اش نشود.
      </p>
      <div className="table-scroll ef-table-wrap">
        <table className="cards-on-mobile ef-table">
          <thead>
            <tr>
              <th>قسط</th>
              <th>سررسید</th>
              <th>مبلغ</th>
              <th>وصول‌شده</th>
            </tr>
          </thead>
          <tbody>
            {draft.map((d, idx) => {
              const inst = plan.installments.find((i) => i.id === d.id)!
              return (
                <tr key={d.id}>
                  <td data-label="قسط">{toFaDigits(inst.seq)}</td>
                  <td data-label="سررسید">
                    <JalaliDatePicker
                      value={d.due}
                      onChange={(iso) =>
                        setDraft(draft.map((x, i) => (i === idx ? { ...x, due: iso } : x)))
                      }
                    />
                  </td>
                  <td data-label="مبلغ">
                    <NumberInput
                      value={d.amount}
                      onChange={(v) => setDraft(draft.map((x, i) => (i === idx ? { ...x, amount: v } : x)))}
                    />
                  </td>
                  <td data-label="وصول‌شده" className="money-cell">
                    {fa(inst.paid_amount)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="inst-reschedule-foot">
        <span className={diff === 0 ? 'pos-in' : 'pos-out'}>
          جمع {fa(sum)} از {fa(target)}
          {diff !== 0 && ` (${diff > 0 ? '+' : ''}${fa(diff)})`}
        </span>
        <button
          type="button"
          className="btn-primary"
          disabled={diff !== 0}
          onClick={() =>
            void onApply(
              draft.map((d) => ({ installment_id: d.id, due_date: d.due, amount: Number(d.amount) || 0 })),
            )
          }
        >
          <Save size={14} /> اعمال زمان‌بندی
        </button>
      </div>
      <Note msg={msg} />
    </div>
  )
}

// ── صفحه ─────────────────────────────────────────────────────────────────────

export function InstallmentSalesPage({
  token,
  bankAccounts,
}: {
  token: string
  bankAccounts: BankAccountCache[]
}) {
  const [plans, setPlans] = useState<InstallmentPlan[]>([])
  const [summary, setSummary] = useState<InstallmentSummary | null>(null)
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<PlanFilter>('all')
  const [search, setSearch] = useState('')
  const [tab, setTab] = useState<Tab>('schedule')
  const [error, setError] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [formMsg, setFormMsg] = useState<Msg>(null)
  const [payMsg, setPayMsg] = useState<Msg>(null)
  const [schedMsg, setSchedMsg] = useState<Msg>(null)

  // وصولِ تک‌قسط
  const [payingId, setPayingId] = useState<string | null>(null)
  const [pay, setPay] = useState({ amount: '', method: 'cash' as 'cash' | 'bank', bankId: '', date: todayIso(), notes: '' })

  // وصولِ یک فیش بین چند قسط + تسویه‌ی زودهنگام
  const [settleOpen, setSettleOpen] = useState(false)
  const [settle, setSettle] = useState({ amount: '', method: 'cash' as 'cash' | 'bank', bankId: '', date: todayIso() })
  const [quote, setQuote] = useState<EarlySettlement | null>(null)
  const [discount, setDiscount] = useState('')

  async function refresh() {
    setError(null)
    try {
      const [ps, cs, sm] = await Promise.all([
        fetchInstallmentPlans(token),
        fetchContacts(token),
        fetchInstallmentSummary(token),
      ])
      setPlans(ps)
      setContacts(cs.filter((c) => c.is_customer))
      setSummary(sm)
    } catch (err) {
      setError(errText(err))
    }
  }
  useEffect(() => {
    void refresh()
  }, [token])

  const selected = useMemo(() => plans.find((p) => p.id === selectedId) ?? null, [plans, selectedId])

  const filtered = useMemo(() => {
    const q = search.trim()
    return plans.filter((p) => {
      if (q && !`${p.contact_name} ${p.title} ${p.number ?? ''}`.includes(q)) return false
      if (filter === 'all') return true
      if (filter === 'overdue') return p.status === 'active' && p.overdue_count > 0
      return p.status === filter
    })
  }, [plans, filter, search])

  const pg = usePagination(filtered, 10, `${filter}|${search}`)

  const counts = useMemo(
    () => ({
      all: plans.length,
      active: plans.filter((p) => p.status === 'active').length,
      overdue: plans.filter((p) => p.status === 'active' && p.overdue_count > 0).length,
      completed: plans.filter((p) => p.status === 'completed').length,
      cancelled: plans.filter((p) => p.status === 'cancelled').length,
    }),
    [plans],
  )

  async function createPlan(form: typeof EMPTY_FORM, total: number) {
    setFormMsg(null)
    if (!form.contactId || !(total > 0) || Number(form.count) < 1) {
      setFormMsg({ text: 'مشتری، قیمت نقدی و تعداد اقساط الزامی‌اند.', kind: 'err' })
      return
    }
    try {
      const plan = await createInstallmentPlan(token, {
        contact_id: form.contactId,
        title: form.title || undefined,
        total_amount: total,
        cash_price: Number(form.cash),
        profit_amount: Number(form.profit) || 0,
        down_payment: Number(form.down) || 0,
        num_installments: Number(form.count),
        interval_months: Number(form.interval) || 1,
        start_date: form.startDate,
        penalty_rate: Number(form.penalty) || 0,
        guarantor_name: form.guarantorName,
        guarantor_phone: form.guarantorPhone,
        guarantor_national_id: form.guarantorId,
      })
      setFormOpen(false)
      await refresh()
      setSelectedId(plan.id)
      setTab('schedule')
    } catch (err) {
      setFormMsg({ text: errText(err), kind: 'err' })
    }
  }

  function startPay(inst: Installment) {
    setPayingId(inst.id)
    setPay({ amount: String(Number(inst.remaining)), method: 'cash', bankId: '', date: todayIso(), notes: '' })
    setPayMsg(null)
  }

  async function submitPay(inst: Installment) {
    if (!selected) return
    setPayMsg(null)
    if (!(Number(pay.amount) > 0)) {
      setPayMsg({ text: 'مبلغ باید بزرگ‌تر از صفر باشد.', kind: 'err' })
      return
    }
    if (pay.method === 'bank' && !pay.bankId) {
      setPayMsg({ text: 'حساب بانکی را انتخاب کنید.', kind: 'err' })
      return
    }
    try {
      await payInstallment(token, selected.id, inst.id, {
        amount: Number(pay.amount),
        transaction_date: pay.date,
        method: pay.method,
        bank_account_id: pay.method === 'bank' ? pay.bankId : null,
        notes: pay.notes,
      })
      setPayingId(null)
      await refresh()
    } catch (err) {
      setPayMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function submitSettle() {
    if (!selected) return
    setPayMsg(null)
    if (!(Number(settle.amount) > 0)) {
      setPayMsg({ text: 'مبلغ باید بزرگ‌تر از صفر باشد.', kind: 'err' })
      return
    }
    if (settle.method === 'bank' && !settle.bankId) {
      setPayMsg({ text: 'حساب بانکی را انتخاب کنید.', kind: 'err' })
      return
    }
    try {
      await settleInstallments(token, selected.id, {
        amount: Number(settle.amount),
        transaction_date: settle.date,
        method: settle.method,
        bank_account_id: settle.method === 'bank' ? settle.bankId : null,
      })
      setSettleOpen(false)
      setSettle({ ...settle, amount: '' })
      await refresh()
    } catch (err) {
      setPayMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function loadQuote(d: string) {
    if (!selected) return
    setDiscount(d)
    try {
      setQuote(await fetchEarlySettlement(token, selected.id, Number(d) || 0))
      setPayMsg(null)
    } catch (err) {
      setPayMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function applyReschedule(lines: { installment_id: string; due_date: string; amount: number }[]) {
    if (!selected) return
    setSchedMsg(null)
    try {
      await rescheduleInstallments(token, selected.id, lines)
      setSchedMsg({ text: 'زمان‌بندی به‌روزرسانی شد.', kind: 'ok' })
      await refresh()
    } catch (err) {
      setSchedMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function cancelPlan(plan: InstallmentPlan) {
    if (!window.confirm(`قرارداد «${plan.title}» لغو شود؟ پرداخت‌های انجام‌شده باقی می‌مانند.`)) return
    try {
      await cancelInstallmentPlan(token, plan.id)
      await refresh()
    } catch (err) {
      setError(errText(err))
    }
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={CalendarClock}
        title="فروش اقساطی"
        description="قرارداد اقساط برای فروشِ نسیه، زمان‌بندیِ وصول، و ثبتِ هر پرداخت به‌صورتِ دریافتِ واقعیِ خزانه. قرارداد بدهی نمی‌سازد — بدهی از فاکتورِ نسیه می‌آید."
      />
      <div className="ef-form">
      {error && <p className="ef-message ef-message--warn">{error}</p>}

      {/* ── سبدِ اقساط ── */}
      <div className="cc-head">
        <div className="cc-summary">
          <Metric
            icon={<CalendarClock size={14} />}
            label="قراردادهای فعال"
            value={summary ? faInt(summary.active_plans) : '—'}
          />
          <Metric
            icon={<CircleDollarSign size={14} />}
            label="ماندهٔ قابل وصول"
            value={summary ? fa(summary.total_remaining) : '—'}
            hint={summary ? `${toFaDigits(summary.collected_pct)}٪ وصول شده` : undefined}
          />
          <Metric
            icon={<AlertTriangle size={14} />}
            label="معوق"
            value={summary ? fa(summary.overdue_amount) : '—'}
            hint={summary ? `${faInt(summary.overdue_count)} قسط` : undefined}
            tone={summary && Number(summary.overdue_amount) > 0 ? 'out' : 'plain'}
          />
          <Metric
            icon={<Wallet size={14} />}
            label="سررسیدِ ۷ روز آینده"
            value={summary ? fa(summary.due_this_week) : '—'}
            hint={summary ? `۳۰ روز: ${fa(summary.due_this_month)}` : undefined}
          />
          <Metric
            icon={<Percent size={14} />}
            label="جریمه‌ی برآوردی"
            value={summary ? fa(summary.penalty_total) : '—'}
            hint="محاسبه‌شده، ثبت‌نشده"
            tone={summary && Number(summary.penalty_total) > 0 ? 'out' : 'plain'}
          />
        </div>
        {summary && <AgingBar summary={summary} />}
      </div>

      <div className="workspace-split cc-split">
        {/* ── فهرستِ قراردادها ── */}
        <SectionCard
          icon={CalendarClock}
          title="قراردادها"
          badge={<CountBadge accent>{faInt(filtered.length)} از {faInt(plans.length)}</CountBadge>}
          actions={
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                setFormOpen(true)
                setFormMsg(null)
              }}
            >
              <Plus size={14} /> قرارداد جدید
            </button>
          }
        >
          <div className="inst-toolbar">
            <div className="inst-filters">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  className={filter === f.key ? 'chip-active' : ''}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label} ({toFaDigits(counts[f.key])})
                </button>
              ))}
            </div>
            <label className="inst-search">
              <Search size={14} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="نامِ مشتری، عنوان، یا شماره"
              />
            </label>
          </div>

          {filtered.length === 0 ? (
            <EmptyState
              icon={CalendarClock}
              text={plans.length === 0 ? 'هنوز قرارداد اقساطی ثبت نشده.' : 'قراردادی مطابقِ فیلتر نیست.'}
            />
          ) : (
            <>
              <ul className="cc-tree inst-list">
                {pg.pageItems.map((p) => (
                  <li key={p.id} className={`cc-node ${selectedId === p.id ? 'is-selected' : ''}`}>
                    <button
                      type="button"
                      className="cc-node-main"
                      onClick={() => {
                        setSelectedId(p.id)
                        setTab('schedule')
                        setQuote(null)
                        setSettleOpen(false)
                      }}
                    >
                      <span className="cc-node-text">
                        <span className="cc-node-title">
                          <span className="cc-kind-chip">{toFaDigits(p.number ?? 0)}</span>
                          <span className="cc-tree-title">{p.contact_name}</span>
                          <span className={`status-badge tone-${PLAN_STATUS[p.status].tone}`}>
                            {PLAN_STATUS[p.status].label}
                          </span>
                        </span>
                        <span className="cc-node-sub">
                          <span>{p.title}</span>
                          {p.next_due_date && p.status === 'active' && (
                            <span>سررسید بعدی {formatJalali(p.next_due_date)}</span>
                          )}
                          {p.overdue_count > 0 && (
                            <span className="status-badge tone-danger">
                              {faInt(p.overdue_count)} معوق
                            </span>
                          )}
                        </span>
                        <ProgressBar
                          paid={Number(p.total_paid)}
                          scheduled={Number(p.total_paid) + Number(p.total_remaining)}
                        />
                      </span>
                      <span className="cc-node-figures">
                        <span className="cc-node-profit">{fa(p.total_remaining)}</span>
                        <span className="cc-node-var">از {fa(p.total_amount)}</span>
                      </span>
                    </button>
                    <span className="cc-node-actions check-actions">
                      <button type="button" onClick={() => printSchedule(p)} aria-label="چاپ">
                        <Printer size={13} />
                      </button>
                      {p.status === 'active' && (
                        <button
                          type="button"
                          className="icon-btn-danger"
                          onClick={() => void cancelPlan(p)}
                          aria-label="لغو قرارداد"
                        >
                          <Ban size={13} />
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </>
          )}

          {formOpen && (
            <div className="cc-form-slot">
              <div className="cc-form-title">
                <Plus size={14} /> قرارداد اقساطی جدید
                <button type="button" className="cc-form-close" onClick={() => setFormOpen(false)}>
                  <X size={14} />
                </button>
              </div>
              <PlanForm
                contacts={contacts}
                onSubmit={createPlan}
                onCancel={() => setFormOpen(false)}
                msg={formMsg}
              />
            </div>
          )}
        </SectionCard>

        {/* ── پرونده‌ی قرارداد ── */}
        <SectionCard
          icon={HandCoins}
          title={selected ? `قرارداد ${toFaDigits(selected.number ?? 0)} — ${selected.contact_name}` : 'پرونده‌ی قرارداد'}
          description={selected ? selected.title : 'یک قرارداد را از فهرست انتخاب کنید.'}
          actions={
            selected ? (
              <button type="button" onClick={() => printSchedule(selected)}>
                <Printer size={13} /> چاپ جدول
              </button>
            ) : undefined
          }
        >
          {!selected ? (
            summary && summary.top_debtors.length > 0 ? (
              <div className="inst-debtors">
                <h4>بدهکارانِ بزرگ</h4>
                <p className="hint">مجموعِ ماندهٔ همه‌ی قراردادهای هر مشتری — ریسک روی «مشتری» است نه «قرارداد».</p>
                <div className="table-scroll ef-table-wrap">
                  <table className="cards-on-mobile ef-table">
                    <thead>
                      <tr>
                        <th>مشتری</th>
                        <th>قرارداد</th>
                        <th>مانده</th>
                        <th>معوق</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.top_debtors.map((d) => (
                        <tr key={d.contact_id}>
                          <td className="card-title" data-label="مشتری">{d.contact_name}</td>
                          <td data-label="قرارداد">{faInt(d.plans)}</td>
                          <td data-label="مانده" className="money-cell">{fa(d.remaining)}</td>
                          <td data-label="معوق" className="money-cell">
                            <span className={Number(d.overdue) > 0 ? 'pos-out' : ''}>{fa(d.overdue)}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <EmptyState icon={HandCoins} text="قراردادی انتخاب نشده." />
            )
          ) : (
            <>
              {/* خلاصه‌ی قرارداد */}
              <div className="cc-summary inst-plan-summary">
                <Metric icon={<Coins size={14} />} label="قیمت نقدی" value={fa(selected.cash_price)} />
                <Metric
                  icon={<Percent size={14} />}
                  label="سود اقساط"
                  value={fa(selected.profit_amount)}
                  hint={`${toFaDigits(selected.profit_pct)}٪ روی قیمت نقدی`}
                />
                <Metric icon={<CircleDollarSign size={14} />} label="مبلغ کل" value={fa(selected.total_amount)} />
                <Metric
                  icon={<Wallet size={14} />}
                  label="مانده"
                  value={fa(selected.total_remaining)}
                  hint={`${toFaDigits(selected.collected_pct)}٪ وصول شده`}
                  tone={Number(selected.overdue_amount) > 0 ? 'out' : 'plain'}
                />
              </div>

              <div className="cc-meta">
                <span>
                  <CalendarClock size={13} /> {toFaDigits(selected.num_installments)} قسط، هر{' '}
                  {toFaDigits(selected.interval_months)} ماه
                </span>
                {Number(selected.down_payment) > 0 && (
                  <span>
                    <HandCoins size={13} /> پیش‌پرداخت {fa(selected.down_payment)}
                  </span>
                )}
                {Number(selected.penalty_rate) > 0 && (
                  <span>
                    <Percent size={13} /> جریمه {toFaDigits(selected.penalty_rate)}٪ ماهانه
                  </span>
                )}
                {selected.guarantor_name && (
                  <span>
                    <ShieldCheck size={13} /> ضامن: {selected.guarantor_name}
                    {selected.guarantor_phone ? ` — ${selected.guarantor_phone}` : ''}
                  </span>
                )}
                {selected.worst_days_late > 0 && (
                  <span className="pos-out">
                    <TrendingDown size={13} /> بیشترین تأخیر {faInt(selected.worst_days_late)} روز
                  </span>
                )}
              </div>

              <div className="cc-tabs">
                <button type="button" className={tab === 'schedule' ? 'is-active' : ''} onClick={() => setTab('schedule')}>
                  اقساط
                </button>
                <button type="button" className={tab === 'payments' ? 'is-active' : ''} onClick={() => setTab('payments')}>
                  پرداخت‌ها
                </button>
                <button
                  type="button"
                  className={tab === 'reschedule' ? 'is-active' : ''}
                  onClick={() => setTab('reschedule')}
                >
                  تنظیم زمان‌بندی
                </button>
              </div>

              {tab === 'schedule' && (
                <>
                  {selected.status === 'active' && (
                    <div className="inst-actions">
                      <button type="button" onClick={() => { setSettleOpen(!settleOpen); setQuote(null) }}>
                        <Layers size={13} /> وصولِ یک فیش بین چند قسط
                      </button>
                      <button type="button" onClick={() => void loadQuote('0')}>
                        <CircleDollarSign size={13} /> تسویه‌ی زودهنگام
                      </button>
                    </div>
                  )}

                  {settleOpen && (
                    <div className="pay-inline inst-settle">
                      <label>
                        مبلغ فیش
                        <NumberInput value={settle.amount} onChange={(v) => setSettle({ ...settle, amount: v })} />
                      </label>
                      <label>
                        تاریخ
                        <JalaliDatePicker value={settle.date} onChange={(iso) => setSettle({ ...settle, date: iso })} />
                      </label>
                      <label>
                        روش
                        <SearchSelect
                          value={settle.method}
                          onChange={(e) => setSettle({ ...settle, method: e.target.value as 'cash' | 'bank' })}
                        >
                          <option value="cash">نقدی (صندوق)</option>
                          <option value="bank">بانکی</option>
                        </SearchSelect>
                      </label>
                      {settle.method === 'bank' && (
                        <label>
                          حساب بانکی
                          <SearchSelect value={settle.bankId} onChange={(e) => setSettle({ ...settle, bankId: e.target.value })}>
                            <option value="">— انتخاب —</option>
                            {bankAccounts.map((b) => (
                              <option key={b.id} value={b.id}>
                                {b.name}
                              </option>
                            ))}
                          </SearchSelect>
                        </label>
                      )}
                      <button type="button" className="btn-primary" onClick={() => void submitSettle()}>
                        <Save size={13} /> تسهیم و ثبت
                      </button>
                    </div>
                  )}

                  {quote && (
                    <div className="pos-summary inst-quote">
                      <div className="pos-row">
                        <span>ماندهٔ اقساط</span>
                        <strong>{fa(quote.remaining)}</strong>
                      </div>
                      <div className="pos-row">
                        <span>سودِ وصول‌نشده (سقفِ تخفیف)</span>
                        <strong>{fa(quote.unearned_profit)}</strong>
                      </div>
                      <label className="inst-quote-input">
                        تخفیفِ تعجیل
                        <NumberInput value={discount} onChange={(v) => void loadQuote(v)} />
                      </label>
                      <div className="pos-row pos-total">
                        <span>مبلغِ قابلِ پرداخت</span>
                        <strong>{fa(quote.payable)}</strong>
                      </div>
                      <p className="hint">
                        برای ثبت، همین مبلغ را در «وصولِ یک فیش» وارد کنید. تخفیف سندِ خودش را می‌خواهد، پس
                        این‌جا فقط محاسبه می‌شود.
                      </p>
                    </div>
                  )}

                  <div className="table-scroll ef-table-wrap">
                    <table className="inst-sched-table cards-on-mobile">
                      <thead>
                        <tr>
                          <th>قسط</th>
                          <th>سررسید</th>
                          <th>مبلغ</th>
                          <th>مانده</th>
                          <th>تأخیر</th>
                          <th>وضعیت</th>
                          <th>اقدام</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selected.installments.map((inst) => (
                          <Fragment key={inst.id}>
                            <tr>
                              <td data-label="قسط">{toFaDigits(inst.seq)}</td>
                              <td data-label="سررسید">{formatJalali(inst.due_date)}</td>
                              <td data-label="مبلغ" className="money-cell">{fa(inst.amount)}</td>
                              <td data-label="مانده" className="money-cell">{fa(inst.remaining)}</td>
                              <td data-label="تأخیر">
                                {inst.days_late > 0 ? (
                                  <span className="pos-out">
                                    {faInt(inst.days_late)} روز
                                    {Number(inst.penalty) > 0 && ` · جریمه ${fa(inst.penalty)}`}
                                  </span>
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td data-label="وضعیت">
                                <span className={`status-badge tone-${INST_STATUS[inst.status].tone}`}>
                                  {INST_STATUS[inst.status].label}
                                </span>
                              </td>
                              <td className="inst-inst-action" data-label="اقدام">
                                {selected.status === 'active' && inst.status !== 'paid' && (
                                  <button type="button" onClick={() => startPay(inst)}>
                                    <Wallet size={13} /> پرداخت
                                  </button>
                                )}
                              </td>
                            </tr>
                            {payingId === inst.id && (
                              <tr className="inst-pay-row">
                                <td colSpan={7}>
                                  <div className="pay-inline">
                                    <label>
                                      مبلغ
                                      <NumberInput value={pay.amount} onChange={(v) => setPay({ ...pay, amount: v })} />
                                    </label>
                                    <label>
                                      تاریخ
                                      <JalaliDatePicker value={pay.date} onChange={(iso) => setPay({ ...pay, date: iso })} />
                                    </label>
                                    <label>
                                      روش
                                      <SearchSelect
                                        value={pay.method}
                                        onChange={(e) => setPay({ ...pay, method: e.target.value as 'cash' | 'bank' })}
                                      >
                                        <option value="cash">نقدی (صندوق)</option>
                                        <option value="bank">بانکی</option>
                                      </SearchSelect>
                                    </label>
                                    {pay.method === 'bank' && (
                                      <label>
                                        حساب بانکی
                                        <SearchSelect value={pay.bankId} onChange={(e) => setPay({ ...pay, bankId: e.target.value })}>
                                          <option value="">— انتخاب —</option>
                                          {bankAccounts.map((b) => (
                                            <option key={b.id} value={b.id}>
                                              {b.name}
                                            </option>
                                          ))}
                                        </SearchSelect>
                                      </label>
                                    )}
                                    <label>
                                      شرح / شماره فیش
                                      <input value={pay.notes} onChange={(e) => setPay({ ...pay, notes: e.target.value })} />
                                    </label>
                                    <button type="button" className="btn-primary" onClick={() => void submitPay(inst)}>
                                      <Save size={13} /> ثبت دریافت
                                    </button>
                                    <button type="button" onClick={() => setPayingId(null)}>
                                      <X size={13} />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Note msg={payMsg} />
                  <p className="hint">
                    هر پرداخت خودکار به‌صورتِ «دریافت از مشتری» در خزانه ثبت می‌شود و ماندهٔ حساب‌های دریافتنی را کم
                    می‌کند. جریمه‌ی دیرکرد فقط محاسبه می‌شود — برای وصولش سندِ جداگانه لازم است.
                  </p>
                </>
              )}

              {tab === 'payments' &&
                (selected.payments.length === 0 ? (
                  <EmptyState icon={Wallet} text="هنوز پرداختی روی این قرارداد ثبت نشده." />
                ) : (
                  <div className="table-scroll ef-table-wrap">
                    <table className="cards-on-mobile ef-table">
                      <thead>
                        <tr>
                          <th>تاریخ</th>
                          <th>قسط</th>
                          <th>مبلغ</th>
                          <th>روش</th>
                          <th>شرح</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selected.payments.map((p) => (
                          <tr key={p.id}>
                            <td data-label="تاریخ">{formatJalali(p.paid_on)}</td>
                            <td data-label="قسط">{toFaDigits(p.installment_seq)}</td>
                            <td data-label="مبلغ" className="money-cell">{fa(p.amount)}</td>
                            <td data-label="روش">{p.method === 'bank' ? 'بانکی' : 'نقدی'}</td>
                            <td className="card-title" data-label="شرح">{p.notes || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}

              {tab === 'reschedule' &&
                (selected.status !== 'active' ? (
                  <EmptyState icon={UserRound} text="فقط زمان‌بندیِ قراردادِ فعال قابلِ تغییر است." />
                ) : (
                  <RescheduleEditor plan={selected} onApply={applyReschedule} msg={schedMsg} />
                ))}
            </>
          )}
        </SectionCard>
      </div>
      </div>
    </div>
  )
}
