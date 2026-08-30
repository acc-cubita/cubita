import { useMemo, useState } from 'react'
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  CreditCard,
  FileSpreadsheet,
  GitCompareArrows,
  Landmark,
  ListTree,
  RefreshCw,
  Save,
  Upload,
} from 'lucide-react'
import {
  fetchBankAccountsLive,
  fetchBankTransactions,
  fetchPosPending,
  fetchStatementLines,
  importStatementLines,
  settlePosTerminal,
} from '../../api'
import type { AccountCache, BankAccountCache } from '../../electron.d'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { BankAccountsPanel } from '../../components/BankAccountsPanel'
import { PosTerminalsPanel } from '../../components/PosTerminalsPanel'
import { ReconciliationPanel } from '../../components/ReconciliationPanel'
import { parseCsv, toNumber } from '../../lib/csv'
import { formatJalali, todayIso } from '../../lib/jalali'
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'

/**
 * عملیاتِ بانکیِ ماژولِ «دریافت و پرداخت» — صورت‌حساب، مغایرت، کارتخوان و مرورِ گردش.
 *
 * سه صفحه‌ی این فایل (حساب بانکی، دستگاه کارتخوان، مغایرت بانکی) پنلِ موجود را
 * می‌پوشانند نه اینکه از نو بنویسند: همان پنل‌ها پیش‌تر تبِ صفحه‌ی «چک و بانک» بودند و
 * حالا هرکدام از منو صفحه‌ی مستقلِ خودش را دارد. دو نمای یک داده نمی‌سازیم.
 */

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

// ═══════════════════ ۱۳) حساب بانکی ═══════════════════

