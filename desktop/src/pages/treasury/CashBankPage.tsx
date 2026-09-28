import { useMemo, useState } from 'react'
import { BookMarked, BookOpen, Landmark, ListChecks, Nfc, Plug, Vault, Wallet } from 'lucide-react'

import {
  createBankAccount,
  createCashbox,
  createCheckbook,
  createPettyCashFund,
  createPosTerminal,
  deleteBankAccount,
  deleteCashbox,
  deleteCheckbook,
  deletePosTerminal,
  fetchAnalytics,
  fetchBankAccountsAdmin,
  fetchCashboxes,
  fetchCheckbookLeaves,
  fetchCheckbooks,
  fetchContacts,
  fetchCurrencies,
  fetchPettyCashFundBalance,
  fetchPettyCashFunds,
  fetchPosTerminals,
  setCheckbookActive,
  updateBankAccount,
  updateCashbox,
  updateCheckbook,
  updatePettyCashFund,
  updatePosTerminal,
  type BankAccountRecord,
  type CashboxRecord,
  type CheckbookRecord,
  type PettyCashFundRecord,
  type PosTerminalRecord,
  type PosTransport,
} from '../../api'
import { AccountLedgerDrawer } from '../../components/AccountLedgerDrawer'
import { DefSheet, type DefCol } from '../../components/DefSheet'
import { RowAction } from '../../components/form/FormKit'
import { Tabs } from '../../components/Tabs'
import type { DefSpec, DefValues } from '../../lib/defSheet'
import { Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'
import { LeafList } from './CheckOpsPages'

/**
 * «حساب‌های نقد و بانک» — همه‌ی تعریف‌های پولِ این ماژول در **یک صفحه با پنج برگه‌ی اکسلی**: صندوق‌ها، حساب‌های
 * بانکی، دستگاه‌های کارتخوان، دسته‌چک‌ها و صندوق‌های تنخواه (مرحله‌ی ۲ِ مرتب‌سازیِ زیرمنوها، ۱۴۰۵/۰۷/۰۶).
 *
 * پیش از این پنج صفحه‌ی جدا بود با فرمِ بالا و جدولِ پایین، و دو «فهرست»ِ جدا («دسته‌چک‌ها»، «دستگاه‌های
 * کارتخوان») که همان جدول را دوباره نشان می‌دادند. حالا هر تعریف همان‌جا که دیده می‌شود ویرایش می‌شود
 * (`DefSheet`) و فهرستِ جدا دو نمای یک داده بود که رفت.
 *
 * **آنچه تعریف نبود بیرون رفت:** «واریز / برداشتِ بانکی» (ثبتِ دستیِ تراکنش) به «مرور عملیات بانکی» و «صدورِ چک
 * از دسته» به ثبتِ چک در «چک‌ها» — هر دو عملیات‌اند، نه تعریف. «تنخواه‌دار»ِ قبلی در واقع شارژِ تنخواه بود و
 * «شارژ تنخواه» نام گرفت؛ خودِ صندوق‌های تنخواه (تنخواه‌دار، سقف، محل) تا امروز در سرور بودند ولی رابطی نداشتند.
 */

const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')
/** شناسه‌ی خالی و تاریخِ خالی در برگه رشته‌ی خالی‌اند؛ سرور `null` می‌خواهد. */
const orNull = (v: unknown) => {
  const s = String(v ?? '').trim()
  return s === '' ? null : s
}
const s = (v: unknown) => String(v ?? '').trim()
/** مبلغ: صفر خط تیره. */
const amount = (v: string | number) => (Number(v) === 0 ? '—' : fa(v))

type Opt = { value: string; label: string }

export function CashBankPage({ token }: { token: string }) {
  const refs = useAsync(async () => {
    const [analytics, currencies] = await Promise.all([
      fetchAnalytics(token).catch(() => []),
      fetchCurrencies(token).catch(() => []),
    ])
    return { analytics, currencies }
  }, [token])
  const analyticOpts: Opt[] = useMemo(
    () => (refs.data?.analytics ?? []).map((a) => ({ value: a.id, label: `${a.code} — ${a.name}` })),
    [refs.data],
  )
  //: ریال همیشه هست؛ بقیه از تنظیماتِ ارز. ارزی که پیش از این روی رکوردی نشسته ولی از فهرست رفته، در همان ردیف
  //: دیده می‌شود (`withCurrent`) تا انتخاب‌گر مقدارِ ثبت‌شده را خالی نشان ندهد.
  const currencyOpts: Opt[] = useMemo(() => {
    const codes = new Set(['IRR', ...(refs.data?.currencies ?? []).map((c) => c.code)])
    return [...codes].map((c) => ({ value: c, label: c }))
  }, [refs.data])

  return (
    <OpsPage
      canvas
      icon={Vault}
      title="حساب‌های نقد و بانک"
      description="هرجا پولِ کسب‌وکار نگه داشته می‌شود — صندوق، حسابِ بانکی، کارتخوان، دسته‌چک و تنخواه — در یک صفحه، هر کدام یک برگه."
    >
      <Tabs
        syncPage="cashbank"
        tabs={[
          {
            key: 'cashboxes',
            label: 'صندوق‌ها',
            icon: Vault,
            content: <CashboxesTab token={token} analyticOpts={analyticOpts} currencyOpts={currencyOpts} />,
          },
          {
            key: 'banks',
            label: 'حساب‌های بانکی',
            icon: Landmark,
            content: <BanksTab token={token} analyticOpts={analyticOpts} currencyOpts={currencyOpts} />,
          },
          {
            key: 'pos',
            label: 'دستگاه‌های کارتخوان',
            icon: Nfc,
            content: <PosTab token={token} analyticOpts={analyticOpts} currencyOpts={currencyOpts} />,
          },
          { key: 'checkbooks', label: 'دسته‌چک‌ها', icon: BookMarked, content: <CheckbooksTab token={token} /> },
          { key: 'petty', label: 'صندوق‌های تنخواه', icon: Wallet, content: <PettyFundsTab token={token} /> },
        ]}
      />
    </OpsPage>
  )
}

/** گزینه‌ها به‌اضافه‌ی مقدارِ فعلیِ ردیف، اگر در فهرست نیست. */
const withCurrent = (opts: Opt[], current: unknown, label?: string): Opt[] => {
  const v = s(current)
  return !v || opts.some((o) => o.value === v) ? opts : [...opts, { value: v, label: label ?? v }]
}

/** جمعِ مانده‌ها **درونِ هر ارز** — ریال و دلار جمع‌شدنی نیستند و «جمعِ کل» بیشتر گمراه می‌کند تا کمک. */
function perCurrency<T>(rows: readonly T[], code: (r: T) => string, value: (r: T) => number): [string, number][] {
  const m = new Map<string, number>()
  for (const r of rows) m.set(code(r), (m.get(code(r)) ?? 0) + value(r))
  return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]))
}

