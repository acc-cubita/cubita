import { useCallback, useEffect, useState } from 'react'
import { Landmark, Save, Pencil, X, RefreshCw, BookOpen, Plus } from 'lucide-react'
import {
  fetchBankAccountsAdmin, createBankAccount, updateBankAccount, createBankTransaction,
  type BankAccountRecord,
} from '../api'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { AccountLedgerDrawer } from './AccountLedgerDrawer'
import { JalaliDatePicker } from './JalaliDatePicker'
import { todayIso } from '../lib/jalali'

interface Draft { name: string; bank_name: string; account_number: string; iban: string }
const EMPTY: Draft = { name: '', bank_name: '', account_number: '', iban: '' }

/**
 * مدیریتِ حساب‌های بانکی — ساخت، ویرایش (نام/بانک/شماره/شبا)، فعال/غیرفعال‌سازی،
 * و «کارتِ حساب» که گردش و موجودیِ دفترِ کلِ متناظر را نشان می‌دهد (شاملِ دریافت/پرداخت
 * و چک‌ها — نه فقط واریز/برداشتِ دستی). به‌علاوه‌ی فرمِ واریز/برداشتِ بانکی.
 */
export function BankAccountsPanel({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const postable = accounts.filter((a) => !a.is_group)
  const [banks, setBanks] = useState<BankAccountRecord[] | null>(null)
  const pg = usePagination(banks ?? [], 10)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [form, setForm] = useState<Draft>(EMPTY)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [ledger, setLedger] = useState<{ id: string; code: string; name: string } | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      setBanks(await fetchBankAccountsAdmin(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  function startEdit(b: BankAccountRecord) {
    setEditingId(b.id)
    setForm({ name: b.name, bank_name: b.bank_name, account_number: b.account_number, iban: b.iban })
    setMessage(null)
  }
  function resetForm() { setForm(EMPTY); setEditingId(null); setMessage(null) }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setMessage(null)
    if (!form.name.trim()) { setMessage('نام حساب الزامی است.'); return }
    setSaving(true)
    try {
      if (editingId) {
        await updateBankAccount(token, editingId, { name: form.name.trim(), bank_name: form.bank_name.trim(), account_number: form.account_number.trim(), iban: form.iban.trim() })
        setMessage('حساب بانکی ویرایش شد.')
      } else {
        await createBankAccount(token, { name: form.name.trim(), bank_name: form.bank_name.trim(), account_number: form.account_number.trim(), iban: form.iban.trim() })
        setMessage('حساب بانکی ساخته شد.')
      }
      resetForm(); await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally { setSaving(false) }
  }

  async function toggleActive(b: BankAccountRecord) {
    try { await updateBankAccount(token, b.id, { is_active: !b.is_active }); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  return (
    <div className="page-block">
      <div className="workspace-split">
        <SectionCard
          icon={editingId ? Pencil : Plus}
          title={editingId ? 'ویرایش حساب بانکی' : 'حساب بانکیِ جدید'}
          description={editingId ? 'اطلاعاتِ این حساب را به‌روزرسانی کنید.' : 'یک حساب بانکی با شماره و شبا ثبت کنید.'}
          actions={editingId ? <button onClick={resetForm}><X size={13} /> انصراف</button> : undefined}
        >
          <form className="invoice-form form-full" onSubmit={handleSubmit}>
            <div className="field-row">
              <label>نام حساب<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="مثلاً جاری ملت" /></label>
              <label>نام بانک<input value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} placeholder="ملت" /></label>
            </div>
            <div className="field-row">
              <label>شماره حساب<input value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} className="ltr-cell" inputMode="numeric" /></label>
              <label>شماره شبا (IR)<input value={form.iban} onChange={(e) => setForm({ ...form, iban: e.target.value })} className="ltr-cell" placeholder="IR…" /></label>
            </div>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={saving}><Save size={14} /> {editingId ? 'ذخیره' : 'ثبت حساب'}</button>
            </div>
            {message && <div className="hint">{message}</div>}
          </form>
        </SectionCard>

        <SectionCard
          icon={Landmark}
          title="حساب‌های بانکی"
          description={banks ? `${banks.length.toLocaleString('fa-IR')} حساب` : ''}
          actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
        >
          {error && <div className="error">{error}</div>}
          {banks == null ? (
            <p className="muted">در حال بارگذاری…</p>
          ) : banks.length === 0 ? (
            <EmptyState icon={Landmark} text="هنوز حساب بانکی‌ای ثبت نشده." />
          ) : (
            <div className="entity-table-wrap">
              <table className="entity-table bank-table">
                <thead>
                  <tr><th>حساب</th><th>شماره / شبا</th><th>وضعیت</th><th></th></tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((b) => (
                    <tr key={b.id}>
                      <td data-label="حساب" className="entity-name">
                        {b.name}
                        {b.bank_name && <span className="unit-suffix"> · {b.bank_name}</span>}
                      </td>
                      <td data-label="شماره / شبا" className="ltr-cell bank-numbers">
                        {b.account_number || '—'}{b.iban ? <div className="entity-sub">{b.iban}</div> : null}
                      </td>
                      <td data-label="وضعیت">
                        <span className={`status-badge ${b.is_active ? 'tone-success' : 'tone-warning'}`}>{b.is_active ? 'فعال' : 'غیرفعال'}</span>
                      </td>
                      <td className="check-actions">
                        <button type="button" onClick={() => setLedger({ id: b.gl_account_id, code: b.account_number, name: b.name })}><BookOpen size={13} /> کارتِ حساب</button>
                        <button type="button" onClick={() => startEdit(b)}><Pencil size={13} /> ویرایش</button>
                        <button type="button" onClick={() => void toggleActive(b)}>{b.is_active ? 'غیرفعال' : 'فعال'}</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          )}
        </SectionCard>
      </div>

      <BankTransactionForm token={token} banks={(banks ?? []).filter((b) => b.is_active)} accounts={postable} onDone={() => void refresh()} />

      {ledger && <AccountLedgerDrawer token={token} account={ledger} onClose={() => setLedger(null)} />}
    </div>
  )
}

function BankTransactionForm({
  token, banks, accounts, onDone,
}: {
  token: string
  banks: BankAccountRecord[]
  accounts: AccountCache[]
  onDone: () => void
}) {
  const [bankAccountId, setBankAccountId] = useState('')
  const [direction, setDirection] = useState<'deposit' | 'withdraw'>('deposit')
  const [amount, setAmount] = useState('')
  const [counterAccountId, setCounterAccountId] = useState('')
  const [description, setDescription] = useState('')
  const [transactionDate, setTransactionDate] = useState(todayIso())
  const [message, setMessage] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setMessage(null)
    if (!bankAccountId || !counterAccountId || Number(amount) <= 0) { setMessage('حساب بانکی، حساب مقابل و مبلغ (بزرگ‌تر از صفر) الزامی است.'); return }
    try {
      await createBankTransaction(token, {
        bank_account_id: bankAccountId, transaction_date: transactionDate,
        amount: direction === 'deposit' ? Number(amount) : -Number(amount),
        counter_account_id: counterAccountId, description,
      })
      setAmount(''); setDescription(''); setMessage('تراکنش بانکی ثبت شد.'); onDone()
    } catch (err) { setMessage(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  return (
    <SectionCard icon={Save} title="واریز / برداشتِ بانکی" description="جابه‌جاییِ دستیِ وجه بین بانک و حسابِ مقابل (مثلاً صندوق).">
      <form className="invoice-form" onSubmit={handleSubmit}>
        <label>حساب بانکی
          <select value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {banks.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
        <label>نوع
          <select value={direction} onChange={(e) => setDirection(e.target.value as 'deposit' | 'withdraw')}>
            <option value="deposit">واریز</option>
            <option value="withdraw">برداشت</option>
          </select>
        </label>
        <label>مبلغ<NumberInput value={amount} onChange={setAmount} /></label>
        <label>حساب مقابل (مثلاً صندوق)
          <select value={counterAccountId} onChange={(e) => setCounterAccountId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
          </select>
        </label>
        <label>توضیحات<input type="text" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <label>تاریخ<JalaliDatePicker value={transactionDate} onChange={setTransactionDate} /></label>
        <div className="invoice-form-footer"><button type="submit" className="btn-primary"><Save size={14} /> ثبت تراکنش</button></div>
        {message && <div className="hint">{message}</div>}
      </form>
    </SectionCard>
  )
}
