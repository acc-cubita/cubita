import { useState } from 'react'
import { JALALI_MONTH_NAMES, toFaDigits } from '../lib/jalali'
import { faCompact, faFull } from '../lib/format'
import type { DashboardMonth } from '../api'

// میله‌ی گروهیِ فروش/خرید ماهانه — کارِ داده «تغییر در زمان» است. دو سری با لجندِ
// همیشگی و رنگِ ثابت (فروش=series-1، خرید=series-2). متن‌ها با توکنِ جوهر، نه رنگِ
// سری. راهنمای فاصله روی هر ماه؛ گریدلاین‌ها پس‌زمینه‌ای.
const WIDTH = 680
const HEIGHT = 240
const PAD_TOP = 14
const PAD_BOTTOM = 34
const PAD_LEFT = 6
const PAD_RIGHT = 44

const SERIES = [
  { key: 'sales' as const, label: 'فروش', color: 'var(--series-1)' },
  { key: 'purchases' as const, label: 'خرید', color: 'var(--series-2)' },
]

export function MonthlyBarsChart({ monthly }: { monthly: DashboardMonth[] }) {
  const [hover, setHover] = useState<number | null>(null)

  const values = monthly.flatMap((m) => [Number(m.sales), Number(m.purchases)])
  const max = Math.max(1, ...values)

  const plotW = WIDTH - PAD_LEFT - PAD_RIGHT
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM
  const baseY = PAD_TOP + plotH

  const groupW = plotW / Math.max(1, monthly.length)
  const barW = Math.min(18, (groupW * 0.64) / 2)
  const yAt = (v: number) => baseY - (v / max) * plotH

  const gridLines = 4
  const gridValues = Array.from({ length: gridLines + 1 }, (_, i) => (max * i) / gridLines)

  if (monthly.every((m) => Number(m.sales) === 0 && Number(m.purchases) === 0)) {
    return <p className="hint">در بازه‌ی اخیر فروش یا خریدی ثبت نشده.</p>
  }

  return (
    <div className="bars-chart">
      <div className="trend-legend">
        {SERIES.map((s) => (
          <div key={s.key} className="trend-legend-item">
            <span className="trend-legend-dot" style={{ background: s.color }} />
            {s.label}
          </div>
        ))}
      </div>

      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="bars-chart-svg" preserveAspectRatio="xMidYMid meet">
        {gridValues.map((gv, i) => (
          <g key={i}>
            <line x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={yAt(gv)} y2={yAt(gv)} className="trend-gridline" />
            <text x={WIDTH - PAD_RIGHT + 4} y={yAt(gv) + 3} className="trend-axis-label" textAnchor="start">
              {faCompact(gv)}
            </text>
          </g>
        ))}

        {monthly.map((m, i) => {
          const groupCenter = PAD_LEFT + groupW * i + groupW / 2
          const active = hover === i
          return (
            <g key={i}>
              {SERIES.map((s, si) => {
                const v = Number(m[s.key])
                const h = baseY - yAt(v)
                // دو میله کنارِ هم با فاصله‌ی ۲ پیکسل؛ گوشه‌ی بالا گرد.
                const x = groupCenter + (si === 0 ? -barW - 1 : 1)
                return (
                  <rect
                    key={s.key}
                    x={x}
                    y={yAt(v)}
                    width={barW}
                    height={Math.max(0, h)}
                    rx={3}
                    fill={s.color}
                    opacity={hover === null || active ? 1 : 0.4}
                  />
                )
              })}
              <text x={groupCenter} y={HEIGHT - 12} textAnchor="middle" className="trend-axis-label">
                {JALALI_MONTH_NAMES[m.jm - 1].slice(0, 4)}
              </text>
              <rect
                x={PAD_LEFT + groupW * i}
                y={PAD_TOP}
                width={groupW}
                height={plotH}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              />
            </g>
          )
        })}
      </svg>

      {hover !== null && (
        <div className="trend-tooltip">
          <div className="trend-tooltip-date">
            {JALALI_MONTH_NAMES[monthly[hover].jm - 1]} {toFaDigits(monthly[hover].jy)}
          </div>
          {SERIES.map((s) => (
            <div key={s.key} className="trend-tooltip-row">
              <span className="trend-legend-dot" style={{ background: s.color }} />
              <span>{s.label}</span>
              <strong>{faFull(Number(monthly[hover][s.key]))}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