// ═══════════════════ صندوق‌ها ═══════════════════

const CASHBOX_SPEC: DefSpec = {
  text: ['name', 'name2', 'analytic_id', 'currency_code', 'opening_date'],
  bools: ['is_active'],
  defaults: { currency_code: 'IRR' },
  required: [{ field: 'name', label: 'عنوان' }],
  search: ['name', 'name2', 'analytic_code'],
}

function CashboxesTab({ token, analyticOpts, currencyOpts }: { token: string; analyticOpts: Opt[]; currencyOpts: Opt[] }) {
  const list = useAsync(() => fetchCashboxes(token), [token])
  const rows = list.data ?? null
  const totals = perCurrency(rows ?? [], (r) => r.currency_code, (r) => Number(r.balance))
  const cols: DefCol<CashboxRecord>[] = [
    { id: 'name', label: 'عنوان', kind: 'text', field: 'name', enter: true },
    { id: 'name2', label: 'عنوان دوم', kind: 'text', field: 'name2', w: '9%', mhide: true, narrow: true },
    {
      id: 'analytic',
      label: 'تفصیلی',
      title: 'مانده‌ی این صندوق را از بقیه جدا می‌کند. صندوقِ باسابقه تفصیلی‌اش عوض نمی‌شود.',
      kind: 'select',
      field: 'analytic_id',
      emptyOption: '— بدونِ تفصیلی —',
      options: (v) => withCurrent(analyticOpts, v.analytic_id, s(v.analytic_code)),
      w: '16%',
      enter: true,
    },
    { id: 'currency', label: 'ارز', kind: 'select', field: 'currency_code', options: (v) => withCurrent(currencyOpts, v.currency_code), w: '7%' },
    { id: 'opened', label: 'تاریخ افتتاح', title: 'از چه زمانی این صندوق واقعاً باز شده — نه تاریخِ ثبتش در کوبیتا.', kind: 'date', field: 'opening_date', w: '11%', mhide: true },
    { id: 'opening', label: 'موجودی اولیه', title: 'ابتدای سالِ مالی — از دفتر خوانده می‌شود.', kind: 'ro', numeric: true, w: '9%', mhide: true, narrow: true, ro: (r) => (r ? amount(r.opening_balance) : '—') },
    { id: 'balance', label: 'مانده', title: 'نتیجه‌ی هرچه تا امروز افتاده — از دفتر.', kind: 'ro', numeric: true, w: '10%', ro: (r) => (r ? amount(r.balance) : '—') },
    { id: 'active', label: 'وضعیت', kind: 'toggle', field: 'is_active', w: '8%' },
  ]
  return (
    <>
      <section className="cc-head">
        <div className="cc-summary">
          <Metric icon={<Vault size={14} />} label="صندوق‌ها" value={faInt(rows?.length ?? 0)} />
          {totals.map(([code, total]) => (
            <Metric key={code} icon={<Wallet size={14} />} label={`مانده ${code}`} value={fa(total)} tone={total < 0 ? 'out' : 'in'} />
          ))}
        </div>
      </section>
      <DefSheet<CashboxRecord>
        sheetId="cashboxes"
        spec={CASHBOX_SPEC}
        cols={cols}
        autoCol="name"
        slots={[['num', 'name'], ['name2', 'analytic'], ['currency', 'opened'], ['opening', 'balance'], ['active', 'actions']]}
        rows={rows}
        error={list.error}
        reload={list.reload}
        valuesOf={(r) => ({ ...r, analytic_id: r.analytic_id ?? '', opening_date: r.opening_date ?? '' })}
        create={(v) =>
          createCashbox(token, {
            name: s(v.name),
            name2: s(v.name2),
            analytic_id: orNull(v.analytic_id),
            currency_code: s(v.currency_code) || 'IRR',
            opening_date: orNull(v.opening_date),
          })
        }
        update={(r, p) =>
          updateCashbox(token, r.id, {
            ...p,
            ...('analytic_id' in p ? { analytic_id: orNull(p.analytic_id) } : {}),
            ...('opening_date' in p ? { opening_date: orNull(p.opening_date) } : {}),
          } as Parameters<typeof updateCashbox>[2])
        }
        remove={(r) => deleteCashbox(token, r.id)}
        removeBlock={(r) =>
          Number(r.balance) !== 0 || Number(r.opening_balance) !== 0 ? 'این صندوق گردش دارد و حذف نمی‌شود؛ غیرفعالش کنید.' : null
        }
        check={(v, { isNew, saved }) =>
          isNew && saved.length > 0 && !s(v.analytic_id)
            ? 'برای صندوقِ دوم تفصیلی را انتخاب کنید؛ وگرنه مانده‌اش از صندوقِ اول جدا نمی‌شود.'
            : null
        }
        labelOf={(v) => s(v.name)}
        icon={Vault}
        title="صندوق‌ها"
        tip="صندوق جایی است که پولِ نقد نگه داشته می‌شود — با تفصیلی به حسابداری وصل است، نه خودِ حسابِ معین. هر خانه را همان‌جا ویرایش کنید؛ صندوقِ تازه را در ردیفِ خالیِ ته بنویسید و «ذخیره تغییرات» (Ctrl+S) بزنید. اگر صندوقی تعریف نکنید، اولین دریافتِ نقدی خودکار «صندوق اصلی» را می‌سازد."
        unit="صندوق"
        newPlaceholder="صندوقِ تازه: عنوان را بنویسید…"
        findPlaceholder="جست‌وجو: عنوان، کد تفصیلی"
      />
    </>
  )
}

