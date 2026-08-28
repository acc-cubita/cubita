import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { JALALI_MONTH_NAMES, isoToJalali, toFaDigits } from '../lib/jalali'

export interface TrendSeries {
  key: string
  label: string
  color: string
  points: { date: string; value: number }[]
}

const fa = (v: number) => Math.round(v).toLocaleString('fa-IR')
/** برچسبِ کوتاهِ محور: «۵ شهریور». از تقویمِ خودِ برنامه، نه ICUِ مرورگر — تا قالبِ
 *  تاریخ در همه‌ی نمودارها و جدول‌ها یکی بماند. */
const faDate = (iso: string) => {
  const { jm, jd } = isoToJalali(iso.slice(0, 10))
  return `${toFaDigits(jd)} ${JALALI_MONTH_NAMES[jm - 1]}`
}

// برچسبِ محورِ عمودی فشرده تا در گوشه‌ی چپ جا شود و با عددِ روی نمودار قاطی نشود.
function faAxis(v: number): string {
  const sign = v < 0 ? '−' : ''
  const a = Math.abs(v)
  if (a >= 1e9) return sign + (a / 1e9).toLocaleString('fa-IR', { maximumFractionDigits: 1 }) + ' میلیارد'
  if (a >= 1e6) return sign + Math.round(a / 1e6).toLocaleString('fa-IR') + ' م'
  if (a >= 1e3) return sign + Math.round(a / 1e3).toLocaleString('fa-IR') + ' هزار'
  return sign + Math.round(a).toLocaleString('fa-IR')
}

const HEIGHT = 240
const PAD_TOP = 16
const PAD_BOTTOM = 26
const PAD_RIGHT = 12
// گوشه‌ی چپ برای برچسبِ محور (اعداد فشرده) کنار گذاشته می‌شود.
const PAD_LEFT = 48

// نمودارِ «سطحی» (area) با پُرشدگیِ گرادیانی — به‌جای خطِ ساده. عرضِ واقعیِ ظرف را
// اندازه می‌گیرد (ResizeObserver) تا viewBox = پیکسل شود؛ نتیجه: متنِ تیز، بدونِ کشیدگی
// و بدونِ سرریز از پنل. مختصات در فضای W×HEIGHT (نه viewBoxِ ثابتِ کشیده) محاسبه می‌شود.
export function TrendChart({ series }: { series: TrendSeries[] }) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(560)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  useLayoutEffect(() => {
    const el = wrapRef.current
    if (!el) return
    setWidth(el.clientWidth)
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w && w > 0) setWidth(w)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

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

  const W = Math.max(width, 240)
  const plotW = W - PAD_LEFT - PAD_RIGHT
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM

  const xAt = (i: number) => PAD_LEFT + (dates.length === 1 ? plotW / 2 : (i / (dates.length - 1)) * plotW)
  const yAt = (v: number) => PAD_TOP + plotH - ((v - minValue) / (maxValue - minValue)) * plotH

  const gridLines = 4
  const gridValues = Array.from({ length: gridLines + 1 }, (_, i) => minValue + ((maxValue - minValue) * i) / gridLines)

  function lineFor(values: number[]) {
    return values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i)} ${yAt(v)}`).join(' ')
  }

  function areaFor(values: number[]) {
    const line = lineFor(values)
    return `${line} L ${xAt(values.length - 1)} ${yAt(minValue)} L ${xAt(0)} ${yAt(minValue)} Z`
  }

  function handleMove(e: React.MouseEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const ratio = Math.min(1, Math.max(0, x / rect.width))
    const idx = Math.round(ratio * (dates.length - 1))
    setHoverIndex(idx)
  }

  return (
    <div className="trend-chart" ref={wrapRef}>
      <div className="trend-legend">
        {series.map((s) => (
          <div key={s.key} className="trend-legend-item">
            <span className="trend-legend-dot" style={{ background: s.color }} />
            {s.label}
          </div>
        ))}
      </div>

      <svg width={W} height={HEIGHT} viewBox={`0 0 ${W} ${HEIGHT}`} className="trend-chart-svg">
        <defs>
          {series.map((s) => (
            <linearGradient key={`grad-${s.key}`} id={`trend-grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.34} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>

        {gridValues.map((gv, i) => (
          <g key={i}>
            <line x1={PAD_LEFT} x2={W - PAD_RIGHT} y1={yAt(gv)} y2={yAt(gv)} className="trend-gridline" />
            <text x={PAD_LEFT - 8} y={yAt(gv)} className="trend-axis-label" textAnchor="end" dominantBaseline="central">
              {faAxis(gv)}
            </text>
          </g>
        ))}

        {series.map((s, si) => (
          <path key={`area-${s.key}`} d={areaFor(aligned[si])} fill={`url(#trend-grad-${s.key})`} stroke="none" />
        ))}
        {series.map((s, si) => (
          <path
            key={`line-${s.key}`}
            d={lineFor(aligned[si])}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
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
