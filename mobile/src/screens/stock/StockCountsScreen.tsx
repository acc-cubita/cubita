import { useEffect, useState } from 'react'
import { Alert, FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'

import { createStockCount, fetchStockCounts } from '../../api/stock'
import { fetchWarehouses } from '../../api/invoices'
import { isApiError } from '../../api/client'
import type { StockCountSummary, Warehouse } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { canAccess } from '../../auth/access'
import { subscribeDrafts } from '../../stock/countDraft'
import type { StockStackParams } from '../../navigation/types'
import { AppText, Button, Card, Center } from '../../ui'
import { StatusPill } from '../../ui/controls'
import { colors, radius, spacing } from '../../theme'
import { faDate, toFaDigits, todayIso } from '../../lib/format'

const STATUS: Record<StockCountSummary['status'], { label: string; tone: 'accent' | 'success' | 'muted' }> = {
  open: { label: 'باز', tone: 'accent' },
  posted: { label: 'ثبت‌شده', tone: 'success' },
  cancelled: { label: 'لغوشده', tone: 'muted' },
}

/**
 * فهرستِ جلسه‌های انبارگردانی.
 *
 * برای انباردار این **اولین صفحه‌ی اپ** است: تا پیش از این هیچ نقشِ انبار در
 * موبایل محتوایی نداشت و فقط «بیشتر» را می‌دید.
 */
export function StockCountsScreen() {
  const nav = useNavigation<NativeStackNavigationProp<StockStackParams>>()
  const qc = useQueryClient()
  const { me } = useAuth()
  const canCreate = canAccess(me, 'stock')

  const listQ = useQuery({ queryKey: ['stock-counts'], queryFn: fetchStockCounts })
  const whQ = useQuery({ queryKey: ['warehouses'], queryFn: fetchWarehouses })

  const [picking, setPicking] = useState(false)
  const [pending, setPending] = useState<Record<string, number>>({})

  // شمارشِ ثبت‌نشده‌ی هر جلسه، تا انباردار از همین‌جا ببیند کارش هنوز روی گوشی است.
  useEffect(
    () =>
      subscribeDrafts((drafts) => {
        const counts: Record<string, number> = {}
        for (const [sid, lines] of Object.entries(drafts)) counts[sid] = Object.keys(lines).length
        setPending(counts)
      }),
    [],
  )

  const create = useMutation({
    mutationFn: (warehouseId: string) =>
      createStockCount({ warehouse_id: warehouseId, count_date: todayIso() }),
    onSuccess: (s) => {
      setPicking(false)
      void qc.invalidateQueries({ queryKey: ['stock-counts'] })
      qc.setQueryData(['stock-count', s.id], s)
      nav.navigate('StockCount', { id: s.id, title: s.warehouse_name })
    },
    onError: (e) => Alert.alert('جلسه ساخته نشد', isApiError(e) ? e.message : 'خطای نامشخص'),
  })

  const warehouses = whQ.data ?? []
  const sessions = listQ.data ?? []
  const open = sessions.filter((s) => s.status === 'open')

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <AppText variant="title">انبارگردانی</AppText>
          <AppText variant="caption" color={colors.textMuted}>
            شمارشِ فیزیکیِ موجودی، با گوشی در دست
          </AppText>
        </View>
        {canCreate ? (
          <Pressable
            onPress={() => setPicking((p) => !p)}
            accessibilityRole="button"
            accessibilityLabel={picking ? 'بستنِ انتخابِ انبار' : 'جلسه‌ی انبارگردانیِ تازه'}
            accessibilityState={{ expanded: picking }}
            android_ripple={{ color: colors.surfaceAlt, borderless: true }}
            style={styles.newBtn}
          >
            <Ionicons name={picking ? 'close' : 'add'} size={24} color={colors.onAccent} />
          </Pressable>
        ) : null}
      </View>

      {picking ? (
        <Card style={styles.picker}>
          <AppText variant="label" color={colors.textMuted}>
            انبار را انتخاب کنید
          </AppText>
          {warehouses.length === 0 ? (
            <AppText variant="caption" color={colors.textFaint}>
              انباری تعریف نشده است.
            </AppText>
          ) : (
            warehouses.map((w: Warehouse) => {
              // بک‌اند بیش از یک جلسه‌ی بازِ همزمان روی یک انبار نمی‌پذیرد. اینجا
              // هم جلوتر می‌گوییم، وگرنه کاربر می‌زند و ۴۰۰ می‌گیرد.
              const busy = open.some((s) => s.warehouse_id === w.id)
              return (
                <Pressable
                  key={w.id}
                  disabled={busy || create.isPending}
                  onPress={() => create.mutate(w.id)}
                  android_ripple={{ color: colors.surfaceAlt }}
                  style={[styles.whRow, busy && { opacity: 0.45 }]}
                >
                  <AppText variant="body">{w.name}</AppText>
                  {busy ? (
                    <AppText variant="caption" color={colors.textFaint}>
                      جلسه‌ی باز دارد
                    </AppText>
                  ) : null}
                </Pressable>
              )
            })
          )}
        </Card>
      ) : null}

      <FlatList
        data={sessions}
        keyExtractor={(s) => s.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={listQ.isFetching}
            onRefresh={() => void listQ.refetch()}
            tintColor={colors.accent}
          />
        }
        ListEmptyComponent={
          listQ.isLoading ? null : (
            <Center>
              <Ionicons name="cube-outline" size={40} color={colors.textFaint} />
              <AppText variant="body" color={colors.textMuted} style={styles.centerText}>
                هنوز انبارگردانی‌ای ثبت نشده است.
              </AppText>
              {canCreate ? (
                <Button label="شروعِ انبارگردانی" onPress={() => setPicking(true)} variant="ghost" />
              ) : null}
            </Center>
          )
        }
        renderItem={({ item }) => {
          const st = STATUS[item.status]
          const unsent = pending[item.id] ?? 0
          return (
            <Pressable
              onPress={() => nav.navigate('StockCount', { id: item.id, title: item.warehouse_name })}
              android_ripple={{ color: colors.surfaceAlt }}
              style={styles.row}
            >
              <View style={{ flex: 1, gap: 2 }}>
                <AppText variant="body" weight="semibold" numberOfLines={1}>
                  {item.warehouse_name}
                </AppText>
                <AppText variant="caption" color={colors.textMuted}>
                  {faDate(item.count_date)} · {toFaDigits(item.line_count)} کالا
                </AppText>
                {unsent > 0 ? (
                  <AppText variant="caption" color={colors.warning}>
                    {toFaDigits(unsent)} شمارشِ ثبت‌نشده روی این گوشی
                  </AppText>
                ) : null}
              </View>
              <StatusPill label={st.label} tone={st.tone} />
              <Ionicons name="chevron-back" size={18} color={colors.textFaint} />
            </Pressable>
          )
        }}
        ItemSeparatorComponent={() => <View style={{ height: spacing.sm }} />}
      />
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  newBtn: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  picker: { marginHorizontal: spacing.lg, marginBottom: spacing.sm, gap: spacing.sm },
  whRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
  },
  list: { padding: spacing.lg, paddingTop: spacing.sm, flexGrow: 1 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
  },
  centerText: { textAlign: 'center' },
})