// ═══════════════════ حساب‌های بانکی ═══════════════════

const BANK_SPEC: DefSpec = {
  text: [
    'name', 'bank_name', 'account_number', 'blocked_amount', 'analytic_id', 'currency_code', 'iban', 'card_number',
    'branch_name', 'account_type', 'opening_date', 'holder_name', 'holder_name2', 'name2', 'cheque_print_format',
  ],
  bools: ['is_active'],
  numeric: ['blocked_amount'],
  defaults: { currency_code: 'IRR' },
  required: [{ field: 'name', label: 'نام حساب' }],
  search: ['name', 'bank_name', 'branch_name', 'account_number', 'iban', 'card_number', 'analytic_code'],
}

function BanksTab({ token, analyticOpts, currencyOpts }: { token: string; analyticOpts: Opt[]; currencyOpts: Opt[] }) {
  const list = useAsync(() => fetchBankAccountsAdmin(token), [token])
  const rows = list.data ?? null
  const [ledger, setLedger] = useState<BankAccountRecord | null>(null)
  const totals = perCurrency(rows ?? [], (r) => r.currency_code, (r) => Number(r.balance))
  const hasUntagged = (rows ?? []).some((b) => b.analytic_id === null)
  const cols: DefCol<BankAccountRecord>[] = [
    { id: 'name', label: 'نام حساب', kind: 'text', field: 'name', w: 180, enter: true, placeholder: 'مثلاً جاری ملت' },
    { id: 'bank', label: 'بانک', kind: 'text', field: 'bank_name', w: 110, enter: true },
    { id: 'number', label: 'شماره حساب', kind: 'text', field: 'account_number', w: 150, ltr: true, numeric: true, enter: true },
    { id: 'balance', label: 'مانده', title: 'از گردشِ همین حساب در دفتر.', kind: 'ro', numeric: true, w: 140, ro: (r) => (r ? amount(r.balance) : '—') },
    { id: 'available', label: 'قابل استفاده', title: 'مانده منهای مبلغِ بلوکه‌شده.', kind: 'ro', numeric: true, w: 140, ro: (r) => (r ? amount(r.available_balance) : '—') },
    { id: 'blocked', label: 'بلوکه', title: 'مبلغی که بانک اعلام کرده بلوکه است — از مانده کم نمی‌شود؛ فقط «قابل استفاده» را پایین می‌آورد.', kind: 'number', field: 'blocked_amount', w: 130 },
    {
      id: 'analytic',
      label: 'تفصیلی',
      title: 'مانده‌ی این حساب را از بقیه جدا می‌کند. حسابِ باسابقه تفصیلی‌اش عوض نمی‌شود.',
      kind: 'select',
      field: 'analytic_id',
      emptyOption: '— بدونِ تفصیلی —',
      options: (v) => withCurrent(analyticOpts, v.analytic_id, s(v.analytic_code)),
      w: 190,
    },
    { id: 'currency', label: 'ارز', kind: 'select', field: 'currency_code', options: (v) => withCurrent(currencyOpts, v.currency_code), w: 80 },
    { id: 'active', label: 'وضعیت', kind: 'toggle', field: 'is_active', w: 90 },
    { id: 'iban', label: 'شبا', title: 'با IR شروع می‌شود.', kind: 'text', field: 'iban', w: 250, ltr: true },
    { id: 'card', label: 'شماره کارت', title: '۱۶ رقم — با شبا و شماره حساب یکی نیست.', kind: 'text', field: 'card_number', w: 170, ltr: true, numeric: true },
    { id: 'branch', label: 'شعبه', kind: 'text', field: 'branch_name', w: 110 },
    { id: 'type', label: 'نوع حساب', kind: 'text', field: 'account_type', w: 100, placeholder: 'جاری' },
    { id: 'opened', label: 'تاریخ افتتاح', kind: 'date', field: 'opening_date', w: 130 },
    { id: 'opening', label: 'موجودی اولیه', title: 'ابتدای سالِ مالی — از دفتر.', kind: 'ro', numeric: true, w: 130, ro: (r) => (r ? amount(r.opening_balance) : '—') },
    { id: 'holder', label: 'صاحب حساب', title: 'می‌تواند با نامِ شرکت فرق داشته باشد.', kind: 'text', field: 'holder_name', w: 150 },
    { id: 'holder2', label: 'نام دوم صاحب حساب', kind: 'text', field: 'holder_name2', w: 150 },
    { id: 'name2', label: 'عنوان دوم', kind: 'text', field: 'name2', w: 140 },
    { id: 'print', label: 'فرمت چاپ چک', kind: 'text', field: 'cheque_print_format', w: 130 },
  ]
  return (
    <>
      <section className="cc-head">
        <div className="cc-summary">
          <Metric icon={<Landmark size={14} />} label="حساب‌ها" value={faInt(rows?.length ?? 0)} />
          <Metric icon={<Landmark size={14} />} label="فعال" value={faInt((rows ?? []).filter((b) => b.is_active).length)} tone="in" />
          {totals.map(([code, total]) => (
            <Metric key={code} icon={<Wallet size={14} />} label={`مانده ${code}`} value={fa(total)} tone={total < 0 ? 'out' : 'in'} />
          ))}
        </div>
      </section>
      {hasUntagged && (rows ?? []).some((b) => b.analytic_id !== null && Number(b.balance) === 0) && (
        <p className="field-hint">
          حسابی که مانده‌اش صفر است، گردشِ پیش از تفکیک را روی حسابِ بدونِ تفصیلی دارد. برای انتقالش از «انتقال مانده به حساب
          دیگر» استفاده کنید تا اسنادِ گذشته دست‌نخورده بمانند.
        </p>
      )}
      <DefSheet<BankAccountRecord>
        sheetId="bankaccounts"
        spec={BANK_SPEC}
        cols={cols}
        autoCol="name"
        wide
        slots={[['num', 'name'], ['bank'], ['number'], ['balance'], ['available']]}
        rows={rows}
        error={list.error}
        reload={list.reload}
        valuesOf={(r) => ({
          ...r,
          analytic_id: r.analytic_id ?? '',
          opening_date: r.opening_date ?? '',
          blocked_amount: String(Number(r.blocked_amount) || ''),
        })}
        create={(v) =>
          createBankAccount(token, {
            name: s(v.name),
            name2: s(v.name2),
            bank_name: s(v.bank_name),
            branch_name: s(v.branch_name),
            account_number: s(v.account_number),
            account_type: s(v.account_type),
            card_number: s(v.card_number),
            iban: s(v.iban),
            analytic_id: orNull(v.analytic_id),
            currency_code: s(v.currency_code) || 'IRR',
            opening_date: orNull(v.opening_date),
            holder_name: s(v.holder_name),
            holder_name2: s(v.holder_name2),
            blocked_amount: Number(v.blocked_amount) || 0,
            cheque_print_format: s(v.cheque_print_format),
          })
        }
        update={(r, p) =>
          updateBankAccount(token, r.id, {
            ...p,
            ...('analytic_id' in p ? { analytic_id: orNull(p.analytic_id) } : {}),
            ...('opening_date' in p ? { opening_date: orNull(p.opening_date) } : {}),
            ...('blocked_amount' in p ? { blocked_amount: Number(p.blocked_amount) || 0 } : {}),
          } as Parameters<typeof updateBankAccount>[2])
        }
        remove={(r) => deleteBankAccount(token, r.id)}
        removeBlock={(r) =>
          Number(r.balance) !== 0 || Number(r.opening_balance) !== 0 ? 'این حساب گردش دارد و حذف نمی‌شود؛ غیرفعالش کنید.' : null
        }
        check={(v, { isNew, saved }) =>
          isNew && saved.length > 0 && !s(v.analytic_id)
            ? 'برای حسابِ بانکیِ دوم تفصیلی را انتخاب کنید؛ وگرنه مانده‌اش از حسابِ اول جدا نمی‌شود.'
            : null
        }
        rowActions={(r) => (
          <RowAction icon={BookOpen} label="کارتِ حساب" title="گردشِ همین حساب در دفتر" onClick={() => setLedger(r)} />
        )}
        labelOf={(v) => s(v.name)}
        icon={Landmark}
        title="حساب‌های بانکی"
        tip="حساب‌های بانکیِ کسب‌وکار؛ هر رسید و چکِ بانکی به یکی از این‌ها می‌نشیند. برگه پهن است — با لغزشِ افقی به شبا، کارت، شعبه و صاحب حساب می‌رسید؛ نام حساب و شماره‌ی ردیف سرِ جایشان می‌مانند. مانده‌ها همه از دفترند؛ تنها عددِ ذخیره‌شده مبلغِ بلوکه است. واریز یا برداشتِ دستی در «مرور عملیات بانکی» ثبت می‌شود."
        unit="حساب"
        newPlaceholder="حسابِ تازه: نام را بنویسید…"
        findPlaceholder="جست‌وجو: نام، بانک، شماره، شبا"
      />
      {ledger && (
        //: دفتر با **تفصیلیِ همین حساب** فیلتر می‌شود؛ معینِ مشترک گردشِ همه‌ی بانک‌ها را نشان می‌داد.
        <AccountLedgerDrawer
          token={token}
          account={{ id: ledger.gl_account_id, code: ledger.analytic_code ?? ledger.account_number, name: ledger.name }}
          filters={ledger.analytic_id ? { analyticId: ledger.analytic_id } : undefined}
          onClose={() => setLedger(null)}
        />
      )}
    </>
  )
}

