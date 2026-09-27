import { useCallback, useEffect, useRef, useState } from 'react'

import type { Page } from '../api'

/**
 * فهرستِ صفحه‌بندی‌شده با کرسرِ سرور: صفحه‌ی اول با هر عوض‌شدنِ دامنه، و «بعدی» روی همان دامنه.
 *
 * همان محافظِ روزنامه‌ی «گزارش دفتر»، بسته‌بندی‌شده: پاسخِ دیررسیده‌ی دامنه‌ی قبلی (صفحه‌ی اول یا «بعدی») روی دامنه‌ی
 * تازه نمی‌نشیند، و صفحه‌های «بعدی»ِ یک دامنه با برگشتن به همان مقدار زنده نمی‌شوند (هر بار دامنه عوض شود، بارِ تازه است
 * حتی اگر کلید به مقدارِ قبلی برگردد). `scopeKey` دامنه را به‌صورتِ **مقدار** می‌گوید.
 */
export function useCursorList<T>(load: (cursor: string | null) => Promise<Page<T>>, scopeKey: string) {
  const loadRef = useRef(load)
  useEffect(() => {
    loadRef.current = load
  }, [load])
  const [state, setState] = useState<{ items: T[]; cursor: string | null; loading: boolean; error: string | null }>({
    items: [],
    cursor: null,
    loading: true,
    error: null,
  })
  const [moreBusy, setMoreBusy] = useState(false)
  const [moreError, setMoreError] = useState<string | null>(null)
  const run = useRef(0)

  const reload = useCallback(() => {
    const mine = ++run.current
    setState((s) => ({ ...s, loading: true, error: null }))
    setMoreError(null)
    loadRef
      .current(null)
      .then((page) => {
        if (run.current === mine) setState({ items: page.items, cursor: page.next_cursor, loading: false, error: null })
      })
      .catch((err: unknown) => {
        if (run.current === mine)
          setState((s) => ({ ...s, loading: false, error: err instanceof Error ? err.message : 'خطای ناشناخته' }))
      })
  }, [])
  useEffect(reload, [scopeKey, reload])

  async function loadMore() {
    if (!state.cursor || moreBusy) return
    const mine = run.current
    setMoreBusy(true)
    setMoreError(null)
    try {
      const page = await loadRef.current(state.cursor)
      if (run.current === mine) setState((s) => ({ ...s, items: [...s.items, ...page.items], cursor: page.next_cursor }))
    } catch (err) {
      if (run.current === mine) setMoreError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setMoreBusy(false)
    }
  }

  return { ...state, reload, loadMore, moreBusy, moreError, hasMore: state.cursor !== null }
}
