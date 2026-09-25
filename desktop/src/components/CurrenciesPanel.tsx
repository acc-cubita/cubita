import { useEffect, useMemo, useRef, useState } from 'react'
import { Coins, Trash2, TrendingUp } from 'lucide-react'
import { createCurrency, deleteCurrency, fetchCurrencies, fetchRates, upsertRate, type Currency, type ExchangeRate } from '../api'
import { SectionCard } from './SectionCard'
import { SearchSelect } from './SearchSelect'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { SheetFooter, type SheetState } from './SheetFooter'
import { ColResizer } from './XlGrid'
import { CountBadge, RowAction } from './form/FormKit'
import { formatJalali, todayIso } from '../lib/jalali'
import { useAlignToGrid, type SlotMap } from '../lib/alignToGrid'
import { useColumnWidths } from '../lib/useColumnWidths'
import { useSheetNav } from '../lib/useSheetNav'
import { tenantKey } from '../lib/tenantScope'
import {
  blankCurrency,
  blankRate,
  currencyIsBlank,
  currencyProblem,
  editedRate,
  latestRates,
  parseCurrencyDraft,
  pendingCount,
  rateChanges,
  rateIsBlank,
  rateProblem,
  sortRates,
  takenCodes,
  withTrailingBlank,
  type CurrencyDraft,
  type FreshCurrency,
  type FreshRate,
} from '../lib/currencySheet'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')
const pct = (v: number) => `${v.toLocaleString('fa-IR', { maximumFractionDigits: 2, signDisplay: 'exceptZero' })}٪`

/**
 * ارزها و نرخِ برابری — دو برگه‌ی اکسلی با ویرایشِ درجا و یک «ذخیره تغییرات» (Ctrl+S)، هم‌سبکِ «تفصیلی
 * سایر». هم صفحه‌ی «ارزها و نرخ ارز» است و هم پایینِ «صدور سند تسعیر ارز» (تا نرخِ جاافتاده همان‌جا ثبت
 * شود؛ `onSaved` پیش‌نمایشِ تسعیر را دوباره حساب می‌کند).
 *
 * سرور ارز را فقط می‌سازد و حذف می‌کند، و نرخ را «ثبت یا جایگزین» می‌کند (ارز + تاریخ یکتاست). پس ارزِ
 * ثبت‌شده فقط‌خواندنی است، در نرخِ ثبت‌شده فقط خودِ عدد عوض می‌شود، و زیرِ هر برگه یک ردیفِ خالی برای تازه‌ها.
 * نرخ‌ها به ترتیبِ زمان‌اند (تازه‌ها پایین، کنارِ ردیفِ ثبتِ نرخِ امروز) و ستونِ «تغییر» درصدِ تغییر نسبت به نرخِ
 * قبلیِ همان ارز است. نوارِ پایین ستون‌به‌ستون با برگه‌ی نرخ‌ها؛ پیش‌نویسِ ذخیره‌نشده در نشستِ همین کسب‌وکار.
 */

const DRAFT_KEY = 'cubita.currencies.draft'
const CUR_LAYOUT = { fixed: ['num', 'actions'], auto: 'name' } as const
const RATE_LAYOUT = { fixed: ['num', 'actions'], auto: 'currency' } as const
type CurCol = 'code' | 'name' | 'symbol'
type RateCol = 'currency' | 'date' | 'rate'
const CUR_COLS: CurCol[] = ['code', 'name', 'symbol']
const RATE_COLS: RateCol[] = ['currency', 'date', 'rate']

/** نوارِ پایین روی برگه‌ی نرخ‌ها: [دکمه] زیرِ ردیف+ارز، وضعیت زیرِ تاریخ، تازه زیرِ نرخ، ویرایش‌شده زیرِ تغییر. */
const RATE_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  return [w('num') + w('currency'), w('date'), w('rate'), w('change'), w('actions')]
}

let seq = 0
const newKey = () => `n-${Date.now().toString(36)}-${++seq}`
const freshCurrencies = (list: FreshCurrency[]) => withTrailingBlank(list, currencyIsBlank, () => blankCurrency(newKey()))
const freshRates = (list: FreshRate[]) => withTrailingBlank(list, rateIsBlank, () => blankRate(newKey(), todayIso()))