// ═══════════════════ دستگاه‌های کارتخوان ═══════════════════

const TRANSPORTS: Opt[] = [
  { value: 'simulator', label: 'شبیه‌ساز (بدونِ دستگاه)' },
  { value: 'network', label: 'تحت شبکه (IP:Port)' },
  { value: 'serial', label: 'USB / سریال (COM)' },
  { value: 'sdk', label: 'SDK اختصاصیِ PSP' },
]

const POS_SPEC: DefSpec = {
  text: ['label', 'terminal_no', 'bank_account_id', 'analytic_id', 'currency_code', 'psp', 'transport', 'host', 'port', 'com_port', 'name2'],
  bools: ['is_active', 'is_default'],
  numeric: ['port'],
  defaults: { currency_code: 'IRR', transport: 'simulator' },
  required: [{ field: 'label', label: 'نامِ دستگاه' }],
  search: ['label', 'terminal_no', 'bank_account_name', 'psp'],
}

function PosTab({ token, analyticOpts, currencyOpts }: { token: string; analyticOpts: Opt[]; currencyOpts: Opt[] }) {
  const list = useAsync(() => fetchPosTerminals(token), [token])
  const banks = useAsync(() => fetchBankAccountsAdmin(token).catch(() => []), [token])
  const [note, setNote] = useState<Msg>(null)
  const rows = list.data ?? null
  const bankOpts: Opt[] = (banks.data ?? []).map((b) => ({ value: b.id, label: b.name }))
  const desktop = typeof window !== 'undefined' && Boolean(window.cubita?.posTerminal)
  const unsettled = (rows ?? []).reduce((sum, t) => sum + Number(t.unsettled_balance || 0), 0)

  async function test(t: PosTerminalRecord) {
    setNote(null)
    if (!window.cubita?.posTerminal) {
      setNote({ text: 'آزمایشِ اتصال فقط در نسخه‌ی دسکتاپ ممکن است.', kind: 'err' })
      return
    }
    try {
      const res = await window.cubita.posTerminal.status({
        transport: t.transport,
        host: t.host || undefined,
        port: Number(t.port) || undefined,
        comPort: t.com_port || undefined,
        psp: t.psp || undefined,
      })
      setNote({ text: `«${t.label || 'کارتخوان'}»: ${res.message || (res.online ? 'در دسترس' : 'در دسترس نیست')}`, kind: res.online ? 'ok' : 'err' })
    } catch (err) {
      setNote({ text: `«${t.label || 'کارتخوان'}»: ${errText(err)}`, kind: 'err' })
    }
  }

  const cols: DefCol<PosTerminalRecord>[] = [
    { id: 'label', label: 'دستگاه', kind: 'text', field: 'label', w: 170, enter: true },
    { id: 'terminal', label: 'شماره پایانه', title: 'شماره‌ای که خودِ دستگاه گزارش می‌کند — با شماره‌ی کارتِ بانکی یکی نیست.', kind: 'text', field: 'terminal_no', w: 130, ltr: true, enter: true },
    {
      id: 'bank',
      label: 'حسابِ بانکیِ تسویه',
      title: 'واریزِ شرکتِ پرداخت به این حساب می‌نشیند.',
      kind: 'select',
      field: 'bank_account_id',
      emptyOption: '— انتخاب —',
      options: (v) => withCurrent(bankOpts, v.bank_account_id, s(v.bank_account_name)),
      w: 190,
      enter: true,
    },
    { id: 'unsettled', label: 'تسویه‌نشده', title: 'جمعِ رسیدهای کارتیِ هنوز تسویه‌نشده — مانده‌ی بانک نیست.', kind: 'ro', numeric: true, w: 130, ro: (r) => (r ? amount(r.unsettled_balance) : '—') },
    {
      id: 'analytic',
      label: 'تفصیلیِ وجوهِ در راه',
      title: 'بدونِ آن، وجوهِ در راهِ همه‌ی دستگاه‌ها یک عدد می‌شود.',
      kind: 'select',
      field: 'analytic_id',
      emptyOption: '— بدونِ تفصیلی —',
      options: (v) => withCurrent(analyticOpts, v.analytic_id, s(v.analytic_code)),
      w: 190,
    },
    { id: 'currency', label: 'ارز', title: 'باید با ارزِ حسابِ تسویه یکی باشد.', kind: 'select', field: 'currency_code', options: (v) => withCurrent(currencyOpts, v.currency_code), w: 80 },
    { id: 'default', label: 'پیش‌فرض', title: 'دستگاهی که پرداختِ کارتی بی‌انتخاب با آن انجام می‌شود.', kind: 'toggle', field: 'is_default', w: 90, newValue: false, newLock: 'پس از ذخیره می‌توانید پیش‌فرضش کنید.' },
    { id: 'active', label: 'وضعیت', kind: 'toggle', field: 'is_active', w: 90 },
    { id: 'transport', label: 'اتصال', kind: 'select', field: 'transport', options: () => TRANSPORTS, w: 180 },
    { id: 'host', label: 'میزبان (IP)', kind: 'text', field: 'host', w: 140, ltr: true },
    { id: 'port', label: 'پورت', kind: 'text', field: 'port', w: 90, ltr: true, numeric: true },
    { id: 'com', label: 'درگاه سریال', kind: 'text', field: 'com_port', w: 120, ltr: true, placeholder: 'COM3' },
    { id: 'psp', label: 'PSP', title: 'شرکتِ پرداخت (به‌پرداخت، سامان‌کیش، …).', kind: 'text', field: 'psp', w: 120 },
    { id: 'name2', label: 'عنوان دوم', kind: 'text', field: 'name2', w: 140 },
  ]
  const input = (v: DefValues) => ({
    label: s(v.label),
    name2: s(v.name2),
    terminal_no: s(v.terminal_no),
    currency_code: s(v.currency_code) || 'IRR',
    psp: s(v.psp),
    transport: (s(v.transport) || 'simulator') as PosTransport,
    host: s(v.host),
    port: Number(v.port) || 0,
    com_port: s(v.com_port),
    bank_account_id: orNull(v.bank_account_id),
    analytic_id: orNull(v.analytic_id),
  })
  return (
    <>
      <section className="cc-head">
        <div className="cc-summary">
          <Metric icon={<Nfc size={14} />} label="دستگاه‌ها" value={faInt(rows?.length ?? 0)} />
          <Metric icon={<Nfc size={14} />} label="فعال" value={faInt((rows ?? []).filter((t) => t.is_active).length)} tone="in" />
          <Metric icon={<Wallet size={14} />} label="تسویه‌نشده" value={fa(unsettled)} tone={unsettled > 0 ? 'out' : 'plain'} hint="وجوهِ در راه" />
        </div>
      </section>
      {!desktop && (
        <p className="field-hint">
          اتصال و پرداخت با کارتخوان فقط در نسخه‌ی دسکتاپ انجام می‌شود؛ همین‌جا در مرورگر می‌توانید دستگاه‌ها و حسابِ تسویه‌شان را
          تعریف کنید تا در دسکتاپ آماده باشند.
        </p>
      )}
      <Note msg={note} />
      <DefSheet<PosTerminalRecord>
        sheetId="posterminals"
        spec={POS_SPEC}
        cols={cols}
        autoCol="label"
        wide
        slots={[['num', 'label'], ['terminal'], ['bank'], ['unsettled'], ['analytic']]}
        rows={rows}
        error={list.error}
        reload={list.reload}
        valuesOf={(r) => ({ ...r, bank_account_id: r.bank_account_id ?? '', analytic_id: r.analytic_id ?? '', port: r.port ? String(r.port) : '' })}
        create={(v) => createPosTerminal(token, input(v))}
        update={(r, p) => {
          //: PATCHِ کارتخوان همان شِمای کامل را می‌گیرد؛ فقط فیلدهای عوض‌شده جلوی مقدارِ ثبت‌شده می‌نشینند تا
          //: ویرایشِ یک خانه چیزِ دیگری را بازنویسی نکند.
          const merged = { ...r, bank_account_id: r.bank_account_id ?? '', analytic_id: r.analytic_id ?? '', port: String(r.port || ''), ...p }
          return updatePosTerminal(token, r.id, { ...input(merged), is_active: Boolean(merged.is_active), is_default: Boolean(merged.is_default) })
        }}
        remove={(r) => deletePosTerminal(token, r.id)}
        removeBlock={(r) => (Number(r.unsettled_balance) !== 0 ? 'این دستگاه رسیدِ تسویه‌نشده دارد و حذف نمی‌شود؛ غیرفعالش کنید.' : null)}
        rowActions={(r) => <RowAction icon={Plug} label="آزمایشِ اتصال" title="آزمایشِ اتصال با همین تنظیمِ ذخیره‌شده" onClick={() => void test(r)} />}
        labelOf={(v) => s(v.label) || s(v.terminal_no)}
        icon={Nfc}
        title="دستگاه‌های کارتخوان"
        tip="پایانه‌های فروشگاهی و حسابی که واریزشان به آن می‌نشیند. برگه پهن است — تنظیمِ اتصال (نوع، میزبان، پورت، درگاه) با لغزشِ افقی در دسترس است. «آزمایشِ اتصال» تنظیمِ ذخیره‌شده را می‌سنجد؛ پیش از آن تغییرها را ذخیره کنید."
        unit="دستگاه"
        newPlaceholder="دستگاهِ تازه: نام را بنویسید…"
        findPlaceholder="جست‌وجو: نام، شماره پایانه، حساب"
      />
    </>
  )
}

