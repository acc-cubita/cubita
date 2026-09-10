import { Fragment, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BookMarked,
  CheckCircle2,
  Landmark,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  ScrollText,
  Share2,
  Search,
  Trash2,
  Undo2,
} from 'lucide-react'
import {
  createCheckDirect,
  createCheckbook,
  deleteCheckbook,
  fetchBankAccountsLive,
  fetchCheckbookLeaves,
  fetchCheckbooks,
  fetchChecks,
  fetchContacts,
  fetchNextCheckNumber,
  setCheckbookActive,
  updateCheckStatus,
  updateCheckbook,
  type CheckRecord,
  type CheckbookLeaf,
  type CheckbookRecord,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, toFaDigits, todayIso } from '../../lib/jalali'
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'

/**
 * عملیاتِ چکِ ماژولِ «دریافت و پرداخت».
 *
 * **چرا چهار صفحه‌ی جدا و نه یک فهرستِ چک با دکمه‌های همه‌کاره:** پیش‌تر یک جدولِ واحد
 * بود که هر ردیفش بسته به وضعیت، دکمه‌های متفاوتی نشان می‌داد. کاربر باید کلِ دفتر را
 * می‌گشت تا کارِ امروزش را پیدا کند. حالا هر صفحه از منو دقیقاً همان دسته‌ای را
 * می‌آورد که کارِ آن عملیات است: چکِ نزدِ ما برای واگذاری، چکِ نزدِ بانک برای وصول،
 * چکِ صادرشده برای کسر، و جست‌وجو برای وقتی که دنبالِ یک برگِ مشخصی.
 */

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

export const CHECK_STATUS_LABEL: Record<string, string> = {
  in_hand: 'نزدِ ما',
  deposited: 'واگذارشده به بانک',
  cleared: 'وصول‌شده',
  bounced: 'برگشتی',
  endorsed: 'خرج‌شده',
  issued: 'صادرشده',
  returned: 'مسترد شده',
}

const CHECK_STATUS_TONE: Record<string, string> = {
  in_hand: '',
  deposited: 'tone-warning',
  cleared: 'tone-success',
  bounced: 'tone-danger',
  endorsed: 'tone-success',
  issued: 'tone-warning',
  returned: 'tone-danger',
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className={`status-badge ${CHECK_STATUS_TONE[status] ?? ''}`}>
      {CHECK_STATUS_LABEL[status] ?? status}
    </span>
  )
}

/** روزهای مانده تا سررسید — منفی یعنی گذشته. */
function daysToDue(due: string): number {
  return Math.ceil((new Date(due).getTime() - Date.now()) / 86_400_000)
}

function DueChip({ due }: { due: string }) {
  const days = daysToDue(due)
  if (days < 0) return <span className="status-badge tone-danger">{toFaDigits(Math.abs(days))} روز گذشته</span>
  if (days <= 7) return <span className="status-badge tone-warning">{toFaDigits(days)} روز مانده</span>
  return <span className="muted">{toFaDigits(days)} روز مانده</span>
}

// ═══════════════════ اسکلتِ مشترکِ صفحه‌های کنشِ چک ═══════════════════

type Action = { key: string; label: string; icon: typeof CheckCircle2; needsBank?: boolean; tone?: 'danger' }

/**
 * جدولِ چک با کنش‌های وضعیت. هر صفحه فقط می‌گوید کدام چک‌ها را می‌خواهد و چه کنشی
 * روی آن‌ها ممکن است — بقیه‌ی رفتار (بارگذاری، انتخاب بانک، پیام) این‌جا یک‌بار است.
 */
