import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BadgePercent,
  Boxes,
  Calculator,
  ClipboardList,
  FileSpreadsheet,
  Layers,
  ListChecks,
  Lock,
  Pencil,
  Percent,
  PlusCircle,
  Route,
  Scale,
  Ship,
  Tags,
  TrendingUp,
  Undo2,
  Users,
  Wallet,
  X,
} from 'lucide-react'
import {
  closeInvoices,
  fetchChartAccounts,
  updateSaleType,
  type ChartAccount,
  type SaleTypeAccounts,
  createBundle,
  createCommissionRule,
  createCommissionRun,
  createCustoms,
  createDiscountGroup,
  createNote,
  fetchLatestRate,
  fetchNoteAccounts,
  newIdempotencyKey,
  NOTE_PREFILL_KEY,
  type NoteAccount,
  type NotePrefill,
  createPriceAnnouncement,
  createPricingFactor,
  createSaleType,
  createSalesReturnReason,
  fetchCommissionPreview,
  fetchCommissionRules,
  fetchContactGroups,
  fetchContacts,
  fetchCurrencies,
  fetchDiscountGroups,
  fetchItemsLive,
  fetchJournalEntriesFiltered,
  fetchMembers,
  fetchPricingSuggestion,
  fetchSalesInvoices,
  fetchSalesReturnReasons,
  fetchCounterpartyEventLines,
  fetchCounterpartyEvents,
  fetchCounterpartySummary,
  fetchPreinvoiceProgress,
  fetchSalesByCustomer,
  fetchSalesByItem,
  fetchSalesByWarehouse,
  fetchSalesReviewDocuments,
  fetchSalesReviewLines,
  fetchSalesReviewSummary,
  fetchSaleTypes,
  fetchUnits,
  updateSalesReturnReason,
  type ContactGroupRecord,
  type ContactRecord,
  type Currency,
  type DiscountGroup,
  type ItemRecord,
  type PricingFactor,
  type SaleType,
  type SalesReviewDocument,
  type SalesReviewScope,
  type UnitRecord,
} from '../../api'
import type { PageKey } from '../../lib/navModel'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { ItemPicker } from '../../components/ItemPicker'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { EmptyState } from '../../components/EmptyState'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, toFaDigits, todayIso } from '../../lib/jalali'
import {
  ActiveChip,
  AsyncBlock,
  Metric,
  Note,
  OpsPage,
  RangeBar,
  fa,
  faAmount,
  faInt,
  useAsync,
  useRange,
  type Msg,
} from '../accounting/kit'

/**
 * هفده عملیاتِ ماژولِ فروش.
 *
 * تقسیم‌بندی از خودِ کارِ فروش می‌آید و سه دسته است:
 *  - **سندسازها** — فاکتور، برگشتی، اعلامیه، اظهارنامه، محاسبه‌ی پورسانت.
 *  - **تعریف‌ها** — نوعِ فروش، تخفیف، عاملِ افزاینده، گروهِ کالا، اعلامیه‌ی قیمت،
 *    بسته، قاعده‌ی پورسانت. این‌ها یک‌بار ساخته می‌شوند و بارها مصرف.
 *  - **مرورها** — مرورِ فروش، صورت‌حساب و مرورِ جامعِ طرف حساب. خودشان گزارش‌اند و
 *    فهرستِ نظیر نمی‌خواهند.
 *
 * هر صفحه‌ی رکوردساز دفترِ نظیرش را در `SalesListPages` دارد (قاعده‌ی نظیر).
 */

// ═══════════════════════ کمکی‌های مشترک ═══════════════════════

/** فرمِ کوچکِ «ثبت» با پیام و دکمه — تکرارش در هفده صفحه فقط نویز بود. */
function FormCard({
  icon,
  title,
  description,
  msg,
  submitting,
  submitLabel = 'ثبت',
  onSubmit,
  children,
  disabled,
}: {
  icon: typeof Percent
  title: string
  description: string
  msg: Msg
  submitting: boolean
  submitLabel?: string
  onSubmit: () => void
  children: React.ReactNode
  disabled?: boolean
}) {
  return (
    <SectionCard icon={icon} title={title} description={description}>
      <form
        className="invoice-form"
        onSubmit={(e) => {
          e.preventDefault()
          onSubmit()
        }}
      >
        {children}
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={submitting || disabled}>
            <PlusCircle size={14} /> {submitLabel}
          </button>
        </div>
      </form>
      <Note msg={msg} />
    </SectionCard>
  )
}

function useSubmit() {
  const [msg, setMsg] = useState<Msg>(null)
  const [submitting, setSubmitting] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  async function run(action: () => Promise<void>, okText: string) {
    setMsg(null)
    setSubmitting(true)
    try {
      await action()
      setMsg({ text: okText, kind: 'ok' })
      setReloadKey((k) => k + 1)
      return true
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
      return false
    } finally {
      setSubmitting(false)
    }
  }
  return { msg, setMsg, submitting, reloadKey, run }
}

/** کالاها و طرف‌حساب‌ها را چند صفحه لازم دارند؛ یک‌جا و با گاردِ خطا. */
function useItems(token: string) {
  const [items, setItems] = useState<ItemRecord[]>([])
  useEffect(() => {
    fetchItemsLive(token)
      .then((r: ItemRecord[]) => setItems(r.filter((i) => i.is_active)))
      .catch(() => setItems([]))
  }, [token])
  return items
}

function useContacts(token: string) {
  const [rows, setRows] = useState<ContactRecord[]>([])
  useEffect(() => {
    fetchContacts(token)
      .then((r: ContactRecord[]) => setRows(r.filter((c) => c.is_active)))
      .catch(() => setRows([]))
  }, [token])
  return rows
}

/** بازه‌ی تاریخِ ISO. اندپوینتِ فاکتور فیلترِ سرور ندارد، پس بازه اینجا اعمال می‌شود
 *  — و چون `authedGetAll` با کرسر همه‌ی صفحه‌ها را می‌آورد، سقفِ ۲۰۰ردیفی نمی‌خورد. */
function inRange(day: string, from?: string, to?: string): boolean {
  if (from && day < from) return false
  if (to && day > to) return false
  return true
}

/** نامِ طرف حساب در پاسخِ فاکتور نیست؛ از فهرستِ طرف‌حساب‌ها نگاشت می‌شود. */
function useContactNames(token: string): Map<string, string> {
  const contacts = useContacts(token)
  return useMemo(() => new Map(contacts.map((c) => [c.id, c.name])), [contacts])
}

// ═════════════════ ۱) فرآیند فروش — راهنمای مسیر ═════════════════

const FLOW: { step: string; title: string; body: string }[] = [
  {
    step: '۱',
    title: 'تعریف‌های پایه',
    body: 'نوعِ فروش، اعلامیه‌ی قیمت و — اگر لازم است — تخفیف، عاملِ افزاینده و گروهِ کالا را یک‌بار بسازید. فرمِ فاکتور از همین‌ها قیمت پیشنهاد می‌دهد.',
  },
  {
    step: '۲',
    title: 'صدور فاکتور',
    body: 'فاکتور تجاری را ثبت کنید؛ سپس سند حسابداری، خروج انبار و وصول را مستقل و در تاریخ واقعی خودشان ثبت کنید.',
  },
  {
    step: '۳',
    title: 'اصلاح‌ها',
    body: 'برگشت از فروش برای کالای برگشتی؛ اعلامیه‌ی بدهکار/بستانکار برای تعدیلِ مانده بیرون از فاکتور.',
  },
  {
    step: '۴',
    title: 'بستنِ دوره',
    body: 'فاکتورهای بازه را ببندید تا دیگر ویرایش نشوند، بعد پورسانتِ فروشنده‌ها را محاسبه و ذخیره کنید.',
  },
  {
    step: '۵',
    title: 'مرور',
    body: 'مرورِ فروش برای تصویرِ کلی، و مرورِ جامعِ طرف حساب برای دیدنِ همه‌چیزِ یک مشتری در یک صفحه.',
  },
]