// ═══════════════════ دسته‌چک‌ها ═══════════════════

const CHECKBOOK_SPEC: DefSpec = {
  text: ['bank_account_id', 'serial', 'first_number', 'last_number', 'issue_date', 'description', 'cheque_print_format'],
  bools: ['is_active'],
  required: [
    { field: 'bank_account_id', label: 'حساب بانکی' },
    { field: 'first_number', label: 'شماره‌ی اولین برگ' },
    { field: 'last_number', label: 'شماره‌ی آخرین برگ' },
  ],
  search: ['bank_account_name', 'serial', 'first_number', 'last_number', 'description'],
}

function CheckbooksTab({ token }: { token: string }) {
  const list = useAsync(() => fetchCheckbooks(token), [token])
  const banks = useAsync(() => fetchBankAccountsAdmin(token).catch(() => []), [token])
  const [open, setOpen] = useState('')
  const leaves = useAsync(() => (open ? fetchCheckbookLeaves(token, open) : Promise.resolve([])), [token, open])
  const rows = list.data ?? null
  const bankOpts: Opt[] = (banks.data ?? []).map((b) => ({ value: b.id, label: b.name }))
  const remaining = (rows ?? []).filter((b) => b.is_active).reduce((sum, b) => sum + b.remaining_count, 0)
  //: حساب و بازه‌ی شماره با اولین برگِ خرج‌شده قفل می‌شوند (سرور ۴۰۹ می‌دهد) — همان‌جا گفته می‌شود نه بعد از ذخیره.
  const structural = (r: CheckbookRecord) =>
    r.used_count > 0 ? `از این دسته ${faInt(r.used_count)} برگ صادر شده؛ حساب و بازه‌ی شماره دیگر عوض نمی‌شوند.` : null
  const cols: DefCol<CheckbookRecord>[] = [
    {
      id: 'bank',
      label: 'حساب بانکی',
      kind: 'select',
      field: 'bank_account_id',
      emptyOption: '— انتخاب حساب —',
      options: (v) => withCurrent(bankOpts, v.bank_account_id, s(v.bank_account_name)),
      lock: structural,
      enter: true,
    },
    { id: 'serial', label: 'سری', title: 'سریِ روی جلد (صیادی یا شماره‌ی داخلیِ بانک). اختیاری.', kind: 'text', field: 'serial', w: '7%', ltr: true, mhide: true, narrow: true },
    { id: 'first', label: 'از برگ', kind: 'text', field: 'first_number', w: '9%', ltr: true, numeric: true, lock: structural, enter: true },
    { id: 'last', label: 'تا برگ', kind: 'text', field: 'last_number', w: '9%', ltr: true, numeric: true, lock: structural, enter: true },
    { id: 'used', label: 'خرج‌شده', title: 'از بازه‌ی شماره‌ها چند برگ به چک رفته.', kind: 'ro', numeric: true, w: '6%', ro: (r) => (r ? faInt(r.used_count) : '—') },
    { id: 'left', label: 'مانده', kind: 'ro', numeric: true, w: '6%', ro: (r) => (r ? faInt(r.remaining_count) : '—') },
    { id: 'issued', label: 'تاریخ دریافت', title: 'روزی که دسته از بانک گرفته شد.', kind: 'date', field: 'issue_date', w: '11%', mhide: true },
    { id: 'note', label: 'توضیح', kind: 'text', field: 'description', w: '10%', mhide: true, narrow: true },
    { id: 'print', label: 'فرمت چاپ', title: 'خالی یعنی از حسابِ بانکی ارث ببرد.', kind: 'text', field: 'cheque_print_format', w: '7%', mhide: true, narrow: true },
    { id: 'active', label: 'وضعیت', title: 'دسته‌ی بسته برای صدورِ برگ پیشنهاد نمی‌شود.', kind: 'toggle', field: 'is_active', w: '8%' },
  ]
  return (
    <>
      <section className="cc-head">
        <div className="cc-summary">
          <Metric icon={<BookMarked size={14} />} label="دسته‌های باز" value={faInt((rows ?? []).filter((b) => b.is_active).length)} />
          <Metric icon={<ListChecks size={14} />} label="برگِ مانده" value={faInt(remaining)} tone="in" hint="در دسته‌های باز" />
        </div>
      </section>
      <DefSheet<CheckbookRecord>
        sheetId="checkbooks"
        spec={CHECKBOOK_SPEC}
        cols={cols}
        autoCol="bank"
        slots={[['num', 'bank'], ['serial', 'first'], ['last', 'used'], ['left', 'issued'], ['note', 'print', 'active', 'actions']]}
        rows={rows}
        error={list.error}
        reload={list.reload}
        valuesOf={(r) => ({ ...r, issue_date: r.issue_date ?? '' })}
        create={(v) =>
          createCheckbook(token, {
            bank_account_id: s(v.bank_account_id),
            serial: s(v.serial),
            first_number: s(v.first_number),
            last_number: s(v.last_number),
            issue_date: orNull(v.issue_date),
            description: s(v.description),
            cheque_print_format: s(v.cheque_print_format),
          })
        }
        update={async (r, p) => {
          const { is_active, ...rest } = p
          //: وضعیت فقط با مسیرِ صریحِ باز/بستن عوض می‌شود (نه با PATCH) — همان قراردادِ صفحه‌ی قبلی.
          if (Object.keys(rest).length > 0) {
            await updateCheckbook(token, r.id, {
              ...rest,
              ...('issue_date' in rest ? { issue_date: orNull(rest.issue_date) } : {}),
            } as Parameters<typeof updateCheckbook>[2])
          }
          if (is_active !== undefined) await setCheckbookActive(token, r.id, Boolean(is_active))
        }}
        remove={(r) => deleteCheckbook(token, r.id)}
        removeBlock={(r) => (r.used_count > 0 ? 'از این دسته برگ صادر شده و حذف نمی‌شود؛ ببندیدش.' : null)}
        rowActions={(r) => (
          <RowAction
            icon={ListChecks}
            label={open === r.id ? 'بستنِ برگ‌ها' : 'برگ‌های خرج‌شده'}
            title="هر برگ کجا رفت: در وجهِ چه کسی، چه مبلغی، در چه وضعیتی"
            disabled={r.used_count === 0}
            onClick={() => setOpen((o) => (o === r.id ? '' : r.id))}
          />
        )}
        detail={(r) =>
          open === r.id ? (
            <div className="ds-detail-body">
              <LeafList rows={leaves.data ?? []} loading={leaves.loading} error={leaves.error} />
            </div>
          ) : null
        }
        labelOf={(v) => [s(v.bank_account_name), s(v.first_number) && `${s(v.first_number)} تا ${s(v.last_number)}`].filter(Boolean).join(' — ')}
        icon={BookMarked}
        title="دسته‌چک‌ها"
        tip="دسته‌چک‌های هر حسابِ بانکی و اینکه چند برگ مانده. شماره‌ی اولین و آخرین برگ را بنویسید؛ تعداد خودکار حساب می‌شود. حساب و بازه‌ی شماره تا وقتی عوض می‌شوند که برگی خرج نشده باشد. برای صدورِ چک از «اعلامیه پرداخت» یا «چک‌ها» استفاده کنید — برگِ بعدیِ دسته خودکار پیشنهاد می‌شود."
        unit="دسته"
        newPlaceholder=""
        findPlaceholder="جست‌وجو: حساب، سری، شماره"
      />
    </>
  )
}

