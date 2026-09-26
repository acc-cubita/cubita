import { useEffect, useRef } from 'react'

/**
 * Ctrl+S (⌘S) از **هر جای** صفحه، نه فقط از درونِ فرم.
 *
 * صفحه‌هایی که سربرگِ بازه و پارامترهایشان بیرونِ فرمِ سند است (کارتابل، ادغام، شماره‌گذاری): کاربری که شماره‌ی شروع یا
 * بازه را عوض می‌کند و Ctrl+S می‌زند، وگرنه «ذخیره‌ی صفحه»ِ مرورگر را می‌دید. پنجره‌ی باز (`[role="dialog"]`) مالِ خودش
 * است، و رویدادی که کسِ دیگری زودتر گرفته (`defaultPrevented`) دوباره اجرا نمی‌شود.
 */
export function useCtrlS(onSave: () => void): void {
  const latest = useRef(onSave)
  useEffect(() => {
    latest.current = onSave
  }, [onSave])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.code !== 'KeyS' || e.defaultPrevented) return
      if ((e.target as HTMLElement | null)?.closest?.('[role="dialog"]')) return
      e.preventDefault()
      latest.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}
