import { useEffect, useState } from 'react'
import type { AccountCache } from '../electron.d'
import {
  createJournalEntryDirect,
  fetchAnalytics,
  fetchCostCenters,
  fetchCurrencies,
  fetchTafsiliMode,
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
  /** پیگیری — فقط برای حسابی که «پیگیری» دارد؛ سرور بقیه را رد می‌کند. */
  trackingNo?: string
  trackingDate?: string
  /** تفصیلیِ ردیف — برای حسابِ «تفصیلی پذیر» اجباری. خالی = ارث از سطحِ سند. */
  analyticId?: string
}

const emptyLine = (): JournalDraftLine => ({
  accountId: '',
  debit: '',
  credit: '',
  fxAmount: '',
  trackingNo: '',
  trackingDate: '',
  analyticId: '',
})

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
  //: شماره فرعی — ارجاعِ آزادِ کاربر. عطف اینجا نیست: سرور می‌دهدش و فرم نه
  //: نشانش می‌دهد نه می‌فرستدش، چون چیزی برای انتخاب‌کردن ندارد.
  const [subNumber, setSubNumber] = usePersistentState('cubita.draft.journal.subNumber', '')
  const [entryDate, setEntryDate] = usePersistentState('cubita.draft.journal.entryDate', todayIso())
  const [lines, setLines] = usePersistentState<JournalDraftLine[]>('cubita.draft.journal.lines', [emptyLine(), emptyLine()])
  const [message, setMessage] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
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
  /** حساب‌هایی که ردیفشان پیگیری می‌پذیرد — فرم فقط برای همین‌ها فیلد نشان می‌دهد. */
  const trackingAllowed = new Set(accounts.filter((a) => a.has_tracking).map((a) => a.id))
  /** حساب‌هایی که ردیفشان تفصیلی می‌خواهند. */
  const tafsiliRequired = new Set(accounts.filter((a) => a.accepts_tafsili).map((a) => a.id))
  //: سطحِ اجبار از تنظیمات ← شخصی‌سازی می‌آید. در «شناور» فیلد هست ولی اجباری
  //: نیست، پس فرم نباید جلوی ثبت را بگیرد — وگرنه انتخابِ کاربر بی‌اثر می‌شد.
  const [tafsiliMode, setTafsiliMode] = useState('hybrid')
  useEffect(() => {
    fetchTafsiliMode(token)
      .then((r) => setTafsiliMode(r.mode))
      .catch(() => {})
  }, [token])

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
      setMessage({ text: 'سند باید حداقل دو ردیف معتبر (حساب + بدهکار یا بستانکار) داشته باشد.', kind: 'err' })
      return false
    }
    const debitSum = validLines.reduce((sum, l) => sum + (Number(l.debit) || 0), 0)
    const creditSum = validLines.reduce((sum, l) => sum + (Number(l.credit) || 0), 0)
    if (debitSum !== creditSum || debitSum === 0) {
      setMessage({
        text: `سند متوازن نیست: بدهکار ${debitSum.toLocaleString('fa-IR')} و بستانکار ${creditSum.toLocaleString('fa-IR')}.`,
        kind: 'err',
      })
      return false
    }

    // تفصیلیِ اجباری را همین‌جا می‌گیریم، نه با ۴۰۰ از سرور: کاربر باید بداند
    // *کدام ردیف* مشکل دارد، و آن را فقط این‌جا می‌دانیم. سرور هم گاردش را دارد.
    const missingTafsili =
      tafsiliMode === 'floating'
        ? []
        : validLines
            .map((l, i) => ({ l, i }))
            .filter(({ l }) => tafsiliRequired.has(l.accountId) && !(l.analyticId || analyticId))
            .map(({ i }) => (i + 1).toLocaleString('fa-IR'))
    if (missingTafsili.length > 0) {
      setMessage({
        text: `ردیفِ ${missingTafsili.join('، ')}: حسابِ «تفصیلی پذیر» بدونِ تفصیلی ثبت نمی‌شود.`,
        kind: 'err',
      })
      return false
    }

    const rate = Number(fxRate) || 0
    const payload = {
      entry_date: entryDate,
      description,
      cost_center_id: costCenterId || null,
      analytic_id: analyticId || null,
      status,
      sub_number: subNumber.trim() || null,
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
        // پیگیری فقط وقتی فرستاده می‌شود که حساب پذیرایش باشد *و* کاربر چیزی
        // نوشته باشد. اگر کاربر شماره‌ای بزند و بعد حساب را به حسابی بی‌پیگیری
        // عوض کند، آن مقدارِ جامانده سند را با ۴۰۰ رد می‌کرد.
        ...(l.analyticId ? { analytic_id: l.analyticId } : {}),
        ...(trackingAllowed.has(l.accountId) && (l.trackingNo?.trim() || l.trackingDate)
          ? {
              tracking_no: l.trackingNo?.trim() || null,
              tracking_date: l.trackingDate || null,
            }
          : {}),
      })),
    }

    setSubmitting(true)
    try {
      if (isElectron) {
        await window.cubita.queueJournalEntry(payload)
        setMessage({ text: 'سند در صف محلی ذخیره شد؛ با «هم‌گام‌سازی» به سرور ارسال می‌شود.', kind: 'ok' })
      } else {
        await createJournalEntryDirect(token, payload)
        setMessage({
          text: status === 'permanent' ? 'سند به‌صورتِ دائم ثبت شد.' : 'سندِ موقت ثبت شد؛ در کارتابل قابلِ بازبینی است.',
          kind: 'ok',
        })
      }
      setDescription('')
      //: پاک می‌شود مثلِ شرح. چسبیدنِ شماره فرعیِ سندِ قبلی به سندِ بعدی، ارجاعِ
      //: غلط می‌سازد — و ارجاعِ غلط بدتر از ارجاعِ نداشته است.
      setSubNumber('')
      setLines([emptyLine(), emptyLine()])
      setCostCenterId('')
      setAnalyticId('')
      onQueued()
      return true
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return {
    description,
    setDescription,
    subNumber,
    setSubNumber,
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
    trackingAllowed,
    tafsiliRequired,
    tafsiliMode,
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
