import { Fragment, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
  Landmark,
  Plus,
  RefreshCw,
  Save,
  ScrollText,
  Share2,
  Search,
  SlidersHorizontal,
  Undo2,
  Wallet,
  History,
} from 'lucide-react'
import {
  createCheckDirect,
  fetchBankAccountsLive,
  fetchCashboxes,
  fetchCheckTimeline,
  fetchCheckSummary,
  fetchCheckbooks,
  fetchChecks,
  fetchContacts,
  fetchNextCheckNumber,
  updateCheckStatus,
  type CheckEventRecord,
  type CheckRecord,
  type CheckSearchQuery,
  type CheckbookLeaf,
} from '../../api'
import type { PageKey } from '../../lib/navModel'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, toFaDigits, todayIso } from '../../lib/jalali'
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'
import { SearchSelect } from '../../components/SearchSelect'
import { FormField } from '../../components/form/FormKit'
import { Tabs } from '../../components/Tabs'
import { SelectionBar } from '../../components/XlGrid'
import { modsOf, useRowSelection } from '../../lib/rowSelection'

/**
 * «چک‌ها»ی ماژولِ «دریافت و پرداخت» — یک صفحه، چهار برگه.
 *
 * **چرا برگه‌های جدا و نه یک فهرستِ چک با دکمه‌های همه‌کاره:** پیش‌تر یک جدولِ واحد بود که هر ردیفش بسته به
 * وضعیت، دکمه‌های متفاوتی نشان می‌داد. کاربر باید کلِ دفتر را می‌گشت تا کارِ امروزش را پیدا کند. حالا هر برگه
 * دقیقاً همان دسته‌ای را می‌آورد که کارِ آن است: چکِ نزدِ ما برای واگذاری، چکِ نزدِ بانک برای وصول، چکِ صادرشده
 * برای کسر، و جست‌وجو برای وقتی که دنبالِ یک برگِ مشخصی. تا ۱۴۰۵/۰۷/۰۶ این چهار برگه چهار منوی جدا بودند.
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
  cashed: 'نقد شده',
}

const CHECK_STATUS_TONE: Record<string, string> = {
  in_hand: '',
  deposited: 'tone-warning',
  cleared: 'tone-success',
  bounced: 'tone-danger',
  endorsed: 'tone-success',
  issued: 'tone-warning',
  returned: 'tone-danger',
  cashed: 'tone-success',
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

/**
 * تاریخچه‌ی یک چک (§۳۵ §۳۶).
 *
 * **چرا نامِ عملیات کنارِ وضعیت می‌آید و نه فقط وضعیت:** «بازگشت از بانک» و
 * «برگشت از خرج» هر دو به «نزدِ ما» می‌رسند. اگر فقط وضعیت را نشان می‌دادیم،
 * تاریخچه دو رویدادِ کاملاً متفاوت را یک چیز نشان می‌داد.
 */
function CheckTimeline({ steps, loading }: { steps: CheckEventRecord[]; loading: boolean }) {
  if (loading) return <p className="muted">در حال بارگذاری…</p>
  if (steps.length === 0) {
    return (
      <p className="muted">
        رویدادی ثبت نشده. تاریخچه از مهاجرتِ ۰۱۱۰ به بعد نوشته می‌شود؛ برای چک‌های
        پیش از آن، گذرهای گذشته تاریخ و کاربرشان ثبت نشده بود و ساختنشان یعنی جعلِ سابقه.
      </p>
    )
  }
  return (
    <ol className="check-timeline">
      {steps.map((s) => (
        <li key={s.id}>
          <span className="check-timeline__when">{formatJalali(s.event_date)}</span>
          <span className="check-timeline__what">{s.operation_label}</span>
          <span className="check-timeline__where">
            {s.bank_account_name || s.cashbox_name || s.contact_name || '—'}
          </span>
          <span className="check-timeline__state">
            <StatusChip status={s.to_status} />
          </span>
          {s.operation_no ? (
            <span className="check-timeline__no">عملیات {toFaDigits(String(s.operation_no))}</span>
          ) : null}
        </li>
      ))}
    </ol>
  )
}

// ═══════════════════ اسکلتِ مشترکِ صفحه‌های کنشِ چک ═══════════════════

type Action = {
  key: string
  label: string
  icon: typeof CheckCircle2
  /** حسابِ بانکی لازم است — از خودِ چک (برگِ دسته‌چک)، وگرنه از انتخاب‌گرِ بالای جدول. */
  needsBank?: boolean
  /** «نقد کردن» به صندوق می‌رود، نه بانک — دو مسیرِ جدا. */
  needsCashbox?: boolean
  tone?: 'danger'
}

