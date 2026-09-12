import { useEffect, useMemo, useState } from 'react'
import {
  BadgePercent,
  Boxes,
  Calculator,
  ClipboardList,
  FileSpreadsheet,
  Layers,
  Lock,
  Percent,
  PlusCircle,
  Route,
  Search,
  Ship,
  Tags,
  TrendingUp,
  Undo2,
  Users,
  Wallet,
} from 'lucide-react'
import {
  closeInvoices,
  createBundle,
  createCommissionRule,
  createCommissionRun,
  createCustoms,
  createDiscountGroup,
  createNote,
  createPriceAnnouncement,
  createPricingFactor,
  createSaleType,
  createSalesReturnReason,
  fetchCommissionPreview,
  fetchCommissionRules,
  fetchContacts,
  fetchDiscountGroups,
  fetchItemsLive,
  fetchJournalEntriesFiltered,
  fetchMembers,
  fetchPricingSuggestion,
  fetchSalesInvoices,
  fetchSalesReturnReasons,
  fetchSalesSummary,
  updateSalesReturnReason,
  type ContactRecord,
  type ItemRecord,
  type PricingFactor,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { EmptyState } from '../../components/EmptyState'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, todayIso } from '../../lib/jalali'
import {
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
    body: 'فاکتور فروش بزنید. موجودیِ انبار و سند حسابداری همان لحظه خودکار ثبت می‌شوند.',
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

export function CreditDebitNotePage({ token }: { token: string }) {
  const contacts = useContacts(token)
  const { msg, submitting, run } = useSubmit()
  const [kind, setKind] = useState<'debit' | 'credit'>('debit')
  const [noteDate, setNoteDate] = useState(todayIso())
  const [contactId, setContactId] = useState('')
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="اعلامیه بدهکار بستانکار"
      description="تعدیلِ حسابِ طرف مقابل بیرون از فاکتور. برخلافِ بقیه‌ی تعریف‌های این ماژول، این یکی سند حسابداری می‌زند."
    >
      <FormCard
        icon={FileSpreadsheet}
        title="صدور اعلامیه"
        description="بدهکار = طرف به شما بدهکارتر می‌شود. بستانکار = طلبِ شما کم می‌شود."
        msg={msg}
        submitting={submitting}
        submitLabel="صدور و ثبتِ سند"
        disabled={!contactId || !Number(amount)}
        onSubmit={() =>
          void run(async () => {
            await createNote(token, {
              kind,
              note_date: noteDate,
              contact_id: contactId,
              amount: Number(amount),
              reason,
            })
            setAmount('')
            setReason('')
          }, 'اعلامیه صادر و سندش ثبت شد.')
        }
      >
        <label>
          نوعِ اعلامیه
          <select value={kind} onChange={(e) => setKind(e.target.value as 'debit' | 'credit')}>
            <option value="debit">بدهکار — بدهیِ طرف بیشتر می‌شود</option>
            <option value="credit">بستانکار — طلبِ ما کمتر می‌شود</option>
          </select>
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={noteDate} onChange={setNoteDate} />
        </label>
        <label>
          طرف حساب
          <select value={contactId} onChange={(e) => setContactId(e.target.value)}>
            <option value="">— انتخاب کنید —</option>
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
          علت
          <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} />
        </label>
      </FormCard>
    </OpsPage>
  )
}

// ═════════════════════ ۱۰) نوع فروش ═════════════════════

