import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { Search, X } from 'lucide-react'
import { fetchEmployeeCandidates, type EmployeeCandidate } from '../../api'

/**
 * جست‌وجو و انتخابِ کارمند در یک فیلد (combobox) — به‌جای دو فیلدِ جدای «جست‌وجو» و
 * «انتخاب» که قبلاً کنارِ هم بودند.
 *
 * جست‌وجو سمتِ سرور است، نه در مرورگر: با چند صد طرف‌حساب، کشیدنِ همه برای
 * فیلترکردنشان این‌جا از کار می‌افتد.
 *
 * «کارمندی پیدا نشد» فقط بعد از یک جست‌وجوی ناموفق دیده می‌شود، نه پیش از آنکه کاربر
 * چیزی تایپ کند — پیامِ هشدارِ ثابت زیرِ فیلدِ خالی فقط نویز بود.
 */
export function EmployeePicker({
  id,
  token,
  selected,
  onSelect,
}: {
  id: string
  token: string
  selected: EmployeeCandidate | null
  onSelect: (c: EmployeeCandidate | null) => void
}) {
  const listId = useId()
  const boxRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState(selected?.name ?? '')
  const [results, setResults] = useState<EmployeeCandidate[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const timer = setTimeout(() => {
      fetchEmployeeCandidates(token, query)
        .then((rows) => !cancelled && setResults(rows))
        .catch(() => !cancelled && setResults([]))
        .finally(() => !cancelled && setLoading(false))
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [token, query])

  useEffect(() => {
    if (!open) return
    const onOutside = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [open])

  function choose(c: EmployeeCandidate) {
    onSelect(c)
    setQuery(c.name)
    setOpen(false)
    setActive(-1)
  }

  function clear() {
    onSelect(null)
    setQuery('')
    setActive(-1)
    inputRef.current?.focus()
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      setOpen(true)
      if (!results.length) return
      const step = e.key === 'ArrowDown' ? 1 : -1
      setActive((i) => (i + step + results.length) % results.length)
    } else if (e.key === 'Enter' && open && active >= 0 && results[active]) {
      //: بدونِ این، Enter فرمِ قرارداد را ارسال می‌کرد.
      e.preventDefault()
      choose(results[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const trimmed = query.trim()
  const failedSearch = !loading && !results.length && trimmed !== '' && !selected

  return (
    <div className="ef-combo" ref={boxRef}>
      <div className="ef-combo-field">
        <Search size={15} className="ef-combo-icon" aria-hidden="true" />
        <input
          ref={inputRef}
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
          autoComplete="off"
          value={query}
          placeholder="نام یا کد ملیِ کارمند…"
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
            setActive(-1)
            if (selected) onSelect(null)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />
        {(query || selected) && (
          <button type="button" className="ef-combo-clear" onClick={clear} aria-label="پاک‌کردنِ انتخاب">
            <X size={14} />
          </button>
        )}
      </div>

      {open && (
        <ul className="ef-combo-list" role="listbox" id={listId} aria-label="کارمندان">
          {results.length === 0 ? (
            <li className="ef-combo-empty" role="presentation">
              {loading
                ? 'در حال جست‌وجو…'
                : trimmed
                  ? `کارمندی با «${trimmed}» پیدا نشد.`
                  : 'هنوز کارمندی ثبت نشده. در «شرکت ← طرف حساب جدید» تیکِ «کارمند» را بزنید.'}
            </li>
          ) : (
            results.map((c, i) => (
              <li
                key={c.contact_id}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={selected?.contact_id === c.contact_id}
                className={`ef-combo-option${i === active ? ' is-active' : ''}`}
                //: mousedown نه click: click بعد از blurِ ورودی می‌رسد و فهرست تا آن موقع بسته شده.
                onMouseDown={(e) => {
                  e.preventDefault()
                  choose(c)
                }}
                onMouseEnter={() => setActive(i)}
              >
                <span className="ef-combo-name">{c.name}</span>
                {c.national_id && (
                  <span className="ef-combo-meta" dir="ltr">
                    {c.national_id}
                  </span>
                )}
                {c.has_contract && <span className="ef-chip">دارای قرارداد</span>}
              </li>
            ))
          )}
        </ul>
      )}

      {failedSearch && !open && (
        <p className="ef-message ef-message--warn" role="status">
          کارمندی با این نام پیدا نشد.
        </p>
      )}
    </div>
  )
}