/**
 * جدولِ چک با کنش‌های وضعیت — **گریدِ اکسلیِ فهرست** (الگوی «د با کنش»ِ تمِ اکسلی؛ مرجع: کارتابل اسناد موقت).
 *
 * هر برگه فقط می‌گوید کدام چک‌ها را می‌خواهد و چه کنشی روی آن‌ها ممکن است — بقیه‌ی رفتار (بارگذاری، انتخابِ
 * بانک و صندوق، پیام، تاریخچه) این‌جا یک‌بار است. شماره‌ی ردیف انتخاب می‌کند (کلیک، Ctrl، Shift) و نوارِ انتخاب
 * جمعِ مبلغِ انتخاب‌شده‌ها را می‌گوید؛ جمعِ کلِ همین دسته در `tfoot`ِ خودِ گرید است، نه کارتِ جدا. زیرِ ۷۶۰px کارت.
 *
 * - ستونِ «وضعیت» ندارد: هر جدول یک دسته است (نزدِ ما، نزدِ بانک، …) و عنوانِ کارتش همان را می‌گوید.
 * - حساب و صندوقِ مقصد **یک‌بار بالای جدول** انتخاب می‌شوند، نه در هر ردیف: واگذاریِ یک روز معمولاً همه به یک
 *   حساب است، و دو ستونِ انتخاب‌گر جای «طرف حساب» را می‌گرفت. برگی که مقصدِ دیگری دارد؟ انتخاب را پیش از کلیک
 *   عوض کنید.
 * - شماره و کنش‌ها در قابِ باریک میخ‌اند تا با لغزشِ افقی نه برگ گم شود نه دکمه‌هایش.
 */