export function SaleTypePage({ token }: { token: string }) {
  const { msg, submitting, run } = useSubmit()
  const [name, setName] = useState('')
  const [dueDays, setDueDays] = useState('0')
  const [taxRate, setTaxRate] = useState('')
  const [description, setDescription] = useState('')

  return (
    <OpsPage
      icon={Tags}
      title="نوع فروش"
      description="نقدی، اعتباری، امانی، صادراتی… هر نوع مهلتِ تسویه و نرخِ مالیاتِ پیش‌فرضِ خودش را دارد."
    >
      <FormCard
        icon={Tags}
        title="تعریفِ نوعِ فروش"
        description="این‌ها هنگامِ انتخابِ نوع در فاکتور، خودکار پیشنهاد می‌شوند."
        msg={msg}
        submitting={submitting}
        disabled={!name.trim()}
        onSubmit={() =>
          void run(async () => {
            await createSaleType(token, {
              name: name.trim(),
              due_days: Number(dueDays) || 0,
              default_tax_rate: taxRate ? taxRate : null,
              description,
              is_active: true,
            })
            setName('')
            setDueDays('0')
            setTaxRate('')
            setDescription('')
          }, 'نوعِ فروش ثبت شد.')
        }
      >
        <label>
          نام
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
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
      </FormCard>
    </OpsPage>
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

export function PriceAnnouncementPage({ token }: { token: string }) {
  const items = useItems(token)
  const { msg, submitting, run } = useSubmit()
  const [name, setName] = useState('')
  const [effectiveFrom, setEffectiveFrom] = useState(todayIso())
  const [notes, setNotes] = useState('')
  const [prices, setPrices] = useState<Record<string, string>>({})
  const [search, setSearch] = useState('')

  const shown = useMemo(() => {
    const t = search.trim()
    const base = t ? items.filter((i) => i.name.includes(t) || i.sku.includes(t)) : items
    return base.slice(0, 60)
  }, [items, search])
  const filled = Object.entries(prices).filter(([, v]) => Number(v) > 0)

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="اعلامیه قیمت"
      description="قیمتِ کالاها با تاریخِ اجرا. اعلامیه‌ی تازه کنارِ قبلی می‌نشیند، نه به‌جایش — تا فاکتورهای گذشته قابلِ توضیح بمانند."
    >
      <FormCard
        icon={FileSpreadsheet}
        title="اعلامیه‌ی تازه"
        description="فقط کالاهایی که قیمت وارد کرده‌اید ثبت می‌شوند."
        msg={msg}
        submitting={submitting}
        submitLabel={`ثبتِ اعلامیه (${faInt(filled.length)} کالا)`}
        disabled={!name.trim() || filled.length === 0}
        onSubmit={() =>
          void run(async () => {
            await createPriceAnnouncement(token, {
              name: name.trim(),
              effective_from: effectiveFrom,
              notes,
              is_active: true,
              lines: filled.map(([item_id, v]) => ({ item_id, price: Number(v) })),
            })
            setName('')
            setNotes('')
            setPrices({})
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
        <label>
          جست‌وجوی کالا
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="نام یا کدِ کالا" />
        </label>
      </FormCard>

      <SectionCard icon={Boxes} title="قیمت‌ها" description="قیمتِ کالاهایی که در این اعلامیه می‌آیند">
        {shown.length === 0 ? (
          <EmptyState icon={Boxes} text="کالایی با این جست‌وجو نیست." />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>نام</th>
                  <th>قیمتِ فعلی</th>
                  <th>قیمتِ تازه</th>
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
                    <td className="num" data-label="قیمتِ فعلی">
                      {faAmount(i.sales_price)}
                    </td>
                    <td data-label="قیمتِ تازه">
                      <NumberInput
                        value={prices[i.id] ?? ''}
                        onChange={(v) => setPrices((p) => ({ ...p, [i.id]: v }))}
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

export function SalesBrowsePage({ token }: { token: string }) {
  const range = useRange('month')
  const names = useContactNames(token)
  const summary = useAsync(() => fetchSalesSummary(token), [token])
  const invoices = useAsync(() => fetchSalesInvoices(token), [token])
  const [search, setSearch] = useState('')

  const rows = useMemo(() => {
    const t = search.trim()
    const base = (invoices.data ?? []).filter((i) => inRange(i.invoice_date, range.from, range.to))
    if (!t) return base
    return base.filter(
      (i) => (names.get(i.contact_id ?? '') ?? '').includes(t) || String(i.number ?? '').includes(t),
    )
  }, [invoices.data, search, names, range.from, range.to])
  const pg = usePagination(rows, 20, `${range.from}${range.to}${search}`)
  const net = rows.reduce((s, i) => s + Number(i.total_amount || 0), 0)
  const closed = rows.filter((i) => i.closed_at).length

  return (
    <OpsPage
      icon={TrendingUp}
      title="مرور فروش"
      description="تصویرِ کلیِ فروش در یک بازه — شاخص‌ها و فهرستِ فاکتورها با جست‌وجو."
      head={
        <div className="cc-head">
          <RangeBar range={range} />
          <div className="cc-summary">
            <Metric icon={<ClipboardList size={14} />} label="فاکتور" value={faInt(rows.length)} />
            <Metric icon={<TrendingUp size={14} />} label="خالصِ بازه" value={faAmount(net)} tone="in" />
            <Metric icon={<Lock size={14} />} label="بسته‌شده" value={faInt(closed)} />
            <Metric
              icon={<Wallet size={14} />}
              label="سودِ ناخالصِ کل"
              value={faAmount(summary.data?.gross_profit ?? 0)}
              tone="in"
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={TrendingUp} title="فاکتورهای بازه" description={`${faInt(rows.length)} فاکتور`}>
        <div className="acc-filters">
          <label className="acc-search">
            <Search size={14} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="شماره یا نامِ طرف حساب"
            />
          </label>
        </div>
        <AsyncBlock
          loading={invoices.loading}
          error={invoices.error}
          empty={rows.length === 0}
          emptyText="فاکتوری با این شرایط پیدا نشد."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>تاریخ</th>
                  <th>طرف حساب</th>
                  <th>خالص</th>
                  <th>مالیات</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((i) => (
                  <tr key={i.id} className={i.voided_at ? 'acc-row--void' : ''}>
                    <td className="card-title" data-label="شماره">
                      {fa(i.number ?? 0)}
                    </td>
                    <td data-label="تاریخ">{formatJalali(i.invoice_date)}</td>
                    <td data-label="طرف حساب">{names.get(i.contact_id ?? '') ?? '—'}</td>
                    <td className="num" data-label="خالص">
                      {faAmount(i.total_amount)}
                    </td>
                    <td className="num" data-label="مالیات">
                      {faAmount(i.tax_amount)}
                    </td>
                    <td data-label="وضعیت">
                      <span
                        className={`status-badge ${
                          i.voided_at ? 'tone-danger' : i.closed_at ? 'tone-default' : 'tone-success'
                        }`}
                      >
                        {i.voided_at ? 'باطل' : i.closed_at ? 'بسته' : 'باز'}
                      </span>
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

// ═════════ ۸ و ۱۷) صورت‌حساب و مرورِ جامعِ طرف حساب ═════════

/** هر دو صفحه یک طرف‌حساب را می‌خواهند؛ انتخاب‌گرِ مشترک. */
function ContactPicker({
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

export function ContactOverviewPage({ token }: { token: string }) {
  const contacts = useContacts(token)
  const [contactId, setContactId] = useState('')
  const picked = contacts.find((c) => c.id === contactId)

  const invoices = useAsync(
    () => (contactId ? fetchSalesInvoices(token) : Promise.resolve([])),
    [token, contactId],
  )
  const mine = (invoices.data ?? []).filter((i) => i.contact_id === contactId)
  const live = mine.filter((i) => !i.voided_at)
  const net = live.reduce((s, i) => s + Number(i.total_amount || 0), 0)
  const tax = live.reduce((s, i) => s + Number(i.tax_amount || 0), 0)
  const last = live.length ? live.map((i) => i.invoice_date).sort().at(-1) : null

  return (
    <OpsPage
      icon={Users}
      title="مرور جامع طرف حساب"
      description="همه‌چیزِ یک طرف حساب در یک صفحه — مشخصات، سقفِ اعتبار، و خلاصه‌ی خرید."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <ContactPicker contacts={contacts} value={contactId} onChange={setContactId} />
          </div>
          {picked && (
            <div className="cc-summary">
              <Metric icon={<ClipboardList size={14} />} label="فاکتور" value={faInt(live.length)} />
              <Metric icon={<TrendingUp size={14} />} label="خالصِ خرید" value={faAmount(net)} tone="in" />
              <Metric icon={<Percent size={14} />} label="مالیات" value={faAmount(tax)} />
              <Metric
                icon={<Wallet size={14} />}
                label="سقفِ اعتبار"
                value={Number(picked.credit_limit) > 0 ? faAmount(picked.credit_limit) : 'بدون سقف'}
              />
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
          <SectionCard icon={Users} title="مشخصات" description={picked?.name ?? ''}>
            <div className="table-scroll">
              <table className="cards-on-mobile acc-table">
                <tbody>
                  <tr>
                    <td className="card-title" data-label="نوع">
                      نوع
                    </td>
                    <td data-label="مقدار">{picked?.type === 'supplier' ? 'تأمین‌کننده' : 'مشتری'}</td>
                  </tr>
                  <tr>
                    <td className="card-title" data-label="تلفن">
                      تلفن
                    </td>
                    <td data-label="مقدار" dir="ltr">
                      {picked?.phone || '—'}
                    </td>
                  </tr>
                  <tr>
                    <td className="card-title" data-label="آخرین خرید">
                      آخرین خرید
                    </td>
                    <td data-label="مقدار">{last ? formatJalali(last) : '—'}</td>
                  </tr>
                  <tr>
                    <td className="card-title" data-label="فاکتورِ باطل">
                      فاکتورِ باطل
                    </td>
                    <td data-label="مقدار">{faInt(mine.length - live.length)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </SectionCard>

          <SectionCard icon={ClipboardList} title="آخرین فاکتورها" description="ده فاکتورِ اخیر">
            <AsyncBlock
              loading={invoices.loading}
              error={invoices.error}
              empty={live.length === 0}
              emptyText="این طرف حساب هنوز فاکتوری ندارد."
            >
              <div className="table-scroll">
                <table className="cards-on-mobile acc-table">
                  <thead>
                    <tr>
                      <th>شماره</th>
                      <th>تاریخ</th>
                      <th>خالص</th>
                      <th>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {live
                      .slice()
                      .sort((a, b) => b.invoice_date.localeCompare(a.invoice_date))
                      .slice(0, 10)
                      .map((i) => (
                        <tr key={i.id}>
                          <td className="card-title" data-label="شماره">
                            {fa(i.number ?? 0)}
                          </td>
                          <td data-label="تاریخ">{formatJalali(i.invoice_date)}</td>
                          <td className="num" data-label="خالص">
                            {faAmount(i.total_amount)}
                          </td>
                          <td data-label="وضعیت">
                            <span className={`status-badge ${i.closed_at ? 'tone-default' : 'tone-success'}`}>
                              {i.closed_at ? 'بسته' : 'باز'}
                            </span>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </AsyncBlock>
          </SectionCard>
        </>
      )}
    </OpsPage>
  )
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
