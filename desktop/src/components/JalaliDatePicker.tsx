import { useEffect, useLayoutEffect, useRef, useState } from 'react'
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
  id,
  value,
  onChange,
  placeholder = 'انتخاب تاریخ',
  clearLabel,
}: {
  /** شناسه‌ی دکمه‌ی بازکننده — تا `<label htmlFor>` به آن وصل شود. */
  id?: string
  value: string
  onChange: (iso: string) => void
  placeholder?: string
  /**
   * تاریخِ اختیاری: دکمه‌ای کنارِ «امروز» که مقدار را خالی می‌کند (`onChange('')`) — مثلاً «بی‌پایان» برای
   * تاریخِ پایانِ سندِ تکرارشونده. بی‌این، تاریخی که یک‌بار انتخاب شد دیگر خالی نمی‌شد.
   */
  clearLabel?: string
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  const initial = isoToJalali(value || todayIso())
  const [viewYear, setViewYear] = useState(initial.jy)
  const [viewMonth, setViewMonth] = useState(initial.jm)
  const [level, setLevel] = useState<'days' | 'months' | 'years'>('days')

  useLayoutEffect(() => {
    if (!open) return
    function fit() {
      const popover = popoverRef.current
      if (!popover) return
      popover.style.transform = ''
      const rect = popover.getBoundingClientRect()
      const dx = rect.left < 12 ? 12 - rect.left : rect.right > window.innerWidth - 12 ? window.innerWidth - 12 - rect.right : 0
      if (dx) popover.style.transform = `translateX(${dx}px)`
    }
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [open, level])

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
  const yearStart = Math.floor(viewYear / 12) * 12
  const previousLabel = level === 'days' ? 'ماه قبل' : level === 'months' ? 'سال قبل' : 'سال‌های قبل'
  const nextLabel = level === 'days' ? 'ماه بعد' : level === 'months' ? 'سال بعد' : 'سال‌های بعد'

  function move(direction: -1 | 1) {
    if (level !== 'days') {
      setViewYear((year) => Math.min(3177, Math.max(1, year + direction * (level === 'years' ? 12 : 1))))
    } else if (direction === -1) goPrevMonth()
    else goNextMonth()
  }

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
    <div className="jalali-date-field" ref={containerRef} onKeyDown={(event) => {
      if (open && event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        setOpen(false)
        containerRef.current?.querySelector<HTMLButtonElement>('.jalali-date-trigger')?.focus()
      }
    }}>
      <button type="button" id={id} className="jalali-date-trigger" aria-haspopup="dialog" aria-expanded={open} onClick={() => {
        if (!open) {
          const date = isoToJalali(value || todayIso())
          setViewYear(date.jy)
          setViewMonth(date.jm)
          setLevel('days')
        }
        setOpen((current) => !current)
      }}>
        <CalendarIcon size={14} />
        <span className={value ? '' : 'jalali-date-placeholder'}>{value ? formatJalali(value) : placeholder}</span>
      </button>

      {open && (
        <div ref={popoverRef} className="jalali-date-popover" role="dialog" aria-label="انتخاب تاریخ شمسی">
          <div className="jalali-date-header">
            <button type="button" onClick={() => move(-1)} title={previousLabel} aria-label={previousLabel}
              disabled={viewYear <= 1 && (level !== 'days' || viewMonth === 1)}>
              <ChevronRight size={15} />
            </button>
            {level === 'years' ? (
              <span className="jalali-date-title">{toFaDigits(Math.max(1, yearStart))}–{toFaDigits(Math.min(3177, yearStart + 11))}</span>
            ) : (
              <button type="button" className="jalali-date-title" aria-label={level === 'days' ? 'انتخاب ماه' : 'انتخاب سال'}
                onClick={() => setLevel(level === 'days' ? 'months' : 'years')}>
                {level === 'days' && `${JALALI_MONTH_NAMES[viewMonth - 1]} `}{toFaDigits(viewYear)}
              </button>
            )}
            <button type="button" onClick={() => move(1)} title={nextLabel} aria-label={nextLabel}
              disabled={viewYear >= 3177 && (level !== 'days' || viewMonth === 12)}>
              <ChevronLeft size={15} />
            </button>
          </div>

          {level === 'days' && <div className="jalali-date-weekdays">
            {JALALI_WEEKDAY_SHORT.map((w) => (
              <span key={w}>{w}</span>
            ))}
          </div>}

          {level === 'days' && <div className="jalali-date-grid">
            {cells.map((d, idx) => {
              if (d === null) return <span key={idx} className="jalali-date-cell empty" />
              const isSelected = !!selected && selected.jy === viewYear && selected.jm === viewMonth && selected.jd === d
              const isToday = today.jy === viewYear && today.jm === viewMonth && today.jd === d
              return (
                <button
                  key={idx}
                  type="button"
                  className={`jalali-date-cell${isSelected ? ' selected' : ''}${isToday ? ' today' : ''}`}
                  aria-pressed={isSelected}
                  aria-label={`${toFaDigits(d)} ${JALALI_MONTH_NAMES[viewMonth - 1]} ${toFaDigits(viewYear)}`}
                  onClick={() => pickDay(d)}
                >
                  {toFaDigits(d)}
                </button>
              )
            })}
          </div>}

          {level === 'months' && <div className="jalali-date-grid jalali-date-grid--levels">
            {JALALI_MONTH_NAMES.map((name, index) => (
              <button type="button" key={name} className={`jalali-date-cell${selected?.jy === viewYear && selected.jm === index + 1 ? ' selected' : ''}`}
                onClick={() => { setViewMonth(index + 1); setLevel('days') }}>{name}</button>
            ))}
          </div>}
          {level === 'years' && <div className="jalali-date-grid jalali-date-grid--levels">
            {Array.from({ length: 12 }, (_, index) => yearStart + index).map((year) => (
              <button type="button" key={year} disabled={year < 1 || year > 3177}
                className={`jalali-date-cell${selected?.jy === year ? ' selected' : ''}`}
                onClick={() => { setViewYear(year); setLevel('months') }}>{toFaDigits(year)}</button>
            ))}
          </div>}

          <div className="jalali-date-footer">
            <button type="button" onClick={pickToday}>
              امروز
            </button>
            {clearLabel && value && (
              <button
                type="button"
                onClick={() => {
                  onChange('')
                  setOpen(false)
                }}
              >
                {clearLabel}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