function CheckActionTable({
  token,
  rows,
  actions,
  onDone,
  loading,
  error,
  emptyText,
  bankLabel = 'حسابِ بانکی',
}: {
  token: string
  rows: CheckRecord[]
  actions: Action[]
  onDone: (msg: Msg) => void
  loading: boolean
  error: string | null
  emptyText: string
  /** برچسبِ انتخاب‌گرِ حساب — «واگذاری به حسابِ» یا «کسر از حسابِ». */
  bankLabel?: string
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [bankId, setBankId] = useState('')
  const [boxId, setBoxId] = useState('')
  //: تاریخچه فقط برای ردیفِ بازشده خوانده می‌شود — نه برای هر دوازده ردیفِ صفحه.
  const [openId, setOpenId] = useState<string | null>(null)
  const { selected, click, clear } = useRowSelection()
  const needsBank = actions.some((a) => a.needsBank)
  //: چکی که از دسته‌چک صادر شده حسابش را از همان دسته دارد؛ انتخاب‌گر فقط وقتی هست که برگِ بی‌حسابی در دسته باشد.
  const askBank = needsBank && rows.some((c) => !c.bank_account_id)
  const askBox = actions.some((a) => a.needsCashbox)
  const banks = useAsync(() => (needsBank ? fetchBankAccountsLive(token) : Promise.resolve([])), [token, needsBank])
  const boxes = useAsync(() => (askBox ? fetchCashboxes(token, false) : Promise.resolve([])), [token, askBox])
  const history = useAsync(
    () => (openId ? fetchCheckTimeline(token, openId) : Promise.resolve([])),
    [token, openId],
  )
  const pg = usePagination(rows, 12)
  const order = pg.pageItems.map((c) => c.id)
  //: دسته‌ی تازه (بعد از ثبتِ یک کنش) یعنی ردیف‌های دیگر؛ انتخابِ قبلی معنا ندارد.
  useEffect(() => clear(), [rows, clear])

  async function run(check: CheckRecord, action: Action) {
    //: چکی که از یک دسته‌چک صادر شده، حسابش را از همان دسته دارد. پرسیدنِ دوباره
    //: هم اضافه است هم راهی برای ناسازگاری: تعهد روی یک حساب ثبت شده بود و پول
    //: می‌توانست از حسابِ دیگری کم شود. سرور هم حالا حسابِ ناهمخوان را رد می‌کند.
    const bank = check.bank_account_id || (action.needsBank ? bankId : '')
    if (action.needsBank && !bank) {
      onDone({ text: `اول «${bankLabel}» را بالای جدول انتخاب کنید.`, kind: 'err' })
      return
    }
    setBusy(check.id)
    try {
      await updateCheckStatus(token, check.id, action.key, bank || undefined, {
        cashbox_id: action.needsCashbox ? boxId || null : null,
      })
      onDone({ text: `چکِ شماره ${check.number}: ${action.label} ثبت شد.`, kind: 'ok' })
    } catch (err) {
      onDone({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  const total = rows.reduce((s, c) => s + Number(c.amount), 0)
  const picked = rows.filter((c) => selected.has(c.id))
  const pickedSum = picked.reduce((s, c) => s + Number(c.amount), 0)

  return (
    <AsyncBlock loading={loading} error={error} empty={rows.length === 0} emptyText={emptyText}>
      <div className="jg">
        {(askBank || askBox) && (
          <div className="ck-dest">
            {askBank && (
              <label className="acc-inline-field">
                {bankLabel}
                <SearchSelect value={bankId} onChange={(e) => setBankId(e.target.value)}>
                  <option value="">— انتخاب حساب —</option>
                  {(banks.data ?? []).map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </SearchSelect>
              </label>
            )}
            {askBox && (
              <label className="acc-inline-field">
                نقد به صندوقِ
                <SearchSelect value={boxId} onChange={(e) => setBoxId(e.target.value)}>
                  <option value="">— صندوقِ پیش‌فرض —</option>
                  {(boxes.data ?? []).map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </SearchSelect>
              </label>
            )}
          </div>
        )}
        <div className="table-scroll ef-table-wrap jg-wrap ck-wrap">
          <table className={`cards-on-mobile ef-table xl-grid ck-sheet ck-sheet--a${actions.length}`}>
            <colgroup>
              <col className="ck-c-rowhead" />
              <col className="ck-c-number" />
              <col />
              <col className="ck-c-bank" />
              <col className="ck-c-due" />
              <col className="ck-c-amount" />
              <col className="ck-c-actions" />
            </colgroup>
            <thead>
              <tr>
                <th className="xl-rowhead card-hide ck-pin-head">ردیف</th>
                <th className="ck-pin-lead">شماره</th>
                <th>طرف حساب</th>
                <th>بانک</th>
                <th>سررسید</th>
                <th className="num">مبلغ</th>
                <th className="ck-pin-end" aria-label="کنش‌ها" />
              </tr>
            </thead>
            <tbody>
              {pg.pageItems.map((c, i) => {
                const on = selected.has(c.id)
                const open = openId === c.id
                return (
                  <Fragment key={c.id}>
                    <tr className={on ? 'is-selected' : undefined} aria-selected={on}>
                      <td className="xl-rowhead card-hide ck-pin-head">
                        <button
                          type="button"
                          tabIndex={-1}
                          className="xl-rowhead-btn"
                          aria-pressed={on}
                          aria-label={`انتخابِ چکِ ${toFaDigits(c.number)}`}
                          onClick={(e) => click(order, c.id, modsOf(e))}
                        >
                          {faInt(pg.page * 12 + i + 1)}
                        </button>
                      </td>
                      <td className="card-title ck-pin-lead" data-label="شماره">
                        <span dir="ltr">{toFaDigits(c.number)}</span>
                        {c.sayad_id ? <div className="entity-sub" dir="ltr">{toFaDigits(c.sayad_id)}</div> : null}
                      </td>
                      <td className="card-wide" data-label="طرف حساب" title={c.contact_name || undefined}>
                        {c.contact_name || '—'}
                      </td>
                      <td data-label="بانک">{c.bank_name || '—'}</td>
                      <td data-label="سررسید">
                        {formatJalali(c.due_date)} <DueChip due={c.due_date} />
                      </td>
                      <td className="num" data-label="مبلغ">{fa(c.amount)}</td>
                      <td className="card-actions ck-actions ck-pin-end">
                        {actions.map((a) => {
                          const Icon = a.icon
                          return (
                            <button
                              key={a.key}
                              type="button"
                              className={`ck-act${a.tone === 'danger' ? ' danger' : ''}`}
                              onClick={() => void run(c, a)}
                              disabled={busy === c.id}
                            >
                              <Icon size={13} aria-hidden="true" /> {a.label}
                            </button>
                          )
                        })}
                        {/*
                          وضعیتِ فعلی به‌تنهایی توضیح نمی‌دهد چک چطور به اینجا رسیده.
                          «واخواست‌شده» وقتی معنی کامل دارد که بشود دید کِی و به کدام
                          بانک واگذار شده بود. در گرید فقط نشانه است (جا برای کنش‌ها)؛ در کارت برچسب هم دارد.
                        */}
                        <button
                          type="button"
                          className="ck-act ck-act--ghost ck-act--icon"
                          aria-expanded={open}
                          aria-label={open ? 'بستنِ تاریخچه' : 'تاریخچه'}
                          title={open ? 'بستنِ تاریخچه' : 'تاریخچه'}
                          onClick={() => setOpenId(open ? null : c.id)}
                        >
                          <History size={13} aria-hidden="true" />
                          <span className="ck-act-text">{open ? 'بستن' : 'تاریخچه'}</span>
                        </button>
                      </td>
                    </tr>
                    {open && (
                      <tr className="ck-trail-row">
                        <td className="card-full" colSpan={7}>
                          <CheckTimeline steps={history.data ?? []} loading={history.loading} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
            <tfoot>
              <tr>
                <td className="xl-rowhead card-hide ck-pin-head" />
                <td className="card-title ck-pin-lead">جمعِ {faInt(rows.length)} برگ</td>
                <td className="card-hide" colSpan={3} />
                <td className="num" data-label="جمع مبلغ">{fa(total)}</td>
                <td className="card-hide ck-pin-end" />
              </tr>
            </tfoot>
          </table>
        </div>
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        {picked.length > 0 && (
          <SelectionBar count={picked.length} unit="چک" onClear={clear}>
            <span>
              جمع مبلغ <b className="num">{fa(pickedSum)}</b>
            </span>
          </SelectionBar>
        )}
      </div>
    </AsyncBlock>
  )
}

// ═══════════════════ فرمِ ثبتِ چک ═══════════════════

const EMPTY_CHECK = {
  number: '',
  back_number: '',
  sayad_id: '',
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
 * است که کاربر در آن ایستاده — چکِ دریافتی بالای برگه‌ی «چک‌های دریافتنی» ثبت می‌شود و
 * چکِ صادرشده بالای «چک‌های پرداختنی»، از دسته‌ای که شماره‌ی برگِ بعدی‌اش معلوم است.
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
        back_number: form.back_number.trim(),
        sayad_id: form.sayad_id.trim(),
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
      <FormField
        label="شماره چک"
        required
        message={suggestedNumber ? 'شماره‌ی برگِ بعدیِ این دسته پیشنهاد شد.' : null}
      >
        {(id) => (
          <input id={id} dir="ltr" value={number} onChange={(e) => setForm({ ...form, number: e.target.value })} required />
        )}
      </FormField>
      <label>
        بانک
        <input value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} />
      </label>
      <FormField label="کد صیادی" tip="۱۶ رقمِ روی برگ. یکتاییِ واقعیِ چک همین است — شماره‌ی چک بینِ بانک‌ها تکرار می‌شود.">
        {(id) => (
          <input
            id={id}
            dir="ltr"
            inputMode="numeric"
            value={form.sayad_id}
            onChange={(e) => setForm({ ...form, sayad_id: e.target.value })}
          />
        )}
      </FormField>
      <label>
        پشت نمره
        <input
          dir="ltr"
          value={form.back_number}
          onChange={(e) => setForm({ ...form, back_number: e.target.value })}
        />
      </label>
      <label>
        مبلغ (ریال)
        <NumberInput value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} />
      </label>
      <label>
        {type === 'receivable' ? 'از طرف حساب' : 'به طرف حساب'}
        <SearchSelect value={form.contact_id} onChange={(e) => setForm({ ...form, contact_id: e.target.value })}>
          <option value="">— بدون طرف حساب —</option>
          {(contacts.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </SearchSelect>
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

// ═══════════════════ «چک‌ها» — چهار برگه در یک صفحه ═══════════════════

/**
 * «چک‌ها» — همه‌ی کارِ چک در یک صفحه با چهار برگه (مرحله‌ی ۲ِ مرتب‌سازیِ زیرمنوها، ۱۴۰۵/۰۷/۰۶).
 *
 * پیش از این چهار منوی جدا بود («چک دریافتنی»، «وصول چک پرداختنی»، «استرداد چک»، «جست‌وجوی چک») و صدورِ چک هم
 * زیرِ «دسته چک» پنهان بود. حالا یک ردیف در منو و چهار برگه — ولی **هر برگه همان دسته‌ی کاری را می‌آورد که صفحه‌ی
 * قبلی می‌آورد** (نزدِ ما، نزدِ بانک، صادرشده، …): جدولِ همه‌کاره‌ای که هر ردیفش بسته به وضعیت دکمه‌ی دیگری دارد
 * همان چیزی بود که این چیدمان برای حذفش ساخته شده بود.
 */
export function ChecksPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate: (page: PageKey, section?: string | null) => void
}) {
  return (
    <OpsPage
      icon={ScrollText}
      title="چک‌ها"
      description="چکِ دریافتی از ثبت تا وصول، چکِ خودتان از صدور تا کسر از بانک، استرداد، و ردیابیِ هر برگ — هر کار در برگه‌ی خودش."
    >
      <Tabs
        syncPage="checks"
        tabs={[
          { key: 'receivable', label: 'چک‌های دریافتنی', icon: ScrollText, content: <ReceivableTab token={token} /> },
          { key: 'payable', label: 'چک‌های پرداختنی', icon: BadgeCheck, content: <PayableTab token={token} /> },
          { key: 'return', label: 'استرداد چک', icon: Undo2, content: <ReturnTab token={token} /> },
          { key: 'search', label: 'جست‌وجوی چک', icon: Search, content: <SearchTab token={token} onNavigate={onNavigate} /> },
        ]}
      />
    </OpsPage>
  )
}

/** بارگذاری و «پیامِ بعد از کنش» — مشترکِ برگه‌هایی که با `CheckActionTable` کار می‌کنند. */
function useChecks(token: string) {
  const [msg, setMsg] = useState<Msg>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const checks = useAsync(() => fetchChecks(token), [token, reloadKey])
  const done = (m: Msg) => {
    setMsg(m)
    if (m?.kind === 'ok') setReloadKey((k) => k + 1)
  }
  const reload = () => setReloadKey((k) => k + 1)
  return { checks, msg, done, reload }
}

const reloadButton = (reload: () => void) => (
  <button type="button" onClick={reload}>
    <RefreshCw size={13} /> بازخوانی
  </button>
)

// ── دریافتنی ──

function ReceivableTab({ token }: { token: string }) {
  const { checks, msg, done, reload } = useChecks(token)
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

  return (
    <>
      <section className="cc-head">
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
      </section>
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
        actions={reloadButton(reload)}
      >
        <CheckActionTable
          token={token}
          rows={inHand}
          loading={checks.loading}
          error={checks.error}
          emptyText="چکِ دریافتنیِ نزدِ ما نیست."
          onDone={done}
          bankLabel="واگذاری به حسابِ"
          actions={[
            { key: 'deposited', label: 'واگذاری به بانک', icon: Landmark, needsBank: true },
            //: نقد کردن با وصولِ بانکی یکی نیست (§۱۹): پول به صندوق می‌رود، نه
            //: به حسابِ بانکی. تا امروز این راه اصلاً وجود نداشت و کاربر مجبور
            //: بود «وصول» ثبت کند — که پول را به بانکی می‌برد که چیزی نگرفته بود.
            { key: 'cashed', label: 'نقد کردن', icon: Wallet, needsCashbox: true },
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
    </>
  )
}

// ── پرداختنی: صدور از دسته و وصول ──

function PayableTab({ token }: { token: string }) {
  const { checks, msg, done, reload } = useChecks(token)
  //: دسته‌ای که کاربر می‌خواهد از آن برگ صادر کند. تا ۱۴۰۵/۰۷/۰۶ این کار زیرِ تعریفِ «دسته چک» بود — عملیاتی
  //: لای تعریف؛ حالا کنارِ همان چک‌هایی است که صادر می‌کند.
  const [issueFrom, setIssueFrom] = useState('')
  const books = useAsync(() => fetchCheckbooks(token), [token, checks.data])
  const nextNumber = useAsync(
    () => (issueFrom ? fetchNextCheckNumber(token, issueFrom) : Promise.resolve({ number: '' })),
    [token, issueFrom, checks.data],
  )
  const issued = useMemo(
    () => (checks.data ?? []).filter((c) => c.type === 'payable' && c.status === 'issued'),
    [checks.data],
  )
  const dueSoon = issued.filter((c) => daysToDue(c.due_date) <= 7).length
  const open = (books.data ?? []).filter((b) => b.is_active && b.remaining_count > 0)

  return (
    <>
      <section className="cc-head">
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
      </section>
      <Note msg={msg} />

      <SectionCard
        icon={Plus}
        title="صدورِ چک از دسته"
        description="برگِ بعدیِ دسته خودکار پیشنهاد می‌شود و چک به همان دسته وصل می‌ماند، پس شمارِ برگِ باقی‌مانده درست می‌ماند. پرداختی که چند ابزار دارد (نقد + چک + …) از «اعلامیه پرداخت» ثبت می‌شود."
      >
        <label className="acc-inline-field">
          از دسته‌چکِ
          <SearchSelect value={issueFrom} onChange={(e) => setIssueFrom(e.target.value)}>
            <option value="">— انتخاب دسته —</option>
            {open.map((b) => (
              <option key={b.id} value={b.id}>
                {b.bank_account_name} — {b.first_number} تا {b.last_number} ({faInt(b.remaining_count)} برگ مانده)
              </option>
            ))}
          </SearchSelect>
        </label>
        {issueFrom ? (
          <CheckForm
            token={token}
            type="payable"
            checkbookId={issueFrom}
            suggestedNumber={nextNumber.data?.number || undefined}
            onSaved={done}
          />
        ) : (
          <p className="hint">
            {open.length > 0
              ? 'برای صدورِ برگ، اول دسته‌چک را انتخاب کنید.'
              : 'دسته‌چکِ بازی نیست — در «حساب‌های نقد و بانک ← دسته‌چک‌ها» یک دسته تعریف کنید.'}
          </p>
        )}
      </SectionCard>

      <SectionCard
        icon={Landmark}
        title="صادرشده‌ها — در انتظارِ وصول"
        description="چکی که طرفِ مقابل وصول کرده: کسر از حسابِ بانکی و بستنِ بدهی."
        actions={reloadButton(reload)}
      >
        <CheckActionTable
          token={token}
          rows={issued}
          loading={checks.loading}
          error={checks.error}
          emptyText="چکِ پرداختنیِ بازی نیست."
          onDone={done}
          bankLabel="چکِ بی‌دسته از حسابِ"
          actions={[
            { key: 'cleared', label: 'وصول شد', icon: CheckCircle2, needsBank: true },
            { key: 'bounced', label: 'برگشت خورد', icon: AlertTriangle, tone: 'danger' },
          ]}
        />
      </SectionCard>
    </>
  )
}

// ── استرداد ──

function ReturnTab({ token }: { token: string }) {
  const { checks, msg, done, reload } = useChecks(token)
  const returnable = useMemo(
    () => (checks.data ?? []).filter((c) => c.type === 'receivable' && c.status === 'in_hand'),
    [checks.data],
  )
  //: چکِ پرداختنیِ صادرشده‌ای که هنوز وصول نشده — تنها حالتی که استردادش معنا دارد.
  const payableReturnable = useMemo(
    () => (checks.data ?? []).filter((c) => c.type === 'payable' && c.status === 'issued'),
    [checks.data],
  )
  const returned = useMemo(() => (checks.data ?? []).filter((c) => c.status === 'returned'), [checks.data])

  return (
    <>
      <Note msg={msg} />
      <p className="hint acc-note">
        <AlertTriangle size={14} />
        استرداد با «برگشت خوردن» یکی نیست: آن‌جا بانک چک را برگشت می‌زند، این‌جا برگ سالم پس داده می‌شود. چکِ دریافتنی
        فقط وقتی «نزدِ ما»ست قابلِ استرداد است؛ چکی که به بانک واگذار شده یا خرج شده، اول باید با «بازگشت از بانک» یا
        «برگشت از خرج» به دستِ شما برگردد — هر دو در برگه‌ی «چک‌های دریافتنی».
      </p>

      <SectionCard icon={Undo2} title="چک‌های قابلِ استرداد" description="چکِ دریافتنیِ نزدِ ما" actions={reloadButton(reload)}>
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

      {/*
        نوعِ دومِ استرداد (§۳۱): چکی که *ما* صادر کرده‌ایم و پیش از وصول به ما
        برگشته. تا امروز راهی برای ثبتش نبود و کاربر مجبور بود «برگشت خورد» بزند
        — که واخواست است و معنایش برای سابقه‌ی طرف‌حساب کاملاً فرق دارد.
      */}
      <SectionCard icon={Undo2} title="چکِ پرداختنیِ برگشته به ما" description="چکی که خودمان صادر کرده‌ایم و پیش از وصول پس گرفته‌ایم">
        <CheckActionTable
          token={token}
          rows={payableReturnable}
          loading={checks.loading}
          error={checks.error}
          emptyText="چکِ پرداختنیِ بازی نیست."
          onDone={done}
          actions={[{ key: 'returned', label: 'به ما مسترد شد', icon: Undo2 }]}
        />
      </SectionCard>

      <SectionCard icon={ScrollText} title="مستردشده‌ها" description={`${faInt(returned.length)} برگ`}>
        <CheckActionTable
          token={token}
          rows={returned}
          loading={checks.loading}
          error={checks.error}
          emptyText="هنوز چکی مسترد نشده."
          onDone={done}
          actions={[]}
        />
      </SectionCard>
    </>
  )
}

// ── جست‌وجو ──

/**
 * کارگاهِ جستجو و ردیابیِ چک.
 *
 * **این یک فهرست با فیلتر نیست.** نسخه‌ی قبلی همه‌ی چک‌ها را می‌گرفت و در مرورگر
 * غربال می‌کرد — پس «جستجو روی کدِ صیادی» اصلاً ممکن نبود (آن ستون در غربال نبود)
 * و برای دفترِ بزرگ مگابایت داده می‌آمد تا یک برگ پیدا شود.
 *
 * حالا فیلترها روی سرورند، و مهم‌تر: انتخابِ یک ردیف **مسیرِ همان چک** را باز
 * می‌کند — از کجا آمد، الان کجاست، چه بر سرش آمد، و هر گام در کدام سند ثبت شد.
 *
 * **و خودش هیچ وضعیتی را عوض نمی‌کند (§۲۸).** کنش‌های مجاز کاربر را به همان
 * برگه‌ی استانداردِ چک می‌برند؛ موتورِ دومِ گذرِ وضعیت ساخته نمی‌شود.
 */
function SearchTab({
  token,
  onNavigate,
}: {
  token: string
  onNavigate: (page: PageKey, section?: string | null) => void
}) {
  const [q, setQ] = useState('')
  const [type, setType] = useState<'' | 'receivable' | 'payable'>('')
  const [status, setStatus] = useState('')
  const [dueFrom, setDueFrom] = useState('')
  const [dueTo, setDueTo] = useState('')
  const [amountMin, setAmountMin] = useState('')
  const [amountMax, setAmountMax] = useState('')
  const [advanced, setAdvanced] = useState(false)
  //: فیلترِ اعمال‌شده جدا از فیلترِ در حالِ تایپ — وگرنه هر حرف یک درخواست است.
  const [applied, setApplied] = useState<CheckSearchQuery>({})
  const [selected, setSelected] = useState<CheckRecord | null>(null)

  const rows = useAsync(() => fetchChecks(token, applied), [token, applied])
  const summary = useAsync(() => fetchCheckSummary(token, type || undefined), [token, type])

  const list = rows.data ?? []
  const pg = usePagination(list, 15, JSON.stringify(applied))
  const total = list.reduce((s, c) => s + Number(c.amount), 0)

  function apply() {
    setSelected(null)
    setApplied({
      q,
      type: type || undefined,
      status: status || undefined,
      dueFrom: dueFrom || undefined,
      dueTo: dueTo || undefined,
      amountMin: amountMin || undefined,
      amountMax: amountMax || undefined,
    })
  }

  function clear() {
    setQ('')
    setType('')
    setStatus('')
    setDueFrom('')
    setDueTo('')
    setAmountMin('')
    setAmountMax('')
    setSelected(null)
    setApplied({})
  }

  return (
    <>
      <section className="cc-head">
        <div className="cc-toolbar">
          <div className="cc-presets">
            <button type="button" className={type === '' ? 'is-active' : ''} onClick={() => setType('')}>
              همه
            </button>
            <button type="button" className={type === 'receivable' ? 'is-active' : ''} onClick={() => setType('receivable')}>
              دریافتنی
            </button>
            <button type="button" className={type === 'payable' ? 'is-active' : ''} onClick={() => setType('payable')}>
              پرداختنی
            </button>
          </div>
        </div>
        <AsyncBlock
          loading={summary.loading}
          error={summary.error}
          empty={(summary.data ?? []).length === 0}
          emptyText="چکی ثبت نشده."
        >
          <div className="cc-summary">
            {(summary.data ?? []).map((s) => (
              <Metric key={s.status} icon={<ScrollText size={14} />} label={s.label} value={`${faInt(s.count)} برگ · ${fa(s.amount)}`} />
            ))}
          </div>
        </AsyncBlock>
      </section>

      <SectionCard
        icon={Search}
        title="جستجو"
        description="شماره چک، کد صیادی، پشت‌نمره، صاحب چک، بانک یا طرف حساب"
        actions={
          <button type="button" onClick={() => setAdvanced((v) => !v)}>
            <SlidersHorizontal size={13} /> {advanced ? 'فیلتر ساده' : 'فیلتر پیشرفته'}
          </button>
        }
      >
        <div className="acc-filters">
          <label className="acc-search">
            <Search size={14} />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') apply()
              }}
              placeholder="شماره چک، کد صیادی، پشت‌نمره، صاحب چک…"
            />
          </label>
          <button type="button" className="primary" onClick={apply}>
            <Search size={13} /> جستجو
          </button>
          <button type="button" onClick={clear}>
            پاک کردن
          </button>
        </div>

        {advanced && (
          <div className="acc-filters">
            <label>
              وضعیت
              <SearchSelect value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">همه</option>
                {Object.entries(CHECK_STATUS_LABEL).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </SearchSelect>
            </label>
            <label>
              سررسید از
              <JalaliDatePicker value={dueFrom} onChange={setDueFrom} />
            </label>
            <label>
              تا
              <JalaliDatePicker value={dueTo} onChange={setDueTo} />
            </label>
            <label>
              مبلغ از
              <NumberInput value={amountMin} onChange={setAmountMin} placeholder="۰" />
            </label>
            <label>
              تا
              <NumberInput value={amountMax} onChange={setAmountMax} placeholder="۰" />
            </label>
          </div>
        )}
      </SectionCard>

      <SectionCard icon={ScrollText} title="نتیجه" description={`${faInt(list.length)} برگ`}>
        <AsyncBlock loading={rows.loading} error={rows.error} empty={list.length === 0} emptyText="چکی با این شرایط پیدا نشد.">
          <div className="table-scroll ef-table-wrap jg-wrap ck-wrap">
            <table className="cards-on-mobile ef-table xl-grid ck-sheet ck-sheet--find">
              <colgroup>
                <col className="ck-c-rowhead" />
                <col className="ck-c-number" />
                <col className="ck-c-type" />
                <col className="ck-c-amount" />
                <col className="ck-c-date" />
                <col />
                <col className="ck-c-bank" />
                <col className="ck-c-status" />
                <col className="ck-c-holder" />
                <col className="ck-c-go" />
              </colgroup>
              <thead>
                <tr>
                  <th className="xl-rowhead card-hide ck-pin-head">ردیف</th>
                  <th className="ck-pin-lead" title="کد صیادی زیرِ شماره">شماره / صیادی</th>
                  <th>نوع</th>
                  <th className="num">مبلغ</th>
                  <th>سررسید</th>
                  <th>طرف حساب</th>
                  <th>بانک</th>
                  <th>وضعیت</th>
                  <th>موقعیت فعلی</th>
                  <th className="ck-pin-end" aria-label="مسیر چک" />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((c, i) => (
                  <tr key={c.id} className={selected?.id === c.id ? 'is-selected' : undefined}>
                    <td className="xl-rowhead card-hide ck-pin-head">
                      <span className="xl-rowhead-num">{faInt(pg.page * 15 + i + 1)}</span>
                    </td>
                    <td className="card-title ck-pin-lead" data-label="شماره">
                      <span dir="ltr">{toFaDigits(c.number)}</span>
                      {c.sayad_id ? (
                        <div className="entity-sub" dir="ltr" title="کد صیادی">
                          {toFaDigits(c.sayad_id)}
                        </div>
                      ) : null}
                    </td>
                    <td data-label="نوع">{c.type === 'receivable' ? 'دریافتنی' : 'پرداختنی'}</td>
                    <td className="num" data-label="مبلغ">{fa(c.amount)}</td>
                    <td data-label="سررسید">{formatJalali(c.due_date)}</td>
                    <td className="card-wide" data-label="طرف حساب" title={c.contact_name || undefined}>
                      {c.contact_name || '—'}
                    </td>
                    <td data-label="بانک">{c.bank_name || '—'}</td>
                    <td data-label="وضعیت">
                      <StatusChip status={c.status} />
                    </td>
                    <td data-label="موقعیت فعلی" title={c.holder_label || undefined}>
                      {c.holder_label || '—'}
                    </td>
                    <td className="card-actions ck-actions ck-pin-end">
                      <button
                        type="button"
                        className="ck-act ck-act--ghost ck-act--icon"
                        aria-expanded={selected?.id === c.id}
                        aria-label={selected?.id === c.id ? 'بستنِ مسیر چک' : 'مسیر چک'}
                        title={selected?.id === c.id ? 'بستنِ مسیر چک' : 'مسیر چک'}
                        onClick={() => setSelected(selected?.id === c.id ? null : c)}
                      >
                        <History size={13} aria-hidden="true" />
                        <span className="ck-act-text">{selected?.id === c.id ? 'بستن' : 'مسیر چک'}</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td className="xl-rowhead card-hide ck-pin-head" />
                  <td className="card-title ck-pin-lead">جمعِ {faInt(list.length)} برگ</td>
                  <td className="card-hide" />
                  <td className="num" data-label="جمع مبلغ">{fa(total)}</td>
                  <td className="card-hide" colSpan={5} />
                  <td className="card-hide ck-pin-end" />
                </tr>
              </tfoot>
            </table>
          </div>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </AsyncBlock>
      </SectionCard>

      {selected && <CheckDossier token={token} check={selected} onNavigate={onNavigate} />}
    </>
  )
}

/**
 * کنشی که از این وضعیت معنی دارد، و صفحه‌ای که واقعاً انجامش می‌دهد (§۲۷ §۲۸).
 *
 * این‌جا فقط **مسیر** است، نه عمل: برگه‌ی جستجو هیچ گذری ثبت نمی‌کند؛ دکمه کاربر را به برگه‌ای می‌برد که
 * آن گذر را ثبت می‌کند.
 */
const ACTIONS_BY_STATUS: Record<string, { label: string; tab: 'receivable' | 'payable' | 'return' }[]> = {
  in_hand: [
    { label: 'واگذاری به بانک', tab: 'receivable' },
    { label: 'نقد کردن', tab: 'receivable' },
    { label: 'خرج کردن', tab: 'receivable' },
    { label: 'استرداد', tab: 'return' },
  ],
  deposited: [
    { label: 'وصول', tab: 'receivable' },
    { label: 'واخواست', tab: 'receivable' },
    { label: 'بازگشت از بانک', tab: 'receivable' },
  ],
  endorsed: [{ label: 'برگشت از خرج', tab: 'receivable' }],
  issued: [
    { label: 'وصول چک پرداختنی', tab: 'payable' },
    { label: 'استرداد به ما', tab: 'return' },
  ],
}

/**
 * پرونده‌ی یک چک — وضعیت، موقعیت، و مسیرش.
 *
 * تایم‌لاین از همان `check_events` می‌آید که وضعیت از آن می‌آید؛ پس نمی‌تواند با
 * ستونِ وضعیت اختلاف پیدا کند (§۱۳).
 */
function CheckDossier({
  token,
  check,
  onNavigate,
}: {
  token: string
  check: CheckRecord
  onNavigate: (page: PageKey, section?: string | null) => void
}) {
  const events = useAsync(() => fetchCheckTimeline(token, check.id), [token, check.id])
  const actions = ACTIONS_BY_STATUS[check.status] ?? []

  return (
    <SectionCard
      icon={History}
      title={`پرونده‌ی چک ${toFaDigits(check.number)}`}
      description={`${fa(check.amount)} ریال · سررسید ${formatJalali(check.due_date)}`}
    >
      <div className="cc-summary">
        <Metric icon={<ScrollText size={14} />} label="وضعیت" value={CHECK_STATUS_LABEL[check.status] ?? check.status} />
        <Metric icon={<Landmark size={14} />} label="موقعیت فعلی" value={check.holder_label || '—'} />
        <Metric icon={<Wallet size={14} />} label="طرف حساب" value={check.contact_name || '—'} />
      </div>

      <dl className="check-facts">
        <div>
          <dt>کد صیادی</dt>
          <dd dir="ltr">{check.sayad_id ? toFaDigits(check.sayad_id) : '—'}</dd>
        </div>
        <div>
          <dt>پشت‌نمره</dt>
          <dd>{check.back_number ? toFaDigits(check.back_number) : '—'}</dd>
        </div>
        <div>
          <dt>صاحب چک</dt>
          <dd>{check.owner_name || '—'}</dd>
        </div>
        <div>
          <dt>بانک / شعبه</dt>
          <dd>
            {check.bank_name || '—'}
            {check.branch_name ? ` — ${check.branch_name}` : ''}
          </dd>
        </div>
        <div>
          <dt>شرح</dt>
          <dd>{check.description || '—'}</dd>
        </div>
      </dl>

      {actions.length > 0 && (
        <div className="form-actions">
          <span className="muted">عملیاتِ ممکن از این وضعیت:</span>
          {actions.map((a) => (
            <button key={a.label} type="button" onClick={() => onNavigate('checks', a.tab)}>
              {a.label}
            </button>
          ))}
        </div>
      )}

      <AsyncBlock
        loading={events.loading}
        error={events.error}
        empty={(events.data ?? []).length === 0}
        emptyText="این چک پیش از افزوده‌شدنِ تاریخچه ثبت شده، پس گذرهای گذشته‌اش ردی ندارند. از این‌جا به بعد هر گذر ثبت می‌شود."
      >
        <ol className="check-trail">
          {(events.data ?? []).map((e) => (
            <li key={e.id}>
              <span className="check-trail__what">{e.operation_label}</span>
              <span className="check-trail__when">{formatJalali(e.event_date)}</span>
              <span className="check-trail__where">
                {e.bank_account_name || e.cashbox_name || e.contact_name || '—'}
              </span>
              <span className="check-trail__source">
                {e.source_type && e.source_number != null ? (
                  <em>
                    {e.source_label} {faInt(e.source_number)}
                  </em>
                ) : e.operation_no != null ? (
                  <em>عملیات چک {faInt(e.operation_no)}</em>
                ) : (
                  '—'
                )}
              </span>
            </li>
          ))}
        </ol>
      </AsyncBlock>
    </SectionCard>
  )
}

/**
 * برگ‌های خرج‌شده‌ی یک دسته — ناوبریِ برعکسِ دسته ← برگ ← چک (§۲۳).
 *
 * بدونِ این، «۷ برگ خرج شده» عددی است که کاربر باید خودش دنبالِ معنایش بگردد؛ و
 * وقتی گاردِ «این برگ قبلاً خرج شده» بالا می‌آید، اینجا می‌بیند کجا رفته.
 */
export function LeafList({
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
