import { useCallback, useEffect, useMemo, useState } from 'react'
import { Wallet, Save, RefreshCw, ArrowDownToLine, ArrowUpFromLine } from 'lucide-react'
import {
  fetchPettyCashBalance, fetchPettyCashTransactions, createPettyCashCharge, createPettyCashExpense,
  type PettyCashRecord,
} from '../api'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { StatCard } from './StatCard'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

/**
 * تنخواه‌گردان — تا امروز فقط دو فرمِ شارژ/هزینه بود و موجودی/دفترچه‌اش دیده نمی‌شد.
 * حالا: موجودیِ زنده + دفترچه‌ی گردش با ماندهٔ در حال اجرا کنارِ فرم‌ها.
 */
export function PettyCashPanel({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const postable = useMemo(() => accounts.filter((a) => !a.is_group), [accounts])
  const expenseAccounts = useMemo(() => postable.filter((a) => a.type === 'expense'), [postable])

  const [balance, setBalance] = useState<number | null>(null)
  const [txns, setTxns] = useState<PettyCashRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [bal, list] = await Promise.all([fetchPettyCashBalance(token), fetchPettyCashTransactions(token)])
      setBalance(Number(bal.balance) || 0)
      setTxns(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }, [token])

  useEffect(() => { void refresh() }, [refresh])

  // ماندهٔ در حال اجرا: از قدیمی به جدید محاسبه و برای نمایش معکوس می‌شود (تازه‌ترین اول)
  const rows = useMemo(() => {
    const list = [...(txns ?? [])].sort((a, b) => (a.transaction_date < b.transaction_date ? -1 : 1))
    let run = 0
    const withRun = list.map((t) => {
      run += t.type === 'charge' ? Number(t.amount) : -Number(t.amount)
      return { ...t, running: run }
    })
    return withRun.reverse()
  }, [txns])

  // فرم‌ها
  const [chargeAmount, setChargeAmount] = useState('')
  const [chargeSourceId, setChargeSourceId] = useState('')
  const [chargeDate, setChargeDate] = useState(todayIso())
  const [expenseAmount, setExpenseAmount] = useState('')
  const [expenseAccountId, setExpenseAccountId] = useState('')
  const [expenseDescription, setExpenseDescription] = useState('')
  const [expenseDate, setExpenseDate] = useState(todayIso())

  async function handleCharge(e: React.FormEvent) {
    e.preventDefault(); setMessage(null); setError(null)
    if (!chargeSourceId || Number(chargeAmount) <= 0) { setMessage('حساب منبع و مبلغ (بزرگ‌تر از صفر) الزامی است.'); return }
    try {
      await createPettyCashCharge(token, { transaction_date: chargeDate, amount: Number(chargeAmount), source_account_id: chargeSourceId, description: 'شارژ تنخواه‌گردان' })
      setChargeAmount(''); setMessage('تنخواه‌گردان شارژ شد.'); await refresh()
    } catch (err) { setMessage(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  async function handleExpense(e: React.FormEvent) {
    e.preventDefault(); setMessage(null); setError(null)
    if (!expenseAccountId || Number(expenseAmount) <= 0) { setMessage('حساب هزینه و مبلغ (بزرگ‌تر از صفر) الزامی است.'); return }
    try {
      await createPettyCashExpense(token, { transaction_date: expenseDate, amount: Number(expenseAmount), expense_account_id: expenseAccountId, description: expenseDescription })
      setExpenseAmount(''); setExpenseDescription(''); setMessage('هزینه از تنخواه‌گردان ثبت شد.'); await refresh()
    } catch (err) { setMessage(err instanceof Error ? err.message : 'خطای ناشناخته') }
  }

  return (
    <div className="page-block">
      <div className="stat-grid">
        <StatCard icon={<Wallet size={18} />} label="موجودیِ تنخواه‌گردان" value={balance == null ? '—' : fa(balance)} hint="ریال" tone={balance != null && balance < 0 ? 'danger' : 'default'} />
      </div>

      <div className="workspace-split">
        <SectionCard icon={ArrowDownToLine} title="شارژ تنخواه‌گردان" description="انتقالِ پول از صندوق/بانک به تنخواه.">
          <form className="invoice-form" onSubmit={handleCharge}>
            <label>از حساب
              <select value={chargeSourceId} onChange={(e) => setChargeSourceId(e.target.value)}>
                <option value="">— انتخاب —</option>
                {postable.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
              </select>
            </label>
            <label>مبلغ<input type="number" min="0" value={chargeAmount} onChange={(e) => setChargeAmount(e.target.value)} /></label>
            <label>تاریخ<JalaliDatePicker value={chargeDate} onChange={setChargeDate} /></label>
            <div className="invoice-form-footer"><button type="submit" className="btn-primary"><Save size={14} /> شارژ</button></div>
          </form>
        </SectionCard>

        <SectionCard icon={ArrowUpFromLine} title="هزینه‌کرد از تنخواه‌گردان" description="ثبتِ هزینه‌ی پرداخت‌شده از تنخواه.">
          <form className="invoice-form" onSubmit={handleExpense}>
            <label>بابت حساب هزینه
              <select value={expenseAccountId} onChange={(e) => setExpenseAccountId(e.target.value)}>
                <option value="">— انتخاب —</option>
                {expenseAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
              </select>
            </label>
            <label>مبلغ<input type="number" min="0" value={expenseAmount} onChange={(e) => setExpenseAmount(e.target.value)} /></label>
            <label>توضیحات<input type="text" value={expenseDescription} onChange={(e) => setExpenseDescription(e.target.value)} /></label>
            <label>تاریخ<JalaliDatePicker value={expenseDate} onChange={setExpenseDate} /></label>
            <div className="invoice-form-footer"><button type="submit" className="btn-primary"><Save size={14} /> ثبت هزینه</button></div>
          </form>
        </SectionCard>
      </div>
      {message && <div className="hint">{message}</div>}

      <SectionCard
        icon={Wallet}
        title="دفترچه‌ی تنخواه‌گردان"
        description="گردشِ شارژ و هزینه با ماندهٔ در حال اجرا، تازه‌ترین اول."
        actions={<button onClick={() => void refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
      >
        {error && <div className="error">{error}</div>}
        {txns == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState icon={Wallet} text="هنوز گردشی در تنخواه ثبت نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table petty-table">
              <thead>
                <tr><th>تاریخ</th><th>نوع</th><th>شرح</th><th>مبلغ</th><th>مانده</th></tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                    <td data-label="نوع">
                      <span className={`status-badge ${t.type === 'charge' ? 'tone-success' : 'tone-warning'}`}>
                        {t.type === 'charge' ? 'شارژ' : 'هزینه'}
                      </span>
                    </td>
                    <td data-label="شرح">{t.description || '—'}</td>
                    <td data-label="مبلغ" className={`money-cell ${t.type === 'charge' ? 'pos-in' : 'pos-out'}`}>
                      {t.type === 'charge' ? '+' : '−'}{fa(Number(t.amount))}
                    </td>
                    <td data-label="مانده" className="money-cell"><strong>{fa(t.running)}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
