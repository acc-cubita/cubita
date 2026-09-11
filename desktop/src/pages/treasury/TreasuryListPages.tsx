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
  fetchPosSettlement,
  fetchPosSettlements,
  fetchPosTerminals,
  fetchStatementLines,
  voidPosSettlement,
  type BankStatementLineRecord,
} from '../../api'
import { SectionCard } from '../../components/SectionCard'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali } from '../../lib/jalali'
import { AsyncBlock, Metric, Note, OpsPage, fa, faInt, useAsync, type Msg } from '../accounting/kit'

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
                    <td data-label="سری">
                      <span dir="ltr">{b.serial || '—'}</span>
                      {b.cheque_print_format && (
                        <div className="entity-sub" dir="ltr">{b.cheque_print_format}</div>
                      )}
                    </td>
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
 * دفترِ تسویه‌های کارت‌خوان.
 *
 * **پیش از مهاجرتِ ۰۱۰۹ این فهرست از روی `settled_at`ِ رسیدها بازسازی می‌شد** و
 * کامنتش می‌گفت «تسویه چیزی جز این رسیدها نیست، جدولِ موازی یعنی دو حقیقت». آن
 * استدلال یک چیز را نمی‌دید: دو تسویه‌ی متفاوت در یک روز از یک پایانه در آن
 * فهرست **یک ردیف** می‌شدند، و هیچ‌کدام شماره و حسابِ مقصد و برشِ تاریخی نداشتند.
 *
 * حالا تسویه سندِ خودش است. این فهرست همان سند را می‌خواند، پس هنوز دو حقیقت
 * نیست — یک حقیقت است که تا امروز جایی برای نشستن نداشت.
 */
export function PosSettlementListPage({ token }: { token: string }) {
  const [reloadKey, setReloadKey] = useState(0)
  const [openId, setOpenId] = useState<string | null>(null)
  const [msg, setMsg] = useState<Msg>(null)

  const list = useAsync(() => fetchPosSettlements(token), [token, reloadKey])
  //: رسیدهای منبعِ ردیفِ بازشده — §۱۱، جهتِ «این تسویه از کجا آمد».
  const detail = useAsync(
    async () => (openId ? fetchPosSettlement(token, openId) : null),
    [token, openId, reloadKey],
  )

  const rows = list.data ?? []
  const pg = usePagination(rows, 15)
  const live = rows.filter((r) => !r.voided_at)
  const totalNet = live.reduce((s, r) => s + Number(r.net_amount), 0)
  const totalFee = live.reduce((s, r) => s + Number(r.fee_amount), 0)

  async function onVoid(id: string, number: number) {
    const reason = window.prompt(`دلیلِ ابطالِ تسویه‌ی شماره ${number}؟`)
    if (!reason || !reason.trim()) return
    setMsg(null)
    try {
      await voidPosSettlement(token, id, reason.trim())
      setMsg({
        text: `تسویه‌ی ${faInt(number)} با سندِ معکوس باطل شد؛ رسیدهایش دوباره در صفِ تسویه‌اند.`,
        kind: 'ok',
      })
      setReloadKey((k) => k + 1)
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    }
  }

  return (
    <OpsPage
      icon={CreditCard}
      title="تسویه‌های کارتخوان"
      description="واریزهای شرکتِ پرداخت — هر ردیف یک سندِ تسویه با شماره‌ی خودش."
      head={
        <div className="cc-head">
          <div className="cc-summary">
            <Metric icon={<CreditCard size={14} />} label="تسویه‌ها" value={faInt(live.length)} />
            <Metric icon={<Wallet size={14} />} label="جمعِ خالصِ واریز" value={fa(totalNet)} tone="in" />
            <Metric icon={<ScrollText size={14} />} label="جمعِ کارمزد" value={fa(totalFee)} tone="plain" />
          </div>
        </div>
      }
    >
      <Note msg={msg} />

      <SectionCard icon={CreditCard} title="تسویه‌ها" description={`${faInt(rows.length)} ردیف`}>
        <AsyncBlock
          loading={list.loading}
          error={list.error}
          empty={rows.length === 0}
          emptyText="هنوز تسویه‌ای ثبت نشده. از عملیاتِ «تسویه کارت خوان» شروع کنید."
        >
          <div className="table-scroll">
            <table className="cards-on-mobile acc-table">
              <thead>
                <tr>
                  <th>شماره</th>
                  <th>تاریخِ تسویه</th>
                  <th>تسویه تا</th>
                  <th>پایانه</th>
                  <th>حسابِ بانکی</th>
                  <th>رسید</th>
                  <th>ناخالص</th>
                  <th>کارمزد</th>
                  <th>خالص</th>
                  <th className="card-actions"></th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.id} className={r.voided_at ? 'muted-row' : undefined}>
                    <td className="card-title" data-label="شماره">
                      {faInt(r.number)}
                      {r.voided_at ? <div className="entity-sub">باطل‌شده — {r.void_reason}</div> : null}
                    </td>
                    <td data-label="تاریخِ تسویه">{formatJalali(r.settlement_date)}</td>
                    <td data-label="تسویه تا">{formatJalali(r.settle_through)}</td>
                    <td data-label="پایانه">
                      <span dir="ltr">{r.terminal_no || r.terminal_label || '—'}</span>
                    </td>
                    <td data-label="حسابِ بانکی">
                      {r.bank_account_name}
                      {r.bank_account_name2 ? (
                        <div className="entity-sub">{r.bank_account_name2}</div>
                      ) : null}
                    </td>
                    <td className="num" data-label="رسید">{faInt(r.receipt_count)}</td>
                    <td className="num" data-label="ناخالص">{fa(r.gross_amount)}</td>
                    <td className="num" data-label="کارمزد">{fa(r.fee_amount)}</td>
                    <td className="num" data-label="خالص">{fa(r.net_amount)}</td>
                    <td className="card-actions">
                      <button type="button" onClick={() => setOpenId(openId === r.id ? null : r.id)}>
                        {openId === r.id ? 'بستنِ رسیدها' : 'رسیدها'}
                      </button>
                      {r.voided_at ? null : (
                        <button type="button" onClick={() => void onVoid(r.id, r.number)}>
                          ابطال
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        </AsyncBlock>
      </SectionCard>

      {openId ? (
        <SectionCard
          icon={ScrollText}
          title={`رسیدهای تسویه‌ی ${faInt(detail.data?.number ?? 0)}`}
          description="مبلغِ تسویه دقیقاً جمعِ همین‌هاست."
        >
          <AsyncBlock
            loading={detail.loading}
            error={detail.error}
            empty={!detail.data || detail.data.receipts.length === 0}
            emptyText="رسیدی به این تسویه وصل نیست."
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
                  {(detail.data?.receipts ?? []).map((r) => (
                    <tr key={r.id}>
                      <td className="card-title" data-label="تاریخ">{formatJalali(r.transaction_date)}</td>
                      <td data-label="طرفِ مقابل">
                        {r.contact_name}
                        {r.contact_name2 ? <div className="entity-sub">{r.contact_name2}</div> : null}
                      </td>
                      <td data-label="مرجع / پیگیری">
                        <span dir="ltr">{r.reference_no || r.trace_no || '—'}</span>
                      </td>
                      <td data-label="کارت"><span dir="ltr">{r.card_mask || '—'}</span></td>
                      <td className="num" data-label="مبلغ">{fa(r.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </AsyncBlock>
        </SectionCard>
      ) : null}
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
