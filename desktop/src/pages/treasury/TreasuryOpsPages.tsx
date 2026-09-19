import { Fragment, useMemo, useState } from 'react'
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  HandCoins,
  Landmark,
  PiggyBank,
  Receipt,
  RefreshCw,
  Route,
  Save,
  Scale,
  Wallet,
} from 'lucide-react'
import {
  createPettyCashCharge,
  createPettyCashExpense,
  createContactSettlement,
  fetchAllocationHistory,
  fetchBankAccountsLive,
  fetchContacts,
  fetchCounterpartyAccounts,
  fetchOpenItems,
  fetchPettyCashBalance,
  fetchPettyCashTransactions,
  fetchTreasuryTransactions,
  type OpenItem,
  type SettlementSide,
} from '../../api'
import type { AccountCache } from '../../electron.d'
import type { PageKey } from '../../lib/navModel'
import { SectionCard } from '../../components/SectionCard'
import { NumberInput } from '../../components/NumberInput'
import { JalaliDatePicker } from '../../components/JalaliDatePicker'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali, todayIso } from '../../lib/jalali'
// اسکلتِ مشترکِ صفحه‌های عملیات. زیرِ پوشه‌ی accounting/ زندگی می‌کند چون اولین‌بار
// آن‌جا لازم شد، ولی محتوایش عمومی است و قراردادِ صفحه‌ها به همان ارجاع می‌دهد.
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'
import { PaymentVoucherDocumentPage } from './PaymentVoucherPage'
import { ReceiptVoucherDocumentPage } from './ReceiptVoucherPage'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * عملیاتِ پولیِ ماژولِ «دریافت و پرداخت» — رسید، اعلامیه، تسویه‌ی طرف‌حساب، صندوق و تنخواه.
 *
 * **چرا رسید و اعلامیه دو صفحه‌ی جدا شدند و نه یک فرم با سوییچ:** پیش‌تر یک فرم بود با
 * یک `select`ِ «دریافت/پرداخت». همان یک انتخاب تعیین می‌کند سند به کدام سمت می‌خورد،
 * و اشتباهش یعنی سندِ وارونه. دو صفحه‌ی جدا، هرکدام با عنوان و رنگِ خودش، این خطا را
 * از بین می‌برد و از منو هم مستقیم به همان کاری می‌رود که کاربر می‌خواهد.
 */

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

// ═══════════════════ ۱) فرآیند دریافت و پرداخت ═══════════════════

/** یک گامِ راهنما — همان الگوی «عملیات اول دوره». */
function Step({
  index,
  title,
  description,
  state,
  action,
  onGo,
}: {
  index: number
  title: string
  description: string
  state: { label: string; tone: 'ok' | 'todo' | 'warn' }
  action: string
  onGo: () => void
}) {
  return (
    <div className={`ops-step is-${state.tone}`}>
      <span className="ops-step-num">{faInt(index)}</span>
      <div className="ops-step-body">
        <div className="ops-step-head">
          <strong>{title}</strong>
          <span className={`badge ${state.tone === 'ok' ? 'success' : state.tone === 'warn' ? 'warning' : ''}`}>
            {state.label}
          </span>
        </div>
        <p className="ops-step-desc">{description}</p>
      </div>
      <button type="button" onClick={onGo}>
        {action}
      </button>
    </div>
  )
}

/**
 * نقشه‌ی راهِ ماژول: پول از کجا می‌آید و کجا می‌رود.
 *
 * هجده عملیاتِ این ماژول برای کسی که تازه شروع کرده یک فهرستِ بلندِ بی‌ترتیب است.
 * این صفحه ترتیبِ واقعی را نشان می‌دهد و وضعیتِ هر گام را از داده‌ی زنده می‌خواند —
 * نه یک برچسبِ ثابت که هیچ‌وقت سبز نمی‌شود.
 */
