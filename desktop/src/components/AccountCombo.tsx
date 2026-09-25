import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown } from 'lucide-react'

import { matchRank, textMatches } from '../lib/faText'
import { toFaDigits } from '../lib/jalali'
import { placePopover, type Placement } from '../lib/popover'

export interface ComboOption {
  value: string
  label: string
}

/** چطور انتخاب تمام شد — گرید از روی آن خانه‌ی بعد را پیدا می‌کند. */
export type ComboCommit = 'enter' | 'tab'

//: همان سقفِ `SearchSelect`: فهرست سبک می‌ماند و تایپ باریکش می‌کند.
const SHOW_LIMIT = 80

/**
 * خانه‌ی حسابِ گریدِ سند — **خودِ خانه کادرِ جست‌وجوست**.
 *
 * `SearchSelect` دکمه‌ای است که پاپ‌آوری با کادرِ جست‌وجوی جدا باز می‌کند: حرفِ اول دکمه
 * را باز می‌کند، بقیه در کادرِ دیگری تایپ می‌شود، و بعد از Enter فوکوس به دکمه برمی‌گردد و
 * یک Enterِ دیگر لازم است تا جلو برود. برای حسابدار که ردیف پشتِ ردیف می‌زند، این سه جای
 * متفاوت برای یک کار است. این‌جا:
 *
 * - تایپ **در همان خانه** فهرست را زیرش باز و فیلتر می‌کند (کد یا نام؛ رتبه‌بندیِ
 *   `matchRank`: کد/ابتدای نام بالاتر).
 * - ↑/↓ گزینه را جابه‌جا می‌کند؛ **Enter انتخاب می‌کند و خانه را می‌بندد و گرید جلو
 *   می‌رود** (`onCommit`). Tab هم وقتی چیزی تایپ شده همین کار را می‌کند.
 * - Esc و بیرون‌رفتن بی‌انتخاب، مقدارِ قبلی را برمی‌گرداند.
 * - بسته، کلیدهای ناوبری مالِ گرید‌اند؛ فقط Enter روی خانه‌ی خالی فهرست را باز می‌کند تا
 *   ردیف بی‌صدا بی‌حساب رها نشود.
 *
 * کلیدهایی که مصرف می‌کند `stopPropagation` می‌گیرند تا به `onKeyDown`ِ گرید نرسند —
 * همان قراردادِ `DescriptionInput`. فوکوس هیچ‌وقت از کادر بیرون نمی‌رود (گزینه‌ها با
 * `aria-activedescendant` اعلام می‌شوند)، پس گرید همیشه می‌داند کدام خانه فعال است.
 *
 * **چرا جلو بردن با `onCommit` و نه با خودِ Enter.** انتخاب وضعیتِ ردیف را عوض می‌کند (حسابِ
 * تازه ممکن است تفصیلیِ اجباری بخواهد و ستونش تازه پیدا شود). اگر همان Enter به گرید می‌رسید،
 * گرید با وضعیتِ **پیش از** انتخاب مسیر را حساب می‌کرد و از خانه‌ی اجباری می‌پرید.
 */
