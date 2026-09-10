import { useMemo, useState } from 'react'
import {
  BookMarked,
  CreditCard,
  FileSpreadsheet,

  ScrollText,
  Wallet,
} from 'lucide-react'
import {
  fetchBankAccountsAdmin,
  fetchCheckbooks,
  fetchPettyCashTransactions,
  fetchPosTerminals,
  fetchStatementLines,
  fetchTreasuryTransactions,
  type BankStatementLineRecord,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali } from '../../lib/jalali'
import { AsyncBlock, Metric, OpsPage, fa, faInt, useAsync } from '../accounting/kit'

/**
 * دفترهای ماژولِ «دریافت و پرداخت» — نظیرِ فهرستیِ عملیاتِ رکوردساز.
 *
 * قاعده‌ی نظیر (اسکیلِ `cubita-page`): صفحه‌ی عملیات برای **ثبت** است و جدولِ کوچکش
 * فقط ردیف‌های اخیر/نیازمندِ اقدام را نشان می‌دهد؛ صفحه‌ی فهرست دفترِ **مرورِ** همان
 * رکوردهاست — همه‌ی ردیف‌ها، با جمع‌ها و فیلتر و بدونِ فرم. این دو تکراری نیستند:
 * یکی جای کار کردن است و دیگری جای گشتن.
 */

// ═══════════════════ دسته‌چک‌ها ═══════════════════

