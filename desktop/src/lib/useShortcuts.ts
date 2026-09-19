import { useEffect, useRef } from 'react'

import { chordFromEvent, chordId, isTypingTarget, loadShortcuts, type ShortcutMap } from './shortcuts'

/**
 * شنونده‌ی سراسریِ میان‌برهای کاربر.
 *
 * دو گاردِ لازم:
 *
 * * **در حالِ نوشتن اجرا نمی‌شود.** `Ctrl+B` وسطِ شرحِ یک سند نباید صفحه را عوض
 *   کند. (`isTypingTarget`)
 * * **نگاشت از `localStorage` تازه خوانده می‌شود، نه از حافظه‌ی این کامپوننت.**
 *   صفحه‌ی تنظیمات همین نگاشت را عوض می‌کند و بدونِ این، میان‌برِ تازه تا بارِ
 *   بعدیِ برنامه کار نمی‌کرد.
 */
export function useShortcuts(onNavigate: (page: string, section?: string) => void) {
  const navRef = useRef(onNavigate)
  navRef.current = onNavigate

  useEffect(() => {
    //: کش تا هر کلیدفشاری یک `JSON.parse` نشود؛ رویدادِ `storage` و تغییرِ
    //: همین تب آن را باطل می‌کنند.
    let cached: ShortcutMap | null = null
    const get = () => (cached ??= loadShortcuts())

    function onKey(e: KeyboardEvent) {
      if (e.repeat || isTypingTarget(e.target)) return
      if (!e.ctrlKey && !e.altKey && !e.metaKey && !/^F\d{1,2}$/.test(e.code)) return
      const target = get()[chordId(chordFromEvent(e))]
      if (!target) return
      e.preventDefault()
      navRef.current(target.page, target.section)
    }
    //: تبِ دیگر (یا پنجره‌ی دیگرِ همین برنامه) میان‌بری عوض کرده.
    const invalidate = () => { cached = null }

    window.addEventListener('keydown', onKey)
    window.addEventListener('storage', invalidate)
    window.addEventListener('cubita:shortcuts-changed', invalidate)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('storage', invalidate)
      window.removeEventListener('cubita:shortcuts-changed', invalidate)
    }
  }, [])
}
