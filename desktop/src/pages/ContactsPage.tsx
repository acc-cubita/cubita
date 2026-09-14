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
  Save,
  TrendingDown,
  Trash2,
  UserRound,
  UsersRound,
  X,
} from 'lucide-react'
import {
  createContact,
  deleteContact,
  fetchAging,
  fetchContacts,
  fetchPriceLists,
  updateContact,
  type ContactIn,
  type ContactRecord,
  type PriceListRecord,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { BulkImportPanel } from '../components/BulkImportPanel'
import { Pager, usePagination } from '../components/Pager'
import { NumberInput } from '../components/NumberInput'
import { StatCard } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import { EmptyState } from '../components/EmptyState'
import { AgingPanel } from '../components/AgingPanel'
import { ContactStatementDrawer } from '../components/ContactStatementDrawer'

const TYPE_LABELS: Record<ContactRecord['type'], string> = {
  customer: 'مشتری',
  supplier: 'تأمین‌کننده',
  both: 'مشتری و تأمین‌کننده',
}

const EMPTY_FORM: ContactIn = {
  name: '', type: 'customer', phone: '', email: '', address: '', tax_id: '', credit_limit: 0,
  default_price_list_id: null, entity_type: 'real', national_id: '', economic_code: '', postal_code: '',
}

const faMoney = (n: number) => n.toLocaleString('fa-IR')

export function ContactsPage({ token }: { token: string }) {
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [priceLists, setPriceLists] = useState<PriceListRecord[]>([])
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

  // فرم ایجاد/ویرایش طرف حساب
  const [form, setForm] = useState<ContactIn>(EMPTY_FORM)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formMessage, setFormMessage] = useState<string | null>(null)

  async function refresh() {
    setError(null)
    try {
      const [cs, pls, recvAging, payAging] = await Promise.all([
        fetchContacts(token),
        fetchPriceLists(token).catch(() => []),
        fetchAging(token, 'receivable').catch(() => null),
        fetchAging(token, 'payable').catch(() => null),
      ])
      setContacts(cs)
      setPriceLists(pls.filter((p) => p.is_active))
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
  const contactsPg = usePagination(filteredContacts, 10, `${filterType}|${search}`)

  // شاخص‌های بالای صفحه — از همان داده‌ی موجود محاسبه می‌شوند
  const kpis = useMemo(() => {
    const customers = contacts.filter((c) => c.type === 'customer' || c.type === 'both').length
    const suppliers = contacts.filter((c) => c.type === 'supplier' || c.type === 'both').length
    return { total: contacts.length, customers, suppliers }
  }, [contacts])

  async function handleSaveContact(e: React.FormEvent) {
    e.preventDefault()
    setFormMessage(null)
    if (!form.name.trim()) {
      setFormMessage('نام طرف حساب الزامی است.')
      return
    }
    const payload: ContactIn = {
      ...form,
      phone: form.phone || null,
      email: form.email || null,
      tax_id: form.tax_id || null,
      national_id: form.national_id || null,
      economic_code: form.economic_code || null,
      postal_code: form.postal_code || null,
    }
    try {
      if (editingId) {
        await updateContact(token, editingId, payload)
        setFormMessage('طرف حساب ویرایش شد.')
      } else {
        await createContact(token, payload)
        setFormMessage('طرف حساب جدید ثبت شد.')
      }
      setForm(EMPTY_FORM)
      setEditingId(null)
      await refresh()
    } catch (err) {
      setFormMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  function startEdit(c: ContactRecord) {
    setEditingId(c.id)
    setForm({
      name: c.name,
      type: c.type,
      phone: c.phone ?? '',
      email: c.email ?? '',
      address: c.address,
      tax_id: c.tax_id ?? '',
      credit_limit: Number(c.credit_limit) || 0,
      default_price_list_id: c.default_price_list_id ?? null,
      entity_type: c.entity_type ?? 'real',
      national_id: c.national_id ?? '',
      economic_code: c.economic_code ?? '',
      postal_code: c.postal_code ?? '',
    })
    setFormMessage(null)
  }

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
      if (editingId === c.id) {
        setEditingId(null)
        setForm(EMPTY_FORM)
      }
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const contactsTab = (
    <div className="workspace-split">
      <SectionCard
        icon={editingId ? Pencil : Plus}
        title={editingId ? 'ویرایش طرف حساب' : 'طرف حساب جدید'}
        description={editingId ? 'اطلاعات این طرف حساب را به‌روزرسانی کنید.' : 'مشتری یا تأمین‌کننده‌ی تازه را ثبت کنید.'}
        actions={
          editingId ? (
            <button
              onClick={() => {
                setEditingId(null)
                setForm(EMPTY_FORM)
                setFormMessage(null)
              }}
            >
              <X size={13} /> انصراف
            </button>
          ) : undefined
        }
      >
        <form className="invoice-form form-full" onSubmit={handleSaveContact}>
          <label>
            نام
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="نام شخص یا شرکت" required />
          </label>
          <label>
            نوع
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              <option value="customer">مشتری</option>
              <option value="supplier">تأمین‌کننده</option>
              <option value="both">مشتری و تأمین‌کننده</option>
            </select>
          </label>
          <div className="field-row">
            <label>
              تلفن
              <input type="text" value={form.phone ?? ''} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </label>
            <label>
              ایمیل
              <input type="text" value={form.email ?? ''} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </label>
          </div>
          <div className="field-row">
            <label>
              نوعِ شخص
              <select value={form.entity_type ?? 'real'} onChange={(e) => setForm({ ...form, entity_type: e.target.value as 'real' | 'legal' })}>
                <option value="real">حقیقی</option>
                <option value="legal">حقوقی</option>
              </select>
            </label>
            <label>
              {form.entity_type === 'legal' ? 'شناسه ملی' : 'کد ملی'}
              <input
                type="text"
                value={form.national_id ?? ''}
                onChange={(e) => setForm({ ...form, national_id: e.target.value })}
                placeholder={form.entity_type === 'legal' ? '۱۱ رقم' : '۱۰ رقم'}
              />
            </label>
          </div>
          <div className="field-row">
            <label>
              کد اقتصادی
              <input type="text" value={form.economic_code ?? ''} onChange={(e) => setForm({ ...form, economic_code: e.target.value })} />
            </label>
            <label>
              کد پستی
              <input type="text" value={form.postal_code ?? ''} onChange={(e) => setForm({ ...form, postal_code: e.target.value })} placeholder="۱۰ رقم" />
            </label>
          </div>
          <label>
            سقف اعتبار (ریال)
            <NumberInput
              value={form.credit_limit || ''}
              onChange={(v) => setForm({ ...form, credit_limit: Number(v) || 0 })}
              placeholder="۰ = بدون سقف"
            />
          </label>
          {priceLists.length > 0 && (
            <label>
              لیستِ قیمتِ پیش‌فرض
              <select
                value={form.default_price_list_id ?? ''}
                onChange={(e) => setForm({ ...form, default_price_list_id: e.target.value || null })}
              >
                <option value="">— قیمتِ پایه —</option>
                {priceLists.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            نشانی
            <input type="text" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary">
              <Save size={14} /> {editingId ? 'ذخیره تغییرات' : 'ثبت طرف حساب'}
            </button>
          </div>
          {formMessage && <div className="hint">{formMessage}</div>}
        </form>
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
          <div className="entity-table-wrap">
            <div className="table-scroll">
              <table className="entity-table contacts-table cards-on-mobile">
                <thead>
                  <tr>
                    <th>نام</th>
                    <th>نوع</th>
                    <th>مانده</th>
                    <th>سقف اعتبار</th>
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
                        <button type="button" onClick={() => startEdit(c)}><Pencil size={13} /> ویرایش</button>
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
