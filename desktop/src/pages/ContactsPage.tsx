import { useEffect, useMemo, useState } from 'react'
import {
  Ban,
  Building2,
  CalendarClock,
  FileText,
  FileUp,
  HandCoins,
  Pencil,
  Plus,
  RotateCcw,
  TrendingDown,
  Trash2,
  UserRound,
  UsersRound,
} from 'lucide-react'
import {
  deleteContact,
  fetchAging,
  fetchContacts,
  updateContact,
  type ContactRecord,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { BulkImportPanel } from '../components/BulkImportPanel'
import { Pager, usePagination } from '../components/Pager'
import { SortBar, SortTh, useSort } from '../components/SortControls'
import { StatCard } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import { EmptyState } from '../components/EmptyState'
import { AgingPanel } from '../components/AgingPanel'
import { ContactStatementDrawer } from '../components/ContactStatementDrawer'
import type { PageKey } from '../lib/navModel'

const TYPE_LABELS: Record<ContactRecord['type'], string> = {
  customer: 'مشتری',
  supplier: 'تأمین‌کننده',
  both: 'مشتری و تأمین‌کننده',
  //: نقشِ معاملاتی ندارد — واسطه، سهامدار یا کارمندِ خالص. تا مهاجرتِ ۰۱۶۴ چنین
  //: کسی به‌زور «تأمین‌کننده» برچسب می‌خورد.
  none: 'بدونِ نقشِ معاملاتی',
}

const faMoney = (n: number) => n.toLocaleString('fa-IR')

export function ContactsPage({
  token,
  onNavigate,
  onEditContact,
}: {
  token: string
  onNavigate: (page: PageKey) => void
  /** ویرایش در **فرمِ کامل** انجام می‌شود، نه این‌جا — وگرنه نیمی از فیلدها
   *  بی‌صدا از دسترس خارج می‌مانند. */
  onEditContact: (id: string) => void
}) {
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [recvMap, setRecvMap] = useState<Map<string, number>>(new Map())
  const [payMap, setPayMap] = useState<Map<string, number>>(new Map())
  const [agingTotals, setAgingTotals] = useState<{ recv: number; pay: number }>({ recv: 0, pay: 0 })
  const [filterType, setFilterType] = useState<'all' | 'customer' | 'supplier'>('all')
  //: پیش‌فرض «همه» — عمداً. پنهان‌کردنِ خودکارِ غیرفعال‌ها یعنی کاربری که تازه
  //: یکی را غیرفعال کرده فکر کند پاکش کرده. غیرفعال یعنی «دیگر پیشنهادش نکن»،
  //: نه «ناپدید شو».
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all')
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [statementContact, setStatementContact] = useState<{ id: string; name: string } | null>(null)


  async function refresh() {
    setError(null)
    try {
      const [cs, recvAging, payAging] = await Promise.all([
        fetchContacts(token),
        fetchAging(token, 'receivable').catch(() => null),
        fetchAging(token, 'payable').catch(() => null),
      ])
      setContacts(cs)
      setRecvMap(new Map((recvAging?.rows ?? []).map((r) => [r.contact_id, Number(r.total)])))
      setPayMap(new Map((payAging?.rows ?? []).map((r) => [r.contact_id, Number(r.total)])))
      setAgingTotals({ recv: Number(recvAging?.grand_total ?? 0), pay: Number(payAging?.grand_total ?? 0) })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  // ماندهٔ خالصِ هر طرف حساب: مثبت = بدهکار (طلبِ ما)، منفی = بستانکار (بدهیِ ما)
  const balanceOf = (id: string) => (recvMap.get(id) ?? 0) - (payMap.get(id) ?? 0)

  useEffect(() => {
    void refresh()
  }, [])

  const filteredContacts = useMemo(
    () =>
      contacts.filter((c) => {
        if (filterType !== 'all' && c.type !== filterType && c.type !== 'both') return false
        if (filterActive !== 'all' && c.is_active !== (filterActive === 'active')) return false
        if (search && !c.name.includes(search) && !(c.phone ?? '').includes(search)) return false
        return true
      }),
    [contacts, filterType, filterActive, search],
  )
  //: `balanceOf` و `credit_limit` هر دو عددند ولی از دو جای متفاوت می‌آیند —
  //: مانده مشتق از دو گزارشِ سنی است و سقف روی خودِ رکورد. مرتب‌سازی هر دو را
  //: `number` می‌گیرد تا «۱۰۰» بعد از «۹» نیفتد.
  const sort = useSort<ContactRecord>(
    {
      name: { label: 'نام', get: (c) => c.name },
      type: { label: 'نوع', get: (c) => TYPE_LABELS[c.type] ?? c.type },
      balance: { label: 'مانده', get: (c) => balanceOf(c.id), kind: 'number' },
      credit: { label: 'سقف اعتبار', get: (c) => Number(c.credit_limit) || 0, kind: 'number' },
    },
    'name',
  )
  const sortedContacts = useMemo(() => sort.apply(filteredContacts), [sort, filteredContacts])
  const contactsPg = usePagination(sortedContacts, 10, `${filterType}|${search}|${sort.resetKey}`)

  // شاخص‌های بالای صفحه — از همان داده‌ی موجود محاسبه می‌شوند
  const kpis = useMemo(() => {
    const customers = contacts.filter((c) => c.is_customer).length
    const suppliers = contacts.filter((c) => c.is_supplier).length
    return { total: contacts.length, customers, suppliers }
  }, [contacts])

  /** فعال/غیرفعال — **فقط همین یک فیلد فرستاده می‌شود.**
   *
   * سرور `PATCH` را جزئی می‌گیرد، پس این درخواست هیچ‌چیزِ دیگری را دست نمی‌زند.
   * اگر به‌جایش کلِ فرم فرستاده می‌شد، غیرفعال‌کردنِ یک طرف‌حساب از روی جدول
   * مقدارهای فرمِ باز (یا خالی) را هم رویش می‌نشاند.
   */
  async function handleToggleActive(c: ContactRecord) {
    const next = !c.is_active
    if (!next && !window.confirm(`«${c.name}» غیرفعال شود؟ در فهرست‌های انتخاب پیشنهاد نمی‌شود، ولی تاریخچه و اسنادش دست‌نخورده می‌مانند.`)) return
    setError(null)
    try {
      await updateContact(token, c.id, { is_active: next })
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  /** حذف — و ۴۰۹ این‌جا **خطا نیست، جواب است.**
   *
   * طرف‌حسابی که در فاکتور یا سند استفاده شده پاک نمی‌شود و سرور همان‌جا
   * می‌گوید به‌جایش غیرفعالش کنید. پیامِ سرور عیناً نشان داده می‌شود چون
   * دلیلِ دقیق را می‌داند (سیستمی؟ مانده‌ی اول دوره؟ ارجاع؟) و ما نمی‌دانیم.
   */
  async function handleDelete(c: ContactRecord) {
    if (!window.confirm(`«${c.name}» برای همیشه حذف شود؟ اگر در سندی استفاده شده باشد حذف نمی‌شود.`)) return
    setError(null)
    try {
      await deleteContact(token, c.id)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const contactsTab = (
    <div className="workspace-split">
      {/* **فرمِ ساخت/ویرایش از این‌جا برداشته شد.**
          دو مسیرِ ساختِ طرف‌حساب وجود داشت و این یکی ناقص بود: نقشِ سهامدار و
          درصدِ سهم، واسطه و پورسانت، گروه، محلِ جغرافیایی، نرخِ تخفیف، کدِ
          تفصیلی، ماندهٔ اول دوره، نشانی‌ها، تلفن‌ها و افرادِ مرتبط هیچ‌کدام
          این‌جا پرسیده نمی‌شدند — و چون فرمِ کامل فقط می‌ساخت، رکوردی که از
          این‌جا ساخته می‌شد **برای همیشه** ناقص می‌مانْد.
          «هرگز دو نمای یک داده نساز». */}
      <SectionCard
        icon={Plus}
        title="ثبت و ویرایشِ طرف حساب"
        description="فرمِ کاملِ طرف حساب — با نقش‌ها، نشانی‌ها، تلفن‌ها، افرادِ مرتبط و کدِ تفصیلی."
      >
        <p className="hint">
          ساخت و ویرایشِ طرف حساب از فرمِ کامل انجام می‌شود تا همه‌ی اطلاعات — از جمله
          نقشِ «سهامدار» و ماندهٔ اول دوره — یک‌جا ثبت شوند.
        </p>
        <div className="invoice-form-footer">
          <button type="button" className="btn-primary" onClick={() => onNavigate('contactnew')}>
            <Plus size={14} /> طرف حساب جدید
          </button>
        </div>
      </SectionCard>

      <SectionCard
        icon={UsersRound}
        title="لیست اشخاص"
        description={`${faMoney(filteredContacts.length)} طرف حساب`}
        actions={
          <div className="check-actions">
            <select value={filterType} onChange={(e) => setFilterType(e.target.value as typeof filterType)}>
              <option value="all">همه</option>
              <option value="customer">مشتریان</option>
              <option value="supplier">تأمین‌کنندگان</option>
            </select>
            <select value={filterActive} onChange={(e) => setFilterActive(e.target.value as typeof filterActive)}>
              <option value="all">فعال و غیرفعال</option>
              <option value="active">فقط فعال</option>
              <option value="inactive">فقط غیرفعال</option>
            </select>
            <input type="text" placeholder="جستجو نام یا تلفن..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        }
      >
        {filteredContacts.length === 0 ? (
          <EmptyState icon={UsersRound} text="طرف حسابی ثبت نشده." />
        ) : (
          <>
          {/* زیرِ ۷۶۰px سرستون‌ها پنهان می‌شوند؛ بدونِ این نوار مرتب‌سازی در
              موبایل هیچ راهی نداشت. همان حالت را می‌خورد، پس دو کنترل نیست. */}
          <SortBar sort={sort} />
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table contacts-table cards-on-mobile">
                <thead>
                  <tr>
                    <SortTh sort={sort} k="name">نام</SortTh>
                    <SortTh sort={sort} k="type">نوع</SortTh>
                    <SortTh sort={sort} k="balance">مانده</SortTh>
                    <SortTh sort={sort} k="credit">سقف اعتبار</SortTh>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {contactsPg.pageItems.map((c) => {
                    const bal = balanceOf(c.id)
                    const limit = Number(c.credit_limit) || 0
                    const overLimit = limit > 0 && (recvMap.get(c.id) ?? 0) > limit
                    return (
                    <tr key={c.id} className={c.is_active ? undefined : 'row-inactive'}>
                      <td data-label="نام">
                        <div className="entity-cell">
                          <div className={`entity-avatar tone-${c.type}`}>{c.name.trim().charAt(0) || '؟'}</div>
                          <div>
                            <div className="entity-name">{c.name}</div>
                            <div className="entity-sub">{c.phone || (c.economic_code ? `کد اقتصادی: ${c.economic_code}` : '')}</div>
                          </div>
                        </div>
                      </td>
                      <td data-label="نوع">
                        <span className={`status-badge type-badge ${c.type}`}>{TYPE_LABELS[c.type]}</span>
                        {/* واسطه و سهامدار در `type` نمی‌گنجند و پرچمِ جدا دارند. بی این
                            دو نشان، نقشی که در فرمِ کاملِ «طرف حساب جدید» ثبت شده این‌جا
                            ناپیدا می‌ماند و کاربر گمان می‌کند پاک شده. */}
                        {c.is_broker && <> <span className="status-badge">واسطه</span></>}
                        {c.is_shareholder && <> <span className="status-badge">سهامدار</span></>}
                        {/* بی این نشان، طرف‌حسابِ غیرفعال از فعال جدا نبود و کاربر
                            نمی‌فهمید چرا در فهرست‌های انتخاب پیدایش نمی‌کند. */}
                        {!c.is_active && <> <span className="status-badge tone-muted">غیرفعال</span></>}
                      </td>
                      <td data-label="مانده" className="money-cell">
                        {bal === 0 ? '۰' : (
                          <span className={bal > 0 ? 'bal-debit' : 'bal-credit'}>
                            {faMoney(Math.abs(Math.round(bal)))} <span className="bal-tag">{bal > 0 ? 'بدهکار' : 'بستانکار'}</span>
                          </span>
                        )}
                      </td>
                      <td data-label="سقف اعتبار" className="money-cell">
                        {limit > 0 ? (
                          <>
                            {faMoney(limit)}
                            {overLimit && <span className="status-badge tone-danger credit-over">فراتر از سقف</span>}
                          </>
                        ) : '—'}
                      </td>
                      <td className="check-actions card-actions">
                        <button type="button" onClick={() => setStatementContact({ id: c.id, name: c.name })}><FileText size={13} /> صورت‌حساب</button>
                        <button type="button" onClick={() => onEditContact(c.id)}><Pencil size={13} /> ویرایش</button>
                        <button type="button" onClick={() => void handleToggleActive(c)}>
                          {c.is_active ? <><Ban size={13} /> غیرفعال</> : <><RotateCcw size={13} /> فعال</>}
                        </button>
                        <button type="button" className="icon-btn-danger" aria-label="حذف" onClick={() => void handleDelete(c)}><Trash2 size={13} /> حذف</button>
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={contactsPg.page} pageCount={contactsPg.pageCount} onChange={contactsPg.setPage} />
          </div>
          </>
        )}
      </SectionCard>
    </div>
  )

  return (
    <div className="page panels">
      <PageHeader
        icon={UsersRound}
        title="اشخاص"
        description="مشتریان و تأمین‌کنندگان را مدیریت کنید و دریافت و پرداخت‌هایشان را با سند خودکار ثبت کنید."
      />

      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard icon={<UsersRound size={18} />} label="کل اشخاص" value={faMoney(kpis.total)} hint="مشتری و تأمین‌کننده" />
        <StatCard icon={<UserRound size={18} />} label="مشتریان" value={faMoney(kpis.customers)} />
        <StatCard icon={<Building2 size={18} />} label="تأمین‌کنندگان" value={faMoney(kpis.suppliers)} />
        <StatCard icon={<HandCoins size={18} />} label="مطالباتِ باز" value={faMoney(agingTotals.recv)} tone={agingTotals.recv > 0 ? 'success' : 'default'} hint="ریال، طلبِ ما" />
        <StatCard icon={<TrendingDown size={18} />} label="بدهی به تأمین‌کنندگان" value={faMoney(agingTotals.pay)} tone={agingTotals.pay > 0 ? 'warning' : 'default'} hint="ریال" />
      </div>

      <Tabs
        syncPage="contacts"
        tabs={[
          { key: 'contacts', label: 'طرف حساب‌ها', icon: UsersRound, content: contactsTab },
          { key: 'aging', label: 'سنین مطالبات', icon: CalendarClock, content: <AgingPanel token={token} onStatement={setStatementContact} /> },
          { key: 'import', label: 'ورود گروهی اشخاص', icon: FileUp, content: <BulkImportPanel token={token} kind="contacts" /> },
        ]}
      />

      {statementContact && <ContactStatementDrawer token={token} contact={statementContact} onClose={() => setStatementContact(null)} />}
    </div>
  )
}
