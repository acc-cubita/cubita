import { useEffect, useMemo, useState } from 'react'
import { FileSignature, Plus } from 'lucide-react'
import {
  CONTRACT_TYPE_LABELS,
  fetchJobTitles,
  fetchSalaryContracts,
  fetchServiceLocations,
  type JobTitleRecord,
  type SalaryContractRecord,
  type ServiceLocationRecord,
} from '../../api'
import { EmptyState } from '../../components/EmptyState'
import { Pager, usePagination } from '../../components/Pager'
import { SectionCard } from '../../components/SectionCard'
import { ListToolbar, SearchField } from '../../components/form/FormKit'
import { formatJalali } from '../../lib/jalali'
import type { PageKey } from '../../lib/navModel'
import { AsyncBlock, OpsPage } from '../accounting/kit'
import { SearchSelect } from '../../components/SearchSelect'

/**
 * دفترِ قراردادهای حقوق — نظیرِ «قرارداد جدید».
 *
 * فرم رکورد می‌سازد، این‌جا رکوردها مرور می‌شوند. سه تاریخِ قرارداد هر سه ستون
 * دارند چون هر کدام معنای متفاوتی دارند و کاربر باید بتواند تشخیص دهد کدام قرارداد
 * هنوز معتبر است.
 *
 * چیدمان همان «قرارداد جدید» است: کارت با سایه‌ی نرم و نوارِ فیلترِ هم‌ارتفاعِ فرم‌ها.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')
const faAmount = (v: string | number) => (Number(v) === 0 ? '—' : Math.round(Number(v)).toLocaleString('fa-IR'))
const errText = (err: unknown) => (err instanceof Error ? err.message : 'خطای ناشناخته')

export function ContractListPage({
  token,
  onNavigate,
}: {
  token: string
  onNavigate?: (page: PageKey) => void
}) {
  const [rows, setRows] = useState<SalaryContractRecord[] | null>(null)
  const [locations, setLocations] = useState<ServiceLocationRecord[]>([])
  const [jobs, setJobs] = useState<JobTitleRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('')

  useEffect(() => {
    void fetchSalaryContracts(token)
      .then(setRows)
      .catch((err) => setError(errText(err)))
    void fetchServiceLocations(token).then(setLocations).catch(() => {})
    void fetchJobTitles(token).then(setJobs).catch(() => {})
  }, [token])

  const locationName = useMemo(() => new Map(locations.map((l) => [l.id, l.name])), [locations])
  const jobName = useMemo(() => new Map(jobs.map((j) => [j.id, j.name])), [jobs])

  const shown = useMemo(() => {
    const q = query.trim()
    return (rows ?? []).filter((r) => {
      if (typeFilter && r.contract_type !== typeFilter) return false
      if (!q) return true
      return [r.employee_name, r.number].some((v) => (v ?? '').includes(q))
    })
  }, [rows, query, typeFilter])

  const pg = usePagination(shown, 10, `${query}|${typeFilter}`)

  return (
    <OpsPage
      icon={FileSignature}
      title="قراردادها"
      description="همه‌ی قراردادهای استخدام و اصلاح، با تاریخ‌های صدور و اعتبار و مبلغِ حقوق پایه."
    >
      <div className="ef-form">
        <SectionCard
          icon={FileSignature}
          title={rows ? `${fa(shown.length)} قرارداد` : 'در حال بارگذاری…'}
          actions={
            onNavigate && (
              <button type="button" className="btn-primary" onClick={() => onNavigate('contractnew')}>
                <Plus size={14} /> قرارداد جدید
              </button>
            )
          }
        >
          <ListToolbar>
            <SearchField value={query} onChange={setQuery} placeholder="نام کارمند یا شماره…" />
            <SearchSelect aria-label="نوع قرارداد" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">همه‌ی انواع</option>
              {Object.entries(CONTRACT_TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </SearchSelect>
          </ListToolbar>
          <AsyncBlock
            loading={rows == null}
            error={error}
            empty={rows != null && shown.length === 0}
            emptyText={
              query || typeFilter
                ? 'چیزی پیدا نشد — فیلترها را تغییر دهید.'
                : 'هنوز قراردادی ثبت نشده — با «قرارداد جدید» اولی را بسازید.'
            }
          >
            {shown.length === 0 ? (
              <EmptyState
                icon={FileSignature}
                text={
                  query || typeFilter
                    ? 'چیزی پیدا نشد — فیلترها را تغییر دهید.'
                    : 'هنوز قراردادی ثبت نشده — با «قرارداد جدید» اولی را بسازید.'
                }
              />
            ) : (
              <div className="table-scroll">
                <table className="cards-on-mobile">
                  <thead>
                    <tr>
                      <th>کارمند</th>
                      <th>نوع</th>
                      <th>شماره</th>
                      <th>تاریخ صدور</th>
                      <th>تاریخ اعتبار</th>
                      <th>پایان خدمت</th>
                      <th>محل خدمت</th>
                      <th>شغل</th>
                      <th>حقوق پایه</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pg.pageItems.map((r) => (
                      <tr key={r.id}>
                        <td className="card-title" data-label="کارمند">{r.employee_name || '—'}</td>
                        <td data-label="نوع">
                          <span className="badge">{CONTRACT_TYPE_LABELS[r.contract_type] ?? r.contract_type}</span>
                        </td>
                        <td data-label="شماره">{r.number ? <span dir="ltr">{r.number}</span> : '—'}</td>
                        <td data-label="تاریخ صدور">{formatJalali(r.effective_from)}</td>
                        <td data-label="تاریخ اعتبار">{r.valid_until ? formatJalali(r.valid_until) : '—'}</td>
                        <td data-label="پایان خدمت">{r.service_end_date ? formatJalali(r.service_end_date) : '—'}</td>
                        <td data-label="محل خدمت">
                          {r.service_location_id ? locationName.get(r.service_location_id) ?? '—' : '—'}
                        </td>
                        <td data-label="شغل">{r.job_title_id ? jobName.get(r.job_title_id) ?? '—' : '—'}</td>
                        <td className="num" data-label="حقوق پایه">{faAmount(r.base_salary)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
              </div>
            )}
          </AsyncBlock>
        </SectionCard>
      </div>
    </OpsPage>
  )
}