function loadDraft(): CurrencyDraft {
  const key = tenantKey(DRAFT_KEY)
  let d: CurrencyDraft | null = null
  try {
    d = key ? parseCurrencyDraft(sessionStorage.getItem(key)) : null
  } catch {
    d = null
  }
  return {
    currencies: freshCurrencies(d?.currencies ?? []),
    rates: freshRates(d?.rates ?? []),
    edits: d?.edits ?? {},
  }
}
const hasContent = (d: CurrencyDraft) =>
  Object.keys(d.edits).length > 0 || d.currencies.some((c) => !currencyIsBlank(c)) || d.rates.some((r) => !rateIsBlank(r))

type CurRow = { kind: 'saved'; key: string; c: Currency } | { kind: 'new'; key: string; f: FreshCurrency }
type RateRow = { kind: 'saved'; key: string; r: ExchangeRate } | { kind: 'new'; key: string; f: FreshRate }

export function CurrenciesPanel({ token, onSaved }: { token: string; onSaved?: () => void }) {
  const [currencies, setCurrencies] = useState<Currency[] | null>(null)
  const [rates, setRates] = useState<ExchangeRate[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [draft, setDraft] = useState<CurrencyDraft>(loadDraft)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [only, setOnly] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(() =>
    hasContent(loadDraft()) ? { text: 'تغییرهای ذخیره‌نشده‌ی دفعه‌ی قبل برگشت — «ذخیره تغییرات» بزنید.', kind: 'ok' } : null,
  )
  const formRef = useRef<HTMLFormElement>(null)
  const curGrid = useRef<HTMLDivElement>(null)
  const rateGrid = useRef<HTMLDivElement>(null)
  const scrolled = useRef(false)
  const curCw = useColumnWidths('cubita.grid.currencies.shares', CUR_LAYOUT)
  const rateCw = useColumnWidths('cubita.grid.rates.shares', RATE_LAYOUT)
  useAlignToGrid(formRef, '.jf-foot--cols', { table: '.cur-rates', slots: RATE_SLOTS })

  async function refresh() {
    try {
      const [cs, rs] = await Promise.all([fetchCurrencies(token), fetchRates(token)])
      setCurrencies(cs)
      setRates(rs)
      setLoadError(null)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }
  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    const key = tenantKey(DRAFT_KEY)
    if (!key) return
    try {
      if (hasContent(draft)) sessionStorage.setItem(key, JSON.stringify(draft))
      else sessionStorage.removeItem(key)
    } catch {
      //: ذخیره‌نشدنِ پیش‌نویس فقط یعنی با بستنِ صفحه می‌رود.
    }
  }, [draft])

  const sortedRates = useMemo(() => sortRates(rates), [rates])
  //: درصدِ تغییر با نرخِ ویرایش‌شده حساب می‌شود — کاربر همان‌جا می‌بیند عددش نسبت به قبل چقدر است.
  const changes = useMemo(
    () => rateChanges(sortedRates.map((r) => ({ ...r, rate: draft.edits[r.id]?.trim() ? draft.edits[r.id] : r.rate }))),
    [sortedRates, draft.edits],
  )
  const latest = useMemo(() => latestRates(rates), [rates])
  const counts = pendingCount(draft, rates)

  //: برگه‌ی نرخ‌ها را یک‌بار تا پایین می‌برد: تازه‌ترین نرخ‌ها و ردیفِ ثبتِ نرخِ امروز آن‌جاست.
  useEffect(() => {
    if (scrolled.current || rates.length === 0 || !rateGrid.current) return
    scrolled.current = true
    rateGrid.current.scrollTop = rateGrid.current.scrollHeight
  }, [rates.length])

  const curRows: CurRow[] = [
    ...(currencies ?? []).map((c): CurRow => ({ kind: 'saved', key: c.id, c })),
    ...draft.currencies.map((f): CurRow => ({ kind: 'new', key: f.key, f })),
  ]
  const rateRows: RateRow[] = [
    ...sortedRates.filter((r) => !only || r.currency_code === only).map((r): RateRow => ({ kind: 'saved', key: r.id, r })),
    ...draft.rates.map((f): RateRow => ({ kind: 'new', key: f.key, f })),
  ]

  function editCurrency(key: string, patch: Partial<FreshCurrency>) {
    setErrors((e) => omit(e, [key]))
    setDraft((d) => ({ ...d, currencies: freshCurrencies(d.currencies.map((f) => (f.key === key ? { ...f, ...patch } : f))) }))
  }
  function editRate(row: RateRow, patch: Partial<FreshRate>) {
    setErrors((e) => omit(e, [row.key]))
    setDraft((d) =>
      row.kind === 'saved'
        ? { ...d, edits: { ...d.edits, [row.key]: patch.rate ?? '' } }
        : { ...d, rates: freshRates(d.rates.map((f) => (f.key === row.key ? { ...f, ...patch } : f))) },
    )
  }
  const dropCurrency = (key: string) => setDraft((d) => ({ ...d, currencies: freshCurrencies(d.currencies.filter((f) => f.key !== key)) }))
  const dropRate = (key: string) => setDraft((d) => ({ ...d, rates: freshRates(d.rates.filter((f) => f.key !== key)) }))

  async function removeCurrency(c: Currency) {
    if (!window.confirm(`ارزِ ${c.code} (${c.name}) حذف شود؟`)) return
    try {
      await deleteCurrency(token, c.id)
      setMsg({ text: `ارزِ ${c.code} حذف شد.`, kind: 'ok' })
      await refresh()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  async function save() {
    if (busy) return
    const saved = currencies ?? []
    const problems: Record<string, string> = {}
    const jobs: { key: string; run: () => Promise<unknown> }[] = []
    //: ارزها اول: نرخِ ارزِ تازه تا ارز ساخته نشده ثبت نمی‌شود (انتخاب‌گرِ نرخ فقط ثبت‌شده‌ها را دارد).
    for (const f of draft.currencies) {
      if (currencyIsBlank(f)) continue
      const p = currencyProblem(f, takenCodes(saved, draft.currencies, f.key))
      if (p) problems[f.key] = p
      else
        jobs.push({
          key: f.key,
          run: () => createCurrency(token, { code: f.code.trim().toUpperCase(), name: f.name.trim(), symbol: f.symbol.trim() }),
        })
    }
    for (const r of rates) {
      const v = editedRate(r, draft.edits[r.id])
      if (v === null) continue
      const p = rateProblem({ ...r, rate: v })
      if (p) problems[r.id] = p
      else jobs.push({ key: r.id, run: () => upsertRate(token, { currency_code: r.currency_code, rate_date: r.rate_date, rate: Number(v) }) })
    }
    for (const f of draft.rates) {
      if (rateIsBlank(f)) continue
      const p = rateProblem(f)
      if (p) problems[f.key] = p
      else jobs.push({ key: f.key, run: () => upsertRate(token, { currency_code: f.currency_code, rate_date: f.rate_date, rate: Number(f.rate) }) })
    }
    if (jobs.length === 0 && Object.keys(problems).length === 0) {
      setMsg({ text: 'تغییری برای ذخیره نیست.', kind: 'ok' })
      return
    }
    setBusy(true)
    setMsg(null)
    const done: string[] = []
    for (const j of jobs) {
      try {
        await j.run()
        done.push(j.key)
      } catch (err) {
        problems[j.key] = err instanceof Error ? err.message : 'خطای ناشناخته'
      }
    }
    setDraft((d) => ({
      currencies: freshCurrencies(d.currencies.filter((f) => !done.includes(f.key))),
      rates: freshRates(d.rates.filter((f) => !done.includes(f.key))),
      edits: omit(d.edits, done),
    }))
    setErrors(problems)
    await refresh()
    setBusy(false)
    if (done.length > 0) onSaved?.()
    const bad = Object.keys(problems).length
    setMsg(
      bad > 0
        ? { text: `${fa(bad)} ردیف ذخیره نشد — دلیلش زیرِ برگه است.${done.length ? ` ${fa(done.length)} ردیف ذخیره شد.` : ''}`, kind: 'err' }
        : { text: `${fa(done.length)} ردیف ذخیره شد.`, kind: 'ok' },
    )
  }

  const curNav = useSheetNav<CurCol>({
    gridRef: curGrid,
    cols: CUR_COLS,
    rowCount: curRows.length,
    //: ارزِ ثبت‌شده فقط‌خواندنی است (سرور ویرایشِ ارز ندارد).
    enabled: (row) => curRows[row]?.kind === 'new',
    //: Enter: کد → نام → ردیفِ بعد؛ نماد اختیاری است و با Tab.
    enterPath: (row, col) => curRows[row]?.kind === 'new' && col !== 'symbol',
    onAppendRow: () => curRows.length - 1,
    onDeleteRow: (row) => {
      const r = curRows[row]
      if (r?.kind !== 'new' || currencyIsBlank(r.f)) return false
      dropCurrency(r.key)
      return true
    },
    rowHasContent: () => false,
  })
  const rateNav = useSheetNav<RateCol>({
    gridRef: rateGrid,
    cols: RATE_COLS,
    rowCount: rateRows.length,
    //: در نرخِ ثبت‌شده فقط خودِ عدد عوض می‌شود — ارز و تاریخ کلیدِ نرخ‌اند.
    enabled: (row, col) => rateRows[row]?.kind === 'new' || col === 'rate',
    //: Enter: ارز → نرخ → ردیفِ بعد؛ تاریخ پیش‌فرضِ امروز را دارد و با Tab عوض می‌شود.
    enterPath: (row, col) => col !== 'date' && (rateRows[row]?.kind === 'new' || col === 'rate'),
    onAppendRow: () => rateRows.length - 1,
    onDeleteRow: (row) => {
      const r = rateRows[row]
      if (r?.kind !== 'new' || rateIsBlank(r.f)) return false
      dropRate(r.key)
      return true
    },
    rowHasContent: () => false,
  })

  const head = (cw: typeof curCw, id: string, label: string, next: string, title?: string) => (
    <th data-col={id} title={title}>
      {label}
      {cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  const curErrors = curRows.filter((r) => errors[r.key])
  const rateErrors = rateRows.filter((r) => errors[r.key])
  const state: SheetState = Object.keys(errors).length > 0 ? 'err' : counts.fresh + counts.edited > 0 ? 'dirty' : 'clean'
  const saved = currencies ?? []

  return (
    <form
      ref={formRef}
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        void save()
      }}
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.code === 'KeyS') {
          e.preventDefault()
          void save()
        }
      }}
    >
      <SectionCard
        icon={Coins}
        title="ارزها"
        tip="ارزهای خارجی را تعریف کنید؛ ریال ارزِ پایه است و لازم نیست اضافه شود. ارزِ تازه را در ردیفِ خالیِ آخر بنویسید (کدِ سه‌حرفیِ استاندارد، مثلِ USD)."
        badge={<CountBadge accent>{fa(saved.length)} ارز</CountBadge>}
      >
        {loadError && <p className="ef-message ef-message--warn">{loadError}</p>}
        <div className="jg">
          <div ref={curGrid} className="table-scroll ef-table-wrap jg-wrap" onKeyDown={curNav.onKeyDown} role="grid" aria-label="ارزها">
            <table ref={curCw.frame} className="ef-table ef-table--edit jg-table xl-grid table-plain cur-list">
              <colgroup>
                <col className="jg-c-num" style={curCw.col('num')} />
                <col className="jg-c-code" style={curCw.col('code')} />
                <col className="jg-c-account" style={curCw.col('name')} />
                <col className="jg-c-sym" style={curCw.col('symbol')} />
                <col className="jg-c-last" style={curCw.col('last')} />
                <col className="jg-c-act1" style={curCw.col('actions')} />
              </colgroup>
              <thead>
                <tr>
                  <th className="ef-col-min xl-rowhead" data-col="num">
                    ردیف
                  </th>
                  {head(curCw, 'code', 'کد', 'name')}
                  {head(curCw, 'name', 'نام', 'symbol')}
                  {head(curCw, 'symbol', 'نماد', 'last')}
                  {head(curCw, 'last', 'نرخِ آخر', 'actions', 'آخرین نرخِ ثبت‌شده‌ی این ارز (ریال به‌ازای یک واحد).')}
                  <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
                </tr>
              </thead>
              <tbody>
                {curRows.map((row, i) => {
                  const last = i === curRows.length - 1
                  const blank = row.kind === 'new' && currencyIsBlank(row.f)
                  const cls = [row.kind === 'new' && !blank && 'xl-row--new', errors[row.key] && 'xl-row--error'].filter(Boolean).join(' ')
                  const lr = row.kind === 'saved' ? latest.get(row.c.code) : undefined
                  return (
                    <tr key={row.key} className={cls || undefined} title={errors[row.key]}>
                      <td className="ef-col-min xl-rowhead">
                        <span className="xl-rowhead-num">{last && blank ? '+' : fa(i + 1)}</span>
                      </td>
                      {row.kind === 'saved' ? (
                        <>
                          <td className="xl-txt" dir="ltr">
                            {row.c.code}
                          </td>
                          <td className="xl-txt">{row.c.name}</td>
                          <td className="xl-txt">{row.c.symbol || '—'}</td>
                        </>
                      ) : (
                        <>
                          <td data-cell={`${i}-0`}>
                            <input
                              type="text"
                              dir="ltr"
                              maxLength={3}
                              aria-label={`کدِ ارزِ ردیفِ ${fa(i + 1)}`}
                              value={row.f.code}
                              onChange={(e) => editCurrency(row.key, { code: e.target.value.toUpperCase() })}
                            />
                          </td>
                          <td data-cell={`${i}-1`}>
                            <input
                              type="text"
                              aria-label={`نامِ ارزِ ردیفِ ${fa(i + 1)}`}
                              value={row.f.name}
                              placeholder={last && blank ? 'ارزِ تازه: کد و نام را بنویسید…' : undefined}
                              onChange={(e) => editCurrency(row.key, { name: e.target.value })}
                            />
                          </td>
                          <td data-cell={`${i}-2`}>
                            <input
                              type="text"
                              aria-label={`نمادِ ارزِ ردیفِ ${fa(i + 1)}`}
                              value={row.f.symbol}
                              onChange={(e) => editCurrency(row.key, { symbol: e.target.value })}
                            />
                          </td>
                        </>
                      )}
                      <td className="num xl-ro">
                        {lr ? (
                          <>
                            {fa(lr.rate)} <span className="xl-ro-note">{formatJalali(lr.rate_date)}</span>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="ef-col-min jg-actions">
                        <div className="row-actions">
                          <RowAction
                            icon={Trash2}
                            label="حذف ارز"
                            danger
                            disabled={blank}
                            title={row.kind === 'saved' ? 'حذفِ ارز' : 'حذفِ ردیف (Ctrl+Delete)'}
                            onClick={() => (row.kind === 'saved' ? void removeCurrency(row.c) : dropCurrency(row.key))}
                          />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
        {curErrors.length > 0 && (
          <ul className="xl-errbar" role="alert">
            {curErrors.map((r) => (
              <li key={r.key}>
                <b>{r.kind === 'new' ? r.f.code || r.f.name || 'ارزِ تازه' : r.c.code}</b> — {errors[r.key]}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard
        icon={TrendingUp}
        title="نرخ برابری"
        tip="چند ریال به‌ازای یک واحد ارز. هر ارز در هر روز یک نرخ دارد — نرخِ همان روز را دوباره بنویسید تا جایگزین شود. فرمِ فاکتور آخرین نرخ را پیشنهاد می‌دهد."
        badge={<CountBadge>{fa(rates.length)} نرخ</CountBadge>}
        actions={
          saved.length > 1 ? (
            <div className="cur-only">
              <SearchSelect aria-label="نمایشِ نرخ‌های یک ارز" value={only} onChange={(e) => setOnly(e.target.value)}>
                <option value="">همه‌ی ارزها</option>
                {saved.map((c) => (
                  <option key={c.id} value={c.code}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </SearchSelect>
            </div>
          ) : undefined
        }
      >
        {saved.length === 0 ? (
          <div className="ef-empty">ابتدا در «ارزها» یک ارز بنویسید و ذخیره کنید؛ بعد نرخش را این‌جا ثبت کنید.</div>
        ) : (
          <div className="jg">
            <div ref={rateGrid} className="table-scroll ef-table-wrap jg-wrap" onKeyDown={rateNav.onKeyDown} role="grid" aria-label="نرخ‌های برابری">
              <table ref={rateCw.frame} className="ef-table ef-table--edit jg-table xl-grid table-plain cur-rates">
                <colgroup>
                  <col className="jg-c-num" style={rateCw.col('num')} />
                  <col className="jg-c-account" style={rateCw.col('currency')} />
                  <col className="jg-c-date" style={rateCw.col('date')} />
                  <col className="jg-c-amount" style={rateCw.col('rate')} />
                  <col className="jg-c-chg" style={rateCw.col('change')} />
                  <col className="jg-c-act1" style={rateCw.col('actions')} />
                </colgroup>
                <thead>
                  <tr>
                    <th className="ef-col-min xl-rowhead" data-col="num">
                      ردیف
                    </th>
                    {head(rateCw, 'currency', 'ارز', 'date')}
                    {head(rateCw, 'date', 'تاریخ', 'rate')}
                    {head(rateCw, 'rate', 'نرخ (ریال)', 'change')}
                    {head(rateCw, 'change', 'تغییر', 'actions', 'درصدِ تغییر نسبت به نرخِ قبلیِ همین ارز.')}
                    <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
                  </tr>
                </thead>
                <tbody>
                  {rateRows.map((row, i) => {
                    const last = i === rateRows.length - 1
                    const blank = row.kind === 'new' && rateIsBlank(row.f)
                    const value = row.kind === 'saved' ? (draft.edits[row.key] ?? row.r.rate) : row.f.rate
                    const changed = row.kind === 'saved' && editedRate(row.r, draft.edits[row.key]) !== null
                    //: ردیفِ تازه: تغییر نسبت به آخرین نرخِ ثبت‌شده‌ی همان ارز — پیش از ذخیره دیده می‌شود.
                    const prev = row.kind === 'new' && row.f.currency_code ? latest.get(row.f.currency_code) : undefined
                    const change =
                      row.kind === 'saved'
                        ? (changes.get(row.key) ?? null)
                        : prev && Number(row.f.rate) > 0
                          ? ((Number(row.f.rate) - Number(prev.rate)) / Number(prev.rate)) * 100
                          : null
                    const cls = [
                      row.kind === 'new' && !blank && 'xl-row--new',
                      changed && 'xl-row--dirty',
                      errors[row.key] && 'xl-row--error',
                    ]
                      .filter(Boolean)
                      .join(' ')
                    return (
                      <tr key={row.key} className={cls || undefined} title={errors[row.key]}>
                        <td className="ef-col-min xl-rowhead">
                          <span className="xl-rowhead-num">{last && blank ? '+' : fa(i + 1)}</span>
                        </td>
                        {row.kind === 'saved' ? (
                          <>
                            <td className="xl-txt">
                              <span dir="ltr">{row.r.currency_code}</span>
                              {saved.find((c) => c.code === row.r.currency_code) && (
                                <> — {saved.find((c) => c.code === row.r.currency_code)!.name}</>
                              )}
                            </td>
                            <td className="xl-txt">{formatJalali(row.r.rate_date)}</td>
                          </>
                        ) : (
                          <>
                            <td data-cell={`${i}-0`}>
                              <SearchSelect
                                aria-label={`ارزِ ردیفِ ${fa(i + 1)}`}
                                value={row.f.currency_code}
                                onChange={(e) => editRate(row, { currency_code: e.target.value })}
                              >
                                <option value="">{last && blank ? 'نرخِ تازه: ارز را انتخاب کنید…' : '— ارز —'}</option>
                                {saved.map((c) => (
                                  <option key={c.id} value={c.code}>
                                    {c.code} — {c.name}
                                  </option>
                                ))}
                              </SearchSelect>
                            </td>
                            <td data-cell={`${i}-1`}>
                              <JalaliDatePicker value={row.f.rate_date} onChange={(v) => editRate(row, { rate_date: v })} />
                            </td>
                          </>
                        )}
                        <td data-cell={`${i}-2`} className={changed ? 'is-changed' : undefined}>
                          <NumberInput
                            aria-label={`نرخِ ردیفِ ${fa(i + 1)}`}
                            allowDecimal
                            value={value}
                            onChange={(v) => editRate(row, { rate: v })}
                          />
                        </td>
                        <td className={`num xl-ro${change === null ? '' : change > 0 ? ' pos-in' : change < 0 ? ' pos-out' : ''}`}>
                          {change === null ? '—' : pct(change)}
                        </td>
                        <td className="ef-col-min jg-actions">
                          <div className="row-actions">
                            <RowAction
                              icon={Trash2}
                              label="حذف ردیف"
                              danger
                              disabled={row.kind === 'saved' || blank}
                              title={row.kind === 'saved' ? 'نرخِ ثبت‌شده حذف نمی‌شود — نرخِ درست را روی همان ردیف بنویسید.' : 'حذفِ ردیف (Ctrl+Delete)'}
                              onClick={() => dropRate(row.key)}
                            />
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {rateErrors.length > 0 && (
          <ul className="xl-errbar" role="alert">
            {rateErrors.map((r) => (
              <li key={r.key}>
                <b>
                  {r.kind === 'new'
                    ? `${r.f.currency_code || 'نرخِ تازه'} ${r.f.rate_date ? formatJalali(r.f.rate_date) : ''}`
                    : `${r.r.currency_code} ${formatJalali(r.r.rate_date)}`}
                </b>{' '}
                — {errors[r.key]}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SheetFooter state={state} fresh={counts.fresh} edited={counts.edited} submitting={busy} message={msg} columns />
    </form>
  )
}

function omit<T>(o: Record<string, T>, keys: readonly string[]): Record<string, T> {
  if (!keys.some((k) => k in o)) return o
  const out = { ...o }
  for (const k of keys) delete out[k]
  return out
}