export function AccountCombo({
  value,
  options,
  onChange,
  onCommit,
  placeholder = 'کد یا نامِ حساب…',
  'aria-label': ariaLabel,
}: {
  value: string
  options: ComboOption[]
  onChange: (value: string) => void
  onCommit?: (how: ComboCommit) => void
  placeholder?: string
  'aria-label'?: string
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [rect, setRect] = useState<Placement | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const listId = useId()

  const selected = options.find((o) => o.value === value) ?? null

  const { filtered, hidden } = useMemo(() => {
    const hits = query.trim()
      ? options
          .filter((o) => textMatches(o.label, query))
          .map((o, i) => ({ o, i, r: matchRank(o.label, query) }))
          .sort((a, b) => a.r - b.r || a.i - b.i)
          .map((x) => x.o)
      : options
    return { filtered: hits.slice(0, SHOW_LIMIT), hidden: Math.max(0, hits.length - SHOW_LIMIT) }
  }, [options, query])

  function reposition() {
    const el = inputRef.current
    if (!el) return
    setRect(
      placePopover(el.getBoundingClientRect(), { width: window.innerWidth, height: window.innerHeight }, { chrome: 0 }),
    )
  }

  useLayoutEffect(() => {
    if (!open) return
    reposition()
    window.addEventListener('scroll', reposition, true)
    window.addEventListener('resize', reposition)
    return () => {
      window.removeEventListener('scroll', reposition, true)
      window.removeEventListener('resize', reposition)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView?.({ block: 'nearest' })
  }, [active, open])

  /** بازکردن با فهرستِ کامل (کلیک، F4، Alt+↓، Enter روی خانه‌ی خالی). */
  function openFull() {
    setQuery('')
    setActive(Math.max(0, options.findIndex((o) => o.value === value)))
    setOpen(true)
  }

  function close() {
    setOpen(false)
    setQuery('')
  }

  function pick(o: ComboOption) {
    if (o.value !== value) onChange(o.value)
    close()
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    const own = () => {
      e.preventDefault()
      e.stopPropagation()
    }
    //: میان‌برها (Ctrl+S، Ctrl+D، …) مالِ گرید و فرم‌اند؛ Alt+↓ را گرید با `openCellPicker` می‌فرستد.
    if (e.ctrlKey || e.metaKey || e.altKey) return

    if (!open) {
      if ((e.key === 'Enter' || e.code === 'NumpadEnter') && !e.shiftKey && !value) {
        own()
        openFull()
      }
      return
    }

    const pickActive = () => {
      const o = filtered[active]
      if (!o) return false
      pick(o)
      return true
    }
    if (e.key === 'ArrowDown') {
      own()
      setActive((a) => Math.min(a + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      own()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'PageDown') {
      own()
      setActive((a) => Math.min(a + 8, filtered.length - 1))
    } else if (e.key === 'PageUp') {
      own()
      setActive((a) => Math.max(a - 8, 0))
    } else if (e.key === 'Enter' || e.code === 'NumpadEnter') {
      own()
      if (pickActive()) onCommit?.('enter')
    } else if (e.key === 'Escape') {
      own()
      close()
    } else if (e.key === 'Tab') {
      //: تایپ‌کرده و Tab زده: همان گزینه‌ی برجسته را می‌خواهد (مثلِ تکمیلِ خودکارِ Excel).
      //: بی‌تایپ، Tab فقط رد می‌شود و مقدارِ قبلی می‌ماند.
      if (!e.shiftKey && query.trim() && filtered[active]) {
        own()
        pickActive()
        onCommit?.('tab')
      } else {
        close()
      }
    }
  }

  const activeId = open && filtered[active] ? `${listId}-${active}` : undefined

  return (
    <div className={`jg-combo${open ? ' is-open' : ''}`}>
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        aria-label={ariaLabel}
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={activeId}
        autoComplete="off"
        spellCheck={false}
        value={open ? query : (selected?.label ?? '')}
        //: باز و بی‌تایپ: نامِ حسابِ فعلی کم‌رنگ می‌ماند تا کاربر بداند چه چیزی را عوض می‌کند.
        placeholder={open ? (selected?.label ?? placeholder) : placeholder}
        onChange={(e) => {
          setQuery(e.target.value)
          setActive(0)
          if (!open) setOpen(true)
        }}
        //: رسیدن به خانه کلِ نام را انتخاب می‌کند تا تایپ جایگزینش کند (قاعده‌ی Excel و گرید).
        onFocus={(e) => e.currentTarget.select()}
        onClick={() => {
          if (!open) openFull()
        }}
        onKeyDown={onKeyDown}
        onBlur={() => {
          if (open) close()
        }}
      />
      <ChevronDown className="jg-combo-chev" size={15} aria-hidden="true" />

      {open &&
        rect &&
        createPortal(
          <div
            className="item-picker-pop jg-combo-pop"
            style={{ position: 'fixed', top: rect.top, bottom: rect.bottom, left: rect.left, width: rect.width }}
            //: کلیک روی گزینه نباید فوکوس را از کادر بگیرد — وگرنه `onBlur` فهرست را می‌بست.
            onMouseDown={(e) => e.preventDefault()}
          >
            <ul id={listId} role="listbox" aria-label={ariaLabel} className="item-picker-list" ref={listRef} style={{ maxHeight: rect.maxH }}>
              {filtered.length === 0 ? (
                <li className="item-picker-empty">حسابی با این کد یا نام پیدا نشد.</li>
              ) : (
                filtered.map((o, i) => (
                  <li
                    key={o.value}
                    id={`${listId}-${i}`}
                    role="option"
                    aria-selected={i === active}
                    className={`item-picker-opt${i === active ? ' active' : ''}${o.value === value ? ' selected' : ''}`}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => pick(o)}
                  >
                    <span className="item-picker-opt-name">{o.label}</span>
                  </li>
                ))
              )}
            </ul>
            {hidden > 0 && (
              <p className="item-picker-more">
                {toFaDigits(String(hidden))} حسابِ دیگر هم هست — برای پیدا‌کردنشان بیشتر تایپ کنید.
              </p>
            )}
          </div>,
          document.body,
        )}
    </div>
  )
}
