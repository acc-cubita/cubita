import { useEffect, useMemo, useState } from 'react'
import { BarChart3, FilePenLine, FileSignature, ListChecks, Receipt } from 'lucide-react'
import {
  fetchContractAmendments,
  fetchContracts,
  fetchContractStatements,
  type ContractAmendmentRecord,
  type ContractRecord,
  type ContractStatementRecord,
  type ContractStatus,
} from '../../api'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import { EmptyState } from '../../components/EmptyState'
import { StatCard } from '../../components/StatCard'
import { Pager, usePagination } from '../../components/Pager'
import { formatJalali } from '../../lib/jalali'

const fa = (n: number) => Number(n || 0).toLocaleString('fa-IR')
const money = (v: string | number) => Number(v || 0).toLocaleString('fa-IR')

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'خطای ناشناخته'
}

const STATUS_LABELS: Record<ContractStatus, string> = {
  draft: 'پیش‌نویس',
  active: 'جاری',
  suspended: 'معلق',
  terminated: 'فسخ‌شده',
  completed: 'تکمیل‌شده',
  cancelled: 'لغوشده',
}

const STATUS_TONE: Record<ContractStatus, string> = {
  draft: '',
  active: 'success',
  suspended: 'warn',
  terminated: 'danger',
  completed: 'success',
  cancelled: 'danger',
}

