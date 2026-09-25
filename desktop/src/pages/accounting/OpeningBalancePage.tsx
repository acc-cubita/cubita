import { useEffect, useId, useMemo, useRef, useState, type Dispatch, type MouseEvent, type SetStateAction } from 'react'
import { CheckCircle2, Trash2, Wallet } from 'lucide-react'
import {
  createOpeningBalances,
  fetchAccountsLive,
  fetchItemsLive,
  fetchOpeningStatus,
  fetchWarehousesLive,
  type OpeningStatus,
} from '../../api'
import { NumberInput } from '../../components/NumberInput'
import { SectionCard } from '../../components/SectionCard'
import { SearchSelect } from '../../components/SearchSelect'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { AccountCombo, type ComboOption } from '../../components/AccountCombo'
import { BalanceFooter } from '../../components/BalanceFooter'
import { balanceState } from '../../lib/balanceState'
import { ColResizer, SelectionBar } from '../../components/XlGrid'
import { AddRowButton, CountBadge, RowAction } from '../../components/form/FormKit'
import { toNumber } from '../../lib/csv'
import { formatJalali, todayIso } from '../../lib/jalali'
import { useAlignToGrid, type SlotMap } from '../../lib/alignToGrid'
import { useColumnWidths } from '../../lib/useColumnWidths'
import { modsOf, useRowSelection } from '../../lib/rowSelection'
import { useSheetNav } from '../../lib/useSheetNav'
import { fa, faAmount, OpsPage, type Msg } from './kit'

/**
 * مانده‌های اول دوره — سندِ افتتاحیه‌ی نقطه‌ی شروعِ کار با کوبیتا.
 *
 * این صفحه پیش‌تر تبِ «فرآیند راه‌اندازی» بود، ولی خروجی‌اش یک **سندِ حسابداری** است و
 * جایش دفترداری است نه یک ماژولِ راه‌اندازیِ جداگانه: همان‌جا که کاربر چارت را می‌سازد و
 * سندِ اختتامیه/افتتاحیه‌ی سالِ بعد را صادر می‌کند. مجوزِ سرور هم از قبل `accounting` بود.
 *
 * فقط **یک** سندِ افتتاحیه مجاز است؛ اگر ثبت شده باشد صفحه به‌جای فرم، وضعیت را نشان
 * می‌دهد — اصلاح از راهِ سندِ دستی انجام می‌شود تا نقطه‌ی شروعِ دفتر دوباره‌نویسی نشود.
 *
 * **هم‌سبکِ «سند حسابداری»** (خواسته‌ی آرش: صفحه‌ها یکی‌یکی با همان تم): سربرگِ خانه‌ای، گریدِ اکسلی
 * با همان کلاس‌های گریدِ سند (`jg-table xl-grid`)، همان صفحه‌کلید (`useSheetNav`)، همان کادرِ «کد یا
 * نامِ حساب» و همان نوارِ پایین (`BalanceFooter`) — سربرگ و پایین ستون‌به‌ستون با گریدِ حساب‌ها
 * (`useAlignToGrid`). سندِ افتتاحیه «شرح ردیف» ندارد؛ پس وضعیتِ توازن تکه‌ی چپِ خانه‌ی «ردیف + حساب»
 * را می‌گیرد، کنارِ جمعِ بدهکار، و دو جمع باز دقیقاً زیرِ ستون‌های خودشان‌اند.
 */

type AccLine = { account_id: string; debit: string; credit: string }
type StockLine = { item_id: string; warehouse_id: string; qty: string; unit_cost: string }

const BLANK_LINE: AccLine = { account_id: '', debit: '', credit: '' }

/** سربرگ و نوارِ پایین روی گریدِ حساب‌ها: [دکمه | وضعیت] زیرِ ردیف+حساب، بعد بدهکار، بستانکار، آیکون. */
const OPENING_SLOTS: SlotMap = (cols) => {
  const w = (id: string) => cols.find((c) => c.id === id)?.w ?? 0
  const lead = w('num') + w('account')
  const status = Math.max(0, Math.min(220, lead * 0.35, lead - 200))
  return [lead - status, status, w('debit'), w('credit'), w('actions')]
}

