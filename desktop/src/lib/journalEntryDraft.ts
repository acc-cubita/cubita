import { useEffect, useState } from 'react'
import type { AccountCache } from '../electron.d'
import {
  createJournalEntryDirect,
  fetchAnalytics,
  fetchCostCenters,
  fetchCurrencies,
  fetchLatestRate,
  type AnalyticAccount,
  type CostCenterRecord,
  type Currency,
} from '../api'
import { isElectron } from '../platform'
import { todayIso } from './jalali'
import { usePersistentState } from './usePersistentState'

export interface JournalDraftLine {
  accountId: string
  debit: string
  credit: string
  /** مبلغ به ارزِ انتخابیِ سند. خالی = ردیفِ ریالی. */
  fxAmount?: string
}

const emptyLine = (): JournalDraftLine => ({ accountId: '', debit: '', credit: '', fxAmount: '' })

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
  const [analytics, setAnalytics] = useState<AnalyticAccount[]>([])
  const [analyticId, setAnalyticId] = usePersistentState('cubita.draft.journal.analyticId', '')
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [currencyCode, setCurrencyCode] = usePersistentState('cubita.draft.journal.currency', '')
  const [fxRate, setFxRate] = usePersistentState('cubita.draft.journal.fxRate', '')
  //: سندِ تازه پیش‌فرض «موقت» است تا در کارتابل بازبینی شود؛ دفترداری که بازبینی
  //: نمی‌خواهد می‌تواند همان‌جا «دائم» بزند.
  const [status, setStatus] = usePersistentState<'temporary' | 'permanent'>(
    'cubita.draft.journal.status',
    'temporary',
  )

  const postableAccounts = accounts.filter((a) => !a.is_group)

  // مراکز هزینه/تفصیلی/ارز زنده خوانده می‌شوند (در کش محلی نیستند)؛ آفلاین که نشد،
  // فهرست خالی می‌ماند و انتخاب‌گر بی‌اثر است — ثبت سند مثل قبل کار می‌کند.
  useEffect(() => {
    fetchCostCenters(token)
      .then((rows) => setCostCenters(rows.filter((c) => c.is_active)))
      .catch(() => setCostCenters([]))
    fetchAnalytics(token)
      .then((rows) => setAnalytics(rows.filter((a) => a.is_active)))
      .catch(() => setAnalytics([]))
    fetchCurrencies(token)
      .then(setCurrencies)
      .catch(() => setCurrencies([]))
  }, [token])

  // با انتخابِ ارز، آخرین نرخِ ثبت‌شده پیشنهاد می‌شود تا کاربر عددی را که خودش
  // در «ارزها و نرخ ارز» گذاشته دوباره تایپ نکند.
  useEffect(() => {
    if (!currencyCode) return
    fetchLatestRate(token, currencyCode)
      .then((r) => setFxRate(String(r.rate ?? '')))
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, currencyCode])

  function updateLine(index: number, patch: Partial<JournalDraftLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  /** مبلغِ ارزی → معادلِ ریالی، روی همان طرفی که ردیف دارد.
   *
   *  قاعده‌ی ساده و قابلِ پیش‌بینی: اگر بستانکار پر است روی بستانکار می‌نشیند،
   *  وگرنه روی بدهکار. کاربر همیشه می‌تواند بعدش عددِ ریالی را دستی عوض کند. */
  function setLineFx(index: number, value: string) {
    const rate = Number(fxRate) || 0
    setLines((prev) =>
      prev.map((line, i) => {
        if (i !== index) return line
        const rial = rate > 0 && value ? String(Math.round(Number(value) * rate)) : ''
        if (!rial) return { ...line, fxAmount: value }
        return Number(line.credit) > 0
          ? { ...line, fxAmount: value, credit: rial, debit: '' }
          : { ...line, fxAmount: value, debit: rial, credit: '' }
      }),
    )
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

    const rate = Number(fxRate) || 0
    const payload = {
      entry_date: entryDate,
      description,
      cost_center_id: costCenterId || null,
      analytic_id: analyticId || null,
      status,
      lines: validLines.map((l) => ({
        account_id: l.accountId,
        debit: Number(l.debit) || 0,
        credit: Number(l.credit) || 0,
        // ردیفِ ارزی فقط وقتی ثبت می‌شود که هم ارز انتخاب شده باشد هم مبلغِ ارزی
        // نوشته شده باشد — نصفه‌کاره‌اش برای تسعیر بی‌فایده است.
        ...(currencyCode && Number(l.fxAmount)
          ? {
              currency_code: currencyCode,
              fx_amount: Number(l.fxAmount),
              fx_rate: rate || null,
            }
          : {}),
      })),
    }

    setSubmitting(true)
    try {
      if (isElectron) {
        await window.cubita.queueJournalEntry(payload)
        setMessage('سند در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور ارسال می‌شود.')
      } else {
        await createJournalEntryDirect(token, payload)
        setMessage(status === 'permanent' ? 'سند به‌صورتِ دائم ثبت شد.' : 'سندِ موقت ثبت شد؛ در کارتابل قابلِ بازبینی است.')
      }
      setDescription('')
      setLines([emptyLine(), emptyLine()])
      setCostCenterId('')
      setAnalyticId('')
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
    setLineFx,
    addLine,
    removeLine,
    costCenters,
    costCenterId,
    setCostCenterId,
    analytics,
    analyticId,
    setAnalyticId,
    currencies,
    currencyCode,
    setCurrencyCode,
    fxRate,
    setFxRate,
    status,
    setStatus,
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
