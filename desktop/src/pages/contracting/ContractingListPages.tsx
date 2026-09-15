import { useEffect, useMemo, useState } from 'react'
import { FileSignature, BarChart3, ListChecks } from 'lucide-react'
import { fetchContracts, type ContractRecord, type ContractStatus } from '../../api'
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
