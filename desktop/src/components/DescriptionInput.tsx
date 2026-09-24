import { memo, useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'

import { placePopover, type Placement } from '../lib/popover'
import { suggestDescriptions } from '../lib/descriptionMemory'

/**
 * کادرِ شرح با پیشنهادِ شرح‌های تکراری (UI-01 §۲۰).
 *
 * **هیچ‌چیز خودکار نمی‌نشیند.** فهرست فقط با تایپ باز می‌شود و تا کاربر ↓ نزند هیچ
 * گزینه‌ای انتخاب نیست؛ پس Enter بدونِ انتخاب همان کارِ همیشگیِ گرید را می‌کند
 * (رفتن به خانه‌ی بعد) و فهرست بسته می‌شود.
 *
 * **کلیدهای فهرست مالِ فهرست‌اند:** وقتی باز است ↑/↓، Enterِ روی گزینه و Escape
 * `stopPropagation` می‌گیرند تا به `onKeyDown`ِ گرید نرسند — وگرنه پیکان هم گزینه را
 * عوض می‌کرد و هم ردیف را. فوکوس هیچ‌وقت از کادر بیرون نمی‌رود
 * (`aria-activedescendant`)، پس گرید همچنان همین خانه را خانه‌ی فعال می‌بیند.
 *
 * **کارایی:** مخزن فقط با `getPool` و فقط هنگامِ تایپ در **همین** کادر خوانده
 * می‌شود. `getPool` باید پایدار باشد تا `memo`ِ ردیف‌های گرید نشکند.
 */
export const DescriptionInput = memo(function DescriptionInput({
  value,
  row,
  onUpdate,
  getDescriptionPool,
  'aria-label': ariaLabel,
  placeholder,
}: {
  value: string
  row: number
  onUpdate: (row: number, patch: { description: string }) => void
  getDescriptionPool: (row: number) => string[]
  'aria-label'?: string
  placeholder?: string
}) {
  const id = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [items, setItems] = useState<string[]>([])
  const [active, setActive] = useState(-1)
  const [rect, setRect] = useState<Placement | null>(null)
  const open = items.length > 0

  const close = useCallback(() => {
    setItems([])
    setActive(-1)
  }, [])

  function refresh(text: string) {
    const next = suggestDescriptions(getDescriptionPool(row), text)
    setItems(next)
    setActive(-1)
    const el = inputRef.current
    if (next.length > 0 && el) {
      setRect(placePopover(el.getBoundingClientRect(), { width: window.innerWidth, height: window.innerHeight }, { chrome: 8, maxH: 220 }))
    }
  }

  function pick(s: string) {
    onUpdate(row, { description: s })
    close()
  }

  //: فهرستِ ثابت‌جا با اسکرولِ گرید جابه‌جا نمی‌شود؛ بستنش صادق‌تر از فهرستی است
  //: که از کادرش جدا شده.
  useEffect(() => {
    if (!open) return
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [open, close])

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (!open) return
    const own = () => {
      e.preventDefault()
      e.stopPropagation()
    }
    if (e.key === 'ArrowDown') {
      own()
      setActive((a) => (a + 1) % items.length)
    } else if (e.key === 'ArrowUp') {
      own()
      setActive((a) => (a <= 0 ? items.length - 1 : a - 1))
    } else if (e.key === 'Enter' && active >= 0) {
      own()
      pick(items[active])
    } else if (e.key === 'Escape') {
      own()
      close()
    } else if (e.key === 'Enter') {
      close() // بی‌انتخاب: Enter به گرید می‌رسد
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        aria-label={ariaLabel}
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-activedescendant={open && active >= 0 ? `${id}-${active}` : undefined}
        value={value}
        placeholder={placeholder}
        onChange={(e) => {
          onUpdate(row, { description: e.target.value })
          refresh(e.target.value)
        }}
        onKeyDown={onKeyDown}
        onBlur={close}
      />
      {open &&
        rect &&
        createPortal(
          <div
            className="item-picker-pop desc-suggest"
            style={{ position: 'fixed', top: rect.top, bottom: rect.bottom, left: rect.left, width: rect.width }}
          >
            <ul className="item-picker-list" role="listbox" id={id} aria-label="شرح‌های پیشنهادی" style={{ maxHeight: rect.maxH }}>
              {items.map((s, i) => (
                <li
                  key={s}
                  id={`${id}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  className={`item-picker-opt${i === active ? ' active' : ''}`}
                  //: `mousedown` و نه `click`: کلیک اول فوکوس را از کادر می‌گیرد و `onBlur`
                  //: فهرست را پیش از رسیدنِ کلیک می‌بندد.
                  onMouseDown={(e) => {
                    e.preventDefault()
                    pick(s)
                  }}
                >
                  {s}
                </li>
              ))}
            </ul>
          </div>,
          document.body,
        )}
    </>
  )
})
