import { useEffect, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import type { MeResponse } from '../api'
import type { PageKey } from '../lib/navModel'
import { buildCommands, searchCommands, type Command } from '../lib/commands'

/**
 * کامندپالتِ سراسری — پرش به هر صفحه یا شروعِ یک کار. منبعِ فرمان‌ها همان
 * navModel + taskRegistry است تا با منو یکی بماند.
 *
 * **حالتِ باز/بسته بیرون است.** `Ctrl+K` تنها راهِ بازکردنش نیست: دکمه‌ی جست‌وجوی
 * نوارِ بالا هم همین را باز می‌کند، و روی موبایل که صفحه‌کلیدی نیست، تنها راه
 * همان دکمه است. پس مالکِ حالت `Dashboard` است که هر دو را رندر می‌کند.
 */
export function CommandPalette({
  me,
  onNavigate,
  open,
  onOpenChange,
}: {
  me: MeResponse
  onNavigate: (page: PageKey, section: string | null) => void
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  // Ctrl/⌘+K برای باز/بسته؛ Escape برای بستن. سراسری تا از هر جای برنامه در دسترس باشد.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      //: `e.code` جای فیزیکیِ کلید است و به چیدمان کار ندارد؛ `e.key` در چیدمانِ
      //: فارسی «ن» می‌دهد و میانبر بی‌صدا از کار می‌افتاد. `e.key` به‌عنوان تکیه‌گاه
      //: می‌ماند برای صفحه‌کلیدهایی که `code` معناداری نمی‌دهند (مثلِ صفحه‌کلیدِ مجازی).
      if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyK' || e.key.toLowerCase() === 'k')) {
        e.preventDefault()
        onOpenChange(!open)
      } else if (e.key === 'Escape') {
        onOpenChange(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  const commands = useMemo(() => buildCommands(me), [me])
  const filtered = useMemo(() => searchCommands(commands, query), [commands, query])

  useEffect(() => {
    setActive(0)
  }, [query, open])

  useEffect(() => {
    if (open) {
      setQuery('')
      // فوکوس بعد از mount شدنِ ورودی
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  // آیتمِ فعال همیشه در دید بماند (پیمایش با کلید)
  useEffect(() => {
    listRef.current?.querySelector('.cmdk-item.is-active')?.scrollIntoView({ block: 'nearest' })
  }, [active])

  if (!open) return null

  function run(c: Command) {
    onNavigate(c.page, c.section ?? null)
    onOpenChange(false)
  }

  function onInputKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const c = filtered[active]
      if (c) run(c)
    }
  }

  return (
    <div className="cmdk-overlay" onMouseDown={() => onOpenChange(false)}>
      <div className="cmdk" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="جست‌وجوی فرمان">
        <div className="cmdk-search">
          <Search size={18} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKey}
            placeholder="برو به… یا یک کار را شروع کن (مثلاً «فاکتور فروش»)"
            aria-label="جست‌وجو"
          />
          <kbd className="cmdk-esc">Esc</kbd>
        </div>
        <ul className="cmdk-list" ref={listRef}>
          {filtered.length === 0 ? (
            <li className="cmdk-empty">چیزی پیدا نشد</li>
          ) : (
            filtered.map((c, i) => (
              <li key={c.id}>
                <button
                  type="button"
                  className={`cmdk-item${i === active ? ' is-active' : ''}`}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => run(c)}
                >
                  <span className="cmdk-item-icon">{c.icon}</span>
                  <span className="cmdk-item-text">
                    <span className="cmdk-item-title">{c.title}</span>
                    {c.subtitle && <span className="cmdk-item-sub">{c.subtitle}</span>}
                  </span>
                  <span className={`cmdk-item-kind is-${c.kind}`}>{c.kind === 'task' ? 'شروعِ کار' : 'صفحه'}</span>
                </button>
              </li>
            ))
          )}
        </ul>
        <div className="cmdk-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> جابه‌جایی</span>
          <span><kbd>↵</kbd> انتخاب</span>
          <span><kbd>Ctrl</kbd>+<kbd>K</kbd> باز/بسته</span>
        </div>
      </div>
    </div>
  )
}
