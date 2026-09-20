import { useEffect, useMemo, useState } from 'react'
import { HandCoins, Landmark, TrendingDown, TrendingUp, Wallet } from 'lucide-react'
import {
  fetchOwnerTransactions,
  fetchPartnerBalances,
  type OwnerTransactionRecord,
  type PartnerBalanceRecord,
} from '../../api'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import { CountBadge, FormField, ListToolbar } from '../../components/form/FormKit'
import { EmptyState } from '../../components/EmptyState'
import { StatCard } from '../../components/StatCard'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali } from '../../lib/jalali'
import { SearchSelect } from '../../components/SearchSelect'

const fa = (n: number) => Number(n || 0).toLocaleString('fa-IR')

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'خطای ناشناخته'
}

/** کدام نوع‌ها سرمایه را تکان می‌دهند و کدام جاری شرکا را.
 *
 *  همان تفکیکی که بک‌اند در `_POSTING` دارد. تکرارش این‌جا عمدی است و فقط برای
 *  **نمایش** است — هیچ سندی از روی این ساخته نمی‌شود. */
const CAPITAL_TYPES = new Set(['capital_contribution', 'capital_withdrawal'])
const INFLOW_TYPES = new Set(['capital_contribution', 'loan_to_entity', 'repayment_from_partner'])

function balanceText(value: string | number): string {
  const n = Number(value || 0)
  if (n === 0) return '—'
  return n > 0 ? `${fa(n)} طلبکار` : `${fa(Math.abs(n))} بدهکار`
}

/** دفترِ تراکنش‌های مالک و شریک.
 *
 *  صفحه‌ی نظیرِ «تراکنش شریک» (عملیات). آن‌جا ثبت می‌شود، این‌جا مرور — همان
 *  مرزی که قراردادِ صفحه‌های کوبیتا می‌گذارد. */
