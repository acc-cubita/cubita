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
  fetchPosSettlementPreview,
  fetchPosTerminals,
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
import { SearchSelect } from '../../components/SearchSelect'

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
              <SearchSelect value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
                <option value="">— انتخاب —</option>
                {(banks.data ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </SearchSelect>
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
          <label>
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
 * **دو رویداد، نه یکی.** مشتری کارت می‌کشد و پول به «وجوهِ در راهِ کارت‌خوان»
 * می‌رود؛ چند روز بعد شرکتِ پرداخت جمعِ چند تراکنش را منهای کارمزد به حساب واریز
 * می‌کند. این صفحه رویدادِ دوم را ثبت می‌کند: پول را از وجوهِ در راه به بانک
 * می‌برد و کارمزد را به هزینه.
 *
 * تا مهاجرتِ ۰۱۰۹ رویدادِ اول مستقیم روی بانک می‌نشست و این صفحه فقط رسیدها را
 * علامت می‌زد. متنِ قبلیِ همین فایل می‌گفت «مبلغِ ناخالص دوباره ثبت نمی‌شود —
 * وگرنه درآمد دو بار می‌آمد»، که با آن مدل درست بود؛ حالا ثبت می‌شود، چون
 * انتقالِ بین دو حسابِ خزانه است نه درآمد.
 */
export function PosSettlementPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [posTerminalId, setPosTerminalId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  //: «تسویه تا تاریخ» — برشِ انتخابِ رسیدها (§۹). با تاریخِ واریزِ پایین یکی نیست.
  const [settleThrough, setSettleThrough] = useState(todayIso())
  const [settlementDate, setSettlementDate] = useState(todayIso())
  const [fee, setFee] = useState('')
  const [note, setNote] = useState('')

  const data = useAsync(
    async () => {
      const [pending, terminals] = await Promise.all([
        fetchPosPending(token, { posTerminalId: posTerminalId || undefined }),
        fetchPosTerminals(token),
      ])
      return { pending, terminals }
    },
    [token, posTerminalId, reloadKey],
  )

  //: رسیدهای دقیقی که با این برش تسویه می‌شوند — فقط وقتی دستگاه انتخاب شده،
  //: چون دامنه و حسابِ مقصد هر دو از خودِ دستگاه می‌آیند.
  const preview = useAsync(
    async () =>
      posTerminalId
        ? fetchPosSettlementPreview(token, {
            posTerminalId,
            settleThrough,
            dateFrom: dateFrom || undefined,
          })
        : null,
    [token, posTerminalId, settleThrough, dateFrom, reloadKey],
  )

  const pending = data.data?.pending ?? []
  const terminals = data.data?.terminals ?? []
  const selected = terminals.find((t) => t.id === posTerminalId) ?? null
  const eligible = preview.data
  const gross = Number(eligible?.gross_amount ?? 0)
  const pg = usePagination(eligible?.receipts ?? [], 10, `${posTerminalId}|${settleThrough}`)

  async function submit() {
    setMsg(null)
    if (!posTerminalId) {
      setMsg({ text: 'اول دستگاهِ کارت‌خوان را انتخاب کنید.', kind: 'err' })
      return
    }
    if (!selected?.bank_account_id) {
      setMsg({ text: 'این دستگاه حسابِ بانکیِ تسویه ندارد؛ اول آن را تعیین کنید.', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      const res = await settlePosTerminal(token, {
        pos_terminal_id: posTerminalId,
        settlement_date: settlementDate,
        settle_through: settleThrough,
        date_from: dateFrom || null,
        fee_amount: Number(fee || 0),
        note: note.trim(),
      })
      setMsg({
        text:
          `تسویه‌ی شماره ${faInt(res.number)} ثبت شد — ${faInt(res.receipt_count)} رسید، ` +
          `ناخالص ${fa(res.gross_amount)}، کارمزد ${fa(res.fee_amount)}، ` +
          `خالصِ واریز به «${res.bank_account_name}» ${fa(res.net_amount)} ریال.`,
        kind: 'ok',
      })
      setFee('')
      setNote('')
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
      description="بردنِ وجوهِ در راهِ یک دستگاه به حسابِ بانکی‌اش، همراه با کارمزد."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              دستگاه
              <SearchSelect value={posTerminalId} onChange={(e) => setPosTerminalId(e.target.value)}>
                <option value="">— انتخابِ دستگاه —</option>
                {terminals.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.terminal_no ? `${t.terminal_no} — ` : ''}
                    {t.label || 'کارتخوان'}
                  </option>
                ))}
              </SearchSelect>
            </label>
            <label className="acc-inline-field">
              تسویه تا تاریخ
              <JalaliDatePicker value={settleThrough} onChange={setSettleThrough} />
            </label>
            <label className="acc-inline-field">
              از تاریخ (اختیاری)
              <JalaliDatePicker value={dateFrom} onChange={setDateFrom} placeholder="از ابتدا" />
            </label>
          </div>
          <div className="cc-summary">
            <Metric
              icon={<CreditCard size={14} />}
              label="رسیدِ واجدِ شرایط"
              value={faInt(eligible?.receipt_count ?? 0)}
            />
            <Metric icon={<ArrowDownToLine size={14} />} label="جمعِ ناخالص" value={fa(gross)} tone="in" />
            <Metric
              icon={<ArrowUpFromLine size={14} />}
              label="خالصِ واریز"
              value={fa(gross - Number(fee || 0))}
              tone="plain"
              hint="پس از کارمزدِ واردشده"
            />
          </div>
        </div>
      }
    >
      <Note msg={msg} />

      {/* نمای کلی: کجا پولِ نرسیده هست — پیش از انتخابِ دستگاه هم مفید است. */}
      <SectionCard
        icon={CreditCard}
        title="وجوهِ در راه، به تفکیکِ دستگاه و روز"
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
          emptyText="پولِ کارتیِ نرسیده‌ای نیست."
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
                {pending.map((g) => (
                  <tr key={`${g.terminal_no}-${g.transaction_date}`}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(g.transaction_date)}</td>
                    <td data-label="پایانه"><span dir="ltr">{g.terminal_label || g.terminal_no || '—'}</span></td>
                    <td className="num" data-label="شمارِ تراکنش">{faInt(g.count)}</td>
                    <td className="num" data-label="جمعِ ناخالص">{fa(g.gross_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>

      {/*
        رسیدهای منبع (§۱۰ §۱۲). بدونِ این، مبلغِ تسویه یک جمعِ توضیح‌ناپذیر بود:
        کاربر عدد را می‌دید ولی نمی‌توانست بگوید از کجا آمده.
      */}
      <SectionCard
        icon={ListTree}
        title="رسیدهایی که تسویه می‌شوند"
        description={
          selected
            ? `${faInt(eligible?.receipt_count ?? 0)} رسید تا ${formatJalali(settleThrough)}`
            : 'اول دستگاه را انتخاب کنید'
        }
      >
        <AsyncBlock
          loading={preview.loading}
          error={preview.error}
          empty={!eligible || eligible.receipts.length === 0}
          emptyText={
            selected
              ? 'رسیدِ تسویه‌نشده‌ای برای این دستگاه تا این تاریخ نیست.'
              : 'برای دیدنِ رسیدها، دستگاهِ کارت‌خوان را از بالا انتخاب کنید.'
          }
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>طرفِ مقابل</th>
                  <th>مرجع / پیگیری</th>
                  <th>کارت</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.id}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(r.transaction_date)}</td>
                    <td data-label="طرفِ مقابل">
                      {r.contact_name}
                      {r.contact_name2 ? <div className="entity-sub">{r.contact_name2}</div> : null}
                    </td>
                    <td data-label="مرجع / پیگیری"><span dir="ltr">{r.reference_no || r.trace_no || '—'}</span></td>
                    <td data-label="کارت"><span dir="ltr">{r.card_mask || '—'}</span></td>
                    <td className="num" data-label="مبلغ">{fa(r.amount)}</td>
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
        description="این رسیدها تسویه‌شده علامت می‌خورند، خالص به بانک می‌رود و کارمزد به هزینه."
      >
        <div className="invoice-form form-full">
          <label>
            تاریخِ واریزِ شرکتِ پرداخت
            <JalaliDatePicker value={settlementDate} onChange={setSettlementDate} />
            <span className="field-hint">
              روزی که پول به بانک نشست — لازم نیست با «تسویه تا تاریخ» یکی باشد.
            </span>
          </label>
          <label>
            کارمزد (ریال)
            <NumberInput value={fee} onChange={setFee} />
            <span className="field-hint">۰ بگذارید اگر کارمزدی کسر نشده.</span>
          </label>
          <label>
            حسابِ بانکیِ واریز
            <input value={selected?.bank_account_name ?? ''} readOnly placeholder="— از دستگاه —" />
            <span className="field-hint">
              {selected
                ? 'از حسابِ تسویه‌ی همین دستگاه می‌آید و اینجا عوض نمی‌شود.'
                : 'پس از انتخابِ دستگاه پر می‌شود.'}
            </span>
          </label>
          <label>
            توضیح (اختیاری)
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="مثلاً شماره‌ی پیگیریِ واریزِ بانک" />
          </label>
        </div>
        <div className="invoice-form-footer">
          <button
            type="button"
            className="btn-primary"
            onClick={() => void submit()}
            disabled={busy || !posTerminalId || (eligible?.receipt_count ?? 0) === 0}
          >
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
              <SearchSelect value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
                <option value="">همه‌ی حساب‌ها</option>
                {(banks.data ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </SearchSelect>
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
