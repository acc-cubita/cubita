import { useMemo, useState } from 'react'

export interface TrendSeries {
  key: string
  label: string
  color: string
  points: { date: string; value: number }[]
}

const fa = (v: number) => Math.round(v).toLocaleString('fa-IR')
const faDate = (iso: string) => new Date(iso).toLocaleDateString('fa-IR', { month: 'short', day: 'numeric' })

const WIDTH = 640
const HEIGHT = 220
const PAD_TOP = 16
const PAD_BOTTOM = 28
const PAD_RIGHT = 8
const PAD_LEFT = 8

export function TrendChart({ series }: { series: TrendSeries[] }) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const { dates, aligned, minValue, maxValue } = useMemo(() => {
    const dateSet = new Set<string>()
    for (const s of series) for (const p of s.points) dateSet.add(p.date)
    const dates = Array.from(dateSet).sort()

    const aligned = series.map((s) => {
      const byDate = new Map(s.points.map((p) => [p.date, p.value]))
      let last = s.points[0]?.value ?? 0
      return dates.map((d) => {
        if (byDate.has(d)) last = byDate.get(d) as number
        return last
      })
    })

    const allValues = aligned.flat()
    const min = Math.min(0, ...allValues)
    const max = Math.max(0, ...allValues)
    const pad = (max - min) * 0.1 || 1
    return { dates, aligned, minValue: min - pad, maxValue: max + pad }
  }, [series])

  if (dates.length === 0) {
    return <p className="hint">هنوز داده‌ای برای نمودار ثبت نشده.</p>
  }

  const plotW = WIDTH - PAD_LEFT - PAD_RIGHT
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM

  const xAt = (i: number) => PAD_LEFT + (dates.length === 1 ? plotW / 2 : (i / (dates.length - 1)) * plotW)
  const yAt = (v: number) => PAD_TOP + plotH - ((v - minValue) / (maxValue - minValue)) * plotH

  const gridLines = 4
  const gridValues = Array.from({ length: gridLines + 1 }, (_, i) => minValue + ((maxValue - minValue) * i) / gridLines)

  function pathFor(values: number[]) {
    return values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i)} ${yAt(v)}`).join(' ')
  }

  function areaFor(values: number[]) {
    const line = values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i)} ${yAt(v)}`).join(' ')
    return `${line} L ${xAt(values.length - 1)} ${yAt(minValue)} L ${xAt(0)} ${yAt(minValue)} Z`
  }

  function handleMove(e: React.MouseEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const ratio = Math.min(1, Math.max(0, (x - PAD_LEFT) / plotW))
    const idx = Math.round(ratio * (dates.length - 1))
    setHoverIndex(idx)
  }

  return (
    <div className="trend-chart">
      <div className="trend-legend">
        {series.map((s) => (
          <div key={s.key} className="trend-legend-item">
            <span className="trend-legend-dot" style={{ background: s.color }} />
            {s.label}
          </div>
        ))}
      </div>

      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="trend-chart-svg" preserveAspectRatio="none">
        {gridValues.map((gv, i) => (
          <g key={i}>
            <line x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={yAt(gv)} y2={yAt(gv)} className="trend-gridline" />
            <text x={WIDTH - PAD_RIGHT} y={yAt(gv) - 3} className="trend-axis-label" textAnchor="end">
              {fa(gv)}
            </text>
          </g>
        ))}

        {series.map((s, si) => (
          <path key={`area-${s.key}`} d={areaFor(aligned[si])} fill={s.color} opacity={0.1} stroke="none" />
        ))}
        {series.map((s, si) => (
          <path key={`line-${s.key}`} d={pathFor(aligned[si])} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        ))}

        {series.map((s, si) => {
          const lastIdx = aligned[si].length - 1
          return (
            <text
              key={`end-${s.key}`}
              x={xAt(lastIdx) - 6}
              y={yAt(aligned[si][lastIdx]) - 8}
              textAnchor="end"
              className="trend-end-label"
            >
              {fa(aligned[si][lastIdx])}
            </text>
          )
        })}

        {hoverIndex !== null && (
          <g>
            <line
              x1={xAt(hoverIndex)}
              x2={xAt(hoverIndex)}
              y1={PAD_TOP}
              y2={PAD_TOP + plotH}
              className="trend-crosshair"
            />
            {series.map((s, si) => (
              <circle
                key={`dot-${s.key}`}
                cx={xAt(hoverIndex)}
                cy={yAt(aligned[si][hoverIndex])}
                r={4}
                fill={s.color}
                stroke="var(--surface)"
                strokeWidth={2}
              />
            ))}
          </g>
        )}

        <rect
          x={PAD_LEFT}
          y={PAD_TOP}
          width={plotW}
          height={plotH}
          fill="transparent"
          onMouseMove={handleMove}
          onMouseLeave={() => setHoverIndex(null)}
        />
      </svg>

      {hoverIndex !== null && (
        <div className="trend-tooltip">
          <div className="trend-tooltip-date">{faDate(dates[hoverIndex])}</div>
          {series.map((s, si) => (
            <div key={s.key} className="trend-tooltip-row">
              <span className="trend-legend-dot" style={{ background: s.color }} />
              <span>{s.label}</span>
              <strong>{fa(aligned[si][hoverIndex])}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
