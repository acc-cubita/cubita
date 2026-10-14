const ITEM_CHANGED = 'cubita:items-changed'

/** اعلان فقط بعد از موفقیت سرور است؛ شکست تازه‌سازی نباید ثبت موفق را شکست نشان دهد. */
export async function withItemChange<T>(mutation: Promise<T>): Promise<T> {
  const result = await mutation
  window.dispatchEvent(new Event(ITEM_CHANGED))
  return result
}

/** تغییر حین دریافت، یک دور تازه می‌خواهد تا پاسخ قدیمی ثبت بعدی را پنهان نکند. */
export function subscribeItemChanges(refresh: () => Promise<void>, onError: (error: unknown) => void): () => void {
  let running = false
  let pending = false
  let disposed = false
  const changed = async () => {
    pending = true
    if (running) return
    running = true
    try {
      while (pending && !disposed) {
        pending = false
        try { await refresh() } catch (error) { if (!disposed) onError(error) }
      }
    } finally { running = false }
  }
  window.addEventListener(ITEM_CHANGED, changed)
  return () => { disposed = true; window.removeEventListener(ITEM_CHANGED, changed) }
}
