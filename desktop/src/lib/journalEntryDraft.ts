import { useEffect, useState } from 'react'
import type { AccountCache } from '../electron.d'
import { createJournalEntryDirect, fetchCostCenters, type CostCenterRecord } from '../api'
import { isElectron } from '../platform'
import { todayIso } from './jalali'
import { usePersistentState } from './usePersistentState'

export interface JournalDraftLine {
  accountId: string
  debit: string
  credit: string
}

const emptyLine = (): JournalDraftLine => ({ accountId: '', debit: '', credit: '' })

/** منطقِ مشترکِ «ثبت سند حسابداری دستی» — مصرف‌شده در فرمِ کلاسیک و ویزارد. */
export function useJournalEntryDraft({
  token,
  accounts,
  onQueued,
}: {
  token: string
  accounts: AccountCache[]
  onQueued: () => void
}) {
  // ورودی‌های کاربر ماندگار می‌شوند (رفرش/جابه‌جایی پیش‌نویس را نمی‌برد)؛ داده‌ی سرور و پیام/در‌حال‌ثبت نه.
  const [description, setDescription] = usePersistentState('cubita.draft.journal.description', '')
  const [entryDate, setEntryDate] = usePersistentState('cubita.draft.journal.entryDate', todayIso())
  const [lines, setLines] = usePersistentState<JournalDraftLine[]>('cubita.draft.journal.lines', [emptyLine(), emptyLine()])
  const [message, setMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [costCenters, setCostCenters] = useState<CostCenterRecord[]>([])
  const [costCenterId, setCostCenterId] = usePersistentState('cubita.draft.journal.costCenterId', '')

  const postableAccounts = accounts.filter((a) => !a.is_group)

  // مراکز هزینه زنده خوانده می‌شوند (در کش محلی نیستند)؛ آفلاین که نشد، فهرست خالی
  // می‌ماند و انتخاب‌گر بی‌اثر است — ثبت سند بدون مرکز مثل قبل کار می‌کند.
  useEffect(() => {
    fetchCostCenters(token)
      .then((rows) => setCostCenters(rows.filter((c) => c.is_active)))
      .catch(() => setCostCenters([]))
  }, [token])

  function updateLine(index: number, patch: Partial<JournalDraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  function addLine() {
    setLines((prev) => [...prev, emptyLine()])
  }

  function removeLine(index: number) {
    setLines((prev) => (prev.length > 2 ? prev.filter((_, i) => i !== index) : prev))
  }

  const totalDebit = lines.reduce((sum, l) => sum + (Number(l.debit) || 0), 0)
  const totalCredit = lines.reduce((sum, l) => sum + (Number(l.credit) || 0), 0)
  const isBalanced = totalDebit === totalCredit && totalDebit > 0
  const validLineCount = lines.filter(
    (l) => l.accountId && ((Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0),
  ).length

  async function submit(): Promise<boolean> {
    setMessage(null)

    const validLines = lines.filter((l) => l.accountId && ((Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0))
    if (validLines.length < 2) {
      setMessage('سند باید حداقل دو ردیف معتبر (حساب + بدهکار یا بستانکار) داشته باشد.')
      return false
    }
    const debitSum = validLines.reduce((sum, l) => sum + (Number(l.debit) || 0), 0)
    const creditSum = validLines.reduce((sum, l) => sum + (Number(l.credit) || 0), 0)
    if (debitSum !== creditSum || debitSum === 0) {
      setMessage(`سند متوازن نیست: بدهکار=${debitSum.toLocaleString('fa-IR')} بستانکار=${creditSum.toLocaleString('fa-IR')}`)
      return false
    }

    const payload = {
      entry_date: entryDate,
      description,
      cost_center_id: costCenterId || null,
      lines: validLines.map((l) => ({
        account_id: l.accountId,
        debit: Number(l.debit) || 0,
        credit: Number(l.credit) || 0,
      })),
    }

    setSubmitting(true)
    try {
      if (isElectron) {
        await window.cubita.queueJournalEntry(payload)
        setMessage('سند در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور ارسال می‌شود.')
      } else {
        await createJournalEntryDirect(token, payload)
        setMessage('سند با موفقیت ثبت شد.')
      }
      setDescription('')
      setLines([emptyLine(), emptyLine()])
      setCostCenterId('')
      onQueued()
      return true
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    description,
    setDescription,
    entryDate,
    setEntryDate,
    lines,
    updateLine,
    addLine,
    removeLine,
    costCenters,
    costCenterId,
    setCostCenterId,
    postableAccounts,
    totalDebit,
    totalCredit,
    isBalanced,
    validLineCount,
    message,
    submitting,
    submit,
  }
}

export type JournalEntryDraft = ReturnType<typeof useJournalEntryDraft>
