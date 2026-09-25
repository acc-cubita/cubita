import { createElement, useCallback, useState } from 'react'

import { JournalGrid } from '../components/JournalGrid'
import type { JournalDraftLine, JournalEntryDraft } from '../lib/journalEntryDraft'
import * as ops from '../lib/journalLineOps'

/**
 * پیش‌نویسِ آزمایشیِ `JournalGrid` برای تست‌های jsdom.
 *
 * بدل نیست: ردیف‌ها در `useState` می‌مانند و هر کنش همان تابعِ خالصِ
 * `journalLineOps` است که `useJournalEntryDraft` صدا می‌زند. فقط بارگذاریِ شبکه
 * (حساب‌ها، تفصیلی‌ها، ارز) کنار گذاشته شده.
 */
export const ACCOUNTS = [
  { id: 'bank', code: '1101', name: 'بانک ملی', is_group: false, has_tracking: false },
  { id: 'cust', code: '1301', name: 'طرف حساب', is_group: false, has_tracking: false },
]

export const line = (p: Partial<JournalDraftLine> = {}): JournalDraftLine => ({
  accountId: '',
  debit: '',
  credit: '',
  fxAmount: '',
  trackingNo: '',
  trackingDate: '',
  analyticId: '',
  description: '',
  ...p,
})

//: آخرین ردیف‌های رندرشده — تست از این‌جا وضعیت را می‌خواند.
export let latest: JournalDraftLine[] = []

//: همه‌ی مقدارهایی که به ردیف‌ها می‌رسند پایدارند — همان‌طور که در هوکِ واقعی
//: (`useCallback`/`useMemo`). بی این، `memo`ِ هر ۳۰۰ ردیف در هر کلید می‌شکست و سنجه‌ی
//: کارایی بدتر از برنامه‌ی واقعی نشان می‌داد.
const NO_ANALYTICS: never[] = []
const NONE = new Set<string>()
const NO_CENTERS: { id: string; code: string; name: string; is_active: boolean }[] = []
const noop = () => {}

export function Harness({
  initial,
  onSubmit,
  costCenters = NO_CENTERS,
}: {
  initial: JournalDraftLine[]
  onSubmit?: () => void
  costCenters?: { id: string; code: string; name: string; is_active: boolean }[]
}) {
  const [lines, setLines] = useState(initial)
  latest = lines
  const updateLine = useCallback(
    (i: number, patch: Partial<JournalDraftLine>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l))),
    [],
  )
  const removeLine = useCallback((i: number) => setLines((ls) => ops.removeAt(ls, i)), [])
  const removeLines = useCallback((ix: number[]) => setLines((ls) => ops.removeRows(ls, ix, () => line())), [])
  const duplicateLine = useCallback((i: number) => {
    setLines((ls) => ops.duplicateAt(ls, i))
    return i + 1
  }, [])
  const copyPreviousInto = useCallback((i: number) => setLines((ls) => ops.copyPreviousInto(ls, i)), [])
  const remaining = ops.remainingOf(ops.sumSide(lines, 'debit'), ops.sumSide(lines, 'credit'))
  const d = {
    lines,
    updateLine,
    setLineFx: noop,
    addLine: () => setLines((ls) => [...ls, line()]),
    removeLine,
    removeLines,
    duplicateLine,
    copyPreviousInto,
    remaining,
    applyRemaining: (i: number) => {
      if (!remaining) return false
      updateLine(i, remaining.side === 'debit' ? { debit: String(remaining.amount), credit: '' } : { credit: String(remaining.amount), debit: '' })
      return true
    },
    postableAccounts: ACCOUNTS,
    analytics: NO_ANALYTICS,
    analyticId: '',
    costCenters,
    costCenterId: '',
    tafsiliRequired: NONE,
    trackingAllowed: NONE,
    tafsiliMode: 'optional',
    currencyCode: '',
    submitting: false,
    submit: async () => {
      onSubmit?.()
      return true
    },
  } as unknown as JournalEntryDraft
  return createElement(JournalGrid, { d })
}
