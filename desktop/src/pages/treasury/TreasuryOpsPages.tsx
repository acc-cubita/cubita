import { useMemo, useState } from 'react'
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Banknote,
  CheckCircle2,
  HandCoins,
  Landmark,
  PiggyBank,
  Receipt,
  RefreshCw,
  Route,
  Save,
  Scale,
  Wallet,
} from 'lucide-react'
import {
  createPettyCashCharge,
  createPettyCashExpense,
  createTreasuryPayment,
  createTreasuryReceipt,
  fetchAging,
  fetchBankAccountsLive,
  fetchContacts,
  fetchPettyCashBalance,
  fetchPettyCashTransactions,
  fetchTreasuryTransactions,
  type AgingRow,
  type ContactRecord,
} from '../../api'
import type { AccountCache } from '../../electron.d'
import type { PageKey } from '../../lib/navModel'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, todayIso } from '../../lib/jalali'
// اسکلتِ مشترکِ صفحه‌های عملیات. زیرِ پوشه‌ی accounting/ زندگی می‌کند چون اولین‌بار
// آن‌جا لازم شد، ولی محتوایش عمومی است و قراردادِ صفحه‌ها به همان ارجاع می‌دهد.
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'

/**
 * عملیاتِ پولیِ ماژولِ «دریافت و پرداخت» — رسید، اعلامیه، تسویه‌ی طرف‌حساب، صندوق و تنخواه.
 *
 * **چرا رسید و اعلامیه دو صفحه‌ی جدا شدند و نه یک فرم با سوییچ:** پیش‌تر یک فرم بود با
 * یک `select`ِ «دریافت/پرداخت». همان یک انتخاب تعیین می‌کند سند به کدام سمت می‌خورد،
 * و اشتباهش یعنی سندِ وارونه. دو صفحه‌ی جدا، هرکدام با عنوان و رنگِ خودش، این خطا را
 * از بین می‌برد و از منو هم مستقیم به همان کاری می‌رود که کاربر می‌خواهد.
 */

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

// ═══════════════════ ۱) فرآیند دریافت و پرداخت ═══════════════════

/** یک گامِ راهنما — همان الگوی «عملیات اول دوره». */
function Step({
  index,
  title,
  description,
  state,
  action,
  onGo,
}: {
  index: number
  title: string
  description: string
  state: { label: string; tone: 'ok' | 'todo' | 'warn' }
  action: string
  onGo: () => void
}) {
  return (
    <div className={`ops-step is-${state.tone}`}>
      <span className="ops-step-num">{faInt(index)}</span>
      <div className="ops-step-body">
        <div className="ops-step-head">
          <strong>{title}</strong>
          <span className={`badge ${state.tone === 'ok' ? 'success' : state.tone === 'warn' ? 'warning' : ''}`}>
            {state.label}
          </span>
        </div>
        <p className="ops-step-desc">{description}</p>
      </div>
      <button type="button" onClick={onGo}>
        {action}
      </button>
    </div>
  )
}

/**
 * نقشه‌ی راهِ ماژول: پول از کجا می‌آید و کجا می‌رود.
 *
 * هجده عملیاتِ این ماژول برای کسی که تازه شروع کرده یک فهرستِ بلندِ بی‌ترتیب است.
 * این صفحه ترتیبِ واقعی را نشان می‌دهد و وضعیتِ هر گام را از داده‌ی زنده می‌خواند —
 * نه یک برچسبِ ثابت که هیچ‌وقت سبز نمی‌شود.
 */
