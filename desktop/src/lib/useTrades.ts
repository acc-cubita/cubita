import { useEffect, useState } from 'react'

import { fetchTrades, type TradeGroup } from '../api'

/**
 * فهرستِ اصناف — یک بار گرفته می‌شود و تا پایانِ نشست می‌ماند.
 *
 * **چرا کشِ سطحِ ماژول.** این فهرست ثابت است (تغییرش یعنی انتشارِ نسخه‌ی تازه) ولی
 * سه جای متفاوت می‌خواهدش: ثبت‌نام، شخصی‌سازیِ پنل، و تنظیماتِ پخش. بدونِ کش، هر
 * بار که کاربر بینِ تب‌ها می‌رود یک درخواستِ تازه می‌رود برای داده‌ای که عوض نشده.
 *
 * خطا **بی‌صدا** به فهرستِ خالی می‌رسد و مصرف‌کننده خودش تصمیم می‌گیرد چه نشان دهد؛
 * هیچ‌کدام از این سه صفحه نباید به‌خاطرِ نرسیدنِ یک فهرستِ کمکی از کار بیفتند — به
 * ویژه ثبت‌نام، که صنف در آن اختیاری است.
 */
let cache: TradeGroup[] | null = null
let inflight: Promise<TradeGroup[]> | null = null

function load(): Promise<TradeGroup[]> {
  if (cache) return Promise.resolve(cache)
  if (!inflight) {
    inflight = fetchTrades()
      .then((groups) => {
        cache = groups
        return groups
      })
      .catch(() => [])
      .finally(() => {
        inflight = null
      })
  }
  return inflight
}

export function useTrades(): { groups: TradeGroup[]; loading: boolean } {
  const [groups, setGroups] = useState<TradeGroup[]>(cache ?? [])
  const [loading, setLoading] = useState(cache === null)

  useEffect(() => {
    if (cache) return
    let alive = true
    load().then((g) => {
      if (!alive) return
      setGroups(g)
      setLoading(false)
    })
    return () => {
      alive = false
    }
  }, [])

  return { groups, loading }
}

/** برچسبِ فارسیِ یک صنف. کلیدِ ناشناخته خودش برمی‌گردد — مثلِ `trade_label` سمتِ سرور. */
export function labelOfTrade(groups: TradeGroup[], key: string | null | undefined): string {
  if (!key) return ''
  for (const g of groups) {
    for (const t of g.trades) if (t.key === key) return t.label
  }
  return key
}
