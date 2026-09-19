import { useEffect, useMemo, useRef, useState } from 'react'
import { CornerDownLeft, Search } from 'lucide-react'

import { buildCommands, searchCommands } from '../lib/commands'
import type { MeResponse } from '../api'
import type { PageKey } from '../lib/navModel'

/**
 * جست‌وجوی ماژول روی داشبورد.
 *
 * **چرا این‌جا و نه فقط در نوارِ بالا:** کادرِ نوار وقتی جا کم بیاید کنار می‌رود
 * (کلاسِ `topnav--tight`). با چهارده ماژول، روی نمایشگرِ معمولی *همیشه* کنار
 * رفته است — یعنی در عمل برای بیشترِ کاربران وجود ندارد. `Ctrl+K` هم هست ولی
 * کسی که نداند وجود دارد، پیدایش نمی‌کند.
 *
 * منبعِ نتایج همان `buildCommands` است که کامندپالت می‌خوانَد؛ این نمای دوم
 * است، نه فهرستِ دوم.
 */
export function ModuleSearch({
  me,
  onNavigate,
}: {
  me: MeResponse
  onNavigate: (page: PageKey, section?: string) => void
}) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  const commands = useMemo(() => buildCommands(me), [me])
  //: هشت‌تا سقفِ عمدی است: فهرستِ بلند زیرِ یک کادرِ داشبورد، بقیه‌ی صفحه را
  //: می‌پوشاند و کاربر را از همان چیزی که آمده ببیند دور می‌کند.
  const results = useMemo(
    () => (query.trim() ? searchCommands(commands, query, 8) : []),
    [commands, query],
  )

  useEffect(() => setActive(0), [query])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  function go(index: number) {
    const c = results[index]
    if (!c) return
    onNavigate(c.page, c.section)
    setQuery('')
    setOpen(false)
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      go(active)
    } else if (e.key === 'Escape') {
      setQuery('')
      setOpen(false)
    }
  }

  const showResults = open && query.trim().length > 0

  return (
    <div className="mod-search" ref={boxRef}>
      <div className="mod-search-field">
        <Search size={18} />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
          placeholder="جست‌وجوی ماژول یا کار — مثلاً «فاکتور فروش» یا «انبار»"
          aria-label="جست‌وجوی ماژول یا کار"
          aria-expanded={showResults}
          role="combobox"
          aria-controls="mod-search-results"
        />
        <kbd className="mod-search-kbd" title="میان‌برِ صفحه‌کلید">Ctrl + K</kbd>
      </div>

      {showResults && (
        <div className="mod-search-results" id="mod-search-results" role="listbox">
          {results.length === 0 ? (
            <p className="mod-search-empty">چیزی با این نام پیدا نشد.</p>
          ) : (
            results.map((c, i) => (
              <button
                key={c.id}
                type="button"
                role="option"
                aria-selected={i === active}
                className={`mod-search-item${i === active ? ' is-active' : ''}`}
                onMouseEnter={() => setActive(i)}
                onClick={() => go(i)}
              >
                <span className="mod-search-item-icon">{c.icon}</span>
                <span className="mod-search-item-text">
                  <span className="mod-search-item-title">{c.title}</span>
                  {c.subtitle && <span className="mod-search-item-sub">{c.subtitle}</span>}
                </span>
                {i === active && <CornerDownLeft size={14} className="mod-search-item-enter" />}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