// ═══════════════════ صندوق‌های تنخواه ═══════════════════

const PETTY_SPEC: DefSpec = {
  text: ['name', 'custodian_contact_id', 'location', 'spending_limit', 'notes'],
  bools: ['is_active'],
  numeric: ['spending_limit'],
  required: [{ field: 'name', label: 'نامِ صندوق' }],
  search: ['name', 'location', 'notes'],
}

type FundRow = PettyCashFundRecord & { balance: string | null }

function PettyFundsTab({ token }: { token: string }) {
  const list = useAsync(async (): Promise<FundRow[]> => {
    const funds = await fetchPettyCashFunds(token)
    //: مانده‌ی هر صندوق از رویدادهای خودش؛ چند صندوق بیشتر نیست، پس درخواستِ جدا برای هر کدام بی‌هزینه است.
    const balances = await Promise.all(funds.map((f) => fetchPettyCashFundBalance(token, f.id).catch(() => null)))
    return funds.map((f, i) => ({ ...f, balance: balances[i]?.balance ?? null }))
  }, [token])
  const contacts = useAsync(() => fetchContacts(token).catch(() => []), [token])
  const rows = list.data ?? null
  const contactOpts: Opt[] = useMemo(() => (contacts.data ?? []).map((c) => ({ value: c.id, label: c.name })), [contacts.data])
  const cols: DefCol<FundRow>[] = [
    { id: 'name', label: 'صندوقِ تنخواه', kind: 'text', field: 'name', enter: true },
    {
      id: 'custodian',
      label: 'تنخواه‌دار',
      title: 'طرف‌حسابی که پول دستِ اوست — لازم نیست کاربرِ برنامه باشد. تعویضش هویتِ صندوق را عوض نمی‌کند.',
      kind: 'select',
      field: 'custodian_contact_id',
      emptyOption: '— انتخاب —',
      options: (v) => withCurrent(contactOpts, v.custodian_contact_id),
      w: '18%',
      enter: true,
    },
    { id: 'location', label: 'محل', kind: 'text', field: 'location', w: '10%', mhide: true, narrow: true },
    { id: 'limit', label: 'سقفِ هزینه', title: '۰ یعنی بی‌سقف. هشدار است نه گارد.', kind: 'number', field: 'spending_limit', w: '10%' },
    { id: 'balance', label: 'مانده', title: 'از شارژها و صورت‌هزینه‌های همین صندوق.', kind: 'ro', numeric: true, w: '10%', ro: (r) => (r?.balance != null ? amount(r.balance) : '—') },
    { id: 'notes', label: 'یادداشت', kind: 'text', field: 'notes', w: '12%', mhide: true, narrow: true },
    { id: 'active', label: 'وضعیت', kind: 'toggle', field: 'is_active', w: '8%' },
  ]
  return (
    <>
      <section className="cc-head">
        <div className="cc-summary">
          <Metric icon={<Wallet size={14} />} label="صندوق‌های تنخواه" value={faInt(rows?.length ?? 0)} />
          <Metric icon={<Wallet size={14} />} label="فعال" value={faInt((rows ?? []).filter((f) => f.is_active).length)} tone="in" />
        </div>
      </section>
      <DefSheet<FundRow>
          sheetId="pettyfunds"
          spec={PETTY_SPEC}
          cols={cols}
          autoCol="name"
          slots={[['num', 'name'], ['custodian'], ['location', 'limit'], ['balance'], ['notes', 'active', 'actions']]}
          rows={rows}
          error={list.error}
          reload={list.reload}
          valuesOf={(r) => ({
            ...r,
            custodian_contact_id: r.custodian_contact_id ?? '',
            spending_limit: String(Number(r.spending_limit) || ''),
          })}
          create={(v) =>
            createPettyCashFund(token, {
              name: s(v.name),
              custodian_contact_id: orNull(v.custodian_contact_id),
              location: s(v.location),
              spending_limit: Number(v.spending_limit) || 0,
              notes: s(v.notes),
            })
          }
          update={(r, p) =>
            updatePettyCashFund(token, r.id, {
              ...p,
              ...('custodian_contact_id' in p ? { custodian_contact_id: orNull(p.custodian_contact_id) } : {}),
              ...('spending_limit' in p ? { spending_limit: Number(p.spending_limit) || 0 } : {}),
            } as Parameters<typeof updatePettyCashFund>[2])
          }
          //: سرور حذفِ صندوقِ تنخواه را ندارد — سابقه‌ی هزینه‌ها به آن بسته است.
          remove={() => Promise.reject(new Error('صندوقِ تنخواه حذف نمی‌شود؛ غیرفعالش کنید.'))}
          removeBlock={() => 'صندوقِ تنخواه حذف نمی‌شود؛ غیرفعالش کنید.'}
          labelOf={(v) => s(v.name)}
          icon={Wallet}
          title="صندوق‌های تنخواه"
          tip="هر تنخواه‌گردان یک صندوق است: نام، تنخواه‌دار (طرف‌حساب)، محل و سقفِ هزینه. با یک صندوقِ فعال، شارژ و صورت‌هزینه خودکار به همان می‌نشینند؛ با بیش از یکی، در «شارژ تنخواه» و «صورت هزینه تنخواه» صندوق را انتخاب می‌کنید. شارژ و هزینه‌ای که پیش از تعریفِ صندوق ثبت شده به صندوقی وصل نیست و فقط در مانده‌ی کلِ تنخواه شمرده می‌شود."
          unit="صندوق"
          newPlaceholder="صندوقِ تازه: نام را بنویسید…"
          findPlaceholder="جست‌وجو: نام، محل"
        />
    </>
  )
}

