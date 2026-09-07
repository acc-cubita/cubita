import { useCallback, useMemo, useRef, useState } from 'react'
import { Pressable, StyleSheet, View } from 'react-native'
import { useRoute, type RouteProp } from '@react-navigation/native'
import { onlineManager, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'

import { fetchStockCount } from '../../api/stock'
import { fetchItems } from '../../api/invoices'
import { BarcodeScanner } from '../../scan/BarcodeScanner'
import { barcodeIndex, resolveScan, type ScanResolution } from '../../stock/scanResolve'
import { setCount, syncSession } from '../../stock/countDraft'
import type { StockStackParams } from '../../navigation/types'
import { AppText, Center } from '../../ui'
import { colors, radius, spacing } from '../../theme'
import { faQty, toFaDigits } from '../../lib/format'

/** آخرین نتیجه‌ی اسکن، همراه با شمارشِ همین نوبت. */
interface Hit {
  resolution: ScanResolution
  /** چند بار در این نوبتِ اسکن شمرده شده. */
  tally: number
}

/**
 * نوبتِ اسکن.
 *
 * ## چرا هر اسکن «۱+ از صفر» است و نه «۱+ روی مقدارِ فعلی»
 *
 * `counted_qty`ِ سرور هنگامِ ساختِ جلسه با *موجودیِ سیستمی* پر می‌شود (تا کاربر
 * فقط اختلاف‌ها را دست بزند). پس افزودن به آن یعنی «۱۲ تای سیستم + ۱ تایی که
 * شمردم = ۱۳» — که غلط است و شبیهِ درست هم هست.
 *
 * شمارشِ فیزیکی همیشه از صفر شروع می‌شود. پس هر ردیف در این نوبت از صفر بالا
 * می‌رود، و مقدارِ قبلی روی کارت نشان داده می‌شود تا چیزی پنهان نماند.
 */
export function StockScanScreen() {
  const { params } = useRoute<RouteProp<StockStackParams, 'StockScan'>>()
  const sessionId = params.sessionId
  const qc = useQueryClient()

  const sessionQ = useQuery({ queryKey: ['stock-count', sessionId], queryFn: () => fetchStockCount(sessionId) })
  const itemsQ = useQuery({ queryKey: ['items'], queryFn: fetchItems })

  const [hit, setHit] = useState<Hit | null>(null)
  // شمارشِ این نوبت به‌ازای هر ردیف. عمداً در حافظه است: «نوبت» با بستنِ صفحه
  // تمام می‌شود، و شمارشِ ماندگار در پیش‌نویسِ روی دیسک نشسته.
  const tally = useRef<Map<string, number>>(new Map()).current

  const index = useMemo(() => barcodeIndex(itemsQ.data ?? []), [itemsQ.data])
  const lines = sessionQ.data?.lines ?? []

  const write = useCallback(
    async (lineId: string, qty: number) => {
      await setCount(sessionId, lineId, String(qty))
      if (onlineManager.isOnline()) {
        if ((await syncSession(sessionId)) === 'synced') {
          void qc.invalidateQueries({ queryKey: ['stock-count', sessionId] })
        }
      }
    },
    [qc, sessionId],
  )

  const onScan = useCallback(
    (code: string) => {
      const resolution = resolveScan(code, index, lines)
      if (resolution.kind !== 'line') {
        setHit({ resolution, tally: 0 })
        return
      }
      const next = (tally.get(resolution.line.id) ?? 0) + 1
      tally.set(resolution.line.id, next)
      setHit({ resolution, tally: next })
      void write(resolution.line.id, next)
    },
    [index, lines, tally, write],
  )

  /** تصحیحِ دستی روی کارت — «یکی زیادی زدم» در انبار عادی است. */
  const bump = (delta: number) => {
    if (!hit || hit.resolution.kind !== 'line') return
    const lineId = hit.resolution.line.id
    const next = Math.max(0, (tally.get(lineId) ?? 0) + delta)
    tally.set(lineId, next)
    setHit({ ...hit, tally: next })
    void write(lineId, next)
  }

  if (sessionQ.isLoading || itemsQ.isLoading) {
    return (
      <Center>
        <AppText variant="body" color={colors.textMuted}>
          در حال آماده‌سازی…
        </AppText>
      </Center>
    )
  }

  return (
    <View style={styles.screen}>
      <BarcodeScanner
        onScan={onScan}
        hint={
          itemsQ.data && itemsQ.data.length > 0
            ? `${toFaDigits(index.size)} کالا بارکد دارد · بارکد را داخلِ کادر بگیرید`
            : 'فهرستِ کالاها هنوز بارگیری نشده — یک بار با اینترنت باز کنید.'
        }
      />
      {hit ? <ResultCard hit={hit} onBump={bump} onDismiss={() => setHit(null)} /> : null}
    </View>
  )
}

function ResultCard({ hit, onBump, onDismiss }: { hit: Hit; onBump: (d: number) => void; onDismiss: () => void }) {
  const r = hit.resolution

  if (r.kind === 'unknown') {
    return (
      <Banner tone="danger" onDismiss={onDismiss}>
        <AppText variant="body" weight="semibold" color={colors.danger}>
          بارکدِ ناشناس
        </AppText>
        <AppText variant="caption" color={colors.textMuted}>
          «{toFaDigits(r.code)}» به هیچ کالایی وصل نیست. بارکدِ کالا را در برنامه ثبت کنید.
        </AppText>
      </Banner>
    )
  }

  if (r.kind === 'notInSession') {
    return (
      <Banner tone="warning" onDismiss={onDismiss}>
        <AppText variant="body" weight="semibold" color={colors.warning}>
          «{r.item.name}» در این جلسه نیست
        </AppText>
        <AppText variant="caption" color={colors.textMuted}>
          این کالا بعد از شروعِ جلسه ساخته شده یا خدماتی است. در این انبارگردانی شمرده نمی‌شود.
        </AppText>
      </Banner>
    )
  }

  const previous = Number(r.line.counted_qty)
  return (
    <Banner tone="accent" onDismiss={onDismiss}>
      <AppText variant="body" weight="semibold" numberOfLines={1}>
        {r.item.name}
      </AppText>
      <AppText variant="caption" color={colors.textMuted}>
        {r.line.item_sku} · سیستم: {faQty(r.line.system_qty)} {r.line.unit}
        {previous !== Number(r.line.system_qty) ? ` · شمارشِ قبلی: ${faQty(previous)}` : ''}
      </AppText>
      <View style={styles.tallyRow}>
        <Pressable onPress={() => onBump(-1)} android_ripple={{ color: colors.surfaceAlt }} style={styles.step}>
          <Ionicons name="remove" size={20} color={colors.text} />
        </Pressable>
        <View style={styles.tallyBox}>
          <AppText variant="title" color={colors.accent}>
            {faQty(hit.tally)}
          </AppText>
          <AppText variant="caption" color={colors.textMuted}>
            شمرده در این نوبت
          </AppText>
        </View>
        <Pressable onPress={() => onBump(1)} android_ripple={{ color: colors.surfaceAlt }} style={styles.step}>
          <Ionicons name="add" size={20} color={colors.text} />
        </Pressable>
      </View>
    </Banner>
  )
}

function Banner({
  tone,
  children,
  onDismiss,
}: {
  tone: 'accent' | 'warning' | 'danger'
  children: React.ReactNode
  onDismiss: () => void
}) {
  const border = tone === 'danger' ? colors.danger : tone === 'warning' ? colors.warning : colors.accent
  return (
    <View style={[styles.banner, { borderColor: border }]}>
      <View style={{ flex: 1, gap: spacing.xs }}>{children}</View>
      <Pressable onPress={onDismiss} android_ripple={{ color: colors.surfaceAlt, borderless: true }} style={styles.close}>
        <Ionicons name="close" size={18} color={colors.textMuted} />
      </Pressable>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  banner: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg,
    top: spacing.lg,
    flexDirection: 'row',
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    backgroundColor: colors.surface,
  },
  close: { width: 28, height: 28, alignItems: 'center', justifyContent: 'center' },
  tallyRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginTop: spacing.xs },
  tallyBox: { flex: 1, alignItems: 'center' },
  step: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    alignItems: 'center',
    justifyContent: 'center',
  },
})
