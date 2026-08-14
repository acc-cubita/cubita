import { faCompact } from '../lib/format'

export interface RankRow {
  id: string
  label: string
  value: number
  sub?: string
}

// میله‌ی افقیِ رتبه‌ای — کارِ داده «بزرگی/رتبه» است، پس تک‌سری و تک‌رنگ (بدون لجند؛
// عنوانِ بخش خودش سری را نام می‌برد). عدد به‌صورت متن کنارِ میله می‌آید تا هویت هرگز
// فقط با رنگ نباشد. HTML ساده به‌جای SVG: هم واکنش‌گرا و هم دسترس‌پذیر.
export function RankBars({ rows, tone = 'var(--series-1)' }: { rows: RankRow[]; tone?: string }) {
  if (rows.length === 0) return <p className="hint">داده‌ای برای نمایش نیست.</p>
  const max = Math.max(...rows.map((r) => r.value), 1)
  return (
    <div className="rank-bars">
      {rows.map((r) => (
        <div key={r.id} className="rank-row">
          <div className="rank-head">
            <span className="rank-label" title={r.label}>{r.label}</span>
            <span className="rank-value">{faCompact(r.value)}</span>
          </div>
          <div className="rank-track">
            <div
              className="rank-fill"
              style={{ width: `${Math.max(2, (r.value / max) * 100)}%`, background: tone }}
            />
          </div>
          {r.sub && <span className="rank-sub">{r.sub}</span>}
        </div>
      ))}
    </div>
  )
}