export function ContractingListPage({ token }: { token: string }) {
  const [contracts, setContracts] = useState<ContractRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void fetchContracts(token)
      .then(setContracts)
      .catch((err) => setError(errText(err)))
  }, [token])

  const pg = usePagination(contracts ?? [], 10)
  const totals = useMemo(() => {
    const rows = contracts ?? []
    return {
      count: rows.length,
      active: rows.filter((c) => c.status === 'active').length,
      amount: rows.reduce((sum, c) => sum + Number(c.total_amount || 0), 0),
    }
  }, [contracts])

  return (
    <div className="page panels">
      <PageHeader
        icon={FileSignature}
        title="پیمان‌ها"
        description="فهرستِ پیمان‌های ثبت‌شده. برای ثبت و تغییرِ وضعیت به «پیمانکاری ← پیمان» بروید."
      />
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard label="کلِ پیمان‌ها" value={fa(totals.count)} icon={<FileSignature size={16} />} />
        <StatCard label="جاری" value={fa(totals.active)} icon={<ListChecks size={16} />} />
        <StatCard label="مبلغِ کل" value={money(totals.amount)} hint="ریال" icon={<BarChart3 size={16} />} />
      </div>

      <SectionCard icon={FileSignature} title="پیمان‌ها">
        {contracts == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : contracts.length === 0 ? (
          <EmptyState icon={FileSignature} text="هنوز پیمانی ثبت نشده — از «پیمانکاری ← پیمان» اولین پیمان را بسازید." />
        ) : (
          <>
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>کارفرما</th>
                    <th>موضوع</th>
                    <th>مبلغ</th>
                    <th>شروع</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((c) => (
                    <tr key={c.id}>
                      <td className="card-title" data-label="شماره">{fa(c.number)}</td>
                      <td data-label="کارفرما">{c.contact_name}</td>
                      <td className="card-wide" data-label="موضوع">{c.subject || '—'}</td>
                      <td className="num" data-label="مبلغ">{money(c.total_amount)}</td>
                      <td data-label="شروع">{formatJalali(c.start_date)}</td>
                      <td data-label="وضعیت">
                        <span className={`badge ${STATUS_TONE[c.status]}`}>{STATUS_LABELS[c.status]}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </>
        )}
      </SectionCard>
    </div>
  )
}

export function ContractAmendmentListPage({ token }: { token: string }) {
  const [amendments, setAmendments] = useState<ContractAmendmentRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void fetchContractAmendments(token)
      .then(setAmendments)
      .catch((err) => setError(errText(err)))
  }, [token])

  const pg = usePagination(amendments ?? [], 10)
  const totals = useMemo(() => {
    const rows = amendments ?? []
    return {
      count: rows.length,
      netDelta: rows.reduce((sum, a) => sum + Number(a.amount_delta || 0), 0),
    }
  }, [amendments])

  return (
    <div className="page panels">
      <PageHeader
        icon={FilePenLine}
        title="متمم‌های پیمان"
        description="فهرستِ متمم‌های ثبت‌شده روی پیمان‌ها. برای ثبتِ متممِ تازه به «پیمانکاری ← متمم پیمان» بروید."
      />
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard label="کلِ متمم‌ها" value={fa(totals.count)} icon={<FilePenLine size={16} />} />
        <StatCard label="خالصِ تغییرِ مبلغ" value={money(totals.netDelta)} hint="ریال" icon={<BarChart3 size={16} />} />
      </div>

      <SectionCard icon={FilePenLine} title="متمم‌ها">
        {amendments == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : amendments.length === 0 ? (
          <EmptyState icon={FilePenLine} text="هنوز متممی ثبت نشده — از «پیمانکاری ← متمم پیمان» اولین متمم را بسازید." />
        ) : (
          <>
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>پیمان</th>
                    <th>موضوع</th>
                    <th>تغییرِ مبلغ</th>
                    <th>تاریخ</th>
                    <th>پایانِ تازه</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((a) => (
                    <tr key={a.id}>
                      <td className="card-title" data-label="شماره">{fa(a.number)}</td>
                      <td data-label="پیمان">{a.contract_number != null ? fa(a.contract_number) : '—'}</td>
                      <td className="card-wide" data-label="موضوع">{a.description || '—'}</td>
                      <td className="num" data-label="تغییرِ مبلغ">{money(a.amount_delta)}</td>
                      <td data-label="تاریخ">{formatJalali(a.date)}</td>
                      <td data-label="پایانِ تازه">{a.new_end_date ? formatJalali(a.new_end_date) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </>
        )}
      </SectionCard>
    </div>
  )
}

export function ContractStatementListPage({ token }: { token: string }) {
  const [statements, setStatements] = useState<ContractStatementRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void fetchContractStatements(token)
      .then(setStatements)
      .catch((err) => setError(errText(err)))
  }, [token])

  const pg = usePagination(statements ?? [], 10)
  const totals = useMemo(() => {
    const rows = statements ?? []
    return {
      count: rows.length,
      gross: rows.reduce((sum, s) => sum + Number(s.gross_amount || 0), 0),
      net: rows.reduce((sum, s) => sum + Number(s.net_amount || 0), 0),
    }
  }, [statements])

  return (
    <div className="page panels">
      <PageHeader
        icon={Receipt}
        title="صورت وضعیت‌های دریافتی"
        description="فهرستِ صورت‌وضعیت‌های ثبت‌شده. برای ثبتِ تازه به «پیمانکاری ← صورت وضعیت دریافتی» بروید."
      />
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        <StatCard label="کلِ صورت‌وضعیت‌ها" value={fa(totals.count)} icon={<Receipt size={16} />} />
        <StatCard label="جمعِ ناخالص" value={money(totals.gross)} hint="ریال" icon={<BarChart3 size={16} />} />
        <StatCard label="جمعِ خالصِ قابلِ‌پرداخت" value={money(totals.net)} hint="ریال" icon={<BarChart3 size={16} />} />
      </div>

      <SectionCard icon={Receipt} title="صورت‌وضعیت‌ها">
        {statements == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : statements.length === 0 ? (
          <EmptyState icon={Receipt} text="هنوز صورت‌وضعیتی ثبت نشده — از «پیمانکاری ← صورت وضعیت دریافتی» اولین را بسازید." />
        ) : (
          <>
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>شماره</th>
                    <th>پیمان</th>
                    <th>تاریخ</th>
                    <th>ناخالص</th>
                    <th>کسرِ سپرده</th>
                    <th>کسرِ پیش‌پرداخت</th>
                    <th>سایرِ کسورات</th>
                    <th>خالص</th>
                  </tr>
                </thead>
                <tbody>
                  {pg.pageItems.map((s) => (
                    <tr key={s.id}>
                      <td className="card-title" data-label="شماره">{fa(s.number)}</td>
                      <td data-label="پیمان">{s.contract_number != null ? fa(s.contract_number) : '—'}</td>
                      <td data-label="تاریخ">{formatJalali(s.date)}</td>
                      <td className="num" data-label="ناخالص">{money(s.gross_amount)}</td>
                      <td className="num" data-label="کسرِ سپرده">{money(s.retention_amount)}</td>
                      <td className="num" data-label="کسرِ پیش‌پرداخت">{money(s.advance_deduction)}</td>
                      <td className="num" data-label="سایرِ کسورات">{money(s.other_deductions)}</td>
                      <td className="num" data-label="خالص">{money(s.net_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </>
        )}
      </SectionCard>
    </div>
  )
}