export function BankAccountsPage({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  return (
    <OpsPage
      icon={Landmark}
      title="حساب بانکی"
      description="حساب‌های بانکیِ کسب‌وکار و حسابِ دفترِ کلِ متناظرشان. هر رسید و چکِ بانکی به یکی از این‌ها می‌نشیند."
    >
      <BankAccountsPanel token={token} accounts={accounts} />
    </OpsPage>
  )
}

// ═══════════════════ ۱۴) دستگاه کارت خوان ═══════════════════

export function PosTerminalsPage({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  return (
    <OpsPage
      icon={CreditCard}
      title="دستگاه کارت خوان"
      description="پایانه‌های فروشگاهی و حسابی که واریزشان به آن می‌نشیند."
    >
      <PosTerminalsPanel token={token} bankAccounts={bankAccounts} />
    </OpsPage>
  )
}

// ═══════════════════ ۱۱) مغایرت بانکی ═══════════════════

export function BankReconcilePage({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  return (
    <OpsPage
      icon={GitCompareArrows}
      title="مغایرت بانکی"
      description="ردیف‌های صورت‌حسابِ بانک را با تراکنش‌های ثبت‌شده تطبیق دهید تا معلوم شود دفتر و بانک کجا اختلاف دارند."
    >
      <ReconciliationPanel token={token} bankAccounts={bankAccounts} />
    </OpsPage>
  )
}

// ═══════════════════ ۱۰) صورت حساب بانکی ═══════════════════

/**
 * واردکردنِ صورت‌حسابِ رسمیِ بانک.
 *
 * جدا از «مغایرت بانکی» است چون دو کارِ متفاوت‌اند: این‌جا داده وارد می‌شود، آن‌جا
 * تطبیق داده می‌شود. یک صفحه‌ی واحد یعنی هر بار که کاربر می‌خواهد فقط تطبیق کند،
 * فرمِ واردکردن هم جلویش باشد.
 */
export function BankStatementPage({ token }: { token: string }) {
  const [bankAccountId, setBankAccountId] = useState('')
  const [text, setText] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const banks = useAsync(() => fetchBankAccountsLive(token), [token])
  const lines = useAsync(
    () => (bankAccountId ? fetchStatementLines(token, bankAccountId) : Promise.resolve([])),
    [token, bankAccountId, reloadKey],
  )

  const rows = lines.data ?? []
  const pg = usePagination(rows, 15, bankAccountId)
  const matched = rows.filter((r) => r.matched_transaction_id).length

  /** هر خط: تاریخ، مبلغ، شرح. مبلغِ منفی = برداشت. */
  const parsed = useMemo(() => {
    if (!text.trim()) return [] as { line_date: string; amount: number; description: string }[]
    return parseCsv(text)
      .filter((cols) => cols.length >= 2 && /\d/.test(cols[0]))
      .map((cols) => ({
        line_date: (cols[0] || '').trim(),
        amount: toNumber(cols[1] || '0'),
        description: (cols[2] || '').trim(),
      }))
  }, [text])

  async function submit() {
    setMsg(null)
    if (!bankAccountId) {
      setMsg({ text: 'اول حساب بانکی را انتخاب کنید.', kind: 'err' })
      return
    }
    if (parsed.length === 0) {
      setMsg({ text: 'ردیفی برای ورود نیست.', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      const saved = await importStatementLines(token, bankAccountId, parsed)
      setMsg({ text: `${faInt(saved.length)} ردیفِ صورت‌حساب وارد شد.`, kind: 'ok' })
      setText('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="صورت حساب بانکی"
      description="ردیف‌های صورت‌حسابِ رسمیِ بانک را وارد کنید؛ تطبیقشان با دفتر در «مغایرت بانکی» انجام می‌شود."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              حساب بانکی
              <select value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
                <option value="">— انتخاب —</option>
                {(banks.data ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {bankAccountId && (
            <div className="cc-summary">
              <Metric icon={<FileSpreadsheet size={14} />} label="ردیف‌های واردشده" value={faInt(rows.length)} />
              <Metric icon={<GitCompareArrows size={14} />} label="تطبیق‌شده" value={faInt(matched)} tone="in" />
              <Metric
                icon={<ArrowUpFromLine size={14} />}
                label="تطبیق‌نشده"
                value={faInt(rows.length - matched)}
                tone={rows.length - matched > 0 ? 'out' : 'plain'}
              />
            </div>
          )}
        </div>
      }
    >
      <Note msg={msg} />

      <SectionCard
        icon={Upload}
        title="ورودِ ردیف‌ها"
        description="سه ستون به‌ترتیب: تاریخ (میلادی، مثل 2026-08-28)، مبلغ (منفی = برداشت)، شرح."
      >
        <div className="invoice-form form-full">
          <label className="form-wide">
            چسباندنِ CSV
            <textarea
              rows={6}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="2026-08-28,15000000,واریز نقدی"
              style={{ width: '100%', fontFamily: 'monospace', direction: 'ltr' }}
            />
          </label>
        </div>
        {parsed.length > 0 && <p className="hint">{faInt(parsed.length)} ردیف آماده‌ی ورود است.</p>}
        <div className="invoice-form-footer">
          <button type="button" className="btn-primary" onClick={() => void submit()} disabled={busy || !bankAccountId}>
            <Save size={14} /> ورودِ صورت‌حساب
          </button>
        </div>
      </SectionCard>

      <SectionCard
        icon={FileSpreadsheet}
        title="ردیف‌های این حساب"
        description={bankAccountId ? `${faInt(rows.length)} ردیف` : 'اول یک حساب انتخاب کنید'}
        actions={
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} disabled={!bankAccountId}>
            <RefreshCw size={13} /> بازخوانی
          </button>
        }
      >
        <AsyncBlock
          loading={lines.loading}
          error={lines.error}
          empty={rows.length === 0}
          emptyText={bankAccountId ? 'ردیفی برای این حساب وارد نشده.' : 'برای دیدنِ ردیف‌ها، حساب بانکی را انتخاب کنید.'}
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>شرح</th>
                  <th>مبلغ</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((l) => (
                  <tr key={l.id}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(l.line_date)}</td>
                    <td className="card-wide" data-label="شرح">{l.description || '—'}</td>
                    <td className="num" data-label="مبلغ">{fa(l.amount)}</td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${l.matched_transaction_id ? 'tone-success' : 'tone-warning'}`}>
                        {l.matched_transaction_id ? 'تطبیق‌شده' : 'تطبیق‌نشده'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ ۹) تسویه کارت خوان ═══════════════════

/**
 * تسویه‌ی واریزِ شرکتِ پرداخت.
 *
 * فروشِ کارتی در لحظه‌ی رسید به بانک بدهکار شده، ولی پول چند روز بعد و **منهای
 * کارمزد** می‌نشیند. این صفحه می‌گوید کدام رسیدها هنوز تسویه نشده‌اند، و با ثبتِ
 * تسویه آن‌ها را علامت می‌زند و کارمزد را به هزینه می‌برد. مبلغِ ناخالص دوباره ثبت
 * نمی‌شود — وگرنه درآمد دوبار می‌آمد.
 */
export function PosSettlementPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [terminalNo, setTerminalNo] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState(todayIso())
  const [settlementDate, setSettlementDate] = useState(todayIso())
  const [bankAccountId, setBankAccountId] = useState('')
  const [fee, setFee] = useState('')

  const data = useAsync(
    async () => {
      const [pending, banks] = await Promise.all([
        fetchPosPending(token, { terminalNo: terminalNo || undefined, dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }),
        fetchBankAccountsLive(token),
      ])
      return { pending, banks }
    },
    [token, terminalNo, dateFrom, dateTo, reloadKey],
  )

  const pending = data.data?.pending ?? []
  const banks = data.data?.banks ?? []
  const gross = pending.reduce((s, g) => s + Number(g.gross_amount), 0)
  const count = pending.reduce((s, g) => s + g.count, 0)
  const pg = usePagination(pending, 12)

  async function submit() {
    setMsg(null)
    if (!dateFrom || !dateTo) {
      setMsg({ text: 'بازه‌ی تاریخ را مشخص کنید.', kind: 'err' })
      return
    }
    if (Number(fee || 0) > 0 && !bankAccountId) {
      setMsg({ text: 'برای ثبتِ کارمزد، حساب بانکی لازم است.', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      const res = await settlePosTerminal(token, {
        settlement_date: settlementDate,
        date_from: dateFrom,
        date_to: dateTo,
        terminal_no: terminalNo || null,
        bank_account_id: bankAccountId || null,
        fee_amount: Number(fee || 0),
      })
      setMsg({
        text: `${faInt(res.settled_count)} رسید تسویه شد — ناخالص ${fa(res.gross_amount)}، کارمزد ${fa(res.fee_amount)}، خالص ${fa(res.net_amount)} ریال.`,
        kind: 'ok',
      })
      setFee('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={CreditCard}
      title="تسویه کارت خوان"
      description="رسیدهای کارتیِ تسویه‌نشده و ثبتِ واریزِ شرکتِ پرداخت، همراه با کارمزد."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              شماره پایانه
              <input
                dir="ltr"
                value={terminalNo}
                onChange={(e) => setTerminalNo(e.target.value)}
                placeholder="12345678"
              />
            </label>
            <label className="acc-inline-field">
              از تاریخ
              <JalaliDatePicker value={dateFrom} onChange={setDateFrom} placeholder="از تاریخ" />
            </label>
            <label className="acc-inline-field">
              تا تاریخ
              <JalaliDatePicker value={dateTo} onChange={setDateTo} placeholder="تا تاریخ" />
            </label>
          </div>
          <div className="cc-summary">
            <Metric icon={<CreditCard size={14} />} label="رسیدِ تسویه‌نشده" value={faInt(count)} />
            <Metric icon={<ArrowDownToLine size={14} />} label="جمعِ ناخالص" value={fa(gross)} tone="in" />
            <Metric
              icon={<ArrowUpFromLine size={14} />}
              label="خالصِ برآوردی"
              value={fa(gross - Number(fee || 0))}
              tone="plain"
              hint="پس از کارمزدِ واردشده"
            />
          </div>
        </div>
      }
    >
      <Note msg={msg} />

      <SectionCard
        icon={CreditCard}
        title="رسیدهای تسویه‌نشده"
        description={`${faInt(pending.length)} روزِ کاری`}
        actions={
          <button type="button" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw size={13} /> بازخوانی
          </button>
        }
      >
        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={pending.length === 0}
          emptyText="رسیدِ کارتیِ تسویه‌نشده‌ای در این بازه نیست."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>پایانه</th>
                  <th>شمارِ تراکنش</th>
                  <th>جمعِ ناخالص</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((g) => (
                  <tr key={`${g.terminal_no}-${g.transaction_date}`}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(g.transaction_date)}</td>
                    <td data-label="پایانه"><span dir="ltr">{g.terminal_no || '—'}</span></td>
                    <td className="num" data-label="شمارِ تراکنش">{faInt(g.count)}</td>
                    <td className="num" data-label="جمعِ ناخالص">{fa(g.gross_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>

      <SectionCard
        icon={Save}
        title="ثبتِ تسویه"
        description="همه‌ی رسیدهای بازه‌ی بالا تسویه‌شده علامت می‌خورند و کارمزد به هزینه می‌رود."
      >
        <div className="invoice-form form-full">
          <label>
            تاریخِ واریزِ شرکتِ پرداخت
            <JalaliDatePicker value={settlementDate} onChange={setSettlementDate} />
          </label>
          <label>
            کارمزد (ریال)
            <NumberInput value={fee} onChange={setFee} />
            <span className="field-hint">۰ بگذارید اگر کارمزدی کسر نشده — سندِ صفر ثبت نمی‌شود.</span>
          </label>
          <label>
            حسابِ بانکیِ واریز
            <select value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
              <option value="">— انتخاب —</option>
              {banks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <span className="field-hint">فقط وقتی کارمزد داری لازم است.</span>
          </label>
        </div>
        <div className="invoice-form-footer">
          <button type="button" className="btn-primary" onClick={() => void submit()} disabled={busy || count === 0}>
            <Save size={14} /> {busy ? 'در حالِ ثبت…' : 'ثبتِ تسویه'}
          </button>
        </div>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ ۱۸) مرور عملیات بانکی ═══════════════════

/** گردشِ هر حسابِ بانکی: واریز، برداشت، و اینکه با صورت‌حساب تطبیق خورده یا نه. */
export function BankLedgerPage({ token }: { token: string }) {
  const [bankAccountId, setBankAccountId] = useState('')
  const [only, setOnly] = useState<'all' | 'in' | 'out' | 'unmatched'>('all')

  const banks = useAsync(() => fetchBankAccountsLive(token), [token])
  const txns = useAsync(
    () => fetchBankTransactions(token, bankAccountId || undefined),
    [token, bankAccountId],
  )

  const rows = useMemo(() => {
    return (txns.data ?? []).filter((t) => {
      const amount = Number(t.amount)
      if (only === 'in') return amount > 0
      if (only === 'out') return amount < 0
      if (only === 'unmatched') return !t.is_reconciled
      return true
    })
  }, [txns.data, only])
  const pg = usePagination(rows, 15, `${bankAccountId}|${only}`)

  const inflow = rows.filter((t) => Number(t.amount) > 0).reduce((s, t) => s + Number(t.amount), 0)
  const outflow = rows.filter((t) => Number(t.amount) < 0).reduce((s, t) => s + Number(t.amount), 0)

  return (
    <OpsPage
      icon={ListTree}
      title="مرور عملیات بانکی"
      description="هر واریز و برداشتِ ثبت‌شده در حساب‌های بانکی — از رسید، چک، تسویه یا ثبتِ دستی."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              حساب بانکی
              <select value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
                <option value="">همه‌ی حساب‌ها</option>
                {(banks.data ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="cc-presets">
              {(
                [
                  ['all', 'همه'],
                  ['in', 'واریز'],
                  ['out', 'برداشت'],
                  ['unmatched', 'تطبیق‌نشده'],
                ] as const
              ).map(([key, label]) => (
                <button key={key} type="button" className={only === key ? 'is-active' : ''} onClick={() => setOnly(key)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="cc-summary">
            <Metric icon={<ArrowDownToLine size={14} />} label="جمعِ واریز" value={fa(inflow)} tone="in" />
            <Metric icon={<ArrowUpFromLine size={14} />} label="جمعِ برداشت" value={fa(Math.abs(outflow))} tone="out" />
            <Metric icon={<Landmark size={14} />} label="خالص" value={fa(inflow + outflow)} tone={inflow + outflow < 0 ? 'out' : 'in'} />
          </div>
        </div>
      }
    >
      <SectionCard icon={ListTree} title="گردشِ بانکی" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={txns.loading}
          error={txns.error}
          empty={rows.length === 0}
          emptyText="تراکنشی با این شرایط نیست."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>شرح</th>
                  <th>منشأ</th>
                  <th>مبلغ</th>
                  <th>تطبیق</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((t) => (
                  <tr key={t.id}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                    <td className="card-wide" data-label="شرح">{t.description || '—'}</td>
                    <td data-label="منشأ">{BANK_SOURCE_LABEL[t.source_type] ?? t.source_type}</td>
                    <td className="num" data-label="مبلغ">
                      <span className={Number(t.amount) < 0 ? 'pos-out' : 'pos-in'}>{fa(t.amount)}</span>
                    </td>
                    <td data-label="تطبیق">
                      <span className={`status-badge ${t.is_reconciled ? 'tone-success' : ''}`}>
                        {t.is_reconciled ? 'تطبیق‌شده' : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

const BANK_SOURCE_LABEL: Record<string, string> = {
  manual: 'ثبتِ دستی',
  check_clear: 'وصولِ چک',
  pos_settlement: 'تسویه‌ی کارتخوان',
  treasury: 'دریافت/پرداخت',
}