export function PayFlowPage({ token, onNavigate }: { token: string; onNavigate: (page: PageKey) => void }) {
  const state = useAsync(
    async () => {
      const [banks, treasury, petty] = await Promise.all([
        fetchBankAccountsLive(token),
        fetchTreasuryTransactions(token),
        fetchPettyCashBalance(token).catch(() => ({ balance: '0' })),
      ])
      return { banks, treasury, petty }
    },
    [token],
  )

  const banks = state.data?.banks ?? []
  const treasury = state.data?.treasury ?? []
  const receipts = treasury.filter((t) => t.type === 'receipt').length
  const payments = treasury.filter((t) => t.type === 'payment').length

  return (
    <OpsPage
      icon={Route}
      title="فرآیند دریافت و پرداخت"
      description="ترتیبِ کارها در این ماژول: از تعریفِ محلِ پول تا ثبتِ رسید و اعلامیه و تطبیقِ بانک."
    >
      <SectionCard
        icon={Route}
        title="مسیرِ کار"
        description="هر گام صفحه‌ی خودش را دارد؛ این‌جا فقط ترتیب و وضعیت است."
        actions={
          <button type="button" onClick={state.reload}>
            <RefreshCw size={13} /> بازخوانی
          </button>
        }
      >
        <AsyncBlock loading={state.loading} error={state.error}>
          <div className="ops-steps">
            <Step
              index={1}
              title="محلِ نگهداریِ پول"
              description="حسابِ بانکی، صندوقِ نقدی و دستگاهِ کارتخوان را تعریف کنید. هر رسید باید بگوید پول کجا نشست."
              state={
                banks.length > 0
                  ? { label: `${faInt(banks.length)} حساب بانکی`, tone: 'ok' }
                  : { label: 'انجام نشده', tone: 'todo' }
              }
              action="حساب بانکی"
              onGo={() => onNavigate('bankaccounts')}
            />
            <Step
              index={2}
              title="ثبتِ دریافت"
              description="هر پولی که از مشتری می‌گیرید — نقدی، بانکی یا کارتخوان — با «رسید دریافت» ثبت می‌شود و سندش خودکار می‌خورد."
              state={
                receipts > 0
                  ? { label: `${faInt(receipts)} رسید`, tone: 'ok' }
                  : { label: 'هنوز رسیدی نیست', tone: 'todo' }
              }
              action="رسید دریافت"
              onGo={() => onNavigate('receiptvoucher')}
            />
            <Step
              index={3}
              title="ثبتِ پرداخت"
              description="پرداخت به تأمین‌کننده با «اعلامیه پرداخت». همان مسیر، در جهتِ عکس."
              state={
                payments > 0
                  ? { label: `${faInt(payments)} اعلامیه`, tone: 'ok' }
                  : { label: 'هنوز پرداختی نیست', tone: 'todo' }
              }
              action="اعلامیه پرداخت"
              onGo={() => onNavigate('paymentvoucher')}
            />
            <Step
              index={4}
              title="چک‌ها"
              description="چکِ دریافتی را واگذار و وصول کنید، چکِ صادرشده را از دسته‌چک بکشید و سررسیدش را پیگیری کنید."
              state={{ label: 'هر وقت چک داشتید', tone: 'warn' }}
              action="عملیات چک"
              onGo={() => onNavigate('checkops')}
            />
            <Step
              index={5}
              title="تطبیق با بانک"
              description="صورت‌حسابِ بانک را وارد کنید و مغایرت‌ها را ببندید — تنها راهِ مطمئن‌شدن از اینکه دفتر با بانک یکی است."
              state={{ label: 'پایانِ هر ماه', tone: 'warn' }}
              action="مغایرت بانکی"
              onGo={() => onNavigate('bankreconcile')}
            />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ ۲ و ۳) رسید دریافت / اعلامیه پرداخت ═══════════════════

/** فرمِ مشترکِ رسید و اعلامیه — تنها تفاوت، جهتِ پول و واژه‌هاست. */
function VoucherPage({
  token,
  kind,
}: {
  token: string
  kind: 'receipt' | 'payment'
}) {
  const isReceipt = kind === 'receipt'
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const [date, setDate] = useState(todayIso())
  const [contactId, setContactId] = useState('')
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState<'cash' | 'bank'>('cash')
  const [bankAccountId, setBankAccountId] = useState('')
  const [description, setDescription] = useState('')

  const data = useAsync(
    async () => {
      const [contacts, banks, recent] = await Promise.all([
        fetchContacts(token),
        fetchBankAccountsLive(token),
        fetchTreasuryTransactions(token),
      ])
      return { contacts, banks, recent }
    },
    [token, reloadKey],
  )

  const contacts = useMemo(() => {
    const all: ContactRecord[] = data.data?.contacts ?? []
    return all.filter((c) => (isReceipt ? c.type !== 'supplier' : c.type !== 'customer'))
  }, [data.data, isReceipt])
  const banks = data.data?.banks ?? []
  const recent = useMemo(
    () => (data.data?.recent ?? []).filter((t) => t.type === kind).slice(0, 20),
    [data.data, kind],
  )
  const pg = usePagination(recent, 8)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!contactId) {
      setMsg({ text: 'طرف حساب را انتخاب کنید.', kind: 'err' })
      return
    }
    if (method === 'bank' && !bankAccountId) {
      setMsg({ text: 'برای روشِ بانکی، حساب بانکی لازم است.', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      const payload = {
        transaction_date: date,
        contact_id: contactId,
        amount: Number(amount || 0),
        method,
        bank_account_id: method === 'bank' ? bankAccountId : null,
        description,
      }
      if (isReceipt) await createTreasuryReceipt(token, payload)
      else await createTreasuryPayment(token, payload)
      setMsg({
        text: isReceipt ? 'رسیدِ دریافت ثبت شد و سندش خودکار صادر شد.' : 'اعلامیه‌ی پرداخت ثبت شد و سندش خودکار صادر شد.',
        kind: 'ok',
      })
      setAmount('')
      setDescription('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={isReceipt ? ArrowDownToLine : ArrowUpFromLine}
      title={isReceipt ? 'رسید دریافت' : 'اعلامیه پرداخت'}
      description={
        isReceipt
          ? 'پولی که از مشتری گرفته‌اید را ثبت کنید؛ سندِ حسابداری و مانده‌ی طرف‌حساب خودکار به‌روز می‌شوند.'
          : 'پولی که به تأمین‌کننده داده‌اید را ثبت کنید؛ سندِ حسابداری و مانده‌ی طرف‌حساب خودکار به‌روز می‌شوند.'
      }
    >
      <Note msg={msg} />

      <div className="workspace-split">
        <SectionCard
          icon={isReceipt ? Receipt : Banknote}
          title={isReceipt ? 'رسیدِ تازه' : 'اعلامیه‌ی تازه'}
          description={isReceipt ? 'دریافت از مشتری' : 'پرداخت به تأمین‌کننده'}
        >
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              تاریخ
              <JalaliDatePicker value={date} onChange={setDate} />
            </label>
            <label>
              طرف حساب
              <select value={contactId} onChange={(e) => setContactId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              مبلغ (ریال)
              <NumberInput value={amount} onChange={setAmount} />
            </label>
            <label>
              روش
              <select value={method} onChange={(e) => setMethod(e.target.value as 'cash' | 'bank')}>
                <option value="cash">صندوق (نقدی)</option>
                <option value="bank">بانک</option>
              </select>
            </label>
            {method === 'bank' && (
              <label>
                حساب بانکی
                <select value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
                  <option value="">— انتخاب —</option>
                  {banks.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="form-wide">
              شرح
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}>
                <Save size={14} /> {isReceipt ? 'ثبتِ رسید' : 'ثبتِ اعلامیه'}
              </button>
            </div>
          </form>
        </SectionCard>

        <SectionCard
          icon={HandCoins}
          title={isReceipt ? 'آخرین دریافت‌ها' : 'آخرین پرداخت‌ها'}
          description="بیست موردِ آخر. دفترِ کامل زیرِ کارتِ «فهرست» است."
        >
          <AsyncBlock
            loading={data.loading}
            error={data.error}
            empty={recent.length === 0}
            emptyText={isReceipt ? 'هنوز دریافتی ثبت نشده.' : 'هنوز پرداختی ثبت نشده.'}
          >
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>تاریخ</th>
                    <th>طرف حساب</th>
                    <th>روش</th>
                    <th>مبلغ</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((t) => (
                    <tr key={t.id}>
                      <td className="card-title" data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                      <td className="card-wide" data-label="طرف حساب">{t.contact_name}</td>
                      <td data-label="روش">{t.method === 'bank' ? 'بانک' : 'صندوق'}</td>
                      <td className="money-cell" data-label="مبلغ">{fa(t.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          </AsyncBlock>
        </SectionCard>
      </div>
    </OpsPage>
  )
}

export function ReceiptVoucherPage({ token }: { token: string }) {
  return <VoucherPage token={token} kind="receipt" />
}

export function PaymentVoucherPage({ token }: { token: string }) {
  return <VoucherPage token={token} kind="payment" />
}

// ═══════════════════ ۵) تسویه حساب طرف مقابل ═══════════════════

/**
 * مانده‌ی هر طرف‌حساب و تسویه‌ی آن با یک کلیک.
 *
 * **چرا از گزارشِ سنین می‌خواند و مانده را دوباره حساب نمی‌کند:** مانده‌ی طرف‌حساب یک
 * تعریفِ حسابداری دارد که همان گزارش پیاده کرده. محاسبه‌ی دومِ کلاینتی، دیر یا زود با
 * گزارش اختلاف پیدا می‌کرد و آن‌وقت کدام درست بود؟
 */
export function ContactSettlementPage({ token }: { token: string }) {
  const [kind, setKind] = useState<'receivable' | 'payable'>('receivable')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [method, setMethod] = useState<'cash' | 'bank'>('cash')
  const [bankAccountId, setBankAccountId] = useState('')

  const data = useAsync(
    async () => {
      const [aging, banks] = await Promise.all([fetchAging(token, kind), fetchBankAccountsLive(token)])
      return { aging, banks }
    },
    [token, kind, reloadKey],
  )

  const rows = useMemo(
    () => (data.data?.aging.rows ?? []).filter((r) => Number(r.total) !== 0),
    [data.data],
  )
  const banks = data.data?.banks ?? []
  const pg = usePagination(rows, 12)

  async function settle(row: AgingRow) {
    if (method === 'bank' && !bankAccountId) {
      setMsg({ text: 'برای روشِ بانکی، اول حساب بانکی را انتخاب کنید.', kind: 'err' })
      return
    }
    const amount = Math.abs(Number(row.total))
    if (!window.confirm(`تسویه‌ی کاملِ «${row.contact_name}» به مبلغ ${fa(amount)} ریال ثبت شود؟`)) return
    setBusy(row.contact_id)
    setMsg(null)
    try {
      const payload = {
        transaction_date: todayIso(),
        contact_id: row.contact_id,
        amount,
        method,
        bank_account_id: method === 'bank' ? bankAccountId : null,
        description: 'تسویه حساب',
      }
      if (kind === 'receivable') await createTreasuryReceipt(token, payload)
      else await createTreasuryPayment(token, payload)
      setMsg({ text: `حسابِ «${row.contact_name}» تسویه شد.`, kind: 'ok' })
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  return (
    <OpsPage
      icon={Scale}
      title="تسویه حساب طرف مقابل"
      description="مانده‌ی باز هر طرف‌حساب، و تسویه‌ی کاملِ آن با یک رسید یا اعلامیه."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <div className="cc-presets">
              <button type="button" className={kind === 'receivable' ? 'is-active' : ''} onClick={() => setKind('receivable')}>
                طلب از مشتریان
              </button>
              <button type="button" className={kind === 'payable' ? 'is-active' : ''} onClick={() => setKind('payable')}>
                بدهی به تأمین‌کنندگان
              </button>
            </div>
            <label className="acc-inline-field">
              روشِ تسویه
              <select value={method} onChange={(e) => setMethod(e.target.value as 'cash' | 'bank')}>
                <option value="cash">صندوق (نقدی)</option>
                <option value="bank">بانک</option>
              </select>
            </label>
            {method === 'bank' && (
              <label className="acc-inline-field">
                حساب بانکی
                <select value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
                  <option value="">— انتخاب —</option>
                  {banks.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </div>
      }
    >
      <Note msg={msg} />
      <SectionCard
        icon={Scale}
        title={kind === 'receivable' ? 'طلب‌های باز' : 'بدهی‌های باز'}
        description={`${faInt(rows.length)} طرف حساب`}
        actions={
          <button type="button" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw size={13} /> بازخوانی
          </button>
        }
      >
        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={rows.length === 0}
          emptyText={kind === 'receivable' ? 'طلبِ بازی نیست.' : 'بدهیِ بازی نیست.'}
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>طرف حساب</th>
                  <th>جاری</th>
                  <th>۳۱ تا ۶۰</th>
                  <th>۶۱ تا ۹۰</th>
                  <th>بیش از ۹۰</th>
                  <th>مانده</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.contact_id}>
                    <td className="card-title" data-label="طرف حساب">{r.contact_name}</td>
                    <td className="num" data-label="جاری">{fa(r.current)}</td>
                    <td className="num" data-label="۳۱ تا ۶۰">{fa(r.d31_60)}</td>
                    <td className="num" data-label="۶۱ تا ۹۰">{fa(r.d61_90)}</td>
                    <td className="num" data-label="بیش از ۹۰">{fa(r.over_90)}</td>
                    <td className="num" data-label="مانده"><strong>{fa(r.total)}</strong></td>
                    <td className="card-actions">
                      <button type="button" onClick={() => void settle(r)} disabled={busy === r.contact_id}>
                        <CheckCircle2 size={13} /> {busy === r.contact_id ? 'در حالِ ثبت…' : 'تسویه کامل'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ ۱۲) صندوق ═══════════════════

/**
 * صندوقِ نقدی: چه مقدار پولِ نقد در دستِ ماست و از کجا آمده.
 *
 * صندوق حسابِ جداگانه‌ای در چارت دارد (نقشِ `cash`)؛ این صفحه گردشِ نقدیِ همان را از
 * رسیدها و اعلامیه‌های نقدی می‌سازد. ثبتِ تازه از راهِ «رسید دریافت»/«اعلامیه پرداخت»
 * انجام می‌شود، نه این‌جا — تا یک عملیات دو دروازه نداشته باشد.
 */
export function CashBoxPage({ token, onNavigate }: { token: string; onNavigate: (page: PageKey) => void }) {
  const data = useAsync(() => fetchTreasuryTransactions(token), [token])

  const cash = useMemo(() => (data.data ?? []).filter((t) => t.method === 'cash'), [data.data])
  const inflow = cash.filter((t) => t.type === 'receipt').reduce((s, t) => s + Number(t.amount), 0)
  const outflow = cash.filter((t) => t.type === 'payment').reduce((s, t) => s + Number(t.amount), 0)
  const pg = usePagination(cash, 12)

  return (
    <OpsPage
      icon={PiggyBank}
      title="صندوق"
      description="گردشِ پولِ نقد: هر دریافت و پرداختی که با روشِ «صندوق» ثبت شده."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<ArrowDownToLine size={14} />} label="دریافتِ نقدی" value={fa(inflow)} tone="in" />
            <Metric icon={<ArrowUpFromLine size={14} />} label="پرداختِ نقدی" value={fa(outflow)} tone="out" />
            <Metric
              icon={<PiggyBank size={14} />}
              label="ماندهٔ صندوق"
              value={fa(inflow - outflow)}
              tone={inflow - outflow < 0 ? 'out' : 'in'}
              hint="از گردشِ ثبت‌شده"
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Wallet}
        title="گردشِ صندوق"
        description={`${faInt(cash.length)} تراکنشِ نقدی`}
        actions={
          <button type="button" onClick={() => onNavigate('receiptvoucher')}>
            <Receipt size={13} /> ثبتِ دریافت
          </button>
        }
      >
        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={cash.length === 0}
          emptyText="تراکنشِ نقدی ثبت نشده. از «رسید دریافت» یا «اعلامیه پرداخت» با روشِ «صندوق» شروع کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>نوع</th>
                  <th>طرف حساب</th>
                  <th>شرح</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((t) => (
                  <tr key={t.id}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                    <td data-label="نوع">
                      <span className={`status-badge ${t.type === 'receipt' ? 'tone-success' : 'tone-warning'}`}>
                        {t.type === 'receipt' ? 'دریافت' : 'پرداخت'}
                      </span>
                    </td>
                    <td className="card-wide" data-label="طرف حساب">{t.contact_name}</td>
                    <td className="card-wide" data-label="شرح">{t.description || '—'}</td>
                    <td className="num" data-label="مبلغ">{fa(t.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ ۱۶ و ۱۷) تنخواه‌دار / صورت هزینه تنخواه ═══════════════════

/** شارژِ تنخواه: پول از صندوق یا بانک به دستِ تنخواه‌دار می‌رود. */
export function PettyHolderPage({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const postable = accounts.filter((a) => !a.is_group)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [date, setDate] = useState(todayIso())
  const [amount, setAmount] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [description, setDescription] = useState('')

  const data = useAsync(
    async () => {
      const [balance, rows] = await Promise.all([
        fetchPettyCashBalance(token),
        fetchPettyCashTransactions(token),
      ])
      return { balance, rows }
    },
    [token, reloadKey],
  )
  const charges = useMemo(() => (data.data?.rows ?? []).filter((r) => r.type === 'charge'), [data.data])
  const pg = usePagination(charges, 10)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!sourceId) {
      setMsg({ text: 'حسابِ تأمینِ وجه را انتخاب کنید (صندوق یا بانک).', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      await createPettyCashCharge(token, {
        transaction_date: date,
        amount: Number(amount || 0),
        source_account_id: sourceId,
        description,
      })
      setMsg({ text: 'تنخواه شارژ شد.', kind: 'ok' })
      setAmount('')
      setDescription('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Wallet}
      title="تنخواه دار"
      description="شارژِ تنخواه‌گردان و ماندهٔ در اختیارِ تنخواه‌دار."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric
              icon={<Wallet size={14} />}
              label="ماندهٔ تنخواه"
              value={fa(data.data?.balance.balance ?? 0)}
              tone="in"
              hint="در اختیارِ تنخواه‌دار"
            />
            <Metric icon={<ArrowDownToLine size={14} />} label="شمارِ شارژها" value={faInt(charges.length)} />
          </div>
        </div>
      }
    >
      <Note msg={msg} />
      <div className="workspace-split">
        <SectionCard icon={Wallet} title="شارژِ تنخواه" description="پول از صندوق یا بانک به تنخواه‌دار داده می‌شود.">
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              تاریخ
              <JalaliDatePicker value={date} onChange={setDate} />
            </label>
            <label>
              مبلغ (ریال)
              <NumberInput value={amount} onChange={setAmount} />
            </label>
            <label>
              تأمین از حسابِ
              <select value={sourceId} onChange={(e) => setSourceId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {postable.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-wide">
              شرح
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}>
                <Save size={14} /> ثبتِ شارژ
              </button>
            </div>
          </form>
        </SectionCard>

        <SectionCard icon={Landmark} title="شارژهای ثبت‌شده" description={`${faInt(charges.length)} شارژ`}>
          <AsyncBlock
            loading={data.loading}
            error={data.error}
            empty={charges.length === 0}
            emptyText="هنوز تنخواهی شارژ نشده."
          >
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>تاریخ</th>
                    <th>شرح</th>
                    <th>مبلغ</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="تاریخ">{formatJalali(r.transaction_date)}</td>
                      <td className="card-wide" data-label="شرح">{r.description || '—'}</td>
                      <td className="money-cell" data-label="مبلغ">{fa(r.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          </AsyncBlock>
        </SectionCard>
      </div>
    </OpsPage>
  )
}

/** صورتِ هزینه: تنخواه‌دار خرج کرده و حالا فاکتورهایش را ثبت می‌کند. */
export function PettyExpensePage({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const expenseAccounts = accounts.filter((a) => !a.is_group && a.type === 'expense')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [date, setDate] = useState(todayIso())
  const [amount, setAmount] = useState('')
  const [expenseId, setExpenseId] = useState('')
  const [description, setDescription] = useState('')

  const data = useAsync(
    async () => {
      const [balance, rows] = await Promise.all([
        fetchPettyCashBalance(token),
        fetchPettyCashTransactions(token),
      ])
      return { balance, rows }
    },
    [token, reloadKey],
  )
  const expenses = useMemo(() => (data.data?.rows ?? []).filter((r) => r.type === 'expense'), [data.data])
  const spent = expenses.reduce((s, r) => s + Number(r.amount), 0)
  const pg = usePagination(expenses, 10)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!expenseId) {
      setMsg({ text: 'حسابِ هزینه را انتخاب کنید.', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      await createPettyCashExpense(token, {
        transaction_date: date,
        amount: Number(amount || 0),
        expense_account_id: expenseId,
        description,
      })
      setMsg({ text: 'هزینهٔ تنخواه ثبت شد.', kind: 'ok' })
      setAmount('')
      setDescription('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Receipt}
      title="صورت هزینه تنخواه"
      description="هزینه‌هایی که تنخواه‌دار کرده است؛ هر ردیف از ماندهٔ تنخواه کم و به حسابِ هزینه‌ی خودش برده می‌شود."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Wallet size={14} />} label="ماندهٔ تنخواه" value={fa(data.data?.balance.balance ?? 0)} tone="in" />
            <Metric icon={<ArrowUpFromLine size={14} />} label="جمعِ هزینه‌ها" value={fa(spent)} tone="out" />
            <Metric icon={<Receipt size={14} />} label="شمارِ ردیف‌ها" value={faInt(expenses.length)} />
          </div>
        </div>
      }
    >
      <Note msg={msg} />
      <div className="workspace-split">
        <SectionCard icon={Receipt} title="ثبتِ هزینه" description="هر قلم را به حسابِ هزینه‌ی خودش ببرید.">
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              تاریخ
              <JalaliDatePicker value={date} onChange={setDate} />
            </label>
            <label>
              مبلغ (ریال)
              <NumberInput value={amount} onChange={setAmount} />
            </label>
            <label>
              بابتِ حسابِ هزینه
              <select value={expenseId} onChange={(e) => setExpenseId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {expenseAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-wide">
              شرح
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}>
                <Save size={14} /> ثبتِ هزینه
              </button>
            </div>
          </form>
        </SectionCard>

        <SectionCard icon={Receipt} title="هزینه‌های ثبت‌شده" description={`${faInt(expenses.length)} ردیف`}>
          <AsyncBlock
            loading={data.loading}
            error={data.error}
            empty={expenses.length === 0}
            emptyText="هنوز هزینه‌ای از تنخواه ثبت نشده."
          >
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>تاریخ</th>
                    <th>شرح</th>
                    <th>مبلغ</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="تاریخ">{formatJalali(r.transaction_date)}</td>
                      <td className="card-wide" data-label="شرح">{r.description || '—'}</td>
                      <td className="money-cell" data-label="مبلغ">{fa(r.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          </AsyncBlock>
        </SectionCard>
      </div>
    </OpsPage>
  )
}

// ═══════════════════ فهرست: دریافت‌ها و پرداخت‌ها ═══════════════════

/**
 * دفترِ کاملِ رسیدها و اعلامیه‌ها — همان فهرستی که پیش‌تر تبِ «دریافت و پرداخت» در
 * ماژولِ اشخاص نشان می‌داد. آن‌جا داده‌ی این ماژول در ماژولِ دیگری زندگی می‌کرد.
 */
export function TreasuryLedgerPage({ token }: { token: string }) {
  const [kind, setKind] = useState<'all' | 'receipt' | 'payment'>('all')
  const [q, setQ] = useState('')
  const data = useAsync(() => fetchTreasuryTransactions(token), [token])

  const rows = useMemo(() => {
    const term = q.trim()
    return (data.data ?? []).filter((t) => {
      if (kind !== 'all' && t.type !== kind) return false
      if (!term) return true
      return t.contact_name.includes(term) || (t.description || '').includes(term)
    })
  }, [data.data, kind, q])
  const pg = usePagination(rows, 15, `${kind}|${q}`)

  const inflow = rows.filter((t) => t.type === 'receipt').reduce((s, t) => s + Number(t.amount), 0)
  const outflow = rows.filter((t) => t.type === 'payment').reduce((s, t) => s + Number(t.amount), 0)

  return (
    <OpsPage
      icon={HandCoins}
      title="دریافت‌ها و پرداخت‌ها"
      description="دفترِ کاملِ رسیدها و اعلامیه‌ها — هر ردیف یک سندِ حسابداری دارد."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<ArrowDownToLine size={14} />} label="جمعِ دریافت" value={fa(inflow)} tone="in" />
            <Metric icon={<ArrowUpFromLine size={14} />} label="جمعِ پرداخت" value={fa(outflow)} tone="out" />
            <Metric icon={<Scale size={14} />} label="خالص" value={fa(inflow - outflow)} tone={inflow - outflow < 0 ? 'out' : 'in'} />
          </div>
        </div>
      }
    >
      <SectionCard icon={HandCoins} title="تراکنش‌ها" description={`${faInt(rows.length)} ردیف`}>
        <div className="acc-filters">
          <label className="acc-search">
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="جست‌وجو: نامِ طرف حساب یا شرح"
            />
          </label>
          <label>
            نوع
            <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
              <option value="all">همه</option>
              <option value="receipt">دریافت</option>
              <option value="payment">پرداخت</option>
            </select>
          </label>
        </div>

        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={rows.length === 0}
          emptyText="تراکنشی با این شرایط نیست."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>نوع</th>
                  <th>طرف حساب</th>
                  <th>روش</th>
                  <th>شرح</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((t) => (
                  <tr key={t.id}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                    <td data-label="نوع">
                      <span className={`status-badge ${t.type === 'receipt' ? 'tone-success' : 'tone-warning'}`}>
                        {t.type === 'receipt' ? 'دریافت' : 'پرداخت'}
                      </span>
                    </td>
                    <td className="card-wide" data-label="طرف حساب">{t.contact_name}</td>
                    <td data-label="روش">{t.method === 'bank' ? 'بانک' : 'صندوق'}</td>
                    <td className="card-wide" data-label="شرح">{t.description || '—'}</td>
                    <td className="num" data-label="مبلغ">{fa(t.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
