import { useMemo, type ReactNode } from 'react'
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
  variant = 'inline',
}: {
  token: string
  filters: ReportFilters
  onChange: (next: ReportFilters) => void
  showAnalytic?: boolean
  /** `inline`: برچسب‌کادرهای نوارِ `RangeBar` (پیش‌فرض). `cells`: خانه‌های سربرگِ اکسلی (`jh-field`) برای درونِ
   *  `.jh-bar` — برچسب سرستونِ خاکستری، کادرِ بی‌قاب؛ «از/تا شماره» یک خانه و افتتاحیه/اختتامیه یک کلید. */
  variant?: 'inline' | 'cells'
}) {
  const centers = useAsync(() => fetchCostCenters(token), [token])
  const analytics = useAsync(() => fetchAnalytics(token), [token])
  const set = (patch: Partial<ReportFilters>) => onChange({ ...filters, ...patch })
  const cells = variant === 'cells'

  //: فقط منشأهایی که واقعاً در دفتر دیده می‌شوند — فهرستِ کاملِ برچسب‌ها بلند است
  //: و بیشترش برای این صفحه بی‌معنی.
  const sources = useMemo(
    () => Object.entries(SOURCE_LABELS).sort((a, b) => a[1].localeCompare(b[1])),
    [],
  )

  /** یک فیلتر: برچسب‌کادرِ نوار، یا خانه‌ی سربرگ. `<label>` در هر دو، تا کلیک روی برچسب کادر را بگیرد. */
  const field = (label: string, control: ReactNode) =>
    cells ? (
      <label className="jh-field">
        <span className="jh-label">{label}</span>
        {control}
      </label>
    ) : (
      <label className="acc-inline-field">
        {label}
        {control}
      </label>
    )
  const withSystem = filters.includeSystemEntries !== false
  const entryInput = (key: 'entryFrom' | 'entryTo', label: string) => (
    <input
      type="number"
      dir="ltr"
      aria-label={label}
      //: «تا»ی میانِ دو کادر برچسبِ دومی است؛ جای‌نمای «تا» در کادرِ دوم «تا تا» خوانده می‌شد.
      placeholder={cells && key === 'entryFrom' ? 'از' : undefined}
      value={filters[key] ?? ''}
      onChange={(e) => set({ [key]: e.target.value ? Number(e.target.value) : undefined })}
    />
  )

  return (
    <>
      {field(
        'وضعیت سند',
        <SearchSelect
          aria-label="وضعیت سند"
          value={filters.status ?? ''}
          onChange={(e) => set({ status: (e.target.value || undefined) as ReportFilters['status'] })}
        >
          <option value="">همه</option>
          <option value="permanent">فقط دائم</option>
          <option value="temporary">فقط موقت</option>
        </SearchSelect>,
      )}

      {field(
        'منشأ سند',
        <SearchSelect
          aria-label="منشأ سند"
          value={filters.sourceType ?? ''}
          onChange={(e) => set({ sourceType: e.target.value || undefined })}
        >
          <option value="">همه</option>
          {sources.map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </SearchSelect>,
      )}

      {field(
        'مرکز هزینه',
        <SearchSelect
          aria-label="مرکز هزینه"
          value={filters.costCenterId ?? ''}
          onChange={(e) => set({ costCenterId: e.target.value || undefined })}
        >
          <option value="">کلِ شرکت</option>
          {(centers.data ?? []).map((c: { id: string; name: string }) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </SearchSelect>,
      )}

      {showAnalytic &&
        field(
          'تفصیلی',
          <SearchSelect
            aria-label="تفصیلی"
            value={filters.analyticId ?? ''}
            onChange={(e) => set({ analyticId: e.target.value || undefined })}
          >
            <option value="">همه</option>
            {(analytics.data ?? []).map((a: { id: string; code: string; name: string }) => (
              <option key={a.id} value={a.id}>
                {a.code} — {a.name}
              </option>
            ))}
          </SearchSelect>,
        )}

      {cells ? (
        <div className="jh-field rh-docs">
          <span className="jh-label">شماره سند</span>
          <div className="rh-pair">
            {entryInput('entryFrom', 'از شماره سند')}
            <span aria-hidden="true">تا</span>
            {entryInput('entryTo', 'تا شماره سند')}
          </div>
        </div>
      ) : (
        <>
          {field('از شماره سند', entryInput('entryFrom', 'از شماره سند'))}
          {field('تا شماره سند', entryInput('entryTo', 'تا شماره سند'))}
        </>
      )}

      {cells ? (
        <div className="jh-field rh-sys">
          <span className="jh-label" title="خاموش کنید تا فقط گردشِ عملیاتیِ دوره دیده شود.">
            افتتاحیه و اختتامیه
          </span>
          <button
            type="button"
            className={`xl-toggle${withSystem ? ' is-on' : ''}`}
            aria-pressed={withSystem}
            aria-label="اسنادِ افتتاحیه و اختتامیه"
            title="خاموش کنید تا فقط گردشِ عملیاتیِ دوره دیده شود."
            onClick={() => set({ includeSystemEntries: withSystem ? false : undefined })}
          >
            {withSystem ? 'شامل' : 'بدون'}
          </button>
        </div>
      ) : (
        <label className="cal-check-inline">
          <input
            type="checkbox"
            checked={withSystem}
            onChange={(e) => set({ includeSystemEntries: e.target.checked ? undefined : false })}
          />
          اسنادِ افتتاحیه و اختتامیه
          <span className="field-hint">
            خاموش کنید تا فقط گردشِ عملیاتیِ دوره دیده شود.
          </span>
        </label>
      )}
    </>
  )
}
