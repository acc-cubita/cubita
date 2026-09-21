/**
 * گزارش‌های خطای کلاینت.
 *
 * تا امروز این اندپوینت **هیچ صفحه‌ای نداشت**: داده جمع می‌شد و فقط با کوئریِ
 * دستی خوانده می‌شد. stack trace داده‌ی عملیاتیِ ماست، پس پشتِ هویتِ ستاد.
 */
import { useState } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

import { fetchClientErrors } from '../api'
import { formatJalali, toFaDigits } from '../lib/jalali'
import { AsyncBlock, Card, Chip, PageHeader, TableScroll, faInt, useAsync } from '../ui/kit'

export default function ClientErrorsPage({
  token,
  onUnauthorized,
}: {
  token: string
  onUnauthorized: (e: unknown) => void
}) {
  const [onlyFatal, setOnlyFatal] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const { data, loading, error, reload } = useAsync(
    () => fetchClientErrors(token, onlyFatal).catch((e) => (onUnauthorized(e), Promise.reject(e))),
    [token, onlyFatal],
  )

  const rows = data ?? []

  return (
    <>
      <PageHeader
        icon={AlertTriangle}
        title="گزارش خطاها"
        description="خطاهایی که اپِ مشتری (وب، دسکتاپ، موبایل) خودش گزارش کرده."
        actions={
          <button type="button" className="ad-btn" onClick={reload}>
            <RefreshCw size={15} /> تازه‌سازی
          </button>
        }
      />

      <Card>
        <div className="ad-toolbar">
          <label className="ad-check">
            <input
              type="checkbox"
              checked={onlyFatal}
              onChange={(e) => setOnlyFatal(e.target.checked)}
            />
            فقط خطاهای مرگ‌بار
          </label>
          <span className="ad-count">{faInt(rows.length)} گزارش</span>
        </div>

        <AsyncBlock
          loading={loading}
          error={error}
          empty={rows.length === 0}
          emptyText="گزارشی ثبت نشده — که خبرِ خوبی است."
        >
          <TableScroll>
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>خطا</th>
                  <th>صفحه</th>
                  <th>نسخه</th>
                  <th>سکو</th>
                  <th>زمان</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="card-title" data-label="خطا">
                      {r.fatal ? <Chip text="مرگ‌بار" tone="bad" /> : null} {r.name}
                      <span className="ad-sub">{r.message}</span>
                    </td>
                    <td data-label="صفحه">{r.screen ?? '—'}</td>
                    <td data-label="نسخه" dir="ltr">
                      {r.app_version ? toFaDigits(r.app_version) : '—'}
                    </td>
                    <td data-label="سکو" dir="ltr">
                      {r.platform ?? '—'}
                    </td>
                    <td data-label="زمان">{formatJalali(r.occurred_at)}</td>
                    <td className="card-actions">
                      {r.stack ? (
                        <button
                          type="button"
                          className="ad-btn small"
                          onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                        >
                          {expanded === r.id ? 'بستن' : 'جزئیات'}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>

          {expanded ? (
            <pre className="ad-stack" dir="ltr">
              {rows.find((r) => r.id === expanded)?.stack}
            </pre>
          ) : null}
        </AsyncBlock>
      </Card>
    </>
  )
}
