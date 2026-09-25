import { useEffect, useState } from 'react'

/** همان مقدار، `ms` بعد از آخرین تغییر — برای فیلترِ تایپی که با هر حرف درخواست نفرستد. */
export function useDebounced<T>(value: T, ms = 300): T {
  const [out, setOut] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setOut(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return out
}
