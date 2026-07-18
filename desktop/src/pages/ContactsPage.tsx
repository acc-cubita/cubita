import { useEffect, useMemo, useState } from 'react'
import { HandCoins, Pencil, Plus, Save, UsersRound, Wallet, X } from 'lucide-react'
import {
  createContact,
  createTreasuryPayment,
  createTreasuryReceipt,
  fetchContacts,
  fetchTreasuryTransactions,
  updateContact,
  type ContactIn,
  type ContactRecord,
  type TreasuryTransactionRecord,
} from '../api'
import type { BankAccountCache } from '../electron.d'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { formatJalali } from '../lib/jalali'

const TYPE_LABELS: Record<ContactRecord['type'], string> = {
  customer: 'مشتری',
  supplier: 'تأمین‌کننده',
  both: 'مشتری و تأمین‌کننده',
}

const EMPTY_FORM: ContactIn = { name: '', type: 'customer', phone: '', email: '', address: '', tax_id: '' }

export function ContactsPage({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [transactions, setTransactions] = useState<TreasuryTransactionRecord[]>([])
  const [filterType, setFilterType] = useState<'all' | 'customer' | 'supplier'>('all')
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)

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
      const [cs, txs] = await Promise.all([fetchContacts(token), fetchTreasuryTransactions(token)])
      setContacts(cs)
      setTransactions(txs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

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

  return (
    <div className="page">
      <PageHeader
        icon={UsersRound}
        title="اشخاص"
        description="مشتریان و تأمین‌کنندگان را مدیریت کنید و دریافت و پرداخت‌هایشان را با سند خودکار ثبت کنید."
      />

      {error && <div className="error">{error}</div>}

      <SectionCard
        icon={editingId ? Pencil : Plus}
        title={editingId ? 'ویرایش طرف حساب' : 'طرف حساب جدید'}
        actions={
          editingId ? (
            <button
              onClick={() => {
                setEditingId(null)
                setForm(EMPTY_FORM)
                setFormMessage(null)
              }}
            >
              <X size={13} /> انصراف از ویرایش
            </button>
          ) : undefined
        }
      >
        <form className="invoice-form" onSubmit={handleSaveContact}>
          <label>
            نام
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </label>
          <label>
            نوع
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              <option value="customer">مشتری</option>
              <option value="supplier">تأمین‌کننده</option>
              <option value="both">مشتری و تأمین‌کننده</option>
            </select>
          </label>
          <label>
            تلفن
            <input type="text" value={form.phone ?? ''} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </label>
          <label>
            ایمیل
            <input type="text" value={form.email ?? ''} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label>
            شناسه/کد اقتصادی
            <input type="text" value={form.tax_id ?? ''} onChange={(e) => setForm({ ...form, tax_id: e.target.value })} />
          </label>
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
          <table>
            <thead>
              <tr>
                <th>نام</th>
                <th>نوع</th>
                <th>تلفن</th>
                <th>ایمیل</th>
                <th>اقدام</th>
              </tr>
            </thead>
            <tbody>
              {filteredContacts.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{TYPE_LABELS[c.type]}</td>
                  <td>{c.phone ?? '—'}</td>
                  <td>{c.email ?? '—'}</td>
                  <td>
                    <button type="button" onClick={() => startEdit(c)}>
                      <Pencil size={13} /> ویرایش
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      <SectionCard icon={HandCoins} title="دریافت و پرداخت">
        <p className="hint">
          دریافت از مشتری، حساب‌های دریافتنی را تسویه می‌کند؛ پرداخت به تأمین‌کننده، حساب‌های پرداختنی را. سند
          حسابداری هر دو خودکار صادر می‌شود.
        </p>
        <form className="invoice-form" onSubmit={handleSubmitTransaction}>
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
          <label>
            مبلغ
            <input type="number" min="0" value={txAmount} onChange={(e) => setTxAmount(e.target.value)} required />
          </label>
          <label>
            تاریخ
            <JalaliDatePicker value={txDate} onChange={setTxDate} />
          </label>
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

      <SectionCard icon={Wallet} title="آخرین دریافت‌ها و پرداخت‌ها">
        {transactions.length === 0 ? (
          <EmptyState icon={Wallet} text="هنوز دریافت یا پرداختی ثبت نشده." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>نوع</th>
                <th>طرف حساب</th>
                <th>مبلغ</th>
                <th>روش</th>
                <th>تاریخ</th>
                <th>توضیحات</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.id}>
                  <td>
                    <span className={`status-badge tone-${t.type === 'receipt' ? 'success' : 'warning'}`}>
                      {t.type === 'receipt' ? 'دریافت' : 'پرداخت'}
                    </span>
                  </td>
                  <td>{t.contact_name}</td>
                  <td>{Number(t.amount).toLocaleString('fa-IR')}</td>
                  <td>{t.method === 'cash' ? 'نقدی' : 'بانکی'}</td>
                  <td>{formatJalali(t.transaction_date)}</td>
                  <td>{t.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>
    </div>
  )
}