export function OpeningBalancePage({ token }: { token: string }) {
  const [status, setStatus] = useState<OpeningStatus | null>(null)
  const [accounts, setAccounts] = useState<{ id: string; code: string; name: string; is_group: number }[]>([])
  const [items, setItems] = useState<{ id: string; sku: string; name: string; is_service: boolean }[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [date, setDate] = useState(todayIso())
  const [lines, setLines] = useState<AccLine[]>([{ ...BLANK_LINE }, { ...BLANK_LINE }])
  const [stock, setStock] = useState<StockLine[]>([])
  const [balancingId, setBalancingId] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<Msg>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const uid = useId()
  useAlignToGrid(formRef, '.jh-bar, .jf-foot--cols', { table: '.ob-accounts', slots: OPENING_SLOTS })

  async function refresh() {
    try {
      const [st, accs, its, whs] = await Promise.all([
        fetchOpeningStatus(token),
        fetchAccountsLive(token),
        fetchItemsLive(token),
        fetchWarehousesLive(token),
      ])
      setStatus(st)
      setAccounts(accs)
      setItems(its.filter((i) => !i.is_service))
      setWarehouses(whs)
      const capital = accs.find((a) => a.code === '3101')
      if (capital) setBalancingId(capital.id)
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const postable = useMemo(() => accounts.filter((a) => !a.is_group), [accounts])
  const accountOptions: ComboOption[] = useMemo(
    () => postable.map((a) => ({ value: a.id, label: `${a.code} — ${a.name}` })),
    [postable],
  )
  const itemOptions: ComboOption[] = useMemo(
    () => items.map((it) => ({ value: it.id, label: `${it.sku} — ${it.name}` })),
    [items],
  )
  const stockValue = stock.reduce((s, r) => s + toNumber(r.qty) * toNumber(r.unit_cost), 0)
  const totalDebit = lines.reduce((s, r) => s + toNumber(r.debit), 0) + stockValue
  const totalCredit = lines.reduce((s, r) => s + toNumber(r.credit), 0)
  const filledLines = lines.filter((l) => l.account_id && (toNumber(l.debit) > 0 || toNumber(l.credit) > 0))
  const validStock = stock.filter((s) => s.item_id && s.warehouse_id && toNumber(s.qty) > 0)
  const state = balanceState(totalDebit, totalCredit, Math.abs(totalDebit - totalCredit) < 0.005, Boolean(balancingId))

  async function submit() {
    if (filledLines.length === 0 && validStock.length === 0) {
      setMsg({ text: 'دست‌کم یک مانده‌ی حساب یا یک ردیفِ موجودی وارد کنید.', kind: 'err' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      await createOpeningBalances(token, {
        entry_date: date,
        lines: filledLines.map((l) => ({
          account_id: l.account_id,
          debit: toNumber(l.debit),
          credit: toNumber(l.credit),
        })),
        stock: validStock.map((s) => ({
          item_id: s.item_id,
          warehouse_id: s.warehouse_id,
          qty: toNumber(s.qty),
          unit_cost: toNumber(s.unit_cost),
        })),
        balancing_account_id: balancingId || null,
      })
      setMsg({ text: 'سند افتتاحیه با موفقیت ثبت شد.', kind: 'ok' })
      await refresh()
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  if (status?.exists) {
    return (
      <OpsPage
        canvas
        icon={Wallet}
        title="مانده اول دوره"
        description="مانده‌ی حساب‌ها و موجودیِ انبار در لحظه‌ی شروعِ کار با کوبیتا — از همین‌جا سندِ افتتاحیه ساخته می‌شود."
      >
        <SectionCard icon={Wallet} title="مانده‌های اول دوره">
          <div className="ef-callout">
            <CheckCircle2 size={18} />
            <p>
              سند افتتاحیه‌ی این کسب‌وکار قبلاً ثبت شده است (شماره {fa(status.entry_number ?? 0)}، تاریخ{' '}
              {status.entry_date ? formatJalali(status.entry_date) : '—'}). برای جلوگیری از دوباره‌کاری فقط یک سندِ
              افتتاحیه مجاز است؛ اصلاحات را با «سند حسابداری» انجام دهید.
            </p>
          </div>
        </SectionCard>
      </OpsPage>
    )
  }

  return (
    <OpsPage
      canvas
      icon={Wallet}
      title="مانده اول دوره"
      description="مانده‌ی حساب‌ها و موجودیِ انبار در لحظه‌ی شروعِ کار با کوبیتا — از همین‌جا سندِ افتتاحیه ساخته می‌شود."
    >
      <form
        ref={formRef}
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          if (!busy) void submit()
        }}
        onKeyDown={(e) => {
          //: Ctrl+S از هر جای فرم — روی دکمه نوشته شده (در مرورگر وگرنه «ذخیره‌ی صفحه» باز می‌شد).
          if ((e.ctrlKey || e.metaKey) && e.code === 'KeyS') {
            e.preventDefault()
            if (!busy) void submit()
          }
        }}
      >
        <SectionCard
          icon={Wallet}
          title="سندِ افتتاحیه"
          tip="اختلافِ تراز خودکار به حسابِ سرمایه بسته می‌شود؛ اگر حسابِ تراز را خالی بگذارید، سند باید خودش متوازن باشد."
          badge={<CountBadge>{fa(filledLines.length + validStock.length)} ردیف معتبر</CountBadge>}
        >
          <div className="jh-bar">
            <div className="jh-row">
              <div className="jh-field jh-field--grow">
                <label
                  className="jh-label"
                  htmlFor={`${uid}-bal`}
                  title="اختلافِ بدهکار و بستانکار خودکار به این حساب بسته می‌شود."
                >
                  حسابِ تراز (سرمایه)
                </label>
                <SearchSelect id={`${uid}-bal`} value={balancingId} onChange={(e) => setBalancingId(e.target.value)}>
                  <option value="">— بدون تراز خودکار (باید متوازن باشد) —</option>
                  {postable.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </SearchSelect>
              </div>
              <div className="jh-field jh-field--rest">
                <label className="jh-label" htmlFor={`${uid}-date`}>
                  تاریخِ افتتاحیه <span className="jh-req" aria-hidden="true">*</span>
                </label>
                <JalaliDatePicker id={`${uid}-date`} value={date} onChange={setDate} />
              </div>
            </div>
          </div>

          <AccountSheet lines={lines} setLines={setLines} options={accountOptions} />

          {warehouses.length > 0 && (
            <StockSheet stock={stock} setStock={setStock} options={itemOptions} warehouses={warehouses} value={stockValue} />
          )}
        </SectionCard>

        <BalanceFooter
          totalDebit={totalDebit}
          totalCredit={totalCredit}
          state={state}
          submitting={busy}
          message={msg}
          submitLabel="ثبتِ سند افتتاحیه"
          autoNote="به سرمایه"
          shortcut
          columns
        />
      </form>
    </OpsPage>
  )
}

/** سرستونِ ردیفِ اکسلی: کلیک انتخاب، Ctrl+کلیک افزودن، Shift+کلیک بازه؛ بیرون از Tab. */
function RowHead({ i, selected, onPick }: { i: number; selected: boolean; onPick: (e: MouseEvent) => void }) {
  return (
    <td className="ef-col-min jg-num xl-rowhead card-title">
      <button
        type="button"
        tabIndex={-1}
        className="xl-rowhead-btn"
        aria-pressed={selected}
        aria-label={`انتخابِ ردیفِ ${fa(i + 1)}`}
        onClick={onPick}
      >
        {fa(i + 1)}
      </button>
    </td>
  )
}

type AccCol = 'account' | 'debit' | 'credit'
const ACC_COLS: AccCol[] = ['account', 'debit', 'credit']
const ACC_LAYOUT = { fixed: ['num', 'actions'], auto: 'account' } as const

/** گریدِ مانده‌ی حساب‌ها — همان گریدِ سند، بی ستون‌های شرح و مرکز. */
function AccountSheet({
  lines,
  setLines,
  options,
}: {
  lines: AccLine[]
  setLines: Dispatch<SetStateAction<AccLine[]>>
  options: ComboOption[]
}) {
  const gridRef = useRef<HTMLDivElement>(null)
  const cw = useColumnWidths('cubita.grid.opening.shares', ACC_LAYOUT)
  const { selected, click, clear } = useRowSelection()
  //: افزودن/حذفِ ردیف شاخص‌ها را جابه‌جا می‌کند؛ انتخابِ کهنه ردیفِ اشتباه را می‌گرفت.
  useEffect(() => clear(), [lines.length, clear])
  const rows = [...selected].map(Number).sort((a, b) => a - b)
  const order = lines.map((_, i) => String(i))

  const update = (i: number, patch: Partial<AccLine>) =>
    setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  //: گرید هیچ‌وقت بی‌ردیف نمی‌ماند — همان قاعده‌ی گریدِ سند.
  const remove = (idx: number[]) =>
    setLines((ls) => {
      const keep = ls.filter((_, j) => !idx.includes(j))
      return keep.length > 0 ? keep : [{ ...BLANK_LINE }]
    })
  const append = () => setLines((ls) => [...ls, { ...BLANK_LINE }])

  const nav = useSheetNav<AccCol>({
    gridRef,
    cols: ACC_COLS,
    rowCount: lines.length,
    //: ردیفی که بدهکار گرفته تمام است — Enter از بستانکارش می‌پرد و به حسابِ ردیفِ بعد می‌رود.
    enterPath: (row, col) => col !== 'credit' || !lines[row]?.debit,
    onAppendRow: append,
    onDeleteRow: (row) => {
      if (rows.length > 0) {
        remove(rows)
        return true
      }
      if (lines.length <= 1) return false
      remove([row])
      return true
    },
    rowHasContent: (row) => Boolean(lines[row] && (lines[row].account_id || lines[row].debit || lines[row].credit)),
  })
  const head = (id: string, label: string, next: string) => (
    <th data-col={id}>
      {label}
      {cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  const sum = (side: 'debit' | 'credit') => rows.reduce((s, r) => s + toNumber(lines[r]?.[side] ?? ''), 0)

  return (
    <div className="ob-block">
      <h3 className="ef-block-title">مانده‌ی حساب‌ها</h3>
      <div className="jg">
        <div
          ref={gridRef}
          className="table-scroll ef-table-wrap jg-wrap"
          onKeyDown={nav.onKeyDown}
          role="grid"
          aria-label="مانده‌ی حساب‌ها"
        >
          <table ref={cw.frame} className="ef-table ef-table--edit jg-table xl-grid table-plain ob-accounts">
            <colgroup>
              <col className="jg-c-num" style={cw.col('num')} />
              <col className="jg-c-account" style={cw.col('account')} />
              <col className="jg-c-amount" style={cw.col('debit')} />
              <col className="jg-c-amount" style={cw.col('credit')} />
              <col className="jg-c-act1" style={cw.col('actions')} />
            </colgroup>
            <thead>
              <tr>
                <th className="ef-col-min xl-rowhead" data-col="num">
                  ردیف
                </th>
                {head('account', 'حساب', 'debit')}
                {head('debit', 'بدهکار', 'credit')}
                {head('credit', 'بستانکار', 'actions')}
                <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={i} className={selected.has(String(i)) ? 'is-selected' : undefined}>
                  <RowHead i={i} selected={selected.has(String(i))} onPick={(e) => click(order, String(i), modsOf(e))} />
                  <td className="ef-col-wide" data-cell={`${i}-0`}>
                    <AccountCombo
                      aria-label={`حسابِ ردیفِ ${fa(i + 1)}`}
                      value={l.account_id}
                      options={options}
                      onChange={(v) => update(i, { account_id: v })}
                      onCommit={(how) => nav.commit(i, 'account', how)}
                    />
                  </td>
                  <td data-cell={`${i}-1`}>
                    <NumberInput
                      aria-label={`بدهکارِ ردیفِ ${fa(i + 1)}`}
                      value={l.debit}
                      onChange={(v) => update(i, { debit: v, credit: '' })}
                    />
                  </td>
                  <td data-cell={`${i}-2`}>
                    <NumberInput
                      aria-label={`بستانکارِ ردیفِ ${fa(i + 1)}`}
                      value={l.credit}
                      onChange={(v) => update(i, { credit: v, debit: '' })}
                    />
                  </td>
                  <td className="ef-col-min jg-actions">
                    <div className="row-actions">
                      <RowAction
                        icon={Trash2}
                        label="حذف ردیف"
                        danger
                        disabled={lines.length === 1}
                        title={lines.length === 1 ? 'دست‌کم یک ردیف لازم است.' : 'حذف ردیف (Ctrl+Delete)'}
                        onClick={() => remove([i])}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length > 0 && (
          <SelectionBar count={rows.length} unit="ردیف" onClear={clear}>
            <span>
              جمع بدهکار <b className="num">{fa(sum('debit'))}</b>
            </span>
            <span>
              جمع بستانکار <b className="num">{fa(sum('credit'))}</b>
            </span>
            <button type="button" className="xl-selbar-danger" onClick={() => remove(rows)}>
              <Trash2 size={14} aria-hidden="true" /> حذفِ ردیف‌ها (Ctrl+Delete)
            </button>
          </SelectionBar>
        )}
      </div>
      <AddRowButton onClick={append}>افزودن ردیف (Ctrl+Enter)</AddRowButton>
    </div>
  )
}

type StockCol = 'item' | 'warehouse' | 'qty' | 'unitCost'
const STOCK_COLS: StockCol[] = ['item', 'warehouse', 'qty', 'unitCost']
const STOCK_LAYOUT = { fixed: ['num', 'actions'], auto: 'item' } as const

/** گریدِ موجودیِ اول دوره — ارزشِ هر ردیف (تعداد × بهای واحد) خودکار به بدهکارِ سند می‌رود. */
function StockSheet({
  stock,
  setStock,
  options,
  warehouses,
  value,
}: {
  stock: StockLine[]
  setStock: Dispatch<SetStateAction<StockLine[]>>
  options: ComboOption[]
  warehouses: { id: string; name: string }[]
  value: number
}) {
  const gridRef = useRef<HTMLDivElement>(null)
  const cw = useColumnWidths('cubita.grid.openingStock.shares', STOCK_LAYOUT)
  const { selected, click, clear } = useRowSelection()
  useEffect(() => clear(), [stock.length, clear])
  const rows = [...selected].map(Number).sort((a, b) => a - b)
  const order = stock.map((_, i) => String(i))

  const blank = (): StockLine => ({ item_id: '', warehouse_id: warehouses[0]?.id ?? '', qty: '', unit_cost: '' })
  const update = (i: number, patch: Partial<StockLine>) =>
    setStock((ss) => ss.map((s, j) => (j === i ? { ...s, ...patch } : s)))
  const remove = (idx: number[]) => setStock((ss) => ss.filter((_, j) => !idx.includes(j)))
  const append = () => setStock((ss) => [...ss, blank()])

  const nav = useSheetNav<StockCol>({
    gridRef,
    cols: STOCK_COLS,
    rowCount: stock.length,
    //: انبار پیش‌فرض دارد؛ Enter از کالا مستقیم به تعداد می‌رود. Tab و موس به انبار هم می‌رسند.
    enterPath: (row, col) => col !== 'warehouse' || !stock[row]?.warehouse_id,
    onAppendRow: append,
    onDeleteRow: (row) => {
      remove(rows.length > 0 ? rows : [row])
      return true
    },
    rowHasContent: (row) => Boolean(stock[row] && (stock[row].item_id || stock[row].qty || stock[row].unit_cost)),
  })
  const head = (id: string, label: string, next: string) => (
    <th data-col={id}>
      {label}
      {cw.canResize(id, next) && <ColResizer onBegin={(e) => cw.begin(e, id)} onReset={cw.reset} />}
    </th>
  )
  const rowValue = (s: StockLine) => toNumber(s.qty) * toNumber(s.unit_cost)

  return (
    <div className="ef-block">
      <h3 className="ef-block-title">موجودیِ اول دوره</h3>
      <p className="ef-message ob-note">
        ارزشِ موجودی خودکار به‌عنوانِ بدهکارِ «موجودی کالا» به سند اضافه می‌شود — حسابِ موجودی را دستی وارد نکنید.
      </p>
      {stock.length > 0 && (
        <div className="jg">
          <div
            ref={gridRef}
            className="table-scroll ef-table-wrap jg-wrap"
            onKeyDown={nav.onKeyDown}
            role="grid"
            aria-label="موجودیِ اول دوره"
          >
            <table ref={cw.frame} className="ef-table ef-table--edit jg-table xl-grid table-plain ob-stock">
              <colgroup>
                <col className="jg-c-num" style={cw.col('num')} />
                <col className="jg-c-account" style={cw.col('item')} />
                <col className="jg-c-wh" style={cw.col('warehouse')} />
                <col className="jg-c-qty" style={cw.col('qty')} />
                <col className="jg-c-amount" style={cw.col('unitCost')} />
                <col className="jg-c-amount" style={cw.col('value')} />
                <col className="jg-c-act1" style={cw.col('actions')} />
              </colgroup>
              <thead>
                <tr>
                  <th className="ef-col-min xl-rowhead" data-col="num">
                    ردیف
                  </th>
                  {head('item', 'کالا', 'warehouse')}
                  {head('warehouse', 'انبار', 'qty')}
                  {head('qty', 'تعداد', 'unitCost')}
                  {head('unitCost', 'بهای واحد', 'value')}
                  {head('value', 'ارزش', 'actions')}
                  <th className="ef-col-min" data-col="actions" aria-label="کنش‌ها" />
                </tr>
              </thead>
              <tbody>
                {stock.map((s, i) => (
                  <tr key={i} className={selected.has(String(i)) ? 'is-selected' : undefined}>
                    <RowHead i={i} selected={selected.has(String(i))} onPick={(e) => click(order, String(i), modsOf(e))} />
                    <td className="ef-col-wide" data-cell={`${i}-0`}>
                      <AccountCombo
                        aria-label={`کالای ردیفِ ${fa(i + 1)}`}
                        placeholder="کد یا نامِ کالا…"
                        emptyText="کالایی با این کد یا نام پیدا نشد."
                        value={s.item_id}
                        options={options}
                        onChange={(v) => update(i, { item_id: v })}
                        onCommit={(how) => nav.commit(i, 'item', how)}
                      />
                    </td>
                    <td data-cell={`${i}-1`}>
                      <SearchSelect
                        aria-label={`انبارِ ردیفِ ${fa(i + 1)}`}
                        value={s.warehouse_id}
                        onChange={(e) => update(i, { warehouse_id: e.target.value })}
                      >
                        <option value="">— انبار —</option>
                        {warehouses.map((w) => (
                          <option key={w.id} value={w.id}>
                            {w.name}
                          </option>
                        ))}
                      </SearchSelect>
                    </td>
                    <td data-cell={`${i}-2`}>
                      <NumberInput
                        aria-label={`تعدادِ ردیفِ ${fa(i + 1)}`}
                        value={s.qty}
                        onChange={(v) => update(i, { qty: v })}
                        allowDecimal
                      />
                    </td>
                    <td data-cell={`${i}-3`}>
                      <NumberInput
                        aria-label={`بهای واحدِ ردیفِ ${fa(i + 1)}`}
                        value={s.unit_cost}
                        onChange={(v) => update(i, { unit_cost: v })}
                      />
                    </td>
                    {/* محاسبه‌شده، نه ورودی — خانه‌ی خاکستری و بیرون از مسیرِ صفحه‌کلید. */}
                    <td className="num xl-ro">{faAmount(rowValue(s))}</td>
                    <td className="ef-col-min jg-actions">
                      <div className="row-actions">
                        <RowAction
                          icon={Trash2}
                          label="حذف ردیف"
                          danger
                          title="حذف ردیف (Ctrl+Delete)"
                          onClick={() => remove([i])}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length > 0 && (
            <SelectionBar count={rows.length} unit="ردیف" onClear={clear}>
              <span>
                جمع ارزش <b className="num">{fa(rows.reduce((t, r) => t + (stock[r] ? rowValue(stock[r]) : 0), 0))}</b>
              </span>
              <button type="button" className="xl-selbar-danger" onClick={() => remove(rows)}>
                <Trash2 size={14} aria-hidden="true" /> حذفِ ردیف‌ها (Ctrl+Delete)
              </button>
            </SelectionBar>
          )}
        </div>
      )}
      <AddRowButton onClick={append}>{stock.length > 0 ? 'افزودن ردیف (Ctrl+Enter)' : 'افزودن موجودی'}</AddRowButton>
      {stock.length > 0 && (
        <p className="ef-message ob-note">
          ارزشِ کلِ موجودی <b className="num">{fa(value)}</b> ریال — در «جمع بدهکار»ِ پایینِ صفحه آمده است.
        </p>
      )}
    </div>
  )
}
