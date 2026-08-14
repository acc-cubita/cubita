import { useEffect, useRef, useState } from 'react'
import { Calendar as CalendarIcon, ChevronRight, ChevronLeft } from 'lucide-react'
import {
  JALALI_MONTH_NAMES,
  JALALI_WEEKDAY_SHORT,
  buildJalaliMonthCells,
  formatJalali,
  isoToJalali,
  jalaliToIso,
  toFaDigits,
  todayIso,
} from '../lib/jalali'

export function JalaliDatePicker({
  value,
  onChange,
  placeholder = 'انتخاب تاریخ',
}: {
  value: string
  onChange: (iso: string) => void
  placeholder?: string
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const initial = isoToJalali(value || todayIso())
  const [viewYear, setViewYear] = useState(initial.jy)
  const [viewMonth, setViewMonth] = useState(initial.jm)

  useEffect(() => {
    const j = isoToJalali(value || todayIso())
    setViewYear(j.jy)
    setViewMonth(j.jm)
  }, [value])

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [open])

  const cells = buildJalaliMonthCells(viewYear, viewMonth)
  const selected = value ? isoToJalali(value) : null
  const today = isoToJalali(todayIso())

  function goPrevMonth() {
    if (viewMonth === 1) {
      setViewYear((y) => y - 1)
      setViewMonth(12)
    } else {
      setViewMonth((m) => m - 1)
    }
  }

  function goNextMonth() {
    if (viewMonth === 12) {
      setViewYear((y) => y + 1)
      setViewMonth(1)
    } else {
      setViewMonth((m) => m + 1)
    }
  }

  function pickDay(d: number) {
    onChange(jalaliToIso(viewYear, viewMonth, d))
    setOpen(false)
  }

  function pickToday() {
    onChange(todayIso())
    setOpen(false)
  }

  return (
    <div className="jalali-date-field" ref={containerRef}>
      <button type="button" className="jalali-date-trigger" onClick={() => setOpen((o) => !o)}>
        <CalendarIcon size={14} />
        <span className={value ? '' : 'jalali-date-placeholder'}>{value ? formatJalali(value) : placeholder}</span>
      </button>

      {open && (
        <div className="jalali-date-popover">
          <div className="jalali-date-header">
            <button type="button" onClick={goPrevMonth} title="ماه قبل" aria-label="ماه قبل">
              <ChevronRight size={15} />
            </button>
            <span className="jalali-date-title">
              {JALALI_MONTH_NAMES[viewMonth - 1]} {toFaDigits(viewYear)}
            </span>
            <button type="button" onClick={goNextMonth} title="ماه بعد" aria-label="ماه بعد">
              <ChevronLeft size={15} />
            </button>
          </div>

          <div className="jalali-date-weekdays">
            {JALALI_WEEKDAY_SHORT.map((w) => (
              <span key={w}>{w}</span>
            ))}
          </div>

          <div className="jalali-date-grid">
            {cells.map((d, idx) => {
              if (d === null) return <span key={idx} className="jalali-date-cell empty" />
              const isSelected = !!selected && selected.jy === viewYear && selected.jm === viewMonth && selected.jd === d
              const isToday = today.jy === viewYear && today.jm === viewMonth && today.jd === d
              return (
                <button
                  key={idx}
                  type="button"
                  className={`jalali-date-cell${isSelected ? ' selected' : ''}${isToday ? ' today' : ''}`}
                  onClick={() => pickDay(d)}
                >
                  {toFaDigits(d)}
                </button>
              )
            })}
          </div>

          <div className="jalali-date-footer">
            <button type="button" onClick={pickToday}>
              امروز
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
