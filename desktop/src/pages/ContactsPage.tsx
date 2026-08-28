import { useEffect, useMemo, useState } from 'react'
import {
  Building2,
  CalendarClock,
  FileText,
  FileUp,
  HandCoins,
  Pencil,
  Plus,
  Save,
  TrendingDown,
  UserRound,
  UsersRound,
  Wallet,
  X,
} from 'lucide-react'
import {
  createContact,
  createTreasuryPayment,
  createTreasuryReceipt,
  fetchAging,
  fetchContacts,
  fetchPriceLists,
  fetchTreasuryTransactions,
  updateContact,
  type ContactIn,
  type ContactRecord,
  type PriceListRecord,
  type TreasuryTransactionRecord,
} from '../api'
import type { BankAccountCache } from '../electron.d'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { BulkImportPanel } from '../components/BulkImportPanel'
import { Pager, usePagination } from '../components/Pager'
import { NumberInput } from '../components/NumberInput'
import { StatCard } from '../components/StatCard'
import { Tabs } from '../components/Tabs'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { AgingPanel } from '../components/AgingPanel'
import { ContactStatementDrawer } from '../components/ContactStatementDrawer'
import { formatJalali } from '../lib/jalali'

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

export function ContactsPage({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [priceLists, setPriceLists] = useState<PriceListRecord[]>([])
  const [transactions, setTransactions] = useState<TreasuryTransactionRecord[]>([])
  const [recvMap, setRecvMap] = useState<Map<string, number>>(new Map())
  const [payMap, setPayMap] = useState<Map<string, number>>(new Map())
  const [agingTotals, setAgingTotals] = useState<{ recv: number; pay: number }>({ recv: 0, pay: 0 })
  const [filterType, setFilterType] = useState<'all' | 'customer' | 'supplier'>('all')
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [statementContact, setStatementContact] = useState<{ id: string; name: string } | null>(null)

  // فرم ایجاد/ویرایش طرف حساب
  const [form, setForm] = useState<ContactIn>(EMPTY_FORM)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formMessage, setFormMessage] = useState<string | null>(null)

  // فرم دریافت/پرداخت
  const [txType, setTxType] = useState<'receipt' | 'payment'>('receipt')
  const [txContactId, setTxContactId] = useState('')
  const [txAmount, setTxAmount] = useState('')
  const [txDate, setTxDate] = useState(new Date().toISOString().slice(0, 10))
  const [txMethod, setTxMethod] = useState<'cash' | 'bank'>('cash')
  const [txBankId, setTxBankId] = useState('')
  const [txDescription, setTxDescription] = useState('')
  const [txMessage, setTxMessage] = useState<string | null>(null)

  async function refresh() {
    setError(null)
    try {
      const [cs, txs, pls, recvAging, payAging] = await Promise.all([
        fetchContacts(token),
        fetchTreasuryTransactions(token),
        fetchPriceLists(token).catch(() => []),
        fetchAging(token, 'receivable').catch(() => null),
        fetchAging(token, 'payable').catch(() => null),
      ])
      setContacts(cs)
      setTransactions(txs)
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
        if (search && !c.name.includes(search) && !(c.phone ?? '').includes(search)) return false
        return true
      }),
    [contacts, filterType, search],
  )
  // صفحه‌بندیِ جدول‌ها (۱۰ ردیف): فهرستِ اشخاص و فهرستِ تراکنش‌های خزانه.
  const contactsPg = usePagination(filteredContacts, 10, `${filterType}|${search}`)
  const txPg = usePagination(transactions, 10)

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

  async function handleSubmitTransaction(e: React.FormEvent) {
    e.preventDefault()
    setTxMessage(null)
    if (!txContactId || Number(txAmount) <= 0) {
      setTxMessage('طرف حساب و مبلغ (بزرگ‌تر از صفر) الزامی است.')
      return
    }
    if (txMethod === 'bank' && !txBankId) {
      setTxMessage('برای روش بانکی، حساب بانکی را انتخاب کنید.')
      return
    }
    const payload = {
      transaction_date: txDate,
      contact_id: txContactId,
      amount: Number(txAmount),
      method: txMethod,
      bank_account_id: txMethod === 'bank' ? txBankId : null,
      description: txDescription,
    }
    try {
      if (txType === 'receipt') {
        await createTreasuryReceipt(token, payload)
        setTxMessage('دریافت ثبت شد و سند حسابداری آن خودکار صادر شد.')
      } else {
        await createTreasuryPayment(token, payload)
        setTxMessage('پرداخت ثبت شد و سند حسابداری آن خودکار صادر شد.')
      }
      setTxAmount('')
      setTxDescription('')
      await refresh()
    } catch (err) {
      setTxMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const txContacts =
    txType === 'receipt'
      ? contacts.filter((c) => c.type !== 'supplier')
      : contacts.filter((c) => c.type !== 'customer')

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
            <input type="text" placeholder="جستجو نام یا تلفن..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        }
      >
        {filteredContacts.length === 0 ? (
          <EmptyState icon={UsersRound} text="طرف حسابی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table contacts-table">
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
                  <tr key={c.id}>
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
                    <td className="check-actions">
                      <button type="button" onClick={() => setStatementContact({ id: c.id, name: c.name })}><FileText size={13} /> صورت‌حساب</button>
                      <button type="button" onClick={() => startEdit(c)}><Pencil size={13} /> ویرایش</button>
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
            <Pager page={contactsPg.page} pageCount={contactsPg.pageCount} onChange={contactsPg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )

  const treasuryTab = (
    <div className="workspace-split">
      <SectionCard icon={HandCoins} title="ثبت دریافت / پرداخت" description="سند حسابداری هر تراکنش خودکار صادر می‌شود.">
        <form className="invoice-form form-full" onSubmit={handleSubmitTransaction}>
          <label>
            نوع عملیات
            <select value={txType} onChange={(e) => setTxType(e.target.value as 'receipt' | 'payment')}>
              <option value="receipt">دریافت از مشتری</option>
              <option value="payment">پرداخت به تأمین‌کننده</option>
            </select>
          </label>
          <label>
            طرف حساب
            <select value={txContactId} onChange={(e) => setTxContactId(e.target.value)} required>
              <option value="">— انتخاب —</option>
              {txContacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <div className="field-row">
            <label>
              مبلغ (ریال)
              <NumberInput value={txAmount} onChange={setTxAmount} required />
            </label>
            <label>
              تاریخ
              <JalaliDatePicker value={txDate} onChange={setTxDate} />
            </label>
          </div>
          <label>
            روش
            <select value={txMethod} onChange={(e) => setTxMethod(e.target.value as 'cash' | 'bank')}>
              <option value="cash">نقدی (صندوق)</option>
              <option value="bank">بانکی</option>
            </select>
          </label>
          {txMethod === 'bank' && (
            <label>
              حساب بانکی
              <select value={txBankId} onChange={(e) => setTxBankId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {bankAccounts.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            توضیحات
            <input type="text" value={txDescription} onChange={(e) => setTxDescription(e.target.value)} />
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary">
              <Wallet size={14} /> ثبت {txType === 'receipt' ? 'دریافت' : 'پرداخت'}
            </button>
          </div>
          {txMessage && <div className="hint">{txMessage}</div>}
        </form>
      </SectionCard>

      <SectionCard icon={Wallet} title="آخرین دریافت‌ها و پرداخت‌ها" description={`${faMoney(transactions.length)} تراکنش`}>
        {transactions.length === 0 ? (
          <EmptyState icon={Wallet} text="هنوز دریافت یا پرداختی ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table treasury-table">
              <thead>
                <tr>
                  <th>نوع</th>
                  <th>طرف حساب</th>
                  <th>مبلغ</th>
                  <th>روش</th>
                  <th>تاریخ</th>
                </tr>
              </thead>
              <tbody>
                {txPg.pageItems.map((t) => (
                  <tr key={t.id}>
                    <td data-label="نوع">
                      <span className={`status-badge tone-${t.type === 'receipt' ? 'success' : 'warning'}`}>
                        {t.type === 'receipt' ? 'دریافت' : 'پرداخت'}
                      </span>
                    </td>
                    <td data-label="طرف حساب" className="entity-name">{t.contact_name}</td>
                    <td data-label="مبلغ" className="money-cell">{faMoney(Number(t.amount))}</td>
                    <td data-label="روش">{t.method === 'cash' ? 'نقدی' : 'بانکی'}</td>
                    <td data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={txPg.page} pageCount={txPg.pageCount} onChange={txPg.setPage} />
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
          { key: 'treasury', label: 'دریافت و پرداخت', icon: HandCoins, content: treasuryTab },
          { key: 'aging', label: 'سنین مطالبات', icon: CalendarClock, content: <AgingPanel token={token} onStatement={setStatementContact} /> },
          { key: 'import', label: 'ورود گروهی اشخاص', icon: FileUp, content: <BulkImportPanel token={token} kind="contacts" /> },
        ]}
      />

      {statementContact && <ContactStatementDrawer token={token} contact={statementContact} onClose={() => setStatementContact(null)} />}
    </div>
  )
}