export function SalesFlowPage() {
  return (
    <OpsPage
      icon={Route}
      title="فرآیند فروش"
      description="ترتیبی که کارهای این ماژول در آن انجام می‌شوند — از تعریف‌های پایه تا مرورِ نتیجه."
    >
      <SectionCard icon={Route} title="پنج گام" description="هر گام از کارتِ «عملیات» باز می‌شود.">
        <div className="table-scroll">
          <table className="cards-on-mobile acc-table">
            <thead>
              <tr>
                <th>گام</th>
                <th>چه کاری</th>
                <th>توضیح</th>
              </tr>
            </thead>
            <tbody>
              {FLOW.map((f) => (
                <tr key={f.step}>
                  <td className="card-title" data-label="گام">
                    {f.step}
                  </td>
                  <td data-label="چه کاری">
                    <strong>{f.title}</strong>
                  </td>
                  <td className="card-wide" data-label="توضیح">
                    {f.body}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════════ ۲) بستن فاکتور ═════════════════════

export function InvoiceClosePage({ token }: { token: string }) {
  const range = useRange('month')
  const { msg, submitting, reloadKey, run } = useSubmit()
  const names = useContactNames(token)

  const open = useAsync(() => fetchSalesInvoices(token), [token, reloadKey])
  const rows = (open.data ?? []).filter(
    (i) => !i.closed_at && !i.voided_at && inRange(i.invoice_date, range.from, range.to),
  )
  const pg = usePagination(rows, 15, `${range.from}${range.to}`)
  const total = rows.reduce((s, i) => s + Number(i.total_amount || 0), 0)

  return (
    <OpsPage
      icon={Lock}
      title="بستن فاکتور"
      description="فاکتورِ بسته دیگر ویرایش و ابطال نمی‌شود — مثلِ «دائم‌کردنِ سند» در حسابداری. یک‌طرفه است."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<ClipboardList size={14} />} label="فاکتورِ باز" value={faInt(rows.length)} />
            <Metric icon={<TrendingUp size={14} />} label="جمع" value={faAmount(total)} />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Lock}
        title="فاکتورهای بازِ این بازه"
        description="بستن هیچ اثرِ مالی ندارد؛ فقط فاکتور را قفل می‌کند."
        actions={
          <button
            type="button"
            className="btn-primary"
            disabled={submitting || rows.length === 0}
            onClick={() =>
              void run(async () => {
                await closeInvoices(token, { date_from: range.from ?? null, date_to: range.to ?? null })
              }, 'فاکتورهای بازه بسته شدند.')
            }
          >
            <Lock size={14} /> بستنِ همه‌ی این بازه
          </button>
        }
      >
        <Note msg={msg} />
        <AsyncBlock
          loading={open.loading}
          error={open.error}
          empty={rows.length === 0}
          emptyText="در این بازه فاکتورِ بازی نیست — یا همه بسته شده‌اند یا فاکتوری ثبت نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>تاریخ</th>
                  <th>طرف حساب</th>
                  <th>مبلغ</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((inv) => (
                  <tr key={inv.id}>
                    <td className="card-title" data-label="شماره">
                      {fa(inv.number ?? 0)}
                    </td>
                    <td data-label="تاریخ">{formatJalali(inv.invoice_date)}</td>
                    <td data-label="طرف حساب">{names.get(inv.contact_id ?? '') ?? '—'}</td>
                    <td className="num" data-label="مبلغ">
                      {faAmount(inv.total_amount)}
                    </td>
                    <td className="card-actions">
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() =>
                          void run(async () => {
                            await closeInvoices(token, { invoice_ids: [inv.id] })
                          }, `فاکتور ${fa(inv.number ?? 0)} بسته شد.`)
                        }
                      >
                        <Lock size={13} /> بستن
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

// ═════════════════════ ۹) اعلامیه بدهکار/بستانکار ═════════════════════

/** نوعِ یک سمت — همان «نوع بدهکار/بستانکار»ِ فصل. «حساب» یعنی سمتی که طرف حساب ندارد
 *  (مثلاً تخفیفِ اعطایی)؛ فهرستِ نوع‌ها عمداً بسته نیست و از همین نگاشت می‌آید. */
type SideType = 'customer' | 'supplier' | 'account'

const SIDE_TYPE_LABELS: Record<SideType, string> = {
  customer: 'مشتری',
  supplier: 'تأمین‌کننده',
  account: 'حساب (بدونِ طرف حساب)',
}

const ROLE_OF_SIDE: Record<'customer' | 'supplier', string> = {
  customer: 'accounts_receivable',
  supplier: 'accounts_payable',
}

type NoticeSideState = { type: SideType; contactId: string; accountId: string }

type NoticeRow = {
  key: number
  debit: NoticeSideState
  credit: NoticeSideState
  amount: string
  description: string
}

const emptySide = (type: SideType): NoticeSideState => ({ type, contactId: '', accountId: '' })

const emptyRow = (key: number): NoticeRow => ({
  key,
  debit: emptySide('supplier'),
  credit: emptySide('customer'),
  amount: '',
  description: '',
})

/** ارقامِ فارسی/عربی و ممیزِ فارسی به شکلِ لاتین — نرخ با کیبوردِ فارسی هم تایپ می‌شود. */
const latinNumber = (s: string) =>
  s
    .replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
    .replace(/[٫,]/g, '.')

/**
 * یک سمتِ ردیف: نوع، طرف حساب، معین — و پنلِ «اطلاعات حساب».
 *
 * معینِ سمتِ دارای طرف حساب از **نقش** پیشنهاد می‌شود (مشتری ← دریافتنی، تأمین‌کننده
 * ← پرداختنی) و قفل نیست. سمتِ بی‌طرف‌حساب فقط معین‌هایی را می‌بیند که سرور مجاز
 * می‌داند: نه دریافتنی/پرداختنی، نه حساب‌های خزانه، انبار و مالیات.
 */
function NoticeSide({
  label,
  side,
  contacts,
  partyAccounts,
  otherAccounts,
  onChange,
}: {
  label: string
  side: NoticeSideState
  contacts: ContactRecord[]
  partyAccounts: NoteAccount[]
  otherAccounts: NoteAccount[]
  onChange: (next: NoticeSideState) => void
}) {
  const party = side.type !== 'account'
  const pool = party ? partyAccounts : otherAccounts
  const roleDefault = party ? partyAccounts.find((a) => a.system_role === ROLE_OF_SIDE[side.type as 'customer']) : undefined
  const effective = pool.find((a) => a.id === side.accountId) ?? roleDefault
  const contact = contacts.find((c) => c.id === side.contactId)
  const options = party ? contacts.filter((c) => c.type === side.type || c.type === 'both') : []

  return (
    <div className="cdn-side">
      <h5 className="cdn-side-title">{label}</h5>
      <label>
        نوعِ {label}
        <select value={side.type} onChange={(e) => onChange(emptySide(e.target.value as SideType))}>
          {(Object.keys(SIDE_TYPE_LABELS) as SideType[]).map((t) => (
            <option key={t} value={t}>
              {SIDE_TYPE_LABELS[t]}
            </option>
          ))}
        </select>
      </label>
      {party && (
        <label>
          {SIDE_TYPE_LABELS[side.type]}
          <select value={side.contactId} onChange={(e) => onChange({ ...side, contactId: e.target.value })}>
            <option value="">— انتخاب کنید —</option>
            {options.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        حساب معین
        <select value={side.accountId} onChange={(e) => onChange({ ...side, accountId: e.target.value })}>
          <option value="">
            {party
              ? `پیش‌فرضِ نقش${roleDefault ? ` — ${toFaDigits(roleDefault.code)} ${roleDefault.name}` : ''}`
              : '— انتخاب کنید —'}
          </option>
          {pool.map((a) => (
            <option key={a.id} value={a.id}>
              {toFaDigits(a.code)} — {a.name}
            </option>
          ))}
        </select>
      </label>
      <dl className="cdn-side-info">
        <div>
          <dt>عنوانِ حساب معین</dt>
          <dd>{effective ? `${effective.name} (${toFaDigits(effective.code)})` : '—'}</dd>
        </div>
        <div>
          <dt>تفصیل</dt>
          <dd>{party ? contact?.name ?? '—' : 'ندارد'}</dd>
        </div>
      </dl>
    </div>
  )
}

export function CreditDebitNotePage({ token, onNavigate }: { token: string; onNavigate?: (p: PageKey) => void }) {
  const contacts = useContacts(token)
  const { msg, setMsg, submitting, run } = useSubmit()
  const [partyAccounts, setPartyAccounts] = useState<NoteAccount[]>([])
  const [otherAccounts, setOtherAccounts] = useState<NoteAccount[]>([])
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [loaded, setLoaded] = useState(false)
  const [noteDate, setNoteDate] = useState(todayIso())
  const [reason, setReason] = useState('')
  const [currency, setCurrency] = useState('IRR')
  const [rate, setRate] = useState('1')
  const [rows, setRows] = useState<NoticeRow[]>([emptyRow(1)])
  const [origin, setOrigin] = useState<string | null>(null)
  const nextKey = useRef(2)
  //: کلیدِ یکتاسازی در `useRef` می‌ماند تا رندرِ دوباره کلیدِ تازه نسازد — وگرنه
  //: محافظ بی‌اثر می‌شد و همان چیزی که باید یک بار اعمال شود دو بار می‌شد.
  const idemKey = useRef(newIdempotencyKey())
  //: «رونوشت» یا «اصلاح» از دفترِ اعلامیه‌ها. در initializer فقط خوانده می‌شود و
  //: پس از مصرف پاک — StrictMode این تابع را دو بار صدا می‌زند.
  const [prefill, setPrefill] = useState<NotePrefill | null>(() => {
    try {
      const raw = sessionStorage.getItem(NOTE_PREFILL_KEY)
      return raw ? (JSON.parse(raw) as NotePrefill) : null
    } catch {
      return null
    }
  })

  useEffect(() => {
    Promise.all([fetchNoteAccounts(token, 'counterparty'), fetchNoteAccounts(token, 'other'), fetchCurrencies(token)])
      .then(([party, other, cur]) => {
        setPartyAccounts(party)
        setOtherAccounts(other)
        setCurrencies(cur)
        setLoaded(true)
      })
      .catch((err) => setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' }))
  }, [token, setMsg])

  useEffect(() => {
    if (!prefill || !loaded) return
    //: نوعِ سمت از **نقشِ معین** بازسازی می‌شود، نه از نوعِ طرف حساب: طرف‌حسابی که
    //: هر دو نقش را دارد روی پرداختنی «تأمین‌کننده» است و روی دریافتنی «مشتری».
    const roleOf = (id: string | null) => partyAccounts.find((a) => a.id === id)?.system_role
    const sideFrom = (contactId: string | null, accountId: string | null): NoticeSideState => ({
      type: !contactId ? 'account' : roleOf(accountId) === 'accounts_payable' ? 'supplier' : 'customer',
      contactId: contactId ?? '',
      accountId: accountId ?? '',
    })
    const d = prefill.draft
    setReason(d.reason)
    setCurrency(d.currency_code)
    setRate(String(Number(d.exchange_rate)))
    setRows(
      d.lines.map((l) => ({
        key: nextKey.current++,
        debit: sideFrom(l.debit_contact_id, l.debit_account_id),
        credit: sideFrom(l.credit_contact_id, l.credit_account_id),
        amount: String(Math.round(Number(l.amount))),
        description: l.description,
      })),
    )
    setOrigin(
      prefill.corrects != null
        ? `اصلاحِ اعلامیه‌ی ${fa(prefill.corrects)}: آن اعلامیه باطل شد و این پیش‌نویسِ جایگزینِ آن است. ردیف‌ها را درست کنید و صادر کنید — شماره، تاریخ و سندِ تازه می‌گیرد.`
        : `رونوشت از اعلامیه‌ی ${fa(d.source_number ?? 0)} — ${d.cleared_fields.join('، ')} کپی نشده‌اند و تازه ساخته می‌شوند.`,
    )
    idemKey.current = newIdempotencyKey()
    try {
      sessionStorage.removeItem(NOTE_PREFILL_KEY)
    } catch {
      /* ذخیره‌ی مرورگر در دسترس نیست؛ چیزی برای پاک‌کردن نیست */
    }
    setPrefill(null)
  }, [prefill, loaded, partyAccounts])

  async function chooseCurrency(code: string) {
    setCurrency(code)
    if (code === 'IRR') {
      setRate('1')
      return
    }
    try {
      const latest = await fetchLatestRate(token, code)
      if (latest.rate) setRate(String(Number(latest.rate)))
      else setMsg({ text: `برای ارز ${code} تا امروز نرخی ثبت نشده است؛ نرخ را دستی وارد کنید.`, kind: 'err' })
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  const patch = (key: number, part: Partial<NoticeRow>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...part } : r)))

  const rateNum = Number(latinNumber(rate))
  const foreign = currency !== 'IRR'
  //: همان گردکردنِ سرور (نیم به بالا) — برای مبلغِ مثبت همان `Math.round` است.
  const baseOf = (amount: string) => Math.round((Number(amount) || 0) * (rateNum || 0))
  const total = rows.reduce((s, r) => s + (Number(r.amount) || 0), 0)
  const baseTotal = rows.reduce((s, r) => s + baseOf(r.amount), 0)
  const sideReady = (s: NoticeSideState) => (s.type === 'account' ? !!s.accountId : !!s.contactId)
  const ready =
    rateNum > 0 &&
    (!foreign || rateNum !== 0) &&
    rows.every(
      (r) => Number(r.amount) > 0 && Number.isInteger(Number(r.amount)) && sideReady(r.debit) && sideReady(r.credit),
    )

  //: معینِ سمتِ دارای طرف حساب **صریح** فرستاده می‌شود: همان که پنل نشان داده. اگر
  //: خالی می‌رفت، سرور برای طرف‌حسابی با هر دو نقش همیشه دریافتنی را برمی‌داشت —
  //: حتی وقتی کاربر «تأمین‌کننده» انتخاب کرده بود.
  const accountFor = (s: NoticeSideState): string | null => {
    if (s.accountId) return s.accountId
    if (s.type === 'account') return null
    return partyAccounts.find((a) => a.system_role === ROLE_OF_SIDE[s.type as 'customer'])?.id ?? null
  }

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="اعلامیه بدهکار بستانکار"
      description="مانده‌ی یک حساب یا طرف حساب را به دیگری منتقل می‌کند — بدونِ هیچ دریافت، پرداخت یا حرکتِ کالا. تهاترِ طلبِ ما از یک مشتری با بدهیِ ما به یک تأمین‌کننده، کارِ همین سند است."
      head={
        onNavigate && (
          <div className="cdn-links">
            <button type="button" className="btn-ghost" onClick={() => onNavigate('notelist')}>
              <ListChecks size={14} /> دفترِ اعلامیه‌ها
            </button>
          </div>
        )
      }
    >
      <FormCard
        icon={FileSpreadsheet}
        title="صدور اعلامیه"
        description="با «صدور»، اعلامیه و سندِ حسابداری‌اش در یک تراکنش ثبت می‌شوند — سندِ دومی برای یک اعلامیه ساخته نمی‌شود. هیچ فاکتوری هم تسویه‌شده نمی‌شود."
        msg={msg}
        submitting={submitting}
        submitLabel="صدور و ثبتِ سند"
        disabled={!ready || !loaded}
        onSubmit={() =>
          void run(async () => {
            await createNote(
              token,
              {
                note_date: noteDate,
                reason,
                currency_code: currency,
                exchange_rate: rateNum,
                lines: rows.map((r) => ({
                  debit_contact_id: r.debit.type === 'account' ? null : r.debit.contactId,
                  debit_account_id: accountFor(r.debit),
                  credit_contact_id: r.credit.type === 'account' ? null : r.credit.contactId,
                  credit_account_id: accountFor(r.credit),
                  amount: Number(r.amount),
                  description: r.description,
                })),
              },
              idemKey.current,
            )
            idemKey.current = newIdempotencyKey()
            setRows([emptyRow(nextKey.current++)])
            setReason('')
            setOrigin(null)
          }, 'اعلامیه صادر و سندش ثبت شد.')
        }
      >
        {origin && <p className="hint cdn-origin">{origin}</p>}
        <label>
          تاریخ
          <JalaliDatePicker value={noteDate} onChange={setNoteDate} />
        </label>
        <label>
          ارز
          <select value={currency} onChange={(e) => void chooseCurrency(e.target.value)}>
            <option value="IRR">ریال (IRR)</option>
            {currencies
              .filter((c) => c.code !== 'IRR')
              .map((c) => (
                <option key={c.id} value={c.code}>
                  {c.name} ({c.code})
                </option>
              ))}
          </select>
        </label>
        <label>
          نرخ ارز
          <input
            type="text"
            inputMode="decimal"
            dir="ltr"
            value={rate}
            disabled={!foreign}
            onChange={(e) => setRate(latinNumber(e.target.value))}
          />
          <span className="field-hint">عکسِ همین لحظه — تغییرِ نرخِ روز، اعلامیه‌ی ثبت‌شده را عوض نمی‌کند.</span>
        </label>
        <label>
          شرح
          <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} />
        </label>
      </FormCard>

      <SectionCard
        icon={FileSpreadsheet}
        title="ردیف‌های اعلامیه"
        description={
          foreign
            ? `جمع: ${faAmount(total)} ${currency} — معادل ${faAmount(baseTotal)} ریال`
            : `جمع: ${faAmount(total)} ریال`
        }
        actions={
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setRows((rs) => [...rs, emptyRow(nextKey.current++)])}
          >
            افزودن ردیف
          </button>
        }
      >
        {rows.map((r, i) => (
          <section key={r.key} className="cdn-row">
            <h4 className="cdn-row-title">ردیفِ {toFaDigits(String(i + 1))}</h4>
            <NoticeSide
              label="بدهکار"
              side={r.debit}
              contacts={contacts}
              partyAccounts={partyAccounts}
              otherAccounts={otherAccounts}
              onChange={(next) => patch(r.key, { debit: next })}
            />
            <NoticeSide
              label="بستانکار"
              side={r.credit}
              contacts={contacts}
              partyAccounts={partyAccounts}
              otherAccounts={otherAccounts}
              onChange={(next) => patch(r.key, { credit: next })}
            />
            <div className="cdn-row-amount">
              <label>
                مبلغ ({foreign ? currency : 'ریال'})
                <NumberInput value={r.amount} onChange={(v) => patch(r.key, { amount: v })} />
                {foreign && Number(r.amount) > 0 && (
                  <span className="field-hint">معادل: {faAmount(baseOf(r.amount))} ریال</span>
                )}
              </label>
              <label>
                شرحِ ردیف
                <input
                  type="text"
                  value={r.description}
                  onChange={(e) => patch(r.key, { description: e.target.value })}
                  maxLength={300}
                />
              </label>
              {rows.length > 1 && (
                <button
                  type="button"
                  className="btn-ghost danger"
                  onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}
                >
                  حذفِ ردیف
                </button>
              )}
            </div>
          </section>
        ))}
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════════ ۱۰) نوع فروش ═════════════════════

/**
 * هفت اسلاتِ حسابِ نوعِ فروش، به ترتیبی که در فرم دیده می‌شوند.
 *
 * **چرا اصلاً وجود دارند:** موتورِ ثبتِ فاکتور از ابتدا کالا و خدمت را تفکیک
 * می‌کرد و این حساب‌ها را می‌خواند — ولی هیچ صفحه‌ای نمی‌توانست مقداری به آن‌ها
 * بدهد، پس هر هفت ستون در هر کسب‌وکاری تا ابد `null` می‌ماندند و کلِ قابلیت
 * مرده بود. این فرم همان دَرِ نبوده است.
 */
const SALE_TYPE_ACCOUNT_SLOTS = [
  { key: 'goods_revenue_account_id', label: 'فروش کالا' },
  { key: 'service_revenue_account_id', label: 'فروش خدمات' },
  { key: 'goods_return_account_id', label: 'برگشت فروش کالا' },
  { key: 'service_return_account_id', label: 'برگشت فروش خدمات' },
  { key: 'goods_discount_account_id', label: 'تخفیف فروش کالا' },
  { key: 'service_discount_account_id', label: 'تخفیف فروش خدمات' },
  { key: 'addition_account_id', label: 'اضافات' },
] as const satisfies readonly { key: keyof SaleTypeAccounts; label: string }[]

const EMPTY_ACCOUNTS: SaleTypeAccounts = {
  goods_revenue_account_id: null,
  service_revenue_account_id: null,
  goods_return_account_id: null,
  service_return_account_id: null,
  goods_discount_account_id: null,
  service_discount_account_id: null,
  addition_account_id: null,
}

/** هفت انتخابگرِ حساب — یک‌جا، چون فرمِ ساخت و فرمِ ویرایش دقیقاً همین را می‌خواهند. */
function SaleTypeAccountFields({
  accounts,
  value,
  onChange,
}: {
  accounts: ChartAccount[]
  value: SaleTypeAccounts
  onChange: (next: SaleTypeAccounts) => void
}) {
  return (
    <>
      {SALE_TYPE_ACCOUNT_SLOTS.map(({ key, label }) => (
        <label key={key}>
          {label}
          <select
            value={value[key] ?? ''}
            onChange={(e) => onChange({ ...value, [key]: e.target.value || null })}
          >
            <option value="">پیش‌فرضِ چارتِ حساب‌ها</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </select>
        </label>
      ))}
      <p className="field-hint">
        خالی یعنی حسابِ پیش‌فرضِ چارتِ حساب‌ها استفاده شود. تغییرِ این حساب‌ها فقط روی
        فروش‌های <strong>بعدی</strong> اثر دارد؛ سندِ صادرشده هرگز بازنویسی نمی‌شود.
      </p>
    </>
  )
}

export function SaleTypePage({ token }: { token: string }) {
  const { msg, submitting, reloadKey, run } = useSubmit()
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [title2, setTitle2] = useState('')
  const [dueDays, setDueDays] = useState('0')
  const [taxRate, setTaxRate] = useState('')
  const [description, setDescription] = useState('')
  const [accountIds, setAccountIds] = useState<SaleTypeAccounts>(EMPTY_ACCOUNTS)
  const [accounts, setAccounts] = useState<ChartAccount[]>([])
  const [editing, setEditing] = useState<SaleType | null>(null)

  useEffect(() => {
    fetchChartAccounts(token)
      .then((list) => setAccounts(list.filter((a) => !a.is_group && a.is_active)))
      .catch(() => setAccounts([]))
  }, [token])

  const list = useAsync(() => fetchSaleTypes(token), [token, reloadKey])
  const rows = list.data ?? []

  return (
    <OpsPage
      icon={Tags}
      title="نوع فروش"
      description="نقدی، اعتباری، عمده، صادراتی… هر نوع حساب‌های فروشِ خودش را دارد و سرِ فاکتور انتخاب می‌شود."
    >
      <FormCard
        icon={Tags}
        title="تعریفِ نوعِ فروش"
        description="حساب‌ها هنگامِ صدورِ سندِ فاکتور استفاده می‌شوند — کالا و خدمت هرکدام حسابِ خودش."
        msg={msg}
        submitting={submitting}
        disabled={!name.trim()}
        onSubmit={() =>
          void run(async () => {
            await createSaleType(token, {
              name: name.trim(),
              code: code.trim() || null,
              title2: title2.trim(),
              due_days: Number(dueDays) || 0,
              default_tax_rate: taxRate ? taxRate : null,
              description,
              is_active: true,
              ...accountIds,
            })
            setName('')
            setCode('')
            setTitle2('')
            setDueDays('0')
            setTaxRate('')
            setDescription('')
            setAccountIds(EMPTY_ACCOUNTS)
          }, 'نوعِ فروش ثبت شد.')
        }
      >
        <label>
          نام
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        </label>
        <label>
          کد
          <input type="text" value={code} onChange={(e) => setCode(e.target.value)} maxLength={20} />
          <span className="field-hint">اختیاری. کدِ خودِ نوعِ فروش است، نه شماره‌ی فاکتور.</span>
        </label>
        <label>
          عنوانِ دوم
          <input type="text" value={title2} onChange={(e) => setTitle2(e.target.value)} maxLength={80} />
        </label>
        <label>
          مهلتِ تسویه (روز)
          <NumberInput value={dueDays} onChange={setDueDays} />
          <span className="field-hint">صفر یعنی نقدی.</span>
        </label>
        <label>
          نرخِ مالیاتِ پیش‌فرض (درصد)
          <NumberInput value={taxRate} onChange={setTaxRate} allowDecimal />
          <span className="field-hint">خالی یعنی از تنظیماتِ عمومی بیاید.</span>
        </label>
        <label>
          توضیح
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <SaleTypeAccountFields accounts={accounts} value={accountIds} onChange={setAccountIds} />
      </FormCard>

      <SectionCard
        icon={Tags}
        title="نوع‌های تعریف‌شده"
        description="برای تغییرِ حساب‌ها یا بایگانی‌کردن، ویرایش کنید."
      >
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="هنوز نوعِ فروشی تعریف نشده. از فرمِ بالا بسازید."
        >
          <div className="table-scroll">
            <table className="entity-table cards-on-mobile">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>کد</th>
                  <th>حساب‌های تنظیم‌شده</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const configured = SALE_TYPE_ACCOUNT_SLOTS.filter((slot) => r[slot.key]).length
                  return (
                    <tr key={r.id}>
                      <td className="card-title" data-label="نام">
                        {r.name}
                        {r.title2 ? <div className="entity-sub">{r.title2}</div> : null}
                      </td>
                      <td data-label="کد">{r.code || '—'}</td>
                      <td className="num" data-label="حساب‌های تنظیم‌شده">
                        {configured === 0 ? (
                          <span className="muted">پیش‌فرض</span>
                        ) : (
                          `${faInt(configured)} از ${faInt(SALE_TYPE_ACCOUNT_SLOTS.length)}`
                        )}
                      </td>
                      <td data-label="وضعیت">
                        <ActiveChip active={r.is_active} />
                      </td>
                      <td className="card-actions">
                        <button type="button" onClick={() => setEditing(r)}>
                          <Pencil size={13} /> ویرایش
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>

      {editing && (
        <SaleTypeEditDrawer
          token={token}
          accounts={accounts}
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            void run(async () => {}, 'نوعِ فروش به‌روزرسانی شد.')
          }}
        />
      )}
    </OpsPage>
  )
}

/**
 * ویرایشِ نوعِ فروش — **فقط فیلدهای فرستاده‌شده نوشته می‌شوند.**
 *
 * پیش از این مسیرِ `PATCH` همه‌ی فیلدها را می‌نوشت و یک بدنه‌ی ناقص، بی‌صدا و با
 * ۲۰۰، هر هفت حساب را پاک می‌کرد. حالا سرور جزئی می‌نویسد.
 */
function SaleTypeEditDrawer({
  token,
  accounts,
  row,
  onClose,
  onSaved,
}: {
  token: string
  accounts: ChartAccount[]
  row: SaleType
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(row.name)
  const [code, setCode] = useState(row.code ?? '')
  const [title2, setTitle2] = useState(row.title2)
  const [isActive, setIsActive] = useState(row.is_active)
  const [accountIds, setAccountIds] = useState<SaleTypeAccounts>(() => ({
    goods_revenue_account_id: row.goods_revenue_account_id,
    service_revenue_account_id: row.service_revenue_account_id,
    goods_return_account_id: row.goods_return_account_id,
    service_return_account_id: row.service_return_account_id,
    goods_discount_account_id: row.goods_discount_account_id,
    service_discount_account_id: row.service_discount_account_id,
    addition_account_id: row.addition_account_id,
  }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await updateSaleType(token, row.id, {
        name: name.trim(),
        code: code.trim() || null,
        title2: title2.trim(),
        is_active: isActive,
        ...accountIds,
      })
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <div>
              <div className="drawer-title-main">ویرایشِ نوعِ فروش: {row.name}</div>
              <div className="drawer-title-sub">{row.code || 'بدونِ کد'}</div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن">
            <X size={16} />
          </button>
        </div>
        <div className="drawer-body">
          <form
            className="invoice-form"
            onSubmit={(e) => {
              e.preventDefault()
              void save()
            }}
          >
        <label>
          نام
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
        </label>
        <label>
          کد
          <input type="text" value={code} onChange={(e) => setCode(e.target.value)} maxLength={20} />
        </label>
        <label>
          عنوانِ دوم
          <input type="text" value={title2} onChange={(e) => setTitle2(e.target.value)} maxLength={80} />
        </label>
        <label>
          وضعیت
          <select value={isActive ? '1' : '0'} onChange={(e) => setIsActive(e.target.value === '1')}>
            <option value="1">فعال</option>
            <option value="0">غیرفعال (بایگانی)</option>
          </select>
          <span className="field-hint">
            نوعِ غیرفعال در فاکتورِ تازه انتخاب نمی‌شود، ولی روی فاکتورهای گذشته سرِ جایش
            می‌ماند. نوعِ فروش حذف نمی‌شود.
          </span>
        </label>
        <SaleTypeAccountFields accounts={accounts} value={accountIds} onChange={setAccountIds} />
            {error && <p className="hint acc-note acc-note--err">{error}</p>}
            <div className="invoice-form-footer">
              <button type="button" onClick={onClose}>
                انصراف
              </button>
              <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
                {busy ? 'در حال ذخیره…' : 'ذخیرهٔ تغییرات'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

// ═══════════ ۱۳ و ۱۵) تخفیف و عاملِ افزاینده — یک فرم، دو جهت ═══════════

/** هر دو منو این را رندر می‌کنند و فقط `kind` فرق دارد. یک جدول، دو در. */
function PricingFactorForm({ token, kind }: { token: string; kind: 'discount' | 'markup' }) {
  const items = useItems(token)
  const groups = useAsync(() => fetchDiscountGroups(token), [token])
  const { msg, submitting, run } = useSubmit()
  const [name, setName] = useState('')
  const [mode, setMode] = useState<'percent' | 'amount'>('percent')
  const [value, setValue] = useState('')
  const [scope, setScope] = useState<'all' | 'item' | 'group'>('all')
  const [itemId, setItemId] = useState('')
  const [groupId, setGroupId] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [validTo, setValidTo] = useState('')

  const isDiscount = kind === 'discount'
  return (
    <FormCard
      icon={isDiscount ? Percent : BadgePercent}
      title={isDiscount ? 'تعریفِ تخفیف' : 'تعریفِ عاملِ افزاینده'}
      description={
        isDiscount
          ? 'مبلغ را کم می‌کند. در فرمِ فاکتور پیشنهاد می‌شود و کاربر می‌تواند عوضش کند.'
          : 'مبلغ را زیاد می‌کند (حمل، بسته‌بندی، …). پیش از تخفیف اعمال می‌شود.'
      }
      msg={msg}
      submitting={submitting}
      disabled={!name.trim() || !Number(value)}
      onSubmit={() =>
        void run(async () => {
          await createPricingFactor(token, {
            name: name.trim(),
            kind,
            mode,
            value: Number(value),
            scope,
            item_id: scope === 'item' ? itemId || null : null,
            group_id: scope === 'group' ? groupId || null : null,
            valid_from: validFrom || null,
            valid_to: validTo || null,
            is_active: true,
            description: '',
          })
          setName('')
          setValue('')
        }, isDiscount ? 'تخفیف ثبت شد.' : 'عاملِ افزاینده ثبت شد.')
      }
    >
      <label>
        نام
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
      </label>
      <label>
        مبنا
        <select value={mode} onChange={(e) => setMode(e.target.value as 'percent' | 'amount')}>
          <option value="percent">درصدی</option>
          <option value="amount">مبلغِ ثابت به ازای هر واحد</option>
        </select>
      </label>
      <label>
        {mode === 'percent' ? 'درصد' : 'مبلغ (ریال)'}
        <NumberInput value={value} onChange={setValue} allowDecimal={mode === 'percent'} />
      </label>
      <label>
        دامنه
        <select value={scope} onChange={(e) => setScope(e.target.value as typeof scope)}>
          <option value="all">همه‌ی کالاها</option>
          <option value="item">یک کالا</option>
          <option value="group">یک گروهِ کالا</option>
        </select>
      </label>
      {scope === 'item' && (
        <label>
          کالا
          <select value={itemId} onChange={(e) => setItemId(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.sku} — {i.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {scope === 'group' && (
        <label>
          گروهِ کالا
          <select value={groupId} onChange={(e) => setGroupId(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {(groups.data ?? []).map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        معتبر از
        <JalaliDatePicker value={validFrom} onChange={setValidFrom} />
      </label>
      <label>
        معتبر تا
        <JalaliDatePicker value={validTo} onChange={setValidTo} />
      </label>
    </FormCard>
  )
}

// ═════════════════ علت برگشت کالا ═════════════════

/**
 * مِسترِ علتِ برگشتِ کالا.
 *
 * **چرا جدول و نه متنِ آزاد روی ردیفِ برگشت:** «خرابی»، «خراب بود» و «کالا خراب»
 * سه نوشته‌ی یک علت‌اند. با متنِ آزاد، گزارشِ «برگشت به تفکیکِ علت» هیچ‌وقت
 * ساخته نمی‌شود چون هیچ دو ردیفی با هم جمع نمی‌شوند.
 *
 * غیرفعال‌کردن هست، حذف نیست: علتِ غیرفعال در انتخابِ تازه نمی‌آید ولی روی
 * برگشت‌های تاریخی همچنان دیده می‌شود.
 */
export function ReturnReasonPage({ token }: { token: string }) {
  const { msg, submitting, run } = useSubmit()
  const [title, setTitle] = useState('')
  const [title2, setTitle2] = useState('')
  const list = useAsync(() => fetchSalesReturnReasons(token), [token])
  const rows = list.data ?? []
  const pg = usePagination(rows, 20)

  return (
    <OpsPage
      icon={Undo2}
      title="علت برگشت کالا"
      description="علت‌هایی که هنگامِ ثبتِ فاکتور برگشتی روی هر ردیف انتخاب می‌شوند."
    >
      <FormCard
        icon={Undo2}
        title="علتِ تازه"
        description="عنوان یکتاست. علتِ ثبت‌شده حذف نمی‌شود — غیرفعال می‌شود."
        msg={msg}
        submitting={submitting}
        disabled={!title.trim()}
        onSubmit={() =>
          void run(async () => {
            await createSalesReturnReason(token, { title: title.trim(), title2: title2.trim() })
            setTitle('')
            setTitle2('')
            list.reload()
          }, 'علتِ برگشت ثبت شد.')
        }
      >
        <label>
          عنوان
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} />
        </label>
        <label>
          عنوان دوم
          <input type="text" value={title2} onChange={(e) => setTitle2(e.target.value)} maxLength={120} />
          <span className="field-hint">اختیاری — نامِ جایگزین یا لاتین.</span>
        </label>
      </FormCard>

      <SectionCard icon={Undo2} title="علت‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="هنوز علتی تعریف نشده. اولین علت را از فرمِ بالا بسازید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>عنوان</th>
                  <th>عنوان دوم</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((reason) => (
                  <tr key={reason.id} className={reason.is_active ? '' : 'acc-row--void'}>
                    <td className="card-title" data-label="عنوان">
                      {reason.title}
                    </td>
                    <td className="card-wide" data-label="عنوان دوم" dir="ltr">
                      {reason.title2 || '—'}
                    </td>
                    <td data-label="وضعیت">{reason.is_active ? 'فعال' : 'غیرفعال'}</td>
                    <td className="card-actions" data-label="عملیات">
                      <button
                        type="button"
                        onClick={() =>
                          void updateSalesReturnReason(token, reason.id, {
                            title: reason.title,
                            title2: reason.title2,
                            is_active: !reason.is_active,
                          }).then(
                            () => list.reload(),
                            (err: unknown) =>
                              window.alert(err instanceof Error ? err.message : 'خطای ناشناخته'),
                          )
                        }
                      >
                        {reason.is_active ? 'غیرفعال کن' : 'فعال کن'}
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

export function DiscountPage({ token }: { token: string }) {
  return (
    <OpsPage
      icon={Percent}
      title="تخفیف جدید"
      description="تخفیفی که هنگامِ زدنِ فاکتور پیشنهاد می‌شود. دفترِ همه‌ی تخفیف‌ها و عوامل در فهرست است."
    >
      <PricingFactorForm token={token} kind="discount" />
    </OpsPage>
  )
}

export function MarkupPage({ token }: { token: string }) {
  return (
    <OpsPage
      icon={BadgePercent}
      title="عامل افزاینده جدید"
      description="هزینه‌ای که به قیمت اضافه می‌شود — حمل، بسته‌بندی، بیمه. پیش از تخفیف اعمال می‌شود."
    >
      <PricingFactorForm token={token} kind="markup" />
    </OpsPage>
  )
}

// ═════════════════ ۱۴) گروه کالای تخفیف ═════════════════

export function DiscountGroupPage({ token }: { token: string }) {
  const items = useItems(token)
  const { msg, submitting, run } = useSubmit()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')

  const shown = useMemo(() => {
    const t = search.trim()
    if (!t) return items.slice(0, 60)
    return items.filter((i) => i.name.includes(t) || i.sku.includes(t)).slice(0, 60)
  }, [items, search])

  function toggle(id: string) {
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <OpsPage
      icon={Layers}
      title="گروه کالای تخفیف جدید"
      description="مجموعه‌ای نام‌دار از کالاها که یک تخفیف یا عاملِ افزاینده رویشان اعمال می‌شود."
    >
      <FormCard
        icon={Layers}
        title="ساختِ گروه"
        description="عضویت صریح است — تغییرِ دسته‌بندیِ انبار قیمت را بی‌خبر عوض نمی‌کند."
        msg={msg}
        submitting={submitting}
        disabled={!name.trim() || picked.size === 0}
        onSubmit={() =>
          void run(async () => {
            await createDiscountGroup(token, {
              name: name.trim(),
              description,
              is_active: true,
              item_ids: [...picked],
            })
            setName('')
            setDescription('')
            setPicked(new Set())
          }, 'گروهِ کالا ساخته شد.')
        }
      >
        <label>
          نامِ گروه
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
        </label>
        <label>
          توضیح
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label>
          جست‌وجوی کالا
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="نام یا کدِ کالا"
          />
          <span className="field-hint">{faInt(picked.size)} کالا انتخاب شده است.</span>
        </label>
      </FormCard>

      <SectionCard icon={Boxes} title="کالاها" description={`${faInt(shown.length)} کالا نمایش داده می‌شود`}>
        {shown.length === 0 ? (
          <EmptyState icon={Boxes} text="کالایی با این جست‌وجو نیست. یک‌بار «هم‌گام‌سازی» کنید." />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th />
                  <th>کد</th>
                  <th>نام</th>
                  <th>قیمتِ پایه</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((i) => (
                  <tr key={i.id}>
                    <td data-label="انتخاب">
                      <input type="checkbox" checked={picked.has(i.id)} onChange={() => toggle(i.id)} />
                    </td>
                    <td className="card-title" data-label="کد">
                      {i.sku}
                    </td>
                    <td className="card-wide" data-label="نام">
                      {i.name}
                    </td>
                    <td className="num" data-label="قیمتِ پایه">
                      {faAmount(i.sales_price)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ ۱۱) اعلامیه قیمت ═════════════════

/** یک قاعده‌ی قیمت در حالِ ساخته‌شدن. */
interface RuleDraft {
  key: number
  targetKind: 'item' | 'group'
  itemId: string
  itemGroupId: string
  saleTypeId: string
  unitId: string
  contactGroupId: string
  currencyCode: string
  price: string
  additionPercent: string
  allowRate: boolean
  allowDiscount: boolean
  maxDecrease: string
  maxIncrease: string
}

const EMPTY_RULE: Omit<RuleDraft, 'key'> = {
  targetKind: 'item',
  itemId: '',
  itemGroupId: '',
  saleTypeId: '',
  unitId: '',
  contactGroupId: '',
  currencyCode: 'IRR',
  price: '',
  additionPercent: '',
  allowRate: true,
  allowDiscount: true,
  maxDecrease: '',
  maxIncrease: '',
}

/**
 * اعلامیه قیمت — **ماتریسِ قیمت، نه یک عدد برای هر کالا.**
 *
 * یک کالا هم‌زمان می‌تواند قیمتِ «عادی»، «خرده» و «عمده» داشته باشد، و هرکدام
 * حدِ تغییرِ خودشان را. این صفحه تا امروز فقط `{کالا، قیمت}` می‌فرستاد — یعنی
 * ماتریسی که مدل و حل‌کننده‌اش وجود داشت، از هیچ‌جای محصول قابلِ ورود نبود.
 *
 * قاعده‌ها یکی‌یکی ساخته می‌شوند و بعد با هم ثبت: یک جدولِ دوازده‌ستونیِ ویرایشی
 * روی موبایل غیرقابلِ استفاده است، و اشتباهِ تایپی در آن دیده نمی‌شود.
 */
export function PriceAnnouncementPage({ token }: { token: string }) {
  const items = useItems(token)
  const { msg, submitting, run } = useSubmit()
  const [name, setName] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState(todayIso())
  const [notes, setNotes] = useState('')

  const [saleTypes, setSaleTypes] = useState<SaleType[]>([])
  const [units, setUnits] = useState<UnitRecord[]>([])
  const [contactGroups, setContactGroups] = useState<ContactGroupRecord[]>([])
  const [itemGroups, setItemGroups] = useState<DiscountGroup[]>([])
  const [currencies, setCurrencies] = useState<Currency[]>([])
  useEffect(() => {
    fetchSaleTypes(token).then((r) => setSaleTypes(r.filter((x) => x.is_active))).catch(() => {})
    fetchUnits(token).then(setUnits).catch(() => {})
    fetchContactGroups(token).then((r) => setContactGroups(r.filter((x) => x.is_active))).catch(() => {})
    fetchDiscountGroups(token).then((r) => setItemGroups(r.filter((x) => x.is_active))).catch(() => {})
    fetchCurrencies(token).then(setCurrencies).catch(() => {})
  }, [token])

  const [draft, setDraft] = useState<RuleDraft>({ key: 0, ...EMPTY_RULE })
  const [rules, setRules] = useState<RuleDraft[]>([])
  const nextKey = useRef(1)

  const itemName = (id: string) => items.find((i) => i.id === id)?.name ?? '—'
  const label = <T extends { id: string; name: string }>(rows: T[], id: string) =>
    id ? (rows.find((r) => r.id === id)?.name ?? '—') : 'همه'

  const draftValid =
    Number(draft.price) > 0 &&
    (draft.targetKind === 'item' ? !!draft.itemId : !!draft.itemGroupId)

  function addRule() {
    if (!draftValid) return
    setRules((prev) => [...prev, { ...draft, key: nextKey.current++ }])
    // نوعِ فروش و ارز عمداً می‌مانند: معمولاً چند کالا پشتِ‌هم برای *یک* نوعِ فروش
    // قیمت می‌خورند، و پاک‌کردنشان یعنی کاربر هر بار دوباره انتخابشان کند.
    setDraft((prev) => ({ ...EMPTY_RULE, key: 0, saleTypeId: prev.saleTypeId, currencyCode: prev.currencyCode }))
  }

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="اعلامیه قیمت"
      description="قیمتِ کالاها به ازای نوعِ فروش، واحد، گروهِ مشتری و ارز — با تاریخِ اجرا. اعلامیه‌ی تازه کنارِ قبلی می‌نشیند، نه به‌جایش، تا فاکتورهای گذشته قابلِ توضیح بمانند."
    >
      <FormCard
        icon={FileSpreadsheet}
        title="اعلامیه‌ی تازه"
        description="سربرگِ اعلامیه. قاعده‌ها را در کارتِ پایین بسازید."
        msg={msg}
        submitting={submitting}
        submitLabel={`ثبتِ اعلامیه (${faInt(rules.length)} قاعده)`}
        disabled={!name.trim() || rules.length === 0}
        onSubmit={() =>
          void run(async () => {
            await createPriceAnnouncement(token, {
              name: name.trim(),
              effective_from: effectiveFrom,
              notes,
              is_active: true,
              lines: rules.map((r) => ({
                item_id: r.targetKind === 'item' ? r.itemId : null,
                item_group_id: r.targetKind === 'group' ? r.itemGroupId : null,
                price: Number(r.price),
                sale_type_id: r.saleTypeId || null,
                unit_id: r.unitId || null,
                contact_group_id: r.contactGroupId || null,
                currency_code: r.currencyCode || 'IRR',
                addition_percent: Number(r.additionPercent) || 0,
                allow_rate_change: r.allowRate,
                allow_discount_change: r.allowDiscount,
                max_decrease_percent: Number(r.maxDecrease) || 0,
                max_increase_percent: Number(r.maxIncrease) || 0,
              })),
            })
            setName('')
            setNotes('')
            setRules([])
          }, 'اعلامیه‌ی قیمت ثبت شد.')
        }
      >
        <label>
          نامِ اعلامیه
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={200}
            placeholder="مثلاً «قیمتِ عمده — تیر ۱۴۰۵»"
          />
        </label>
        <label>
          تاریخِ اجرا
          <JalaliDatePicker value={effectiveFrom} onChange={setEffectiveFrom} />
        </label>
        <label>
          توضیح
          <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
      </FormCard>

      <SectionCard
        icon={Tags}
        title="افزودنِ قاعده"
        description="هدف و زمینه را مشخص کنید. هر زمینه‌ای که خالی بماند یعنی «همه»."
        actions={
          <button type="button" className="btn-primary" disabled={!draftValid} onClick={addRule}>
            <PlusCircle size={14} /> افزودن
          </button>
        }
      >
        <div className="invoice-form form-full">
          <label>
            هدفِ قاعده
            <select
              value={draft.targetKind}
              onChange={(e) =>
                setDraft({ ...draft, targetKind: e.target.value as 'item' | 'group', itemId: '', itemGroupId: '' })
              }
            >
              <option value="item">یک کالا/خدمت</option>
              <option value="group">گروهِ فروشِ کالا</option>
            </select>
            <span className="field-hint">
              قاعده‌ای که خودِ کالا را نام ببرد بر قاعده‌ی گروهش می‌چربد.
            </span>
          </label>
          {draft.targetKind === 'item' ? (
            <label>
              کالا/خدمت
              <ItemPicker items={items} value={draft.itemId} onChange={(id) => setDraft({ ...draft, itemId: id })} />
            </label>
          ) : (
            <label>
              گروهِ فروشِ کالا
              <select value={draft.itemGroupId} onChange={(e) => setDraft({ ...draft, itemGroupId: e.target.value })}>
                <option value="">— انتخاب گروه —</option>
                {itemGroups.map((g) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            نوعِ فروش
            <select value={draft.saleTypeId} onChange={(e) => setDraft({ ...draft, saleTypeId: e.target.value })}>
              <option value="">همه</option>
              {saleTypes.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </label>
          <label>
            واحد
            <select value={draft.unitId} onChange={(e) => setDraft({ ...draft, unitId: e.target.value })}>
              <option value="">همه</option>
              {units.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
            <span className="field-hint">
              قیمتِ کارتن از قیمتِ عدد ضربِ ضریبِ تبدیل درنمی‌آید؛ هر واحد قاعده‌ی خودش را دارد.
            </span>
          </label>
          <label>
            گروهِ مشتری
            <select value={draft.contactGroupId} onChange={(e) => setDraft({ ...draft, contactGroupId: e.target.value })}>
              <option value="">همه</option>
              {contactGroups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </label>
          <label>
            ارز
            <select value={draft.currencyCode} onChange={(e) => setDraft({ ...draft, currencyCode: e.target.value })}>
              <option value="IRR">ریال</option>
              {currencies.filter((c) => c.code !== 'IRR').map((c) => (
                <option key={c.code} value={c.code}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            فی
            <NumberInput value={draft.price} onChange={(v) => setDraft({ ...draft, price: v })} />
          </label>
          <label>
            درصدِ اضافات
            <NumberInput value={draft.additionPercent} onChange={(v) => setDraft({ ...draft, additionPercent: v })} />
            <span className="field-hint">ثبت و نمایش می‌شود؛ روی مبلغِ فاکتور اعمال نمی‌شود.</span>
          </label>
          <label className="cal-check-inline">
            <input
              type="checkbox"
              checked={draft.allowRate}
              onChange={(e) => setDraft({ ...draft, allowRate: e.target.checked })}
            />
            امکانِ تغییرِ فی در فاکتور
          </label>
          <label className="cal-check-inline">
            <input
              type="checkbox"
              checked={draft.allowDiscount}
              onChange={(e) => setDraft({ ...draft, allowDiscount: e.target.checked })}
            />
            امکانِ تغییرِ تخفیف در فاکتور
          </label>
          <label>
            درصدِ کاهشِ مجاز
            <NumberInput
              value={draft.maxDecrease}
              onChange={(v) => setDraft({ ...draft, maxDecrease: v })}
              disabled={!draft.allowRate}
            />
            <span className="field-hint">خالی یا صفر = بی‌حد.</span>
          </label>
          <label>
            درصدِ افزایشِ مجاز
            <NumberInput
              value={draft.maxIncrease}
              onChange={(v) => setDraft({ ...draft, maxIncrease: v })}
              disabled={!draft.allowRate}
            />
            <span className="field-hint">لازم نیست با کاهش یکی باشد.</span>
          </label>
        </div>
      </SectionCard>

      <SectionCard
        icon={Boxes}
        title="قاعده‌های این اعلامیه"
        description={`${faInt(rules.length)} قاعده — با ثبتِ اعلامیه همگی با هم ذخیره می‌شوند`}
      >
        {rules.length === 0 ? (
          <EmptyState icon={Boxes} text="هنوز قاعده‌ای افزوده نشده." />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>هدف</th>
                  <th>نوع فروش</th>
                  <th>واحد</th>
                  <th>گروه مشتری</th>
                  <th>ارز</th>
                  <th>فی</th>
                  <th>اضافات</th>
                  <th>تغییر فی</th>
                  <th>تغییر تخفیف</th>
                  <th>کاهش/افزایش</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => (
                  <tr key={r.key}>
                    <td className="card-title" data-label="هدف">
                      {r.targetKind === 'item' ? itemName(r.itemId) : `گروه: ${label(itemGroups, r.itemGroupId)}`}
                    </td>
                    <td data-label="نوع فروش">{label(saleTypes, r.saleTypeId)}</td>
                    <td data-label="واحد">{label(units, r.unitId)}</td>
                    <td data-label="گروه مشتری">{label(contactGroups, r.contactGroupId)}</td>
                    <td data-label="ارز">{r.currencyCode}</td>
                    <td className="num" data-label="فی">{faAmount(r.price)}</td>
                    <td className="num" data-label="اضافات">{r.additionPercent ? `${fa(r.additionPercent)}٪` : '—'}</td>
                    <td data-label="تغییر فی">{r.allowRate ? 'آزاد' : 'قفل'}</td>
                    <td data-label="تغییر تخفیف">{r.allowDiscount ? 'آزاد' : 'قفل'}</td>
                    <td className="num" data-label="کاهش/افزایش">
                      {r.allowRate ? `${fa(r.maxDecrease || 0)}٪ / ${fa(r.maxIncrease || 0)}٪` : '—'}
                    </td>
                    <td className="card-actions">
                      <button
                        type="button"
                        className="icon-btn-danger"
                        onClick={() => setRules((prev) => prev.filter((x) => x.key !== r.key))}
                        aria-label="حذفِ قاعده"
                      >
                        <Undo2 size={13} /> حذف
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ ۱۲) بسته محصول ═════════════════

export function ProductBundlePage({ token }: { token: string }) {
  const items = useItems(token)
  const { msg, submitting, run } = useSubmit()
  const [name, setName] = useState('')
  const [bundlePrice, setBundlePrice] = useState('')
  const [description, setDescription] = useState('')
  const [qtys, setQtys] = useState<Record<string, string>>({})
  const [search, setSearch] = useState('')

  const shown = useMemo(() => {
    const t = search.trim()
    return (t ? items.filter((i) => i.name.includes(t) || i.sku.includes(t)) : items).slice(0, 60)
  }, [items, search])
  const chosen = Object.entries(qtys).filter(([, v]) => Number(v) > 0)

  return (
    <OpsPage
      icon={Boxes}
      title="بسته محصول جدید"
      description="چند کالا که با هم و به یک قیمت فروخته می‌شوند. بسته موجودی ندارد؛ هنگامِ فروش به کالاهای عضوش باز می‌شود."
    >
      <FormCard
        icon={Boxes}
        title="ساختِ بسته"
        description="قیمتِ بسته را خالی بگذارید تا جمعِ قیمتِ اعضا حساب شود."
        msg={msg}
        submitting={submitting}
        submitLabel={`ثبتِ بسته (${faInt(chosen.length)} کالا)`}
        disabled={!name.trim() || chosen.length === 0}
        onSubmit={() =>
          void run(async () => {
            await createBundle(token, {
              name: name.trim(),
              bundle_price: bundlePrice ? Number(bundlePrice) : null,
              is_active: true,
              description,
              lines: chosen.map(([item_id, v]) => ({ item_id, qty: Number(v) })),
            })
            setName('')
            setBundlePrice('')
            setDescription('')
            setQtys({})
          }, 'بسته ساخته شد.')
        }
      >
        <label>
          نامِ بسته
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
        </label>
        <label>
          قیمتِ بسته (ریال)
          <NumberInput value={bundlePrice} onChange={setBundlePrice} />
          <span className="field-hint">خالی = جمعِ قیمتِ اعضا.</span>
        </label>
        <label>
          توضیح
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label>
          جست‌وجوی کالا
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="نام یا کدِ کالا" />
        </label>
      </FormCard>

      <SectionCard icon={Boxes} title="اعضای بسته" description="تعدادِ هر کالا در بسته را وارد کنید">
        {shown.length === 0 ? (
          <EmptyState icon={Boxes} text="کالایی با این جست‌وجو نیست." />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>نام</th>
                  <th>قیمت</th>
                  <th>تعداد در بسته</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((i) => (
                  <tr key={i.id}>
                    <td className="card-title" data-label="کد">
                      {i.sku}
                    </td>
                    <td className="card-wide" data-label="نام">
                      {i.name}
                    </td>
                    <td className="num" data-label="قیمت">
                      {faAmount(i.sales_price)}
                    </td>
                    <td data-label="تعداد در بسته">
                      <NumberInput
                        value={qtys[i.id] ?? ''}
                        onChange={(v) => setQtys((p) => ({ ...p, [i.id]: v }))}
                        allowDecimal
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </OpsPage>
  )
}

// ═════════════════ ۵) پورسانت — قاعده‌ها ═════════════════

export function CommissionPage({ token }: { token: string }) {
  const { msg, submitting, reloadKey, run } = useSubmit()
  const rules = useAsync(() => fetchCommissionRules(token), [token, reloadKey])
  const [people, setPeople] = useState<{ id: string; name: string }[]>([])
  const [salespersonId, setSalespersonId] = useState('')
  const [rate, setRate] = useState('')
  const [basis, setBasis] = useState<'net' | 'profit'>('net')

  useEffect(() => {
    fetchMembers(token)
      .then((r) => setPeople(r.members.map((m) => ({ id: m.user_id, name: m.name || m.email }))))
      .catch(() => setPeople([]))
  }, [token])

  const rows = rules.data ?? []
  return (
    <OpsPage
      icon={Wallet}
      title="پورسانت"
      description="نرخِ پورسانتِ هر فروشنده. هر فروشنده یک قاعده دارد؛ محاسبه در منوی «محاسبه پورسانت» انجام می‌شود."
    >
      <FormCard
        icon={Wallet}
        title="قاعده‌ی تازه"
        description="مبنا یا خالصِ فاکتور است یا سودِ ناخالص — انتخابش اثرِ بزرگی روی عدد دارد."
        msg={msg}
        submitting={submitting}
        disabled={!salespersonId || !Number(rate)}
        onSubmit={() =>
          void run(async () => {
            await createCommissionRule(token, {
              salesperson_id: salespersonId,
              rate: Number(rate),
              basis,
              is_active: true,
              description: '',
            })
            setSalespersonId('')
            setRate('')
          }, 'قاعده‌ی پورسانت ثبت شد.')
        }
      >
        <label>
          فروشنده
          <select value={salespersonId} onChange={(e) => setSalespersonId(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          نرخ (درصد)
          <NumberInput value={rate} onChange={setRate} allowDecimal />
        </label>
        <label>
          مبنا
          <select value={basis} onChange={(e) => setBasis(e.target.value as 'net' | 'profit')}>
            <option value="net">خالصِ فاکتور</option>
            <option value="profit">سودِ ناخالص</option>
          </select>
        </label>
      </FormCard>

      <SectionCard icon={Users} title="قاعده‌های ثبت‌شده" description={`${faInt(rows.length)} فروشنده`}>
        <AsyncBlock
          loading={rules.loading}
          error={rules.error}
          empty={rows.length === 0}
          emptyText="هنوز قاعده‌ای ثبت نشده. بالا یک فروشنده و نرخش را اضافه کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>فروشنده</th>
                  <th>نرخ</th>
                  <th>مبنا</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="card-title" data-label="فروشنده">
                      {r.salesperson_name}
                    </td>
                    <td className="num" data-label="نرخ">
                      {fa(r.rate)}٪
                    </td>
                    <td data-label="مبنا">{r.basis === 'profit' ? 'سودِ ناخالص' : 'خالصِ فاکتور'}</td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${r.is_active ? 'tone-success' : 'tone-default'}`}>
                        {r.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
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

// ═════════════════ ۶) محاسبه پورسانت ═════════════════

export function CommissionCalcPage({ token }: { token: string }) {
  const range = useRange('month')
  const { msg, submitting, reloadKey, run } = useSubmit()
  const [note, setNote] = useState('')

  const preview = useAsync(
    () =>
      range.from && range.to
        ? fetchCommissionPreview(token, range.from, range.to)
        : Promise.resolve({ date_from: '', date_to: '', total_amount: '0', rows: [] }),
    [token, range.from, range.to, reloadKey],
  )
  const rows = preview.data?.rows ?? []

  return (
    <OpsPage
      icon={Calculator}
      title="محاسبه پورسانت"
      description="پورسانتِ بازه را حساب و ذخیره می‌کند. ذخیره‌شده دیگر عوض نمی‌شود — حتی اگر فاکتوری بعداً باطل شود."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<Users size={14} />} label="فروشنده" value={faInt(rows.length)} />
            <Metric
              icon={<Wallet size={14} />}
              label="جمعِ پورسانت"
              value={faAmount(preview.data?.total_amount ?? 0)}
              tone="out"
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Calculator}
        title="پیش‌نمایشِ محاسبه"
        description="تا وقتی ذخیره نکنید، چیزی ثبت نمی‌شود."
        actions={
          <button
            type="button"
            className="btn-primary"
            disabled={submitting || rows.length === 0 || !range.from || !range.to}
            onClick={() =>
              void run(async () => {
                await createCommissionRun(token, {
                  date_from: range.from as string,
                  date_to: range.to as string,
                  note,
                })
                setNote('')
              }, 'محاسبه ذخیره شد.')
            }
          >
            <Calculator size={14} /> ذخیره‌ی محاسبه
          </button>
        }
      >
        <Note msg={msg} />
        <div className="acc-filters">
          <label className="acc-inline-field">
            توضیحِ این محاسبه
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="مثلاً «تیرِ ۱۴۰۵»"
            />
          </label>
        </div>
        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={rows.length === 0}
          emptyText="در این بازه پورسانتی نیست — یا فاکتوری با فروشنده ثبت نشده، یا قاعده‌ای تعریف نشده."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>فروشنده</th>
                  <th>تعداد فاکتور</th>
                  <th>مبنا</th>
                  <th>مبلغِ مبنا</th>
                  <th>نرخ</th>
                  <th>پورسانت</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.salesperson_id}>
                    <td className="card-title" data-label="فروشنده">
                      {r.salesperson_name}
                    </td>
                    <td className="num" data-label="تعداد فاکتور">
                      {faInt(r.invoice_count)}
                    </td>
                    <td data-label="مبنا">{r.basis === 'profit' ? 'سودِ ناخالص' : 'خالص'}</td>
                    <td className="num" data-label="مبلغِ مبنا">
                      {faAmount(r.base_amount)}
                    </td>
                    <td className="num" data-label="نرخ">
                      {fa(r.rate)}٪
                    </td>
                    <td className="num" data-label="پورسانت">
                      {faAmount(r.amount)}
                    </td>
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

// ═════════════════ ۷) اظهارنامه گمرکی ═════════════════

export function CustomsPage({ token }: { token: string }) {
  const { msg, submitting, run } = useSubmit()
  const [no, setNo] = useState('')
  const [decDate, setDecDate] = useState(todayIso())
  const [office, setOffice] = useState('')
  const [hs, setHs] = useState('')
  const [country, setCountry] = useState('')
  const [value, setValue] = useState('')
  const [currency, setCurrency] = useState('IRR')

  return (
    <OpsPage
      icon={Ship}
      title="اظهارنامه گمرکی"
      description="اظهارنامه‌ی فروشِ صادراتی. به فاکتور وصل می‌شود ولی اجباری نیست — گاهی پیش از صدورِ فاکتور باز می‌شود."
    >
      <FormCard
        icon={Ship}
        title="ثبتِ اظهارنامه"
        description="شماره در هر کسب‌وکار یکتاست."
        msg={msg}
        submitting={submitting}
        disabled={!no.trim()}
        onSubmit={() =>
          void run(async () => {
            await createCustoms(token, {
              declaration_no: no.trim(),
              declaration_date: decDate,
              customs_office: office,
              hs_code: hs.trim(),
              destination_country: country,
              declared_value: Number(value) || 0,
              currency_code: currency.trim().toUpperCase() || 'IRR',
              invoice_id: null,
              description: '',
            })
            setNo('')
            setHs('')
            setValue('')
          }, 'اظهارنامه ثبت شد.')
        }
      >
        <label>
          شماره‌ی اظهارنامه
          <input type="text" value={no} onChange={(e) => setNo(e.target.value)} maxLength={40} dir="ltr" />
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={decDate} onChange={setDecDate} />
        </label>
        <label>
          گمرکِ مبدأ
          <input type="text" value={office} onChange={(e) => setOffice(e.target.value)} maxLength={120} />
        </label>
        <label>
          کدِ تعرفه (HS)
          <input type="text" value={hs} onChange={(e) => setHs(e.target.value)} maxLength={20} dir="ltr" />
          <span className="field-hint">کدِ تعرفه‌ی گمرکی؛ صفرِ ابتدایی حفظ می‌شود.</span>
        </label>
        <label>
          کشورِ مقصد
          <input type="text" value={country} onChange={(e) => setCountry(e.target.value)} maxLength={80} />
        </label>
        <label>
          ارزشِ اظهارشده
          <NumberInput value={value} onChange={setValue} allowDecimal />
        </label>
        <label>
          ارز
          <input
            type="text"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            maxLength={3}
            dir="ltr"
          />
          <span className="field-hint">کدِ سه‌حرفی — مثلاً USD، EUR، IRR.</span>
        </label>
      </FormCard>
    </OpsPage>
  )
}

// ═════════════════ ۱۶) مرور فروش ═════════════════

/**
 * مرور فروش — شش نما روی یک حقیقت.
 *
 * تا امروز این صفحه یک تب داشت (فهرستِ فاکتور) و برای فیلترکردنش کلِ فاکتورهای
 * کسب‌وکار را به مرورگر می‌کشید. نه مقداری داشت، نه سمتِ کالا، نه سمتِ انبار، و
 * نه — مهم‌تر از همه — مقایسه‌ی «فروخته‌شده» با «خارج‌شده».
 *
 * هر تب یک درخواستِ جدا دارد و هیچ‌کدام از دیگری ساخته نمی‌شود؛ چون دانه‌بندی‌شان
 * فرق دارد و جمع‌زدنِ دو تب با هم، یک مبلغ را دو بار می‌شمارد.
 */

const SALES_REVIEW_TABS = [
  { key: 'items', label: 'کالا' },
  { key: 'customers', label: 'مشتری' },
  { key: 'documents', label: 'اسناد فروش' },
  { key: 'lines', label: 'اقلام فروش' },
  { key: 'warehouses', label: 'انبار' },
  { key: 'preinvoices', label: 'پیش‌فاکتور' },
  { key: 'voided', label: 'فاکتورهای ابطالی' },
] as const

export function SalesBrowsePage({ token }: { token: string }) {
  const range = useRange('month')
  const contacts = useContacts(token)
  const [contactId, setContactId] = useState('')
  const [tab, setTab] = useState<string>('items')

  const scope = useMemo(
    () => ({ from: range.from, to: range.to, contactId: contactId || undefined }),
    [range.from, range.to, contactId],
  )
  const key = `${scope.from}${scope.to}${scope.contactId ?? ''}`

  const summary = useAsync(() => fetchSalesReviewSummary(token, scope), [token, key])
  const sum = summary.data

  return (
    <OpsPage
      icon={TrendingUp}
      title="مرور فروش"
      description="فروش از چند زاویه — کالا، مشتری، سند، قلم، انبار و پیش‌فاکتور. همه از اسنادِ واقعی."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={<ContactPicker contacts={contacts} value={contactId} onChange={setContactId} />}
          />
          {sum && (
            <div className="cc-summary">
              <Metric icon={<ClipboardList size={14} />} label="فاکتور" value={faInt(sum.invoice_count)} />
              <Metric icon={<TrendingUp size={14} />} label="فروشِ خالص" value={faAmount(sum.net_sales)} tone="in" />
              <Metric icon={<Undo2 size={14} />} label="برگشت" value={faAmount(sum.return_amount)} tone="out" />
              <Metric icon={<Percent size={14} />} label="تخفیف" value={faAmount(sum.discount)} />
              <Metric
                icon={<Boxes size={14} />}
                label="فروخته / خارج‌شده"
                value={`${fa(sum.sold_qty)} / ${fa(sum.issued_qty)}`}
              />
              {Number(sum.unissued_qty) !== 0 && (
                <Metric
                  icon={<Ship size={14} />}
                  label="فروخته و نرفته"
                  value={fa(sum.unissued_qty)}
                  tone="out"
                />
              )}
            </div>
          )}
        </div>
      }
    >
      <SectionCard
        icon={TrendingUp}
        title="نما"
        description="هر نما دانه‌بندیِ خودش را دارد و با نمای دیگر جمع نمی‌شود."
      >
        <div className="acc-filters">
          <label className="acc-inline-field">
            زاویه
            <select value={tab} onChange={(e) => setTab(e.target.value)}>
              {SALES_REVIEW_TABS.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        {tab === 'items' && <SalesItemsView token={token} scope={scope} cacheKey={key} />}
        {tab === 'customers' && <SalesCustomersView token={token} scope={scope} cacheKey={key} />}
        {tab === 'documents' && <SalesDocumentsView token={token} scope={scope} cacheKey={key} />}
        {tab === 'lines' && <SalesLinesView token={token} scope={scope} cacheKey={key} />}
        {tab === 'warehouses' && <SalesWarehousesView token={token} scope={scope} cacheKey={key} />}
        {tab === 'preinvoices' && <PreinvoiceProgressView token={token} scope={scope} cacheKey={key} />}
        {tab === 'voided' && <SalesVoidedView token={token} scope={scope} cacheKey={key} />}
      </SectionCard>
    </OpsPage>
  )
}

type ViewProps = { token: string; scope: SalesReviewScope; cacheKey: string }

/** تفاوتِ تجاری و فیزیکی — همان چیزی که این گزارش برایش ساخته شده. */
function GapCell({ value }: { value: string }) {
  const n = Number(value || 0)
  if (n === 0) return <>—</>
  return <span className={n > 0 ? 'stock-over' : undefined}>{fa(value)}</span>
}

function SalesItemsView({ token, scope, cacheKey }: ViewProps) {
  const list = useAsync(() => fetchSalesByItem(token, scope), [token, cacheKey])
  const rows = list.data ?? []
  const pg = usePagination(rows, 20, cacheKey)
  return (
    <AsyncBlock
      loading={list.loading}
      error={list.error}
      empty={rows.length === 0}
      emptyText="در این بازه فروشی ثبت نشده."
    >
      <div className="table-scroll">
        <table className="cards-on-mobile acc-table">
          <thead>
            <tr>
              <th>کد</th>
              <th>کالا/خدمت</th>
              <th>واحد</th>
              <th>فروخته</th>
              <th>برگشت</th>
              <th>خارج‌شده</th>
              <th>فروخته و نرفته</th>
              <th>فیِ متوسط</th>
              <th>تخفیف</th>
              <th>مالیات</th>
              <th>فروشِ خالص</th>
              <th>موجودی</th>
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((r) => (
              <tr key={r.item_id}>
                <td data-label="کد" dir="ltr">{r.item_code || '—'}</td>
                <td className="card-title" data-label="کالا/خدمت">
                  {r.item_name}
                  {r.is_service && <span className="status-badge tone-default">خدمت</span>}
                </td>
                <td data-label="واحد">{r.unit_name || '—'}</td>
                <td className="num" data-label="فروخته">
                  {fa(r.sold_qty)}
                  {r.sold_qty_secondary != null && (
                    <span className="field-hint">
                      {fa(r.sold_qty_secondary)} {r.secondary_unit_name}
                    </span>
                  )}
                </td>
                <td className="num" data-label="برگشت">{fa(r.returned_qty)}</td>
                <td className="num" data-label="خارج‌شده">
                  {r.is_service ? '—' : fa(r.issued_qty)}
                </td>
                <td className="num" data-label="فروخته و نرفته">
                  {r.is_service ? '—' : <GapCell value={r.unissued_qty} />}
                </td>
                <td className="num" data-label="فیِ متوسط">
                  {r.average_unit_price == null ? '—' : faAmount(r.average_unit_price)}
                </td>
                <td className="num" data-label="تخفیف">{faAmount(r.discount)}</td>
                <td className="num" data-label="مالیات">{faAmount(r.tax)}</td>
                <td className="num" data-label="فروشِ خالص">{faAmount(r.net_sales)}</td>
                <td className="num" data-label="موجودی">
                  {r.is_service ? '—' : fa(r.stock_qty)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
      </div>
      <span className="field-hint">
        «فروخته» و «خارج‌شده» دو عددِ مستقل‌اند و هیچ‌کدام از دیگری حساب نمی‌شود؛ ستونِ
        «فروخته و نرفته» اختلافشان است. «موجودی» از دفترِ موجودی می‌آید و «فیِ متوسط»
        از معاملاتِ واقعی — نه از اعلامیه‌ی قیمتِ امروز.
      </span>
    </AsyncBlock>
  )
}

function SalesCustomersView({ token, scope, cacheKey }: ViewProps) {
  const list = useAsync(() => fetchSalesByCustomer(token, scope), [token, cacheKey])
  const rows = list.data ?? []
  const pg = usePagination(rows, 20, cacheKey)
  return (
    <AsyncBlock
      loading={list.loading}
      error={list.error}
      empty={rows.length === 0}
      emptyText="در این بازه فروشی ثبت نشده."
    >
      <div className="table-scroll">
        <table className="cards-on-mobile acc-table">
          <thead>
            <tr>
              <th>مشتری</th>
              <th>گروه</th>
              <th>فاکتور</th>
              <th>فروخته</th>
              <th>خارج‌شده</th>
              <th>ناخالص</th>
              <th>تخفیف</th>
              <th>برگشت</th>
              <th>فروشِ خالص</th>
              <th>سقفِ اعتبار</th>
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((r) => (
              <tr key={r.contact_id ?? 'walk-in'}>
                <td className="card-title" data-label="مشتری">{r.contact_name}</td>
                <td data-label="گروه">{r.group_name || '—'}</td>
                <td className="num" data-label="فاکتور">{faInt(r.invoice_count)}</td>
                <td className="num" data-label="فروخته">{fa(r.sold_qty)}</td>
                <td className="num" data-label="خارج‌شده">{fa(r.issued_qty)}</td>
                <td className="num" data-label="ناخالص">{faAmount(r.gross_amount)}</td>
                <td className="num" data-label="تخفیف">{faAmount(r.discount)}</td>
                <td className="num" data-label="برگشت">{faAmount(r.return_amount)}</td>
                <td className="num" data-label="فروشِ خالص">{faAmount(r.net_sales)}</td>
                <td className="num" data-label="سقفِ اعتبار">
                  {Number(r.credit_limit) > 0 ? faAmount(r.credit_limit) : 'بدون سقف'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
      </div>
      <span className="field-hint">
        این اعداد <strong>فروشِ همین بازه</strong> است، نه ماندهٔ حساب. ماندهٔ طرف حساب —
        که دریافت و پرداخت و اعلامیه را هم می‌بیند — در «مرور جامع طرف حساب» است. و گروهِ
        مشتری از مِسترِ <strong>امروز</strong> خوانده می‌شود، پس اگر مشتری گروهش عوض شده
        باشد فروشِ گذشته‌اش زیرِ گروهِ تازه دیده می‌شود.
      </span>
    </AsyncBlock>
  )
}

function DocumentsTable({ rows, cacheKey, voided }: { rows: SalesReviewDocument[]; cacheKey: string; voided?: boolean }) {
  const pg = usePagination(rows, 20, cacheKey)
  return (
    <div className="table-scroll">
      <table className="cards-on-mobile acc-table">
        <thead>
          <tr>
            <th>شماره</th>
            <th>تاریخ</th>
            <th>مشتری</th>
            <th>نوع فروش</th>
            <th>ردیف</th>
            <th>فروخته</th>
            <th>خارج‌شده</th>
            <th>ناخالص</th>
            <th>تخفیف</th>
            <th>مالیات</th>
            <th>برگشت</th>
            <th>فروشِ خالص</th>
          </tr>
        </thead>
        <tbody>
          {pg.pageItems.map((r) => (
            <tr key={r.source_id} className={r.is_voided ? 'acc-row--void' : ''}>
              <td className="card-title" data-label="شماره">{r.number != null ? fa(r.number) : '—'}</td>
              <td data-label="تاریخ">{formatJalali(r.document_date)}</td>
              <td data-label="مشتری">{r.contact_name}</td>
              <td data-label="نوع فروش">{r.sale_type_name || '—'}</td>
              <td className="num" data-label="ردیف">{faInt(r.line_count)}</td>
              <td className="num" data-label="فروخته">{fa(r.sold_qty)}</td>
              <td className="num" data-label="خارج‌شده">{fa(r.issued_qty)}</td>
              <td className="num" data-label="ناخالص">{faAmount(r.gross_amount)}</td>
              <td className="num" data-label="تخفیف">{faAmount(r.discount)}</td>
              <td className="num" data-label="مالیات">{faAmount(r.tax)}</td>
              <td className="num" data-label="برگشت">{faAmount(r.return_amount)}</td>
              <td className="num" data-label="فروشِ خالص">
                {voided ? '—' : faAmount(r.net_sales)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
    </div>
  )
}

function SalesDocumentsView({ token, scope, cacheKey }: ViewProps) {
  const list = useAsync(() => fetchSalesReviewDocuments(token, scope), [token, cacheKey])
  const rows = list.data ?? []
  return (
    <AsyncBlock
      loading={list.loading}
      error={list.error}
      empty={rows.length === 0}
      emptyText="در این بازه سندی ثبت نشده."
    >
      <DocumentsTable rows={rows} cacheKey={cacheKey} />
      <span className="field-hint">
        مبلغِ هر سند از جمعِ ردیف‌های خودش می‌آید — فاکتورِ سه‌ردیفی یک سند است و یک بار
        شمرده می‌شود. برای دیدنِ ردیف‌ها به نمای «اقلام فروش» بروید؛ آن دو با هم
        <strong> جمع نمی‌شوند</strong>.
      </span>
    </AsyncBlock>
  )
}

function SalesVoidedView({ token, scope, cacheKey }: ViewProps) {
  const list = useAsync(
    () => fetchSalesReviewDocuments(token, { ...scope, voided: true }),
    [token, cacheKey],
  )
  const rows = list.data ?? []
  return (
    <AsyncBlock
      loading={list.loading}
      error={list.error}
      empty={rows.length === 0}
      emptyText="در این بازه فاکتوری باطل نشده."
    >
      <DocumentsTable rows={rows} cacheKey={`v${cacheKey}`} voided />
      <span className="field-hint">
        این فاکتورها در <strong>هیچ نمای دیگری</strong> شمرده نمی‌شوند — نه در فروشِ خالص،
        نه در کالا و مشتری. ولی تاریخ پاک نمی‌شود: «فاکتوری بود و باطل شد» خودش یک واقعیتِ
        حسابرسی است.
      </span>
    </AsyncBlock>
  )
}

function SalesLinesView({ token, scope, cacheKey }: ViewProps) {
  const list = useAsync(() => fetchSalesReviewLines(token, scope), [token, cacheKey])
  const rows = list.data ?? []
  const pg = usePagination(rows, 25, cacheKey)
  return (
    <AsyncBlock
      loading={list.loading}
      error={list.error}
      empty={rows.length === 0}
      emptyText="در این بازه قلمی ثبت نشده."
    >
      <div className="table-scroll">
        <table className="cards-on-mobile acc-table">
          <thead>
            <tr>
              <th>سند</th>
              <th>تاریخ</th>
              <th>مشتری</th>
              <th>کالا/خدمت</th>
              <th>بارکد</th>
              <th>انبار</th>
              <th>فروخته</th>
              <th>خارج‌شده</th>
              <th>برگشت</th>
              <th>فی</th>
              <th>خالص</th>
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((r) => (
              <tr key={r.line_id} className={r.is_voided ? 'acc-row--void' : ''}>
                <td className="card-title" data-label="سند">{r.number != null ? fa(r.number) : '—'}</td>
                <td data-label="تاریخ">{formatJalali(r.document_date)}</td>
                <td data-label="مشتری">{r.contact_name}</td>
                <td className="card-wide" data-label="کالا/خدمت">{r.item_name}</td>
                <td data-label="بارکد" dir="ltr">{r.barcode || '—'}</td>
                <td data-label="انبار">
                  {r.warehouse_names.length ? r.warehouse_names.join('، ') : '—'}
                </td>
                <td className="num" data-label="فروخته">
                  {fa(r.sold_qty)}
                  {r.sold_qty_secondary != null && (
                    <span className="field-hint">{fa(r.sold_qty_secondary)}</span>
                  )}
                </td>
                <td className="num" data-label="خارج‌شده">{fa(r.issued_qty)}</td>
                <td className="num" data-label="برگشت">{fa(r.returned_qty)}</td>
                <td className="num" data-label="فی">{faAmount(r.unit_price)}</td>
                <td className="num" data-label="خالص">{faAmount(r.net_sales)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
      </div>
      <span className="field-hint">
        ستونِ «انبار» از <strong>سندِ خروج</strong> می‌آید نه از سربرگِ فاکتور — پس یک قلم
        می‌تواند چند انبار داشته باشد، و قلمی که هنوز نرفته خط تیره است.
      </span>
    </AsyncBlock>
  )
}

function SalesWarehousesView({ token, scope, cacheKey }: ViewProps) {
  const list = useAsync(() => fetchSalesByWarehouse(token, scope), [token, cacheKey])
  const rows = list.data ?? []
  return (
    <AsyncBlock
      loading={list.loading}
      error={list.error}
      empty={rows.length === 0}
      emptyText="در این بازه خروجی بابتِ فروش ثبت نشده."
    >
      <div className="table-scroll">
        <table className="cards-on-mobile acc-table">
          <thead>
            <tr>
              <th>انبار</th>
              <th>سندِ خروج</th>
              <th>فاکتور</th>
              <th>مقدارِ خارج‌شده</th>
              <th>بهای تمام‌شده</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.warehouse_id}>
                <td className="card-title" data-label="انبار">{r.warehouse_name}</td>
                <td className="num" data-label="سندِ خروج">{faInt(r.issue_count)}</td>
                <td className="num" data-label="فاکتور">{faInt(r.invoice_count)}</td>
                <td className="num" data-label="مقدارِ خارج‌شده">{fa(r.issued_qty)}</td>
                <td className="num" data-label="بهای تمام‌شده">{faAmount(r.issued_cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <span className="field-hint">
        این نما <strong>دفترِ موجودی نیست</strong> و ماندهٔ انبار را نگه نمی‌دارد؛ فقط
        می‌گوید بابتِ فروشِ این بازه از هر انبار چه‌قدر خارج شده. ماندهٔ انبار در «انبار ←
        موجودی» است.
      </span>
    </AsyncBlock>
  )
}

function PreinvoiceProgressView({ token, scope, cacheKey }: ViewProps) {
  const list = useAsync(() => fetchPreinvoiceProgress(token, scope), [token, cacheKey])
  const rows = list.data ?? []
  const pg = usePagination(rows, 20, cacheKey)
  return (
    <AsyncBlock
      loading={list.loading}
      error={list.error}
      empty={rows.length === 0}
      emptyText="در این بازه پیش‌فاکتوری ثبت نشده."
    >
      <div className="table-scroll">
        <table className="cards-on-mobile acc-table">
          <thead>
            <tr>
              <th>شماره</th>
              <th>تاریخ</th>
              <th>مشتری</th>
              <th>وضعیت</th>
              <th>کالا/خدمت</th>
              <th>پیشنهادشده</th>
              <th>فاکتورشده</th>
              <th>خارج‌شده</th>
              <th>ماندهٔ فاکتورشدنی</th>
              <th>ماندهٔ ارسالی</th>
            </tr>
          </thead>
          <tbody>
            {pg.pageItems.map((r) => (
              <tr key={r.line_id}>
                <td className="card-title" data-label="شماره">{r.number != null ? fa(r.number) : '—'}</td>
                <td data-label="تاریخ">{formatJalali(r.quotation_date)}</td>
                <td data-label="مشتری">{r.contact_name}</td>
                <td data-label="وضعیت">
                  <span className="status-badge tone-default">{r.status}</span>
                </td>
                <td className="card-wide" data-label="کالا/خدمت">{r.item_name}</td>
                <td className="num" data-label="پیشنهادشده">{fa(r.quoted_qty)}</td>
                <td className="num" data-label="فاکتورشده">{fa(r.invoiced_qty)}</td>
                <td className="num" data-label="خارج‌شده">{fa(r.issued_qty)}</td>
                <td className="num" data-label="ماندهٔ فاکتورشدنی">
                  <GapCell value={r.remaining_invoiceable} />
                </td>
                <td className="num" data-label="ماندهٔ ارسالی">
                  <GapCell value={r.remaining_issueable} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
      </div>
      <span className="field-hint">
        <strong>وضعیتِ سند و پیشرفتِ تحقق دو چیزند:</strong> پیش‌فاکتوری می‌تواند
        «تأییدشده» باشد و هنوز هیچ فاکتوری نخورده باشد. هر سه مقدار مستقل‌اند و
        «فاکتورشده»/«خارج‌شده» هیچ‌جا ذخیره نمی‌شوند — از تخصیص‌های واقعی مشتق می‌شوند.
      </span>
    </AsyncBlock>
  )
}

// ═════════ ۸ و ۱۷) صورت‌حساب و مرورِ جامعِ طرف حساب ═════════

/** انتخاب‌گرِ مشترکِ طرف حساب — «صورت‌حساب»، «مرور جامع»، «مرور فروش» و
 *  «فاکتورهای فروش» همه همین را می‌خواهند. صادر شده تا نسخه‌ی دومی ساخته نشود. */
export function ContactPicker({
  contacts,
  value,
  onChange,
}: {
  contacts: ContactRecord[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label className="acc-inline-field">
      طرف حساب
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">— انتخاب کنید —</option>
        {contacts.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </label>
  )
}

export function ContactStatementPage({ token }: { token: string }) {
  const contacts = useContacts(token)
  const range = useRange('year')
  const [contactId, setContactId] = useState('')

  const entries = useAsync(
    () =>
      contactId
        ? fetchJournalEntriesFiltered(token, { dateFrom: range.from, dateTo: range.to, limit: 200 })
        : Promise.resolve([]),
    [token, contactId, range.from, range.to],
  )
  const invoices = useAsync(
    () =>
      contactId
        ? fetchSalesInvoices(token)
        : Promise.resolve([]),
    [token, contactId, range.from, range.to],
  )
  const mine = (invoices.data ?? []).filter(
    (i) => i.contact_id === contactId && !i.voided_at && inRange(i.invoice_date, range.from, range.to),
  )
  const pg = usePagination(mine, 20, contactId + range.from + range.to)
  const total = mine.reduce((s, i) => s + Number(i.total_amount || 0) + Number(i.tax_amount || 0), 0)

  return (
    <OpsPage
      icon={ClipboardList}
      title="صورت حساب طرف مقابل"
      description="گردشِ فاکتورهای یک طرف حساب در یک بازه، با جمعِ قابلِ پرداخت."
      head={
        <div className="cc-head">
          <RangeBar range={range} extra={<ContactPicker contacts={contacts} value={contactId} onChange={setContactId} />} />
          <div className="cc-summary">
            <Metric icon={<ClipboardList size={14} />} label="فاکتور" value={faInt(mine.length)} />
            <Metric icon={<TrendingUp size={14} />} label="جمعِ با مالیات" value={faAmount(total)} tone="in" />
          </div>
        </div>
      }
    >
      <SectionCard icon={ClipboardList} title="گردشِ فاکتورها" description="فاکتورهای باطل‌شده نمی‌آیند.">
        {!contactId ? (
          <EmptyState icon={Users} text="یک طرف حساب انتخاب کنید تا صورت‌حسابش نشان داده شود." />
        ) : (
          <AsyncBlock
            loading={invoices.loading || entries.loading}
            error={invoices.error}
            empty={mine.length === 0}
            emptyText="در این بازه فاکتوری برای این طرف حساب نیست."
          >
            <div className="table-scroll">
              <table className="cards-on-mobile acc-table">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>تاریخ</th>
                    <th>خالص</th>
                    <th>مالیات</th>
                    <th>قابلِ پرداخت</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((i) => (
                    <tr key={i.id}>
                      <td className="card-title" data-label="شماره">
                        {fa(i.number ?? 0)}
                      </td>
                      <td data-label="تاریخ">{formatJalali(i.invoice_date)}</td>
                      <td className="num" data-label="خالص">
                        {faAmount(i.total_amount)}
                      </td>
                      <td className="num" data-label="مالیات">
                        {faAmount(i.tax_amount)}
                      </td>
                      <td className="num" data-label="قابلِ پرداخت">
                        {faAmount(Number(i.total_amount || 0) + Number(i.tax_amount || 0))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          </AsyncBlock>
        )}
      </SectionCard>
    </OpsPage>
  )
}

/**
 * مرور جامع طرف حساب — سه سطح، و هیچ‌کدام از دیگری ساخته نمی‌شود.
 *
 * تا امروز این صفحه فقط **فاکتورهای فروش** را نشان می‌داد، و برای فیلترکردنشان
 * کلِ فاکتورهای فروشِ کسب‌وکار را به مرورگر می‌کشید. نه مانده‌ای داشت، نه سمتِ
 * تأمین‌کننده، نه خطِ زمانی.
 *
 * سه سطح عمداً سه درخواستِ جدا دارند: اگر یک پاسخِ واحد همه را می‌داد، رابط
 * وادار می‌شد اقلام را جمع بزند تا خلاصه دربیاورد — و همان‌جاست که یک مبلغ
 * چند بار شمرده می‌شود.
 */
export function ContactOverviewPage({ token }: { token: string }) {
  const contacts = useContacts(token)
  const range = useRange('year')
  const [contactId, setContactId] = useState('')
  const [role, setRole] = useState<'' | 'customer' | 'supplier'>('')
  const [open, setOpen] = useState<{ type: string; id: string } | null>(null)
  const picked = contacts.find((c) => c.id === contactId)

  const summary = useAsync(
    () => (contactId ? fetchCounterpartySummary(token, contactId) : Promise.resolve(null)),
    [token, contactId],
  )
  const events = useAsync(
    () =>
      contactId
        ? fetchCounterpartyEvents(token, contactId, {
            from: range.from,
            to: range.to,
            role: role || undefined,
          })
        : Promise.resolve([]),
    [token, contactId, range.from, range.to, role],
  )
  const lines = useAsync(
    () =>
      contactId && open
        ? fetchCounterpartyEventLines(token, contactId, open.type, open.id)
        : Promise.resolve(null),
    [token, contactId, open?.type, open?.id],
  )

  const rows = events.data ?? []
  const pg = usePagination(rows, 20, `${contactId}${range.from}${range.to}${role}`)
  const sum = summary.data

  return (
    <OpsPage
      icon={Users}
      title="مرور جامع طرف حساب"
      description="مانده‌ی هر نقش، خطِ زمانیِ رویدادها، و اقلامِ هر سند — همه از دفتر، در یک صفحه."
      head={
        <div className="cc-head">
          <RangeBar
            range={range}
            extra={
              <>
                <ContactPicker contacts={contacts} value={contactId} onChange={setContactId} />
                <label className="acc-inline-field">
                  نقش
                  <select value={role} onChange={(e) => setRole(e.target.value as typeof role)}>
                    <option value="">همه</option>
                    <option value="customer">مشتری</option>
                    <option value="supplier">تأمین‌کننده</option>
                  </select>
                </label>
              </>
            }
          />
          {sum && (
            <div className="cc-summary">
              {sum.positions.map((p) => (
                <Metric
                  key={p.role}
                  icon={p.role === 'customer' ? <TrendingUp size={14} /> : <Wallet size={14} />}
                  label={p.role_label}
                  value={faAmount(p.net)}
                  tone={Number(p.net) >= 0 ? 'in' : 'out'}
                />
              ))}
              <Metric icon={<Scale size={14} />} label="مانده کل" value={faAmount(sum.total_net)} />
              {Number(sum.uncleared_cheques) > 0 && (
                <Metric
                  icon={<ClipboardList size={14} />}
                  label="چکِ وصول‌نشده"
                  value={faAmount(sum.uncleared_cheques)}
                />
              )}
            </div>
          )}
        </div>
      }
    >
      {!contactId ? (
        <SectionCard icon={Users} title="طرف حساب" description="یکی را انتخاب کنید.">
          <EmptyState icon={Users} text="برای دیدنِ مرورِ جامع، یک طرف حساب انتخاب کنید." />
        </SectionCard>
      ) : (
        <>
          {/* ── سطحِ ۱: نقش‌ها ───────────────────────────────────────────── */}
          <SectionCard
            icon={Scale}
            title="مانده به تفکیکِ نقش"
            description={`${picked?.name ?? ''} — طلبِ ما از او و بدهیِ ما به او دو عددِ جدا می‌مانند.`}
          >
            <AsyncBlock
              loading={summary.loading}
              error={summary.error}
              empty={!sum || sum.positions.length === 0}
              emptyText="هیچ معینِ طرف مقابلی در چارت پیدا نشد."
            >
              <div className="table-scroll">
                <table className="cards-on-mobile acc-table">
                  <thead>
                    <tr>
                      <th>نقش</th>
                      <th>حساب معین</th>
                      <th>بدهکار</th>
                      <th>بستانکار</th>
                      <th>مانده</th>
                      <th>ماندهٔ قابل تسویه</th>
                      <th>ماندهٔ دفتری</th>
                      <th>بی‌سند</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(sum?.positions ?? []).map((p) => (
                      <tr key={p.role}>
                        <td className="card-title" data-label="نقش">
                          {p.role_label}
                        </td>
                        <td data-label="حساب معین">
                          <span dir="ltr">{p.account_code}</span> — {p.account_name}
                        </td>
                        <td className="num" data-label="بدهکار">
                          {faAmount(p.debit_total)}
                        </td>
                        <td className="num" data-label="بستانکار">
                          {faAmount(p.credit_total)}
                        </td>
                        <td className="num" data-label="مانده">
                          {faAmount(p.net)}
                        </td>
                        <td className="num" data-label="ماندهٔ قابل تسویه">
                          {faAmount(p.open_net)}
                        </td>
                        <td className="num" data-label="ماندهٔ دفتری">
                          {p.ledger_net == null ? '—' : faAmount(p.ledger_net)}
                        </td>
                        <td className="num" data-label="بی‌سند">
                          {p.unattributed == null ? '—' : faAmount(p.unattributed)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {sum && !sum.has_analytic && (
                <span className="field-hint">
                  این طرف حساب کدِ تفصیلی ندارد، پس ماندهٔ دفتریِ شخصی‌اش قابلِ استخراج نیست و
                  ستونش خط تیره می‌ماند. «مانده» از اسنادِ خودش حساب می‌شود.
                </span>
              )}
              {sum?.positions.some((p) => p.unattributed != null && Number(p.unattributed) !== 0) && (
                <span className="field-hint">
                  ستونِ «بی‌سند» یعنی گردشی روی آن معین هست که سندِ شناخته‌شده‌ای پشتش نیست —
                  معمولاً سندِ دستی یا ماندهٔ اول دوره. پنهان نمی‌شود تا معلوم باشد اختلافِ
                  گزارش و دفتر از کجاست.
                </span>
              )}
            </AsyncBlock>
          </SectionCard>

          {/* ── سطحِ ۲: رویدادها ─────────────────────────────────────────── */}
          <SectionCard
            icon={ClipboardList}
            title="رویدادها"
            description={`${faInt(rows.length)} رویداد — فاکتور، دریافت، پرداخت و اعلامیه در یک خطِ زمانی. روی هر ردیف بزنید تا اقلامش را ببینید.`}
          >
            <AsyncBlock
              loading={events.loading}
              error={events.error}
              empty={rows.length === 0}
              emptyText="در این بازه رویدادی برای این طرف حساب ثبت نشده."
            >
              <div className="table-scroll">
                <table className="cards-on-mobile acc-table">
                  <thead>
                    <tr>
                      <th>تاریخ</th>
                      <th>نوع</th>
                      <th>شماره</th>
                      <th>نقش</th>
                      <th>سند حسابداری</th>
                      <th>بدهکار</th>
                      <th>بستانکار</th>
                      <th>ارز</th>
                      <th>ماندهٔ در خط</th>
                      <th>تسویه</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {pg.pageItems.map((e) => {
                      const isOpen = open?.type === e.source_type && open?.id === e.source_id
                      return (
                        <tr key={`${e.source_type}-${e.source_id}`} className={isOpen ? 'row-open' : undefined}>
                          <td data-label="تاریخ">{formatJalali(e.document_date)}</td>
                          <td className="card-title" data-label="نوع">
                            {e.label}
                          </td>
                          <td data-label="شماره">{e.number != null ? fa(e.number) : '—'}</td>
                          <td data-label="نقش">{e.role_label}</td>
                          <td data-label="سند حسابداری">
                            {e.entry_number != null ? fa(e.entry_number) : '—'}
                          </td>
                          <td className="num" data-label="بدهکار">
                            {e.side === 'debit' ? faAmount(e.document_amount) : '—'}
                          </td>
                          <td className="num" data-label="بستانکار">
                            {e.side === 'credit' ? faAmount(e.document_amount) : '—'}
                          </td>
                          <td data-label="ارز">
                            {e.fx_amount == null ? (
                              '—'
                            ) : (
                              <>
                                {faAmount(e.fx_amount)} <span dir="ltr">{e.currency_code}</span>
                              </>
                            )}
                          </td>
                          <td className="num" data-label="ماندهٔ در خط">
                            {faAmount(e.running_balance)}
                          </td>
                          <td data-label="تسویه">
                            <span
                              className={`status-badge ${
                                e.status === 'settled' ? 'tone-success' : e.status === 'over' ? 'tone-danger' : 'tone-default'
                              }`}
                            >
                              {e.status_label}
                            </span>
                          </td>
                          <td className="card-actions">
                            <button
                              type="button"
                              className="btn-ghost"
                              onClick={() =>
                                setOpen(isOpen ? null : { type: e.source_type, id: e.source_id })
                              }
                            >
                              {isOpen ? 'بستنِ اقلام' : 'اقلام'}
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
              </div>
              <span className="field-hint">
                سندِ حسابداریِ هر رویداد ردیفِ جدا نمی‌گیرد و شماره‌اش روی همان ردیف می‌نشیند —
                وگرنه فاکتور و سندش دو اثرِ مستقل به نظر می‌رسیدند و مانده دو برابر می‌شد.
              </span>
            </AsyncBlock>
          </SectionCard>

          {/* ── سطحِ ۳: اقلام ────────────────────────────────────────────── */}
          {open && (
            <SectionCard
              icon={Layers}
              title="اقلامِ سند"
              description={lines.data?.label ?? 'در حال بارگذاری…'}
              actions={
                <button type="button" className="btn-ghost" onClick={() => setOpen(null)}>
                  بستن
                </button>
              }
            >
              <AsyncBlock
                loading={lines.loading}
                error={lines.error}
                empty={(lines.data?.lines.length ?? 0) === 0}
                emptyText="این سند قلمی برای نمایش ندارد."
              >
                <div className="table-scroll">
                  <table className="cards-on-mobile acc-table">
                    <thead>
                      <tr>
                        <th>نوع قلم</th>
                        <th>کد</th>
                        <th>عنوان</th>
                        <th>شرح</th>
                        <th>تعداد</th>
                        <th>فی</th>
                        <th>فیِ خالص</th>
                        <th>بدهکار</th>
                        <th>بستانکار</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(lines.data?.lines ?? []).map((l, i) => (
                        <tr key={`${l.kind}-${l.seq}-${i}`}>
                          <td className="card-title" data-label="نوع قلم">
                            {LINE_KIND_LABELS[l.kind] ?? l.kind}
                          </td>
                          <td data-label="کد" dir="ltr">
                            {l.code || '—'}
                          </td>
                          <td className="card-wide" data-label="عنوان">
                            {l.title}
                          </td>
                          <td className="card-wide" data-label="شرح">
                            {l.description || '—'}
                          </td>
                          <td className="num" data-label="تعداد">
                            {l.quantity == null ? '—' : fa(l.quantity)}
                          </td>
                          <td className="num" data-label="فی">
                            {l.unit_price == null ? '—' : faAmount(l.unit_price)}
                          </td>
                          <td className="num" data-label="فیِ خالص">
                            {l.net_unit_price == null ? '—' : faAmount(l.net_unit_price)}
                          </td>
                          <td className="num" data-label="بدهکار">
                            {l.debit == null ? '—' : faAmount(l.debit)}
                          </td>
                          <td className="num" data-label="بستانکار">
                            {l.credit == null ? '—' : faAmount(l.credit)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <span className="field-hint">
                  ستونی که برای یک قلم معنی ندارد خط تیره می‌ماند، نه صفر: «فی» برای ردیفِ
                  کالا معنی دارد و برای ردیفِ دفتر یا چک نه. و <strong>جمعِ ردیف‌های کالا با
                  ردیف‌های دفتر اثرِ اقتصادی نیست</strong> — اثر همان ردیف‌های دفتر است.
                </span>
              </AsyncBlock>
            </SectionCard>
          )}
        </>
      )}
    </OpsPage>
  )
}

/** برچسبِ نوعِ قلم — اقلامِ یک سند همه از یک جنس نیستند. */
const LINE_KIND_LABELS: Record<string, string> = {
  product: 'کالا/خدمت',
  journal: 'ردیف سند',
  adjustment: 'تعدیل',
}

// ═════════════════ کمکی: پیشنهادِ قیمت (برای فرمِ فاکتور) ═════════════════

/** نمایشِ «این قیمت از کجا آمد» — در فرمِ فاکتور کنارِ ردیف می‌نشیند. */
export function PricingHint({
  token,
  itemId,
  qty,
}: {
  token: string
  itemId: string
  qty: number
}) {
  const [hint, setHint] = useState<{ net: string; applied: { kind: string; name: string; value: string }[] } | null>(
    null,
  )
  useEffect(() => {
    if (!itemId || qty <= 0) {
      setHint(null)
      return
    }
    fetchPricingSuggestion(token, itemId, qty)
      .then((s) => setHint(s.applied.length ? { net: s.net, applied: s.applied } : null))
      .catch(() => setHint(null))
  }, [token, itemId, qty])

  if (!hint) return null
  return (
    <span className="field-hint">
      پیشنهاد: {faAmount(hint.net)} — {hint.applied.map((a) => a.name).join('، ')}
    </span>
  )
}

export type { PricingFactor }
