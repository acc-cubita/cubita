import { useState } from 'react'
import { Landmark, Save } from 'lucide-react'
import { createBankTransaction, createPettyCashCharge, createPettyCashExpense } from '../api'
import type { AccountCache, BankAccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { JalaliDatePicker } from './JalaliDatePicker'
import { todayIso } from '../lib/jalali'

export function BankingPanel({
  token,
  accounts,
  bankAccounts,
}: {
  token: string
  accounts: AccountCache[]
  bankAccounts: BankAccountCache[]
}) {
  const postableAccounts = accounts.filter((a) => !a.is_group)
  const expenseAccounts = postableAccounts.filter((a) => a.type === 'expense')

  return (
    <SectionCard icon={Landmark} title="بانک و تنخواه‌گردان">
      <p className="hint">این عملیات نیاز به اتصال اینترنت دارند (مستقیم روی سرور ثبت می‌شوند).</p>
      <BankTransactionForm token={token} bankAccounts={bankAccounts} accounts={postableAccounts} />
      <PettyCashForms token={token} sourceAccounts={postableAccounts} expenseAccounts={expenseAccounts} />
    </SectionCard>
  )
}

function BankTransactionForm({
  token,
  bankAccounts,
  accounts,
}: {
  token: string
  bankAccounts: BankAccountCache[]
  accounts: AccountCache[]
}) {
  const [bankAccountId, setBankAccountId] = useState('')
  const [direction, setDirection] = useState<'deposit' | 'withdraw'>('deposit')
  const [amount, setAmount] = useState('')
  const [counterAccountId, setCounterAccountId] = useState('')
  const [description, setDescription] = useState('')
  const [transactionDate, setTransactionDate] = useState(todayIso())
  const [message, setMessage] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!bankAccountId || !counterAccountId || Number(amount) <= 0) {
      setMessage('حساب بانکی، حساب مقابل و مبلغ (بزرگ‌تر از صفر) الزامی است.')
      return
    }
    try {
      await createBankTransaction(token, {
        bank_account_id: bankAccountId,
        transaction_date: transactionDate,
        amount: direction === 'deposit' ? Number(amount) : -Number(amount),
        counter_account_id: counterAccountId,
        description,
      })
      setAmount('')
      setDescription('')
      setMessage('تراکنش بانکی با موفقیت ثبت شد.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <form className="invoice-form" onSubmit={handleSubmit}>
      <h3>واریز/برداشت بانکی</h3>
      <label>
        حساب بانکی
        <select value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
          <option value="">— انتخاب —</option>
          {bankAccounts.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        نوع تراکنش
        <select value={direction} onChange={(e) => setDirection(e.target.value as 'deposit' | 'withdraw')}>
          <option value="deposit">واریز</option>
          <option value="withdraw">برداشت</option>
        </select>
      </label>
      <label>
        مبلغ
        <input type="number" min="0" value={amount} onChange={(e) => setAmount(e.target.value)} />
      </label>
      <label>
        حساب مقابل (مثلاً صندوق)
        <select value={counterAccountId} onChange={(e) => setCounterAccountId(e.target.value)}>
          <option value="">— انتخاب —</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.code} — {a.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        توضیحات
        <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <label>
        تاریخ
        <JalaliDatePicker value={transactionDate} onChange={setTransactionDate} />
      </label>
      <div className="invoice-form-footer">
        <button type="submit" className="btn-primary"><Save size={14} /> ثبت تراکنش</button>
      </div>
      {message && <div className="hint">{message}</div>}
    </form>
  )
}

function PettyCashForms({
  token,
  sourceAccounts,
  expenseAccounts,
}: {
  token: string
  sourceAccounts: AccountCache[]
  expenseAccounts: AccountCache[]
}) {
  const [chargeAmount, setChargeAmount] = useState('')
  const [chargeSourceId, setChargeSourceId] = useState('')
  const [chargeDate, setChargeDate] = useState(todayIso())
  const [expenseAmount, setExpenseAmount] = useState('')
  const [expenseAccountId, setExpenseAccountId] = useState('')
  const [expenseDescription, setExpenseDescription] = useState('')
  const [expenseDate, setExpenseDate] = useState(todayIso())
  const [message, setMessage] = useState<string | null>(null)

  async function handleCharge(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!chargeSourceId || Number(chargeAmount) <= 0) {
      setMessage('حساب منبع و مبلغ (بزرگ‌تر از صفر) الزامی است.')
      return
    }
    try {
      await createPettyCashCharge(token, {
        transaction_date: chargeDate,
        amount: Number(chargeAmount),
        source_account_id: chargeSourceId,
        description: 'شارژ تنخواه‌گردان',
      })
      setChargeAmount('')
      setMessage('تنخواه‌گردان شارژ شد.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleExpense(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    if (!expenseAccountId || Number(expenseAmount) <= 0) {
      setMessage('حساب هزینه و مبلغ (بزرگ‌تر از صفر) الزامی است.')
      return
    }
    try {
      await createPettyCashExpense(token, {
        transaction_date: expenseDate,
        amount: Number(expenseAmount),
        expense_account_id: expenseAccountId,
        description: expenseDescription,
      })
      setExpenseAmount('')
      setExpenseDescription('')
      setMessage('هزینه از تنخواه‌گردان ثبت شد.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <>
      <form className="invoice-form" onSubmit={handleCharge}>
        <h3>شارژ تنخواه‌گردان</h3>
        <label>
          از حساب
          <select value={chargeSourceId} onChange={(e) => setChargeSourceId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {sourceAccounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          مبلغ
          <input type="number" min="0" value={chargeAmount} onChange={(e) => setChargeAmount(e.target.value)} />
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={chargeDate} onChange={setChargeDate} />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary"><Save size={14} /> شارژ</button>
        </div>
      </form>

      <form className="invoice-form" onSubmit={handleExpense}>
        <h3>هزینه‌کرد از تنخواه‌گردان</h3>
        <label>
          بابت حساب هزینه
          <select value={expenseAccountId} onChange={(e) => setExpenseAccountId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {expenseAccounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          مبلغ
          <input type="number" min="0" value={expenseAmount} onChange={(e) => setExpenseAmount(e.target.value)} />
        </label>
        <label>
          توضیحات
          <input type="text" value={expenseDescription} onChange={(e) => setExpenseDescription(e.target.value)} />
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={expenseDate} onChange={setExpenseDate} />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary"><Save size={14} /> ثبت هزینه</button>
        </div>
      </form>

      {message && <div className="hint">{message}</div>}
    </>
  )
}