export function OwnerTransactionListPage({ token }: { token: string }) {
  const [rows, setRows] = useState<OwnerTransactionRecord[] | null>(null)
  const [balances, setBalances] = useState<PartnerBalanceRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [kind, setKind] = useState('')
  const [partner, setPartner] = useState('')

  useEffect(() => {
    void Promise.all([fetchOwnerTransactions(token), fetchPartnerBalances(token)])
      .then(([txns, bals]) => {
        setRows(txns)
        setBalances(bals)
      })
      .catch((err) => setError(errText(err)))
  }, [token])

  const visible = useMemo(() => {
    let out = rows ?? []
    if (kind) out = out.filter((r) => r.type === kind)
    if (partner) out = out.filter((r) => r.contact_id === partner)
    return out
  }, [rows, kind, partner])

  const totals = useMemo(() => {
    const live = visible.filter((r) => !r.voided_at)
    const sum = (pick: (r: OwnerTransactionRecord) => boolean) =>
      live.filter(pick).reduce((s, r) => s + Number(r.amount || 0), 0)
    return {
      count: visible.length,
      contributed: sum((r) => r.type === 'capital_contribution'),
      withdrawn: sum((r) => r.type === 'capital_withdrawal'),
      inflow: sum((r) => INFLOW_TYPES.has(r.type)),
    }
  }, [visible])

  const pg = usePagination(visible, 15)
  const types = useMemo(() => {
    const seen = new Map<string, string>()
    for (const r of rows ?? []) seen.set(r.type, r.type_label)
    return [...seen.entries()]
  }, [rows])

  return (
    <div className="page panels">
      <PageHeader
        icon={HandCoins}
        title="تراکنش‌های شریک"
        description="دفترِ آورده، برداشت، وام و بازپرداختِ مالکان — و ماندهٔ جاری هر شریک."
      />

      <div className="ef-form">
      <section className="kpi-row">
        <StatCard icon={<Landmark size={18} />} label="تعداد" value={fa(totals.count)} />
        <StatCard icon={<TrendingUp size={18} />} label="آورده‌ی سرمایه" value={fa(totals.contributed)} />
        <StatCard icon={<TrendingDown size={18} />} label="کاهشِ سرمایه" value={fa(totals.withdrawn)} />
        <StatCard icon={<Wallet size={18} />} label="ورودیِ نقد" value={fa(totals.inflow)} />
      </section>

      <SectionCard
        icon={Wallet}
        title="ماندهٔ جاری شرکا"
        tip="فقط وام و بازپرداخت. آورده‌ی سرمایه بدهیِ شرکت به شریک نمی‌سازد و این‌جا شمرده نمی‌شود."
        badge={balances.length > 0 ? <CountBadge accent>{fa(balances.length)} شریک</CountBadge> : undefined}
      >
        {balances.length === 0 ? (
          <EmptyState icon={Wallet} text="هنوز سهامداری ثبت نشده است. در پرونده‌ی طرف حساب گزینه‌ی «سهامدار» را فعال کنید." />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead>
                <tr><th>شریک</th><th>سهم</th><th>ماندهٔ جاری</th></tr>
              </thead>
              <tbody>
                {balances.map((b) => (
                  <tr key={b.contact_id}>
                    <td className="card-title" data-label="شریک">{b.contact_name}</td>
                    <td className="num" data-label="سهم">{fa(Number(b.share_percent))}٪</td>
                    <td className="num" data-label="ماندهٔ جاری">{balanceText(b.balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <SectionCard
        icon={HandCoins}
        title="دفترِ تراکنش‌ها"
        badge={rows ? <CountBadge accent>{fa(visible.length)} تراکنش</CountBadge> : undefined}
        description="همه‌ی تراکنش‌های شرکا؛ برای ثبتِ تازه به «تراکنش شریک» بروید."
      >
        <ListToolbar>
          <FormField label="نوع">
            {(id) => (
              <SearchSelect id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="">همه</option>
                {types.map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </SearchSelect>
            )}
          </FormField>
          <FormField label="شریک">
            {(id) => (
              <SearchSelect id={id} value={partner} onChange={(e) => setPartner(e.target.value)}>
                <option value="">همه</option>
                {balances.map((b) => (
                  <option key={b.contact_id} value={b.contact_id}>
                    {b.contact_name}
                  </option>
                ))}
              </SearchSelect>
            )}
          </FormField>
        </ListToolbar>

        {error ? (
          <p className="ef-message ef-message--warn ef-block-note">{error}</p>
        ) : rows === null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : visible.length === 0 ? (
          <EmptyState icon={HandCoins} text="تراکنشی با این شرایط پیدا نشد. از «تراکنش شریک» ثبت کنید." />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead>
                <tr>
                  <th>تاریخ</th><th>شریک</th><th>نوع</th><th>اثر</th>
                  <th>مبلغ</th><th>از/به</th><th>مدرک</th><th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {pg.pageItems.map((r) => (
                  <tr key={r.id}>
                    <td data-label="تاریخ">{formatJalali(r.transaction_date)}</td>
                    <td className="card-title" data-label="شریک">{r.contact_name}</td>
                    <td data-label="نوع">{r.type_label}</td>
                    <td data-label="اثر">
                      <span className={`status-badge ${CAPITAL_TYPES.has(r.type) ? 'tone-success' : 'tone-muted'}`}>
                        {CAPITAL_TYPES.has(r.type) ? 'سرمایه' : 'جاری شرکا'}
                      </span>
                    </td>
                    <td className="num" data-label="مبلغ">{fa(Number(r.amount))}</td>
                    <td data-label="از/به">{r.method === 'bank' ? 'بانک' : 'صندوق'}</td>
                    <td className="card-hide" data-label="مدرک">{r.evidence_ref || '—'}</td>
                    <td data-label="وضعیت">
                      {r.voided_at ? (
                        <span className="status-badge tone-danger" title={r.void_reason}>باطل</span>
                      ) : (
                        <span className="status-badge tone-success">ثبت‌شده</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}
      </SectionCard>
      </div>
    </div>
  )
}