function CheckActionTable({
  token,
  rows,
  actions,
  onDone,
  loading,
  error,
  emptyText,
}: {
  token: string
  rows: CheckRecord[]
  actions: Action[]
  onDone: (msg: Msg) => void
  loading: boolean
  error: string | null
  emptyText: string
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [bankPick, setBankPick] = useState<Record<string, string>>({})
  const banks = useAsync(() => fetchBankAccountsLive(token), [token])
  const pg = usePagination(rows, 12)

  async function run(check: CheckRecord, action: Action) {
    //: چکی که از یک دسته‌چک صادر شده، حسابش را از همان دسته دارد. پرسیدنِ دوباره
    //: هم اضافه است هم راهی برای ناسازگاری: تعهد روی یک حساب ثبت شده بود و پول
    //: می‌توانست از حسابِ دیگری کم شود. سرور هم حالا حسابِ ناهمخوان را رد می‌کند.
    const bankId = bankPick[check.id] || check.bank_account_id || ''
    if (action.needsBank && !bankId) {
      onDone({ text: 'اول حساب بانکی را انتخاب کنید.', kind: 'err' })
      return
    }
    setBusy(check.id)
    try {
      await updateCheckStatus(token, check.id, action.key, bankId || undefined)
      onDone({ text: `چکِ شماره ${check.number}: ${action.label} ثبت شد.`, kind: 'ok' })
    } catch (err) {
      onDone({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  const needsBank = actions.some((a) => a.needsBank)

  return (
    <AsyncBlock loading={loading} error={error} empty={rows.length === 0} emptyText={emptyText}>
      <div className="table-scroll">
        <table className="cards-on-mobile acc-table">
          <thead>
            <tr>
              <th>شماره</th>
              <th>طرف حساب</th>
              <th>بانک</th>
              <th>سررسید</th>
              <th>وضعیت</th>
              <th>مبلغ</th>
              {needsBank && <th>واریز به</th>}
              <th />
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((c) => (
              <tr key={c.id}>
                <td className="card-title" data-label="شماره">{toFaDigits(c.number)}</td>
                <td className="card-wide" data-label="طرف حساب">{c.contact_name || '—'}</td>
                <td data-label="بانک">{c.bank_name || '—'}</td>
                <td data-label="سررسید">
                  {formatJalali(c.due_date)} <DueChip due={c.due_date} />
                </td>
                <td data-label="وضعیت"><StatusChip status={c.status} /></td>
                <td className="num" data-label="مبلغ">{fa(c.amount)}</td>
                {needsBank && (
                  <td data-label="واریز به">
                    {c.bank_account_id ? (
                      //: حساب از خودِ چک می‌آید؛ عوض‌کردنش در همین لحظه یعنی سندِ
                      //: وصول به حسابی بخورد که تعهد آن‌جا ثبت نشده بود.
                      <span className="entity-sub">
                        {(banks.data ?? []).find((b) => b.id === c.bank_account_id)?.name ?? '—'}
                      </span>
                    ) : (
                      <select
                        value={bankPick[c.id] ?? ''}
                        onChange={(e) => setBankPick({ ...bankPick, [c.id]: e.target.value })}
                      >
                        <option value="">— انتخاب —</option>
                        {(banks.data ?? []).map((b) => (
                          <option key={b.id} value={b.id}>
                            {b.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                )}
                <td className="card-actions">
                  {actions.map((a) => {
                    const Icon = a.icon
                    return (
                      <button
                        key={a.key}
                        type="button"
                        className={a.tone === 'danger' ? 'danger' : undefined}
                        onClick={() => void run(c, a)}
                        disabled={busy === c.id}
                      >
                        <Icon size={13} /> {a.label}
                      </button>
                    )
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
      </div>
    </AsyncBlock>
  )
}

// ═══════════════════ فرمِ ثبتِ چک ═══════════════════

const EMPTY_CHECK = {
  number: '',
  bank_name: '',
  amount: '',
  issue_date: todayIso(),
  due_date: todayIso(),
  contact_id: '',
  description: '',
}

/**
 * ثبتِ برگِ تازه.
 *
 * **چرا این‌جا و نه یک عملیاتِ جدا:** ثبتِ چک کارِ مستقلی نیست؛ ادامه‌ی همان جریانی
 * است که کاربر در آن ایستاده — چکِ دریافتی وسطِ «عملیات چک دریافتنی» ثبت می‌شود و
 * چکِ صادرشده وسطِ «دسته چک»، جایی که شماره‌ی برگِ بعدی معلوم است.
 */
function CheckForm({
  token,
  type,
  checkbookId,
  suggestedNumber,
  onSaved,
}: {
  token: string
  type: 'receivable' | 'payable'
  checkbookId?: string
  suggestedNumber?: string
  onSaved: (msg: Msg) => void
}) {
  const [form, setForm] = useState({ ...EMPTY_CHECK })
  const [busy, setBusy] = useState(false)
  const contacts = useAsync(() => fetchContacts(token), [token])

  const number = form.number || suggestedNumber || ''

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!number.trim()) {
      onSaved({ text: 'شماره‌ی چک لازم است.', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      await createCheckDirect(token, {
        type,
        number: number.trim(),
        bank_name: form.bank_name,
        amount: Number(form.amount || 0),
        issue_date: form.issue_date,
        due_date: form.due_date,
        description: form.description,
        contact_id: form.contact_id || null,
        checkbook_id: checkbookId ?? null,
      })
      onSaved({
        text: type === 'receivable' ? 'چکِ دریافتی ثبت شد.' : 'چکِ صادرشده ثبت شد.',
        kind: 'ok',
      })
      setForm({ ...EMPTY_CHECK })
    } catch (err) {
      onSaved({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="invoice-form form-full" onSubmit={submit}>
      <label>
        شماره چک
        <input dir="ltr" value={number} onChange={(e) => setForm({ ...form, number: e.target.value })} required />
        {suggestedNumber && <span className="field-hint">شماره‌ی برگِ بعدیِ این دسته پیشنهاد شد.</span>}
      </label>
      <label>
        بانک
        <input value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} />
      </label>
      <label>
        مبلغ (ریال)
        <NumberInput value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} />
      </label>
      <label>
        {type === 'receivable' ? 'از طرف حساب' : 'به طرف حساب'}
        <select value={form.contact_id} onChange={(e) => setForm({ ...form, contact_id: e.target.value })}>
          <option value="">— بدون طرف حساب —</option>
          {(contacts.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        تاریخ صدور
        <JalaliDatePicker value={form.issue_date} onChange={(iso) => setForm({ ...form, issue_date: iso })} />
      </label>
      <label>
        سررسید
        <JalaliDatePicker value={form.due_date} onChange={(iso) => setForm({ ...form, due_date: iso })} />
      </label>
      <label className="form-wide">
        شرح
        <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </label>
      <div className="invoice-form-footer">
        <button type="submit" className="btn-primary" disabled={busy}>
          <Save size={14} /> {type === 'receivable' ? 'ثبتِ چکِ دریافتی' : 'صدورِ چک'}
        </button>
      </div>
    </form>
  )
}

// ═══════════════════ ۴) عملیات بانکی چک دریافتنی ═══════════════════

export function CheckReceivableOpsPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const checks = useAsync(() => fetchChecks(token), [token, reloadKey])

  const inHand = useMemo(
    () => (checks.data ?? []).filter((c) => c.type === 'receivable' && c.status === 'in_hand'),
    [checks.data],
  )
  const deposited = useMemo(
    () => (checks.data ?? []).filter((c) => c.type === 'receivable' && c.status === 'deposited'),
    [checks.data],
  )
  //: چکی که به تأمین‌کننده داده‌ایم. تا امروز هیچ صفحه‌ای نشانش نمی‌داد — بک‌اند
  //: خرج‌کردن را می‌پذیرفت ولی راهی برای رسیدن به آن در رابط نبود.
  const endorsed = useMemo(
    () => (checks.data ?? []).filter((c) => c.type === 'receivable' && c.status === 'endorsed'),
    [checks.data],
  )

  const done = (m: Msg) => {
    setMsg(m)
    if (m?.kind === 'ok') setReloadKey((k) => k + 1)
  }

  return (
    <OpsPage
      icon={ScrollText}
      title="عملیات بانکی چک دریافتنی"
      description="چکی که از مشتری گرفته‌اید: واگذاری به بانک تا وصول شود، یا خرج کردنش بابتِ بدهیِ خودتان. هر دو راهِ بازگشت دارند."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<ScrollText size={14} />} label="نزدِ ما" value={faInt(inHand.length)} hint="آماده‌ی واگذاری" />
            <Metric icon={<Landmark size={14} />} label="نزدِ بانک" value={faInt(deposited.length)} tone="out" hint="در انتظارِ وصول" />
            <Metric icon={<Share2 size={14} />} label="خرج‌شده" value={faInt(endorsed.length)} hint="نزدِ طرفِ دیگر" />
            <Metric
              icon={<CheckCircle2 size={14} />}
              label="جمعِ در جریان"
              value={fa([...inHand, ...deposited, ...endorsed].reduce((s, c) => s + Number(c.amount), 0))}
              tone="in"
            />
          </div>
        </div>
      }
    >
      <Note msg={msg} />

      <SectionCard
        icon={Plus}
        title="ثبتِ چکِ دریافتی"
        description="برگی که از مشتری گرفته‌اید؛ طلبِ او از «حساب‌های دریافتنی» به «اسنادِ دریافتنی» منتقل می‌شود."
      >
        <CheckForm token={token} type="receivable" onSaved={done} />
      </SectionCard>

      <SectionCard
        icon={ScrollText}
        title="نزدِ ما — آماده‌ی واگذاری"
        description="چک را به بانک واگذار کنید تا در سررسید وصول شود، یا همان برگ را بابتِ بدهیِ خودتان به دیگری بدهید."
        actions={
          <button type="button" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw size={13} /> بازخوانی
          </button>
        }
      >
        <CheckActionTable
          token={token}
          rows={inHand}
          loading={checks.loading}
          error={checks.error}
          emptyText="چکِ دریافتنیِ نزدِ ما نیست."
          onDone={done}
          actions={[
            { key: 'deposited', label: 'واگذاری به بانک', icon: Landmark, needsBank: true },
            { key: 'endorsed', label: 'خرج کردن', icon: Share2 },
          ]}
        />
      </SectionCard>

      <SectionCard icon={Landmark} title="نزدِ بانک — در انتظارِ وصول" description="در سررسید، وصول یا برگشت را ثبت کنید.">
        <CheckActionTable
          token={token}
          rows={deposited}
          loading={checks.loading}
          error={checks.error}
          emptyText="چکی نزدِ بانک نیست."
          onDone={done}
          actions={[
            { key: 'cleared', label: 'وصول شد', icon: CheckCircle2 },
            { key: 'bounced', label: 'برگشت خورد', icon: AlertTriangle, tone: 'danger' },
            { key: 'in_hand', label: 'بازگشت از بانک', icon: Undo2 },
          ]}
        />
      </SectionCard>

      <SectionCard
        icon={Share2}
        title="خرج‌شده‌ها — نزدِ طرفِ دیگر"
        description="برگی که بابتِ بدهیِ خودتان به کسی داده‌اید. اگر پسش بدهد، «برگشت از خرج» را ثبت کنید تا بدهیِ شما هم دوباره باز شود."
      >
        <CheckActionTable
          token={token}
          rows={endorsed}
          loading={checks.loading}
          error={checks.error}
          emptyText="چکِ خرج‌شده‌ای نیست."
          onDone={done}
          actions={[{ key: 'in_hand', label: 'برگشت از خرج', icon: Undo2 }]}
        />
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ ۶) استرداد چک ═══════════════════

export function CheckReturnPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const checks = useAsync(() => fetchChecks(token), [token, reloadKey])

  const returnable = useMemo(
    () => (checks.data ?? []).filter((c) => c.type === 'receivable' && c.status === 'in_hand'),
    [checks.data],
  )
  const returned = useMemo(() => (checks.data ?? []).filter((c) => c.status === 'returned'), [checks.data])

  const done = (m: Msg) => {
    setMsg(m)
    if (m?.kind === 'ok') setReloadKey((k) => k + 1)
  }

  return (
    <OpsPage
      icon={Undo2}
      title="استرداد چک"
      description="چکی که بدونِ وصول به صاحبش پس داده می‌شود — مثلاً وقتی معامله فسخ شده. طلبِ طرف‌حساب دوباره باز می‌شود."
    >
      <Note msg={msg} />

      <p className="hint acc-note">
        <AlertTriangle size={14} />
        استرداد با «برگشت خوردن» یکی نیست: آن‌جا بانک چک را برگشت می‌زند، این‌جا شما خودتان برگ را پس می‌دهید.
        فقط چکِ «نزدِ ما» قابلِ استرداد است. چکی که به بانک واگذار شده یا خرج شده، اول باید با
        «بازگشت از بانک» یا «برگشت از خرج» به دستِ شما برگردد — هر دو در صفحه‌ی «عملیات بانکی چک دریافتنی».
      </p>

      <SectionCard
        icon={Undo2}
        title="چک‌های قابلِ استرداد"
        description="چکِ دریافتنیِ نزدِ ما"
        actions={
          <button type="button" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw size={13} /> بازخوانی
          </button>
        }
      >
        <CheckActionTable
          token={token}
          rows={returnable}
          loading={checks.loading}
          error={checks.error}
          emptyText="چکِ قابلِ استردادی نیست."
          onDone={done}
          actions={[{ key: 'returned', label: 'استرداد به صاحبش', icon: Undo2, tone: 'danger' }]}
        />
      </SectionCard>

      <SectionCard icon={ScrollText} title="مستردشده‌ها" description={`${faInt(returned.length)} برگ`}>
        <AsyncBlock
          loading={checks.loading}
          error={checks.error}
          empty={returned.length === 0}
          emptyText="هنوز چکی مسترد نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>طرف حساب</th>
                  <th>سررسید</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {returned.map((c) => (
                  <tr key={c.id}>
                    <td className="card-title" data-label="شماره">{toFaDigits(c.number)}</td>
                    <td className="card-wide" data-label="طرف حساب">{c.contact_name || '—'}</td>
                    <td data-label="سررسید">{formatJalali(c.due_date)}</td>
                    <td className="num" data-label="مبلغ">{fa(c.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ ۷) وصول چک پرداختنی ═══════════════════

export function CheckPayableClearPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const checks = useAsync(() => fetchChecks(token), [token, reloadKey])

  const issued = useMemo(
    () => (checks.data ?? []).filter((c) => c.type === 'payable' && c.status === 'issued'),
    [checks.data],
  )
  const dueSoon = issued.filter((c) => daysToDue(c.due_date) <= 7).length

  const done = (m: Msg) => {
    setMsg(m)
    if (m?.kind === 'ok') setReloadKey((k) => k + 1)
  }

  return (
    <OpsPage
      icon={Landmark}
      title="وصول چک پرداختنی"
      description="چکی که خودتان صادر کرده‌اید و طرفِ مقابل آن را وصول کرده — کسر از حسابِ بانکی و بستنِ بدهی."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<ScrollText size={14} />} label="صادرشده و باز" value={faInt(issued.length)} />
            <Metric
              icon={<AlertTriangle size={14} />}
              label="سررسیدِ نزدیک (۷ روز)"
              value={faInt(dueSoon)}
              tone={dueSoon > 0 ? 'out' : 'plain'}
            />
            <Metric
              icon={<Landmark size={14} />}
              label="جمعِ تعهد"
              value={fa(issued.reduce((s, c) => s + Number(c.amount), 0))}
              tone="out"
            />
          </div>
        </div>
      }
    >
      <Note msg={msg} />
      <SectionCard
        icon={Landmark}
        title="چک‌های صادرشده"
        description="حسابی که پول از آن کسر می‌شود را انتخاب و وصول را ثبت کنید."
        actions={
          <button type="button" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw size={13} /> بازخوانی
          </button>
        }
      >
        <CheckActionTable
          token={token}
          rows={issued}
          loading={checks.loading}
          error={checks.error}
          emptyText="چکِ پرداختنیِ بازی نیست."
          onDone={done}
          actions={[
            { key: 'cleared', label: 'وصول شد', icon: CheckCircle2, needsBank: true },
            { key: 'bounced', label: 'برگشت خورد', icon: AlertTriangle, tone: 'danger' },
          ]}
        />
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ ۸) جستجوی چک ═══════════════════

export function CheckSearchPage({ token }: { token: string }) {
  const [q, setQ] = useState('')
  const [type, setType] = useState<'all' | 'receivable' | 'payable'>('all')
  const [status, setStatus] = useState('all')
  const checks = useAsync(() => fetchChecks(token), [token])

  const rows = useMemo(() => {
    const term = q.trim()
    return (checks.data ?? []).filter((c) => {
      if (type !== 'all' && c.type !== type) return false
      if (status !== 'all' && c.status !== status) return false
      if (!term) return true
      return (
        c.number.includes(term) ||
        (c.contact_name ?? '').includes(term) ||
        c.bank_name.includes(term) ||
        (c.description || '').includes(term)
      )
    })
  }, [checks.data, q, type, status])
  const pg = usePagination(rows, 15, `${q}|${type}|${status}`)

  return (
    <OpsPage
      icon={Search}
      title="جستجوی چک"
      description="همه‌ی چک‌ها — دریافتنی و پرداختنی، باز و بسته — با جست‌وجو روی شماره، طرف حساب، بانک و شرح."
    >
      <SectionCard icon={Search} title="نتیجه" description={`${faInt(rows.length)} برگ`}>
        <div className="acc-filters">
          <label className="acc-search">
            <Search size={14} />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="شماره چک، طرف حساب، بانک یا شرح"
            />
          </label>
          <label>
            نوع
            <select value={type} onChange={(e) => setType(e.target.value as typeof type)}>
              <option value="all">همه</option>
              <option value="receivable">دریافتنی</option>
              <option value="payable">پرداختنی</option>
            </select>
          </label>
          <label>
            وضعیت
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="all">همه</option>
              {Object.entries(CHECK_STATUS_LABEL).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <AsyncBlock
          loading={checks.loading}
          error={checks.error}
          empty={rows.length === 0}
          emptyText="چکی با این شرایط پیدا نشد."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>نوع</th>
                  <th>طرف حساب</th>
                  <th>بانک</th>
                  <th>صدور</th>
                  <th>سررسید</th>
                  <th>وضعیت</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((c) => (
                  <tr key={c.id}>
                    <td className="card-title" data-label="شماره">{toFaDigits(c.number)}</td>
                    <td data-label="نوع">{c.type === 'receivable' ? 'دریافتنی' : 'پرداختنی'}</td>
                    <td className="card-wide" data-label="طرف حساب">{c.contact_name || '—'}</td>
                    <td data-label="بانک">{c.bank_name || '—'}</td>
                    <td data-label="صدور">{formatJalali(c.issue_date)}</td>
                    <td data-label="سررسید">{formatJalali(c.due_date)}</td>
                    <td data-label="وضعیت"><StatusChip status={c.status} /></td>
                    <td className="num" data-label="مبلغ">{fa(c.amount)}</td>
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

/**
 * برگ‌های خرج‌شده‌ی یک دسته — ناوبریِ برعکسِ دسته ← برگ ← چک (§۲۳).
 *
 * بدونِ این، «۷ برگ خرج شده» عددی است که کاربر باید خودش دنبالِ معنایش بگردد؛ و
 * وقتی گاردِ «این برگ قبلاً خرج شده» بالا می‌آید، اینجا می‌بیند کجا رفته.
 */
function LeafList({
  rows,
  loading,
  error,
}: {
  rows: CheckbookLeaf[]
  loading: boolean
  error: string | null
}) {
  return (
    <AsyncBlock loading={loading} error={error} empty={rows.length === 0} emptyText="هنوز برگی از این دسته خرج نشده.">
      <div className="table-scroll">
        <table className="cards-on-mobile acc-table">
          <thead>
            <tr>
              <th>برگ</th>
              <th>تاریخ صدور</th>
              <th>سررسید</th>
              <th>در وجه</th>
              <th>مبلغ</th>
              <th>وضعیت</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((leaf) => (
              <tr key={leaf.check_id}>
                <td className="card-title" data-label="برگ"><span dir="ltr">{leaf.number}</span></td>
                <td data-label="تاریخ صدور">{formatJalali(leaf.issue_date)}</td>
                <td data-label="سررسید">{formatJalali(leaf.due_date)}</td>
                <td data-label="در وجه">{leaf.contact_name || '—'}</td>
                <td className="num" data-label="مبلغ">{fa(Number(leaf.amount))}</td>
                <td data-label="وضعیت">{CHECK_STATUS_LABEL[leaf.status] ?? leaf.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AsyncBlock>
  )
}

// ═══════════════════ ۱۵) دسته چک ═══════════════════

const EMPTY_BOOK = {
  bank_account_id: '',
  serial: '',
  first_number: '',
  last_number: '',
  issue_date: '',
  description: '',
  cheque_print_format: '',
}

export function CheckbooksPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [form, setForm] = useState({ ...EMPTY_BOOK })
  //: دسته‌ای که کاربر می‌خواهد از آن برگ صادر کند (خالی = فقط مدیریتِ دسته‌ها).
  const [issueFrom, setIssueFrom] = useState('')
  //: دسته‌ی در حالِ ویرایش. تا امروز هیچ راهی برای ویرایش نبود، پس یک غلطِ تایپی
  //: در شماره‌ی آخرین برگ تا ابد می‌ماند.
  const [editing, setEditing] = useState<CheckbookRecord | null>(null)
  //: دسته‌ای که برگ‌هایش باز شده — «۷ برگ خرج شده» بدونِ اینکه بشود دید کجا رفت،
  //: عددِ بی‌فایده‌ای است.
  const [openLeaves, setOpenLeaves] = useState('')

  const leaves = useAsync(
    () => (openLeaves ? fetchCheckbookLeaves(token, openLeaves) : Promise.resolve([])),
    [token, openLeaves, reloadKey],
  )

  const nextNumber = useAsync(
    () => (issueFrom ? fetchNextCheckNumber(token, issueFrom) : Promise.resolve({ number: '' })),
    [token, issueFrom, reloadKey],
  )

  const data = useAsync(
    async () => {
      const [books, banks] = await Promise.all([fetchCheckbooks(token), fetchBankAccountsLive(token)])
      return { books, banks }
    },
    [token, reloadKey],
  )
  const books = data.data?.books ?? []
  const banks = data.data?.banks ?? []
  const pg = usePagination(books, 10)

  const remaining = books.filter((b) => b.is_active).reduce((s, b) => s + b.remaining_count, 0)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!form.bank_account_id) {
      setMsg({ text: 'حساب بانکیِ دسته را انتخاب کنید.', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      const payload = {
        bank_account_id: form.bank_account_id,
        serial: form.serial,
        first_number: form.first_number,
        last_number: form.last_number,
        issue_date: form.issue_date || null,
        description: form.description,
        cheque_print_format: form.cheque_print_format,
      }
      if (editing) {
        //: `is_active` عمداً نیست: وضعیت فقط با دکمه‌ی صریحِ باز/بستن عوض می‌شود.
        //: PATCH حالا `exclude_unset` است، پس فیلدِ نفرستاده دست نمی‌خورد.
        await updateCheckbook(token, editing.id, payload)
        setMsg({ text: 'دسته‌چک ویرایش شد.', kind: 'ok' })
      } else {
        await createCheckbook(token, payload)
        setMsg({ text: 'دسته‌چک ثبت شد.', kind: 'ok' })
      }
      setEditing(null)
      setForm({ ...EMPTY_BOOK })
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  function startEdit(book: CheckbookRecord) {
    setEditing(book)
    setForm({
      bank_account_id: book.bank_account_id,
      serial: book.serial,
      first_number: book.first_number,
      last_number: book.last_number,
      issue_date: book.issue_date ?? '',
      description: book.description,
      cheque_print_format: book.cheque_print_format,
    })
  }

  async function toggle(id: string, isActive: boolean) {
    try {
      await setCheckbookActive(token, id, isActive)
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  async function remove(id: string) {
    if (!window.confirm('این دسته‌چک حذف شود؟')) return
    try {
      await deleteCheckbook(token, id)
      setMsg({ text: 'دسته‌چک حذف شد.', kind: 'ok' })
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  return (
    <OpsPage
      icon={BookMarked}
      title="دسته چک"
      description="دسته‌چک‌های هر حسابِ بانکی: بازه‌ی شماره‌ی برگ‌ها و اینکه چند برگ مانده."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<BookMarked size={14} />} label="دسته‌های باز" value={faInt(books.filter((b) => b.is_active).length)} />
            <Metric icon={<ScrollText size={14} />} label="برگِ مانده" value={faInt(remaining)} tone="in" hint="در دسته‌های باز" />
          </div>
        </div>
      }
    >
      <Note msg={msg} />

      <SectionCard
        icon={Plus}
        title="صدورِ چک از دسته"
        description="برگِ بعدی خودکار پیشنهاد می‌شود و چک به همین دسته وصل می‌ماند، پس شمارِ برگِ باقی‌مانده درست می‌ماند."
      >
        <label className="acc-inline-field">
          از دسته‌چکِ
          <select value={issueFrom} onChange={(e) => setIssueFrom(e.target.value)}>
            <option value="">— انتخاب دسته —</option>
            {books
              .filter((b) => b.is_active && b.remaining_count > 0)
              .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.bank_account_name} — {b.first_number} تا {b.last_number} ({b.remaining_count} برگ مانده)
                </option>
              ))}
          </select>
        </label>
        {issueFrom ? (
          <CheckForm
            token={token}
            type="payable"
            checkbookId={issueFrom}
            suggestedNumber={nextNumber.data?.number || undefined}
            onSaved={(m) => {
              setMsg(m)
              if (m?.kind === 'ok') setReloadKey((k) => k + 1)
            }}
          />
        ) : (
          <p className="hint">برای صدورِ برگ، اول دسته‌چک را انتخاب کنید.</p>
        )}
      </SectionCard>

      <div className="workspace-split">
        <SectionCard
          icon={editing ? Pencil : Plus}
          title={editing ? 'ویرایشِ دسته‌چک' : 'دسته‌چکِ تازه'}
          description={
            editing
              ? 'حساب و بازه‌ی شماره فقط تا وقتی عوض می‌شوند که هنوز برگی خرج نشده باشد.'
              : 'شماره‌ی اولین و آخرین برگ را بنویسید؛ تعداد خودکار حساب می‌شود.'
          }
          actions={
            editing ? (
              <button
                type="button"
                onClick={() => {
                  setEditing(null)
                  setForm({ ...EMPTY_BOOK })
                }}
              >
                انصراف
              </button>
            ) : undefined
          }
        >
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              حساب بانکی
              <select
                value={form.bank_account_id}
                onChange={(e) => setForm({ ...form, bank_account_id: e.target.value })}
                required
              >
                <option value="">— انتخاب —</option>
                {banks.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              سریِ دسته
              <input
                dir="ltr"
                value={form.serial}
                onChange={(e) => setForm({ ...form, serial: e.target.value })}
                placeholder="1234567890123456"
              />
              <span className="field-hint">اختیاری — سریِ صیاد یا شماره‌ی داخلیِ بانک.</span>
            </label>
            <label>
              شماره‌ی اولین برگ
              <input
                dir="ltr"
                value={form.first_number}
                onChange={(e) => setForm({ ...form, first_number: e.target.value })}
                required
              />
            </label>
            <label>
              شماره‌ی آخرین برگ
              <input
                dir="ltr"
                value={form.last_number}
                onChange={(e) => setForm({ ...form, last_number: e.target.value })}
                required
              />
            </label>
            <label>
              تاریخِ دریافتِ دسته
              <JalaliDatePicker value={form.issue_date} onChange={(iso) => setForm({ ...form, issue_date: iso })} />
            </label>
            <label>
              قالبِ چاپِ چک
              <input
                dir="ltr"
                value={form.cheque_print_format}
                onChange={(e) => setForm({ ...form, cheque_print_format: e.target.value })}
              />
              <span className="field-hint">خالی بگذارید تا از حسابِ بانکی ارث ببرد.</span>
            </label>
            <label className="form-wide">
              توضیح
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}>
                <Save size={14} /> {editing ? 'ذخیرهٔ تغییرات' : 'ثبتِ دسته‌چک'}
              </button>
            </div>
          </form>
        </SectionCard>

        <SectionCard
          icon={BookMarked}
          title="دسته‌چک‌ها"
          description={`${faInt(books.length)} دسته`}
          actions={
            <button type="button" onClick={() => setReloadKey((k) => k + 1)}>
              <RefreshCw size={13} /> بازخوانی
            </button>
          }
        >
          <AsyncBlock
            loading={data.loading}
            error={data.error}
            empty={books.length === 0}
            emptyText="هنوز دسته‌چکی ثبت نشده. با فرمِ کنار شروع کنید."
          >
            <div className="table-scroll">
              <table className="cards-on-mobile acc-table">
                <thead>
                  <tr>
                    <th>حساب</th>
                    <th>سری</th>
                    <th>از</th>
                    <th>تا</th>
                    <th>خرج‌شده</th>
                    <th>مانده</th>
                    <th>وضعیت</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((b) => (
                    <Fragment key={b.id}>
                      <tr className={b.is_active ? '' : 'acc-row--void'}>
                        <td className="card-title" data-label="حساب">{b.bank_account_name}</td>
                        <td data-label="سری"><span dir="ltr">{b.serial || '—'}</span></td>
                        <td data-label="از"><span dir="ltr">{b.first_number}</span></td>
                        <td data-label="تا"><span dir="ltr">{b.last_number}</span></td>
                        <td className="num" data-label="خرج‌شده">
                          {b.used_count > 0 ? (
                            <button
                              type="button"
                              className="link-button"
                              onClick={() => setOpenLeaves(openLeaves === b.id ? '' : b.id)}
                            >
                              {toFaDigits(b.used_count)} برگ
                            </button>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="num" data-label="مانده">
                          {toFaDigits(b.remaining_count)} از {toFaDigits(b.leaf_count)}
                        </td>
                        <td data-label="وضعیت">
                          <span className={`status-badge ${b.is_active ? 'tone-success' : ''}`}>
                            {b.is_active ? 'باز' : 'بسته'}
                          </span>
                        </td>
                        <td className="card-actions">
                          <button type="button" onClick={() => startEdit(b)}>
                            <Pencil size={13} /> ویرایش
                          </button>
                          <button type="button" onClick={() => void toggle(b.id, !b.is_active)}>
                            {b.is_active ? 'بستن' : 'بازکردن'}
                          </button>
                          {b.used_count === 0 && (
                            <button type="button" className="danger" onClick={() => void remove(b.id)}>
                              <Trash2 size={13} /> حذف
                            </button>
                          )}
                        </td>
                      </tr>
                      {openLeaves === b.id && (
                        <tr>
                          <td className="card-full" colSpan={8}>
                            <LeafList rows={leaves.data ?? []} loading={leaves.loading} error={leaves.error} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
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
