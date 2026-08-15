import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchPettyCashBalance,
  fetchPettyCashTransactions,
  createPettyCashCharge,
  createPettyCashExpense,
  type PettyCashRecord,
} from '../api'
import type { AccountCache } from '../electron.d'
import { todayIso } from './jalali'

/**
 * منطقِ مشترکِ «تنخواه‌گردان» — موجودیِ زنده + دفترچه‌ی گردش + دو عملیاتِ شارژ/هزینه.
 * فرمِ کلاسیک هر دو فرم را کنارِ هم می‌گذارد؛ ویزارد یکی‌یکی (بر اساسِ نوعِ انتخابی).
 */
export function usePettyCashDraft({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const postable = useMemo(() => accounts.filter((a) => !a.is_group), [accounts])
  const expenseAccounts = useMemo(() => postable.filter((a) => a.type === 'expense'), [postable])

  const [balance, setBalance] = useState<number | null>(null)
  const [txns, setTxns] = useState<PettyCashRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

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

  useEffect(() => {
    void refresh()
  }, [refresh])

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

  // فرمِ شارژ
  const [chargeAmount, setChargeAmount] = useState('')
  const [chargeSourceId, setChargeSourceId] = useState('')
  const [chargeDate, setChargeDate] = useState(todayIso())
  const chargeValid = !!chargeSourceId && Number(chargeAmount) > 0

  // فرمِ هزینه
  const [expenseAmount, setExpenseAmount] = useState('')
  const [expenseAccountId, setExpenseAccountId] = useState('')
  const [expenseDescription, setExpenseDescription] = useState('')
  const [expenseDate, setExpenseDate] = useState(todayIso())
  const expenseValid = !!expenseAccountId && Number(expenseAmount) > 0

  async function submitCharge(): Promise<boolean> {
    setMessage(null)
    setError(null)
    if (!chargeValid) {
      setMessage('حساب منبع و مبلغ (بزرگ‌تر از صفر) الزامی است.')
      return false
    }
    setSubmitting(true)
    try {
      await createPettyCashCharge(token, {
        transaction_date: chargeDate,
        amount: Number(chargeAmount),
        source_account_id: chargeSourceId,
        description: 'شارژ تنخواه‌گردان',
      })
      setChargeAmount('')
      setMessage('تنخواه‌گردان شارژ شد.')
      await refresh()
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  async function submitExpense(): Promise<boolean> {
    setMessage(null)
    setError(null)
    if (!expenseValid) {
      setMessage('حساب هزینه و مبلغ (بزرگ‌تر از صفر) الزامی است.')
      return false
    }
    setSubmitting(true)
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
      await refresh()
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    postable,
    expenseAccounts,
    balance,
    txns,
    rows,
    error,
    message,
    submitting,
    refresh,
    chargeAmount,
    setChargeAmount,
    chargeSourceId,
    setChargeSourceId,
    chargeDate,
    setChargeDate,
    chargeValid,
    submitCharge,
    expenseAmount,
    setExpenseAmount,
    expenseAccountId,
    setExpenseAccountId,
    expenseDescription,
    setExpenseDescription,
    expenseDate,
    setExpenseDate,
    expenseValid,
    submitExpense,
  }
}

export type PettyCashDraft = ReturnType<typeof usePettyCashDraft>
