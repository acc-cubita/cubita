import { useMemo, useState } from 'react'
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  CreditCard,
  GitCompareArrows,
  Landmark,
  ListTree,
  RefreshCw,
  Save,
} from 'lucide-react'
import {
  createBankTransaction,
  fetchBankAccountsLive,
  fetchBankTransactions,
  fetchPosPending,
  fetchPosSettlementPreview,
  fetchPosTerminals,
  settlePosTerminal,
} from '../../api'
import type { AccountCache, BankAccountCache } from '../../electron.d'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { ReconciliationPanel } from '../../components/ReconciliationPanel'
import { formatJalali, todayIso } from '../../lib/jalali'
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'
import { SearchSelect } from '../../components/SearchSelect'
import { FormField } from '../../components/form/FormKit'

/**
 * عملیاتِ بانکیِ ماژولِ «دریافت و پرداخت» — مغایرت‌گیری (ورود و تطبیقِ صورت‌حساب)، کارتخوان و مرورِ گردش.
 *
 * تعریفِ حساب‌های بانکی و کارتخوان‌ها از ۱۴۰۵/۰۷/۰۶ برگه‌های «حساب‌های نقد و بانک»اند (`CashBankPage`)؛ ثبتِ
 * دستیِ واریز/برداشت که لای تعریفِ حساب پنهان بود، این‌جا کنارِ مرورِ همان گردش نشست.
 */

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

// ═══════════════════ ۱۰) مغایرت‌گیری بانکی ═══════════════════

/**
 * ورودِ صورت‌حسابِ بانک **و** تطبیقش با دفتر — یک صفحه (مرحله‌ی ۲ِ مرتب‌سازیِ زیرمنوها، ۱۴۰۵/۰۷/۰۶).
 *
 * تا امروز «صورت حساب بانکی» صفحه‌ی جدایی بود با این استدلال که واردکردن و تطبیق دو کارند. ولی پنلِ تطبیق خودش
 * فایلِ CSV را وارد می‌کرد و ردیف‌های تطبیق‌شده و نشده را نشان می‌داد — پس آن صفحه نمای دومِ همین داده بود، با
 * خواننده‌ی شل‌تری که ستونِ مرجع را نمی‌شناخت. حالا ورود (فایل یا چسباندنِ متن) دکمه‌ای بالای همین پنل است و جلوی
 * تطبیق را نمی‌گیرد؛ دفترِ کاملِ ردیف‌ها «ردیف‌های صورت‌حساب بانکی» در فهرست‌هاست. کلیدِ `bankstatement` به همین‌جا
 * می‌آید (`LEGACY_PAGES`).
 */
export function BankReconcilePage({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  return (
    <OpsPage
      icon={GitCompareArrows}
      title="مغایرت‌گیری بانکی"
      description="صورت‌حسابِ بانک را وارد کنید (فایل یا چسباندنِ متن) و ردیف‌هایش را با تراکنش‌های ثبت‌شده تطبیق دهید تا معلوم شود دفتر و بانک کجا اختلاف دارند."
    >
      <ReconciliationPanel token={token} bankAccounts={bankAccounts} />
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
      title="تسویه کارتخوان"
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
          <FormField label="تاریخِ واریزِ شرکتِ پرداخت" tip="روزی که پول به بانک نشست — لازم نیست با «تسویه تا تاریخ» یکی باشد.">
            {(id) => <JalaliDatePicker id={id} value={settlementDate} onChange={setSettlementDate} />}
          </FormField>
          <FormField label="کارمزد (ریال)" tip="۰ بگذارید اگر کارمزدی کسر نشده.">
            {(id) => <NumberInput id={id} value={fee} onChange={setFee} />}
          </FormField>
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
export function BankLedgerPage({ token, accounts }: { token: string; accounts: AccountCache[] }) {
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
      <ManualBankTransaction
        token={token}
        banks={(banks.data ?? []).map((b) => ({ id: b.id, name: b.name }))}
        accounts={accounts.filter((a) => !a.is_group)}
        onDone={txns.reload}
      />

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

/**
 * واریز / برداشتِ دستی — جابه‌جاییِ وجه بین بانک و حسابِ مقابل (مثلاً صندوق) که از هیچ رسید، چک یا تسویه‌ای نمی‌آید.
 *
 * تا ۱۴۰۵/۰۷/۰۶ زیرِ فرمِ تعریفِ حسابِ بانکی بود — عملیاتی که لای تعریف پنهان مانده بود. جایش کنارِ همان گردشی است
 * که ثبتش می‌کند؛ ردیفِ ثبت‌شده با منشأ «ثبتِ دستی» همین‌جا در گردش می‌آید.
 */
function ManualBankTransaction({
  token,
  banks,
  accounts,
  onDone,
}: {
  token: string
  banks: { id: string; name: string }[]
  accounts: AccountCache[]
  onDone: () => void
}) {
  const [bankAccountId, setBankAccountId] = useState('')
  const [direction, setDirection] = useState<'deposit' | 'withdraw'>('deposit')
  const [amount, setAmount] = useState('')
  const [counterAccountId, setCounterAccountId] = useState('')
  const [description, setDescription] = useState('')
  const [transactionDate, setTransactionDate] = useState(todayIso())
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!bankAccountId || !counterAccountId || Number(amount) <= 0) {
      setMsg({ text: 'حساب بانکی، حساب مقابل و مبلغ (بزرگ‌تر از صفر) لازم است.', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      await createBankTransaction(token, {
        bank_account_id: bankAccountId,
        transaction_date: transactionDate,
        amount: direction === 'deposit' ? Number(amount) : -Number(amount),
        counter_account_id: counterAccountId,
        description,
      })
      setAmount('')
      setDescription('')
      setMsg({ text: 'تراکنشِ بانکی ثبت شد.', kind: 'ok' })
      onDone()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={Save}
      title="واریز / برداشتِ دستی"
      description="جابه‌جاییِ وجه بین بانک و حسابِ مقابل (مثلاً صندوق) که از رسید، چک یا تسویه نمی‌آید."
    >
      <Note msg={msg} />
      <form className="invoice-form" onSubmit={submit}>
        <label>
          حساب بانکی
          <SearchSelect value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {banks.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </SearchSelect>
        </label>
        <label>
          نوع
          <SearchSelect value={direction} onChange={(e) => setDirection(e.target.value as 'deposit' | 'withdraw')}>
            <option value="deposit">واریز</option>
            <option value="withdraw">برداشت</option>
          </SearchSelect>
        </label>
        <label>
          مبلغ
          <NumberInput value={amount} onChange={setAmount} />
        </label>
        <label>
          حساب مقابل
          <SearchSelect value={counterAccountId} onChange={(e) => setCounterAccountId(e.target.value)}>
            <option value="">— انتخاب —</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </SearchSelect>
        </label>
        <label>
          تاریخ
          <JalaliDatePicker value={transactionDate} onChange={setTransactionDate} />
        </label>
        <label className="form-wide">
          شرح
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <div className="invoice-form-footer">
          <button type="submit" className="btn-primary" disabled={busy}>
            <Save size={14} /> ثبتِ تراکنش
          </button>
        </div>
      </form>
    </SectionCard>
  )
}