export function PayFlowPage({ token, onNavigate }: { token: string; onNavigate: (page: PageKey) => void }) {
  const state = useAsync(
    async () => {
      const [banks, treasury, petty] = await Promise.all([
        fetchBankAccountsLive(token),
        fetchTreasuryTransactions(token),
        fetchPettyCashBalance(token).catch(() => ({ balance: '0' })),
      ])
      return { banks, treasury, petty }
    },
    [token],
  )

  const banks = state.data?.banks ?? []
  const treasury = state.data?.treasury ?? []
  const receipts = treasury.filter((t) => t.type === 'receipt').length
  const payments = treasury.filter((t) => t.type === 'payment').length

  return (
    <OpsPage
      icon={Route}
      title="فرآیند دریافت و پرداخت"
      description="ترتیبِ کارها در این ماژول: از تعریفِ محلِ پول تا ثبتِ رسید و اعلامیه و تطبیقِ بانک."
    >
      <SectionCard
        icon={Route}
        title="مسیرِ کار"
        description="هر گام صفحه‌ی خودش را دارد؛ این‌جا فقط ترتیب و وضعیت است."
        actions={
          <button type="button" onClick={state.reload}>
            <RefreshCw size={13} /> بازخوانی
          </button>
        }
      >
        <AsyncBlock loading={state.loading} error={state.error}>
          <div className="ops-steps">
            <Step
              index={1}
              title="محلِ نگهداریِ پول"
              description="حسابِ بانکی، صندوقِ نقدی و دستگاهِ کارتخوان را تعریف کنید. هر رسید باید بگوید پول کجا نشست."
              state={
                banks.length > 0
                  ? { label: `${faInt(banks.length)} حساب بانکی`, tone: 'ok' }
                  : { label: 'انجام نشده', tone: 'todo' }
              }
              action="حساب بانکی"
              onGo={() => onNavigate('bankaccounts')}
            />
            <Step
              index={2}
              title="ثبتِ دریافت"
              description="هر پولی که از مشتری می‌گیرید — نقدی، بانکی یا کارتخوان — با «رسید دریافت» ثبت می‌شود و سندش خودکار می‌خورد."
              state={
                receipts > 0
                  ? { label: `${faInt(receipts)} رسید`, tone: 'ok' }
                  : { label: 'هنوز رسیدی نیست', tone: 'todo' }
              }
              action="رسید دریافت"
              onGo={() => onNavigate('receiptvoucher')}
            />
            <Step
              index={3}
              title="ثبتِ پرداخت"
              description="پرداخت به تأمین‌کننده با «اعلامیه پرداخت». همان مسیر، در جهتِ عکس."
              state={
                payments > 0
                  ? { label: `${faInt(payments)} اعلامیه`, tone: 'ok' }
                  : { label: 'هنوز پرداختی نیست', tone: 'todo' }
              }
              action="اعلامیه پرداخت"
              onGo={() => onNavigate('paymentvoucher')}
            />
            <Step
              index={4}
              title="چک‌ها"
              description="چکِ دریافتی را واگذار و وصول کنید، چکِ صادرشده را از دسته‌چک بکشید و سررسیدش را پیگیری کنید."
              state={{ label: 'هر وقت چک داشتید', tone: 'warn' }}
              action="عملیات چک"
              onGo={() => onNavigate('checkops')}
            />
            <Step
              index={5}
              title="تطبیق با بانک"
              description="صورت‌حسابِ بانک را وارد کنید و مغایرت‌ها را ببندید — تنها راهِ مطمئن‌شدن از اینکه دفتر با بانک یکی است."
              state={{ label: 'پایانِ هر ماه', tone: 'warn' }}
              action="مغایرت بانکی"
              onGo={() => onNavigate('bankreconcile')}
            />
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}

// ═══════════════════ ۲ و ۳) رسید دریافت / اعلامیه پرداخت ═══════════════════

export function ReceiptVoucherPage({ token }: { token: string }) {
  return <ReceiptVoucherDocumentPage token={token} />
}

export function PaymentVoucherPage({ token }: { token: string }) {
  return <PaymentVoucherDocumentPage token={token} />
}

// ═══════════════════ ۵) تسویه حساب طرف مقابل ═══════════════════

/**
 * کدام بدهکار با کدام بستانکار تسویه شد.
 *
 * **این صفحه پول جابه‌جا نمی‌کند — و تا امروز می‌کرد.** نسخه‌ی پیشین یک دکمه بود که
 * برای کلِ ماندهٔ شخص یک *رسیدِ دریافت* می‌ساخت. یعنی نامش تسویه بود ولی کارش ثبتِ
 * پولِ تازه. دریافت و پرداخت همچنان سرِ جای خودشان‌اند («رسید دریافت» و «اعلامیه
 * پرداخت»)؛ این‌جا فقط رابطه ثبت می‌شود: این دریافت بابتِ آن فاکتور بود.
 *
 * پس هیچ سندِ حسابداری‌ای از این صفحه بیرون نمی‌آید. فاکتور و رسید اثرشان را همان
 * لحظه‌ی ثبت زده‌اند و ماندهٔ مشتری همین حالا درست است؛ چیزی که نبود این بود که
 * کدام با کدام.
 */
export function ContactSettlementPage({ token }: { token: string }) {
  const [accountId, setAccountId] = useState('')
  const [contactId, setContactId] = useState('')
  const [settleDate, setSettleDate] = useState(todayIso())
  const [description, setDescription] = useState('')
  const [description2, setDescription2] = useState('')
  /** مبلغِ تسویه‌ی هر قلم، با کلیدِ «نوع:شناسه». خالی یعنی این قلم در تسویه نیست. */
  const [amounts, setAmounts] = useState<Record<string, string>>({})
  const [openHistory, setOpenHistory] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const base = useAsync(async () => {
    const [accounts, contacts] = await Promise.all([
      fetchCounterpartyAccounts(token),
      fetchContacts(token),
    ])
    return { accounts, contacts }
  }, [token])

  const accounts = base.data?.accounts ?? []
  const contacts = base.data?.contacts ?? []
  const activeAccount = accountId || accounts[0]?.id || ''

  const open = useAsync(
    async () =>
      activeAccount && contactId
        ? await fetchOpenItems(token, { accountId: activeAccount, contactId })
        : null,
    [token, activeAccount, contactId, reloadKey],
  )

  const summary = open.data
  const items = useMemo(() => summary?.items ?? [], [summary])
  const debitItems = items.filter((i) => i.side === 'debit')
  const creditItems = items.filter((i) => i.side === 'credit')

  const sideTotal = (side: SettlementSide) =>
    items
      .filter((i) => i.side === side)
      .reduce((sum, i) => sum + (Number(amounts[itemKey(i)]) || 0), 0)
  const debitTotal = sideTotal('debit')
  const creditTotal = sideTotal('credit')
  const difference = debitTotal - creditTotal

  function reset() {
    setAmounts({})
    setOpenHistory(null)
  }

  /**
   * تخصیصِ خودکار — **فقط با فشردنِ دکمه** (§۴۷).
   *
   * قدیمی‌ترین بدهکار را با قدیمی‌ترین بستانکار پر می‌کند تا یکی تمام شود. پیشنهاد
   * است نه تصمیم: همه‌ی مبالغ بعدش قابلِ ویرایش‌اند، چون پرداختِ واقعی همیشه
   * FIFO نیست (§۴۸).
   */
  function autoAllocate() {
    const next: Record<string, string> = {}
    let debitLeft = debitItems.map((i) => ({ item: i, left: Number(i.remaining_amount) }))
    let creditLeft = creditItems.map((i) => ({ item: i, left: Number(i.remaining_amount) }))
    let di = 0
    let ci = 0
    while (di < debitLeft.length && ci < creditLeft.length) {
      const take = Math.min(debitLeft[di].left, creditLeft[ci].left)
      if (take <= 0) {
        if (debitLeft[di].left <= 0) di += 1
        else ci += 1
        continue
      }
      const dk = itemKey(debitLeft[di].item)
      const ck = itemKey(creditLeft[ci].item)
      next[dk] = String((Number(next[dk]) || 0) + take)
      next[ck] = String((Number(next[ck]) || 0) + take)
      debitLeft[di].left -= take
      creditLeft[ci].left -= take
      if (debitLeft[di].left === 0) di += 1
      if (creditLeft[ci].left === 0) ci += 1
    }
    setAmounts(next)
    setMsg(
      Object.keys(next).length === 0
        ? { text: 'چیزی برای تخصیص نیست — یکی از دو سمت خالی است.', kind: 'err' }
        : { text: 'پیشنهادِ تخصیص پر شد؛ مبالغ را می‌توانید تغییر دهید.', kind: 'ok' },
    )
  }

  async function submit() {
    const picked = items
      .filter((i) => (Number(amounts[itemKey(i)]) || 0) > 0)
      .map((i) => ({
        source_type: i.source_type,
        source_id: i.source_id,
        side: i.side,
        amount: Number(amounts[itemKey(i)]),
      }))
    if (picked.length === 0) {
      setMsg({ text: 'هیچ قلمی انتخاب نشده است.', kind: 'err' })
      return
    }
    setBusy(true)
    setMsg(null)
    try {
      const saved = await createContactSettlement(token, {
        settlement_date: settleDate,
        contact_id: contactId,
        account_id: activeAccount,
        description,
        description2,
        items: picked,
      })
      setMsg({
        text: `تسویه‌ی شماره ${faInt(saved.number)} ثبت شد — ${fa(saved.total_amount)} ریال روی ${faInt(saved.allocations.length)} قلم.`,
        kind: 'ok',
      })
      reset()
      setDescription('')
      setDescription2('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const ready = Boolean(activeAccount && contactId)

  return (
    <OpsPage
      icon={Scale}
      title="تسویه حساب طرف مقابل"
      description="کدام فاکتور با کدام دریافت تسویه شد. این‌جا پولی جابه‌جا نمی‌شود؛ فقط رابطه‌ی اسنادِ موجود ثبت می‌گردد."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <label className="acc-inline-field">
              معین طرف مقابل
              <SearchSelect
                value={activeAccount}
                onChange={(e) => {
                  setAccountId(e.target.value)
                  reset()
                }}
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </SearchSelect>
            </label>
            <label className="acc-inline-field">
              طرف حساب
              <SearchSelect
                value={contactId}
                onChange={(e) => {
                  setContactId(e.target.value)
                  reset()
                }}
              >
                <option value="">— انتخاب —</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </SearchSelect>
            </label>
            <label className="acc-inline-field">
              تاریخ تسویه
              <JalaliDatePicker value={settleDate} onChange={setSettleDate} />
            </label>
            <label className="acc-inline-field">
              شرح
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <label className="acc-inline-field">
              شرح دوم
              <input value={description2} onChange={(e) => setDescription2(e.target.value)} />
            </label>
          </div>
          {summary && (
            <div className="cc-summary">
              <Metric
                icon={<ArrowDownToLine size={14} />}
                label="جمع اقلام بدهکار"
                value={fa(summary.debit_total)}
                tone="in"
              />
              <Metric
                icon={<ArrowUpFromLine size={14} />}
                label="جمع اقلام بستانکار"
                value={fa(summary.credit_total)}
                tone="out"
              />
              <Metric icon={<Scale size={14} />} label="ماندهٔ معین" value={fa(summary.net)} />
            </div>
          )}
          {summary && Number(summary.unattributed) !== 0 && (
            <p className="muted">
              {fa(summary.unattributed)} ریال از گردشِ این معین سندِ قابلِ تسویه ندارد و در
              فهرستِ اقلام نمی‌آید — سندِ دستی، ماندهٔ اول دوره، یا چکی که پیش از نسخه‌ی
              ۰۱۱۴ ثبت شده. دفتر درست است؛ فقط این گردش‌ها لنگری برای تخصیص ندارند.
            </p>
          )}
        </div>
      }
    >
      <Note msg={msg} />

      {!ready ? (
        <SectionCard icon={Scale} title="طرف حساب را انتخاب کنید">
          <p className="muted">
            تسویه همیشه برای یک طرف حساب و روی یک معین انجام می‌شود. اقلامِ باز پس از انتخاب
            نمایش داده می‌شوند.
          </p>
        </SectionCard>
      ) : (
        <>
          <SettleSide
            token={token}
            title="اقلام بدهکار"
            hint="سندهایی که طرف حساب را به ما بدهکار کرده‌اند"
            icon={ArrowDownToLine}
            items={debitItems}
            amounts={amounts}
            setAmounts={setAmounts}
            openHistory={openHistory}
            setOpenHistory={setOpenHistory}
            loading={open.loading}
            error={open.error}
          />
          <SettleSide
            token={token}
            title="اقلام بستانکار"
            hint="سندهایی که طلبِ ما را کم کرده‌اند — دریافت، برگشت، چک"
            icon={ArrowUpFromLine}
            items={creditItems}
            amounts={amounts}
            setAmounts={setAmounts}
            openHistory={openHistory}
            setOpenHistory={setOpenHistory}
            loading={open.loading}
            error={open.error}
          />

          <SectionCard
            icon={Scale}
            title="جمع و ثبت"
            description="تسویه تنها وقتی ثبت می‌شود که دو سمت برابر باشند."
            actions={
              <button type="button" onClick={autoAllocate}>
                <Wallet size={13} /> تخصیص خودکار
              </button>
            }
          >
            <div className="settle-totals">
              <div>
                <span>جمع اقلام بدهکار</span>
                <strong>{fa(debitTotal)}</strong>
              </div>
              <div>
                <span>جمع اقلام بستانکار</span>
                <strong>{fa(creditTotal)}</strong>
              </div>
              <div className={difference === 0 ? 'is-ok' : 'is-off'}>
                <span>اختلاف</span>
                <strong>{fa(Math.abs(difference))}</strong>
              </div>
            </div>
            <div className="form-actions">
              <button
                type="button"
                className="primary"
                onClick={() => void submit()}
                disabled={busy || difference !== 0 || debitTotal === 0}
              >
                <Save size={14} /> {busy ? 'در حالِ ثبت…' : 'ثبت تسویه'}
              </button>
              <button type="button" onClick={reset} disabled={busy}>
                پاک کردن اقلام
              </button>
            </div>
            {difference !== 0 && debitTotal + creditTotal > 0 && (
              <p className="muted">
                دو سمت {fa(Math.abs(difference))} ریال اختلاف دارند. تا صفر نشود، تسویه ثبت
                نمی‌شود.
              </p>
            )}
          </SectionCard>
        </>
      )}
    </OpsPage>
  )
}

/** کلیدِ یکتای یک قلم در حافظه‌ی فرم — سند در دو نوعِ مختلف می‌تواند هم‌شناسه باشد. */
const itemKey = (item: OpenItem) => `${item.source_type}:${item.source_id}`

/** شماره‌ی خواندنیِ یک قلم: شماره‌ی خودش، وگرنه شماره‌ی سندِ حسابداری‌اش. */
function itemNumber(item: OpenItem) {
  if (item.number != null) return faInt(item.number)
  if (item.entry_number != null) return `سند ${faInt(item.entry_number)}`
  return '—'
}

/** یک سمتِ تسویه — همان جدولی که فرمِ مرجع دارد، با مبلغِ تسویه‌ی هر قلم. */
function SettleSide({
  token,
  title,
  hint,
  icon,
  items,
  amounts,
  setAmounts,
  openHistory,
  setOpenHistory,
  loading,
  error,
}: {
  token: string
  title: string
  hint: string
  icon: typeof Scale
  items: OpenItem[]
  amounts: Record<string, string>
  setAmounts: (next: Record<string, string>) => void
  openHistory: string | null
  setOpenHistory: (key: string | null) => void
  loading: boolean
  error: string | null
}) {
  return (
    <SectionCard icon={icon} title={title} description={`${hint} — ${faInt(items.length)} قلم`}>
      <AsyncBlock
        loading={loading}
        error={error}
        empty={items.length === 0}
        emptyText="قلمِ بازی در این سمت نیست."
      >
        <div className="table-scroll">
          <table className="cards-on-mobile acc-table">
            <thead>
              <tr>
                <th>نوع</th>
                <th>شماره</th>
                <th>تاریخ</th>
                <th>مبلغ سند</th>
                <th>تسویه‌شده</th>
                <th>مانده قابل تسویه</th>
                <th>مبلغ تسویه</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const key = itemKey(item)
                return (
                  <Fragment key={key}>
                    <tr>
                      <td className="card-title" data-label="نوع">
                        {item.label}
                      </td>
                      <td data-label="شماره">{itemNumber(item)}</td>
                      <td data-label="تاریخ">{formatJalali(item.document_date)}</td>
                      <td className="num" data-label="مبلغ سند">
                        {fa(item.document_amount)}
                      </td>
                      <td className="num" data-label="تسویه‌شده">
                        {fa(item.settled_amount)}
                      </td>
                      <td className="num" data-label="مانده قابل تسویه">
                        <strong>{fa(item.remaining_amount)}</strong>
                      </td>
                      <td data-label="مبلغ تسویه">
                        <NumberInput
                          value={amounts[key] ?? ''}
                          onChange={(v) => setAmounts({ ...amounts, [key]: v })}
                          placeholder="۰"
                        />
                      </td>
                      <td className="card-actions">
                        <button
                          type="button"
                          onClick={() => setOpenHistory(openHistory === key ? null : key)}
                        >
                          <Receipt size={13} /> تاریخچه
                        </button>
                      </td>
                    </tr>
                    {openHistory === key && (
                      <tr className="card-full">
                        <td colSpan={8}>
                          <AllocationHistory token={token} item={item} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      </AsyncBlock>
    </SectionCard>
  )
}

/**
 * تاریخچه‌ی تخصیصِ یک سند — «تسویه‌شده: ۱۰۰» کافی نیست.
 *
 * هر گام با تاریخ و مبلغ و **سمتِ مقابلش** می‌آید؛ تسویه‌های برگشت‌خورده هم
 * می‌مانند و علامت می‌خورند، وگرنه «چرا مانده برگشت؟» بی‌جواب می‌ماند.
 */
function AllocationHistory({ token, item }: { token: string; item: OpenItem }) {
  const data = useAsync(
    () => fetchAllocationHistory(token, item.source_type, item.source_id),
    [token, item.source_type, item.source_id],
  )
  const rows = data.data ?? []
  return (
    <AsyncBlock
      loading={data.loading}
      error={data.error}
      empty={rows.length === 0}
      emptyText="این سند هنوز در هیچ تسویه‌ای نیامده است."
    >
      <ul className="settle-history">
        {rows.map((row) => (
          <li key={row.settlement_id} className={row.voided ? 'is-voided' : ''}>
            <span className="settle-history__head">
              تسویه {faInt(row.number)} — {formatJalali(row.settlement_date)}
              {row.voided && <em> (برگشت‌خورده)</em>}
            </span>
            <span className="settle-history__amount">{fa(row.amount)}</span>
            <span className="settle-history__counter">
              {row.counter_items.length === 0
                ? '—'
                : row.counter_items
                    .map((c) => `${c.label} ${fa(c.amount)}`)
                    .join(' · ')}
            </span>
          </li>
        ))}
      </ul>
    </AsyncBlock>
  )
}

// ═══════════════════ ۱۲) صندوق ═══════════════════

/**
 * صندوقِ نقدی: چه مقدار پولِ نقد در دستِ ماست و از کجا آمده.
 *
 * صندوق حسابِ جداگانه‌ای در چارت دارد (نقشِ `cash`)؛ این صفحه گردشِ نقدیِ همان را از
 * رسیدها و اعلامیه‌های نقدی می‌سازد. ثبتِ تازه از راهِ «رسید دریافت»/«اعلامیه پرداخت»
 * انجام می‌شود، نه این‌جا — تا یک عملیات دو دروازه نداشته باشد.
 */
export function CashBoxPage({ token, onNavigate }: { token: string; onNavigate: (page: PageKey) => void }) {
  const data = useAsync(() => fetchTreasuryTransactions(token), [token])

  const cash = useMemo(() => (data.data ?? []).filter((t) => t.method === 'cash'), [data.data])
  const inflow = cash.filter((t) => t.type === 'receipt' && !t.voided_at).reduce((s, t) => s + Number(t.amount), 0)
  const outflow = cash.filter((t) => t.type === 'payment' && !t.voided_at).reduce((s, t) => s + Number(t.amount), 0)
  const pg = usePagination(cash, 12)

  return (
    <OpsPage
      icon={PiggyBank}
      title="صندوق"
      description="گردشِ پولِ نقد: هر دریافت و پرداختی که با روشِ «صندوق» ثبت شده."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<ArrowDownToLine size={14} />} label="دریافتِ نقدی" value={fa(inflow)} tone="in" />
            <Metric icon={<ArrowUpFromLine size={14} />} label="پرداختِ نقدی" value={fa(outflow)} tone="out" />
            <Metric
              icon={<PiggyBank size={14} />}
              label="ماندهٔ صندوق"
              value={fa(inflow - outflow)}
              tone={inflow - outflow < 0 ? 'out' : 'in'}
              hint="از گردشِ ثبت‌شده"
            />
          </div>
        </div>
      }
    >
      <SectionCard
        icon={Wallet}
        title="گردشِ صندوق"
        description={`${faInt(cash.length)} تراکنشِ نقدی`}
        actions={
          <button type="button" onClick={() => onNavigate('receiptvoucher')}>
            <Receipt size={13} /> ثبتِ دریافت
          </button>
        }
      >
        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={cash.length === 0}
          emptyText="تراکنشِ نقدی ثبت نشده. از «رسید دریافت» یا «اعلامیه پرداخت» با روشِ «صندوق» شروع کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>نوع</th>
                  <th>طرف حساب</th>
                  <th>شرح</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((t) => (
                  <tr key={t.id}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                    <td data-label="نوع">
                      <span className={`status-badge ${t.type === 'receipt' ? 'tone-success' : 'tone-warning'}`}>
                        {t.type === 'receipt' ? 'دریافت' : 'پرداخت'}
                      </span>
                    </td>
                    <td className="card-wide" data-label="طرف حساب">{t.contact_name}</td>
                    <td className="card-wide" data-label="شرح">{t.description || '—'}</td>
                    <td className="num" data-label="مبلغ">{fa(t.amount)}</td>
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

// ═══════════════════ ۱۶ و ۱۷) تنخواه‌دار / صورت هزینه تنخواه ═══════════════════

/** شارژِ تنخواه: پول از صندوق یا بانک به دستِ تنخواه‌دار می‌رود. */
export function PettyHolderPage({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const postable = accounts.filter((a) => !a.is_group)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [date, setDate] = useState(todayIso())
  const [amount, setAmount] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [description, setDescription] = useState('')

  const data = useAsync(
    async () => {
      const [balance, rows] = await Promise.all([
        fetchPettyCashBalance(token),
        fetchPettyCashTransactions(token),
      ])
      return { balance, rows }
    },
    [token, reloadKey],
  )
  const charges = useMemo(() => (data.data?.rows ?? []).filter((r) => r.type === 'charge'), [data.data])
  const pg = usePagination(charges, 10)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!sourceId) {
      setMsg({ text: 'حسابِ تأمینِ وجه را انتخاب کنید (صندوق یا بانک).', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      await createPettyCashCharge(token, {
        transaction_date: date,
        amount: Number(amount || 0),
        source_account_id: sourceId,
        description,
      })
      setMsg({ text: 'تنخواه شارژ شد.', kind: 'ok' })
      setAmount('')
      setDescription('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Wallet}
      title="تنخواه دار"
      description="شارژِ تنخواه‌گردان و ماندهٔ در اختیارِ تنخواه‌دار."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric
              icon={<Wallet size={14} />}
              label="ماندهٔ تنخواه"
              value={fa(data.data?.balance.balance ?? 0)}
              tone="in"
              hint="در اختیارِ تنخواه‌دار"
            />
            <Metric icon={<ArrowDownToLine size={14} />} label="شمارِ شارژها" value={faInt(charges.length)} />
          </div>
        </div>
      }
    >
      <Note msg={msg} />
      <div className="workspace-split">
        <SectionCard icon={Wallet} title="شارژِ تنخواه" description="پول از صندوق یا بانک به تنخواه‌دار داده می‌شود.">
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              تاریخ
              <JalaliDatePicker value={date} onChange={setDate} />
            </label>
            <label>
              مبلغ (ریال)
              <NumberInput value={amount} onChange={setAmount} />
            </label>
            <label>
              تأمین از حسابِ
              <SearchSelect value={sourceId} onChange={(e) => setSourceId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {postable.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </SearchSelect>
            </label>
            <label className="form-wide">
              شرح
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}>
                <Save size={14} /> ثبتِ شارژ
              </button>
            </div>
          </form>
        </SectionCard>

        <SectionCard icon={Landmark} title="شارژهای ثبت‌شده" description={`${faInt(charges.length)} شارژ`}>
          <AsyncBlock
            loading={data.loading}
            error={data.error}
            empty={charges.length === 0}
            emptyText="هنوز تنخواهی شارژ نشده."
          >
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>تاریخ</th>
                    <th>شرح</th>
                    <th>مبلغ</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="تاریخ">{formatJalali(r.transaction_date)}</td>
                      <td className="card-wide" data-label="شرح">{r.description || '—'}</td>
                      <td className="money-cell" data-label="مبلغ">{fa(r.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          </AsyncBlock>
        </SectionCard>
      </div>
    </OpsPage>
  )
}

/** صورتِ هزینه: تنخواه‌دار خرج کرده و حالا فاکتورهایش را ثبت می‌کند. */
export function PettyExpensePage({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const expenseAccounts = accounts.filter((a) => !a.is_group && a.type === 'expense')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [date, setDate] = useState(todayIso())
  const [amount, setAmount] = useState('')
  const [expenseId, setExpenseId] = useState('')
  const [description, setDescription] = useState('')

  const data = useAsync(
    async () => {
      const [balance, rows] = await Promise.all([
        fetchPettyCashBalance(token),
        fetchPettyCashTransactions(token),
      ])
      return { balance, rows }
    },
    [token, reloadKey],
  )
  const expenses = useMemo(() => (data.data?.rows ?? []).filter((r) => r.type === 'expense'), [data.data])
  const spent = expenses.reduce((s, r) => s + Number(r.amount), 0)
  const pg = usePagination(expenses, 10)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!expenseId) {
      setMsg({ text: 'حسابِ هزینه را انتخاب کنید.', kind: 'err' })
      return
    }
    setBusy(true)
    try {
      await createPettyCashExpense(token, {
        transaction_date: date,
        amount: Number(amount || 0),
        expense_account_id: expenseId,
        description,
      })
      setMsg({ text: 'هزینهٔ تنخواه ثبت شد.', kind: 'ok' })
      setAmount('')
      setDescription('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <OpsPage
      icon={Receipt}
      title="صورت هزینه تنخواه"
      description="هزینه‌هایی که تنخواه‌دار کرده است؛ هر ردیف از ماندهٔ تنخواه کم و به حسابِ هزینه‌ی خودش برده می‌شود."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<Wallet size={14} />} label="ماندهٔ تنخواه" value={fa(data.data?.balance.balance ?? 0)} tone="in" />
            <Metric icon={<ArrowUpFromLine size={14} />} label="جمعِ هزینه‌ها" value={fa(spent)} tone="out" />
            <Metric icon={<Receipt size={14} />} label="شمارِ ردیف‌ها" value={faInt(expenses.length)} />
          </div>
        </div>
      }
    >
      <Note msg={msg} />
      <div className="workspace-split">
        <SectionCard icon={Receipt} title="ثبتِ هزینه" description="هر قلم را به حسابِ هزینه‌ی خودش ببرید.">
          <form className="invoice-form form-full" onSubmit={submit}>
            <label>
              تاریخ
              <JalaliDatePicker value={date} onChange={setDate} />
            </label>
            <label>
              مبلغ (ریال)
              <NumberInput value={amount} onChange={setAmount} />
            </label>
            <label>
              بابتِ حسابِ هزینه
              <SearchSelect value={expenseId} onChange={(e) => setExpenseId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {expenseAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </SearchSelect>
            </label>
            <label className="form-wide">
              شرح
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary" disabled={busy}>
                <Save size={14} /> ثبتِ هزینه
              </button>
            </div>
          </form>
        </SectionCard>

        <SectionCard icon={Receipt} title="هزینه‌های ثبت‌شده" description={`${faInt(expenses.length)} ردیف`}>
          <AsyncBlock
            loading={data.loading}
            error={data.error}
            empty={expenses.length === 0}
            emptyText="هنوز هزینه‌ای از تنخواه ثبت نشده."
          >
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>تاریخ</th>
                    <th>شرح</th>
                    <th>مبلغ</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="تاریخ">{formatJalali(r.transaction_date)}</td>
                      <td className="card-wide" data-label="شرح">{r.description || '—'}</td>
                      <td className="money-cell" data-label="مبلغ">{fa(r.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
            </div>
          </AsyncBlock>
        </SectionCard>
      </div>
    </OpsPage>
  )
}

// ═══════════════════ فهرست: دریافت‌ها و پرداخت‌ها ═══════════════════

/**
 * دفترِ کاملِ رسیدها و اعلامیه‌ها — همان فهرستی که پیش‌تر تبِ «دریافت و پرداخت» در
 * ماژولِ اشخاص نشان می‌داد. آن‌جا داده‌ی این ماژول در ماژولِ دیگری زندگی می‌کرد.
 */
export function TreasuryLedgerPage({ token }: { token: string }) {
  const [kind, setKind] = useState<'all' | 'receipt' | 'payment'>('all')
  const [q, setQ] = useState('')
  const data = useAsync(() => fetchTreasuryTransactions(token), [token])

  const rows = useMemo(() => {
    const term = q.trim()
    return (data.data ?? []).filter((t) => {
      if (kind !== 'all' && t.type !== kind) return false
      if (!term) return true
      return t.contact_name.includes(term) || (t.description || '').includes(term)
    })
  }, [data.data, kind, q])
  const pg = usePagination(rows, 15, `${kind}|${q}`)

  const inflow = rows.filter((t) => t.type === 'receipt' && !t.voided_at).reduce((s, t) => s + Number(t.amount), 0)
  const outflow = rows.filter((t) => t.type === 'payment' && !t.voided_at).reduce((s, t) => s + Number(t.amount), 0)

  return (
    <OpsPage
      icon={HandCoins}
      title="دریافت‌ها و پرداخت‌ها"
      description="دفترِ کاملِ رسیدها و اعلامیه‌ها — هر ردیف یک سندِ حسابداری دارد."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<ArrowDownToLine size={14} />} label="جمعِ دریافت" value={fa(inflow)} tone="in" />
            <Metric icon={<ArrowUpFromLine size={14} />} label="جمعِ پرداخت" value={fa(outflow)} tone="out" />
            <Metric icon={<Scale size={14} />} label="خالص" value={fa(inflow - outflow)} tone={inflow - outflow < 0 ? 'out' : 'in'} />
          </div>
        </div>
      }
    >
      <SectionCard icon={HandCoins} title="تراکنش‌ها" description={`${faInt(rows.length)} ردیف`}>
        <div className="acc-filters">
          <label className="acc-search">
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="جست‌وجو: نامِ طرف حساب یا شرح"
            />
          </label>
          <label>
            نوع
            <SearchSelect value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
              <option value="all">همه</option>
              <option value="receipt">دریافت</option>
              <option value="payment">پرداخت</option>
            </SearchSelect>
          </label>
        </div>

        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={rows.length === 0}
          emptyText="تراکنشی با این شرایط نیست."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>نوع</th>
                  <th>طرف حساب</th>
                  <th>روش</th>
                  <th>شرح</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((t) => (
                  <tr key={t.id}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                    <td data-label="نوع">
                      <span className={`status-badge ${t.type === 'receipt' ? 'tone-success' : 'tone-warning'}`}>
                        {t.type === 'receipt' ? 'دریافت' : 'پرداخت'}
                      </span>
                    </td>
                    <td className="card-wide" data-label="طرف حساب">{t.contact_name}</td>
                    <td data-label="روش">{t.method === 'bank' ? 'بانک' : 'صندوق'}</td>
                    <td className="card-wide" data-label="شرح">{t.description || '—'}</td>
                    <td className="num" data-label="مبلغ">{fa(t.amount)}</td>
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
