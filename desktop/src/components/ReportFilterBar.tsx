import { useMemo } from 'react'
import { fetchAnalytics, fetchCostCenters, type ReportFilters } from '../api'
import { SOURCE_LABELS, useAsync } from '../pages/accounting/kit'
import { SearchSelect } from '../components/SearchSelect'

/**
 * فیلترهای مشترکِ گزارش‌های حسابداری — **یک نوار برای هر سه خانواده**.
 *
 * تراز و مرور حساب و دفتر باید با یک فیلتر یک عدد بدهند (§۲۶). سمتِ سرور این با
 * `ReportFilters`ِ مشترک تضمین شده؛ این‌جا هم یک نوار می‌ماند نه سه تا، وگرنه
 * همان واگرایی از سمتِ رابط برمی‌گردد.
 *
 * تاریخ این‌جا نیست: `RangeBar` جای خودش را دارد و در هر سه صفحه از قبل هست.
 */
export function ReportFilterBar({
  token,
  filters,
  onChange,
  showAnalytic = true,
}: {
  token: string
  filters: ReportFilters
  onChange: (next: ReportFilters) => void
  showAnalytic?: boolean
}) {
  const centers = useAsync(() => fetchCostCenters(token), [token])
  const analytics = useAsync(() => fetchAnalytics(token), [token])
  const set = (patch: Partial<ReportFilters>) => onChange({ ...filters, ...patch })

  //: فقط منشأهایی که واقعاً در دفتر دیده می‌شوند — فهرستِ کاملِ برچسب‌ها بلند است
  //: و بیشترش برای این صفحه بی‌معنی.
  const sources = useMemo(
    () => Object.entries(SOURCE_LABELS).sort((a, b) => a[1].localeCompare(b[1])),
    [],
  )

  return (
    <>
      <label className="acc-inline-field">
        وضعیت سند
        <SearchSelect
          value={filters.status ?? ''}
          onChange={(e) => set({ status: (e.target.value || undefined) as ReportFilters['status'] })}
        >
          <option value="">همه</option>
          <option value="permanent">فقط دائم</option>
          <option value="temporary">فقط موقت</option>
        </SearchSelect>
      </label>

      <label className="acc-inline-field">
        منشأ سند
        <SearchSelect
          value={filters.sourceType ?? ''}
          onChange={(e) => set({ sourceType: e.target.value || undefined })}
        >
          <option value="">همه</option>
          {sources.map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </SearchSelect>
      </label>

      <label className="acc-inline-field">
        مرکز هزینه
        <SearchSelect
          value={filters.costCenterId ?? ''}
          onChange={(e) => set({ costCenterId: e.target.value || undefined })}
        >
          <option value="">کلِ شرکت</option>
          {(centers.data ?? []).map((c: { id: string; name: string }) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </SearchSelect>
      </label>

      {showAnalytic && (
        <label className="acc-inline-field">
          تفصیلی
          <SearchSelect
            value={filters.analyticId ?? ''}
            onChange={(e) => set({ analyticId: e.target.value || undefined })}
          >
            <option value="">همه</option>
            {(analytics.data ?? []).map((a: { id: string; code: string; name: string }) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </SearchSelect>
        </label>
      )}

      <label className="acc-inline-field">
        از شماره سند
        <input
          type="number"
          dir="ltr"
          value={filters.entryFrom ?? ''}
          onChange={(e) => set({ entryFrom: e.target.value ? Number(e.target.value) : undefined })}
        />
      </label>

      <label className="acc-inline-field">
        تا شماره سند
        <input
          type="number"
          dir="ltr"
          value={filters.entryTo ?? ''}
          onChange={(e) => set({ entryTo: e.target.value ? Number(e.target.value) : undefined })}
        />
      </label>

      <label className="cal-check-inline">
        <input
          type="checkbox"
          checked={filters.includeSystemEntries !== false}
          onChange={(e) => set({ includeSystemEntries: e.target.checked ? undefined : false })}
        />
        اسنادِ افتتاحیه و اختتامیه
        <span className="field-hint">
          خاموش کنید تا فقط گردشِ عملیاتیِ دوره دیده شود.
        </span>
      </label>
    </>
  )
}