export function CheckbookListPage({ token }: { token: string }) {
  const [only, setOnly] = useState<'all' | 'open' | 'closed'>('all')
  const books = useAsync(() => fetchCheckbooks(token), [token])

  const rows = useMemo(() => {
    return (books.data ?? []).filter((b) =>
      only === 'open' ? b.is_active : only === 'closed' ? !b.is_active : true,
    )
  }, [books.data, only])
  const pg = usePagination(rows, 15, only)

  const remaining = rows.filter((b) => b.is_active).reduce((s, b) => s + b.remaining_count, 0)
  const used = rows.reduce((s, b) => s + b.used_count, 0)

  return (
    <OpsPage
      icon={BookMarked}
      title="دسته‌چک‌ها"
      description="همه‌ی دسته‌چک‌های ثبت‌شده — باز و بسته — با شمارِ برگِ خرج‌شده و باقی‌مانده."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <div className="cc-presets">
              {(
                [
                  ['all', 'همه'],
                  ['open', 'باز'],
                  ['closed', 'بسته'],
                ] as const
              ).map(([key, label]) => (
                <button key={key} type="button" className={only === key ? 'is-active' : ''} onClick={() => setOnly(key)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="cc-summary">
            <Metric icon={<BookMarked size={14} />} label="دسته‌ها" value={faInt(rows.length)} />
            <Metric icon={<ScrollText size={14} />} label="برگِ خرج‌شده" value={faInt(used)} tone="out" />
            <Metric icon={<ScrollText size={14} />} label="برگِ مانده" value={faInt(remaining)} tone="in" hint="در دسته‌های باز" />
          </div>
        </div>
      }
    >
      <SectionCard icon={BookMarked} title="دسته‌چک‌ها" description={`${faInt(rows.length)} دسته`}>
        <AsyncBlock
          loading={books.loading}
          error={books.error}
          empty={rows.length === 0}
          emptyText="دسته‌چکی با این فیلتر نیست. از عملیاتِ «دسته چک» ثبتش کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>حساب بانکی</th>
                  <th>سری</th>
                  <th>از</th>
                  <th>تا</th>
                  <th>برگ</th>
                  <th>خرج‌شده</th>
                  <th>مانده</th>
                  <th>دریافت</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((b) => (
                  <tr key={b.id} className={b.is_active ? '' : 'acc-row--void'}>
                    <td className="card-title" data-label="حساب بانکی">{b.bank_account_name}</td>
                    <td data-label="سری"><span dir="ltr">{b.serial || '—'}</span></td>
                    <td data-label="از"><span dir="ltr">{b.first_number}</span></td>
                    <td data-label="تا"><span dir="ltr">{b.last_number}</span></td>
                    <td className="num" data-label="برگ">{faInt(b.leaf_count)}</td>
                    <td className="num" data-label="خرج‌شده">{faInt(b.used_count)}</td>
                    <td className="num" data-label="مانده">{faInt(b.remaining_count)}</td>
                    <td data-label="دریافت">{b.issue_date ? formatJalali(b.issue_date) : '—'}</td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${b.is_active ? 'tone-success' : ''}`}>
                        {b.is_active ? 'باز' : 'بسته'}
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

// ═══════════════════ دستگاه‌های کارتخوان ═══════════════════

export function PosTerminalListPage({ token }: { token: string }) {
  const terminals = useAsync(() => fetchPosTerminals(token), [token])
  const rows = terminals.data ?? []
  const pg = usePagination(rows, 15)
  const active = rows.filter((t) => t.is_active).length

  return (
    <OpsPage
      icon={CreditCard}
      title="دستگاه‌های کارتخوان"
      description="دفترِ پایانه‌های ثبت‌شده و حسابی که واریزشان به آن می‌نشیند."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<CreditCard size={14} />} label="پایانه‌ها" value={faInt(rows.length)} />
            <Metric icon={<CreditCard size={14} />} label="فعال" value={faInt(active)} tone="in" />
          </div>
        </div>
      }
    >
      <SectionCard icon={CreditCard} title="پایانه‌ها" description={`${faInt(rows.length)} دستگاه`}>
        <AsyncBlock
          loading={terminals.loading}
          error={terminals.error}
          empty={rows.length === 0}
          emptyText="دستگاهی ثبت نشده. از عملیاتِ «دستگاه کارت خوان» شروع کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>شرکتِ پرداخت</th>
                  <th>اتصال</th>
                  <th>پیش‌فرض</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((t) => (
                  <tr key={t.id} className={t.is_active ? '' : 'acc-row--void'}>
                    <td className="card-title" data-label="نام">{t.label || '—'}</td>
                    <td data-label="شرکتِ پرداخت"><span dir="ltr">{t.psp || '—'}</span></td>
                    <td className="card-wide" data-label="اتصال">
                      <span dir="ltr">
                        {t.transport === 'serial' ? t.com_port || '—' : `${t.host || '—'}:${t.port || 0}`}
                      </span>
                    </td>
                    <td data-label="پیش‌فرض">{t.is_default ? 'بله' : '—'}</td>
                    <td data-label="وضعیت">
                      <span className={`status-badge ${t.is_active ? 'tone-success' : ''}`}>
                        {t.is_active ? 'فعال' : 'غیرفعال'}
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

// ═══════════════════ تسویه‌های کارتخوان ═══════════════════

/**
 * دفترِ تسویه‌های انجام‌شده.
 *
 * از خودِ رسیدهای کارتی ساخته می‌شود (`settled_at`)، نه یک جدولِ جدا: تسویه چیزی جز
 * «این رسیدها با هم تسویه شدند» نیست، و ساختنِ جدولِ موازی یعنی دو حقیقتِ ممکن.
 */
export function PosSettlementListPage({ token }: { token: string }) {
  const txns = useAsync(() => fetchTreasuryTransactions(token), [token])

  const groups = useMemo(() => {
    const map = new Map<string, { key: string; day: string; terminal: string; count: number; amount: number }>()
    for (const t of txns.data ?? []) {
      if (t.paid_via !== 'pos_terminal' || !t.settled_at) continue
      const day = t.settled_at.slice(0, 10)
      const terminal = t.terminal_no || ''
      const key = `${day}|${terminal}`
      const row = map.get(key) ?? { key, day, terminal, count: 0, amount: 0 }
      row.count += 1
      row.amount += Number(t.amount)
      map.set(key, row)
    }
    return [...map.values()].sort((a, b) => b.day.localeCompare(a.day))
  }, [txns.data])

  const pg = usePagination(groups, 15)
  const total = groups.reduce((s, g) => s + g.amount, 0)

  return (
    <OpsPage
      icon={CreditCard}
      title="تسویه‌های کارتخوان"
      description="واریزهای شرکتِ پرداخت که ثبت شده‌اند — هر ردیف یک روزِ تسویه‌شده‌ی یک پایانه."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<CreditCard size={14} />} label="تسویه‌ها" value={faInt(groups.length)} />
            <Metric icon={<Wallet size={14} />} label="جمعِ ناخالصِ تسویه‌شده" value={fa(total)} tone="in" />
          </div>
        </div>
      }
    >
      <SectionCard icon={CreditCard} title="تسویه‌ها" description={`${faInt(groups.length)} ردیف`}>
        <AsyncBlock
          loading={txns.loading}
          error={txns.error}
          empty={groups.length === 0}
          emptyText="هنوز تسویه‌ای ثبت نشده. از عملیاتِ «تسویه کارت خوان» شروع کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخِ تسویه</th>
                  <th>پایانه</th>
                  <th>شمارِ رسید</th>
                  <th>جمعِ ناخالص</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((g) => (
                  <tr key={g.key}>
                    <td className="card-title" data-label="تاریخِ تسویه">{formatJalali(g.day)}</td>
                    <td data-label="پایانه"><span dir="ltr">{g.terminal || '—'}</span></td>
                    <td className="num" data-label="شمارِ رسید">{faInt(g.count)}</td>
                    <td className="num" data-label="جمعِ ناخالص">{fa(g.amount)}</td>
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

// ═══════════════════ ردیف‌های صورت‌حساب بانکی ═══════════════════

/** همه‌ی حساب‌ها یک‌جا — صفحه‌ی عملیات هر بار فقط یک حساب را نشان می‌دهد. */
export function StatementListPage({ token }: { token: string }) {
  const [only, setOnly] = useState<'all' | 'matched' | 'unmatched'>('all')

  const data = useAsync(async () => {
    const banks = await fetchBankAccountsAdmin(token)
    const perAccount = await Promise.all(
      banks.map(async (b) => ({
        bank: b,
        lines: await fetchStatementLines(token, b.id).catch(() => [] as BankStatementLineRecord[]),
      })),
    )
    return perAccount.flatMap(({ bank, lines }) => lines.map((l) => ({ ...l, bankName: bank.name })))
  }, [token])

  const rows = useMemo(() => {
    return (data.data ?? []).filter((l) =>
      only === 'matched' ? l.matched_transaction_id : only === 'unmatched' ? !l.matched_transaction_id : true,
    )
  }, [data.data, only])
  const pg = usePagination(rows, 20, only)

  const matched = (data.data ?? []).filter((l) => l.matched_transaction_id).length

  return (
    <OpsPage
      icon={FileSpreadsheet}
      title="ردیف‌های صورت‌حساب بانکی"
      description="همه‌ی ردیف‌های واردشده از صورت‌حسابِ بانک‌ها، با وضعیتِ تطبیقشان."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <div className="cc-presets">
              {(
                [
                  ['all', 'همه'],
                  ['matched', 'تطبیق‌شده'],
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
            <Metric icon={<FileSpreadsheet size={14} />} label="ردیف‌ها" value={faInt((data.data ?? []).length)} />
            <Metric icon={<FileSpreadsheet size={14} />} label="تطبیق‌شده" value={faInt(matched)} tone="in" />
            <Metric
              icon={<FileSpreadsheet size={14} />}
              label="تطبیق‌نشده"
              value={faInt((data.data ?? []).length - matched)}
              tone={(data.data ?? []).length - matched > 0 ? 'out' : 'plain'}
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={FileSpreadsheet} title="ردیف‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={data.loading}
          error={data.error}
          empty={rows.length === 0}
          emptyText="ردیفی با این فیلتر نیست. از عملیاتِ «صورت حساب بانکی» وارد کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>حساب</th>
                  <th>شرح</th>
                  <th>مبلغ</th>
                  <th>تطبیق</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((l) => (
                  <tr key={l.id}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(l.line_date)}</td>
                    <td data-label="حساب">{l.bankName}</td>
                    <td className="card-wide" data-label="شرح">{l.description || '—'}</td>
                    <td className="num" data-label="مبلغ">{fa(l.amount)}</td>
                    <td data-label="تطبیق">
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

// ═══════════════════ گردش تنخواه ═══════════════════

/** شارژ و هزینه در یک دفتر — دو عملیات، یک جدول (قاعده‌ی فهرستِ مشترک). */
export function PettyCashListPage({ token }: { token: string }) {
  const [only, setOnly] = useState<'all' | 'charge' | 'expense'>('all')
  const rowsAll = useAsync(() => fetchPettyCashTransactions(token), [token])

  const rows = useMemo(
    () => (rowsAll.data ?? []).filter((r) => (only === 'all' ? true : r.type === only)),
    [rowsAll.data, only],
  )
  const pg = usePagination(rows, 20, only)

  const charged = (rowsAll.data ?? []).filter((r) => r.type === 'charge').reduce((s, r) => s + Number(r.amount), 0)
  const spent = (rowsAll.data ?? []).filter((r) => r.type === 'expense').reduce((s, r) => s + Number(r.amount), 0)

  return (
    <OpsPage
      icon={Wallet}
      title="گردش تنخواه"
      description="شارژها و هزینه‌های تنخواه‌گردان در یک دفتر — همان دو عملیاتِ «تنخواه دار» و «صورت هزینه تنخواه»."
      head={
        <div className="cc-head">
          <div className="cc-toolbar">
            <div className="cc-presets">
              {(
                [
                  ['all', 'همه'],
                  ['charge', 'شارژ'],
                  ['expense', 'هزینه'],
                ] as const
              ).map(([key, label]) => (
                <button key={key} type="button" className={only === key ? 'is-active' : ''} onClick={() => setOnly(key)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="cc-summary">
            <Metric icon={<Wallet size={14} />} label="جمعِ شارژ" value={fa(charged)} tone="in" />
            <Metric icon={<Wallet size={14} />} label="جمعِ هزینه" value={fa(spent)} tone="out" />
            <Metric
              icon={<Wallet size={14} />}
              label="ماندهٔ محاسباتی"
              value={fa(charged - spent)}
              tone={charged - spent < 0 ? 'out' : 'in'}
            />
          </div>
        </div>
      }
    >
      <SectionCard icon={Wallet} title="گردش" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={rowsAll.loading}
          error={rowsAll.error}
          empty={rows.length === 0}
          emptyText="گردشی با این فیلتر نیست. از «تنخواه دار» شارژ کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>نوع</th>
                  <th>شرح</th>
                  <th>مبلغ</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.id}>
                    <td className="card-title" data-label="تاریخ">{formatJalali(r.transaction_date)}</td>
                    <td data-label="نوع">
                      <span className={`status-badge ${r.type === 'charge' ? 'tone-success' : 'tone-warning'}`}>
                        {r.type === 'charge' ? 'شارژ' : 'هزینه'}
                      </span>
                    </td>
                    <td className="card-wide" data-label="شرح">{r.description || '—'}</td>
                    <td className="num" data-label="مبلغ">{fa(r.amount)}</td>
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
