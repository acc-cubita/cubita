/**
 * صفِ ارسال — دیدن، تلاشِ دوباره، حذف.
 *
 * **چرا لازم شد:** نوارِ «N مورد ثبت نشد» یک بن‌بست بود. کاربر می‌دانست چیزی
 * ثبت نشده ولی نه *کدام* سند، نه *چرا*، و هیچ راهی برای کاری‌کردن نداشت.
 * `discard` در ماژول بود و هیچ صفحه‌ای صدایش نمی‌زد، پس موردِ ردشده تا ابد در
 * صف می‌ماند و نوار **همیشه** قرمز بود. هشداری که همیشه روشن است را کاربر یاد
 * می‌گیرد نادیده بگیرد — و آن‌وقت شکستِ بعدی هم دیده نمی‌شود.
 */
import { useEffect, useState } from 'react'
import { Alert, FlatList, Pressable, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useQueryClient } from '@tanstack/react-query'

import {
  KIND_LABELS,
  discard,
  retryItem,
  subscribeOutbox,
  type OutboxItem,
} from '../offline/outbox'
import { AppText, Card, Center } from '../ui'
import { colors, faMoney, faNum, radius, spacing } from '../theme'
import { faDate } from '../lib/format'

/** خلاصه‌ی یک مورد برای نمایش — از بدنه‌ی خامِ همان درخواست. */
function describe(item: OutboxItem): { amount: string | null; when: string } {
  const body = item.body as Record<string, unknown>
  const amount =
    item.kind === 'salesInvoice'
      ? null
      : typeof body.amount === 'string'
        ? body.amount
        : null
  const when =
    typeof body.invoice_date === 'string'
      ? body.invoice_date
      : typeof body.transaction_date === 'string'
        ? body.transaction_date
        : item.createdAt
  return { amount, when }
}

export function OutboxScreen() {
  const [items, setItems] = useState<OutboxItem[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const qc = useQueryClient()

  useEffect(() => subscribeOutbox(setItems), [])

  const onRetry = async (item: OutboxItem) => {
    setBusy(item.key)
    try {
      const res = await retryItem(item.key)
      if (res === 'sent') {
        // دفتر عوض شده — هرچه از آن تغذیه می‌شود باید تازه شود.
        void qc.invalidateQueries({ queryKey: ['sales-summary'] })
        void qc.invalidateQueries({ queryKey: ['sales-dashboard'] })
        void qc.invalidateQueries({ queryKey: ['alerts'] })
        void qc.invalidateQueries({ queryKey: ['contacts'] })
        Alert.alert('ارسال شد', 'این مورد در دفتر ثبت شد.')
      } else if (res === 'rejected') {
        Alert.alert('باز هم پذیرفته نشد', 'دلیلش زیرِ همان مورد نوشته شده است.')
      } else {
        Alert.alert('هنوز نرفت', 'اتصال برقرار نشد؛ در صف می‌ماند.')
      }
    } finally {
      setBusy(null)
    }
  }

  const onDiscard = (item: OutboxItem) =>
    Alert.alert(
      'حذفِ این مورد؟',
      // صریح، چون برگشت ندارد.
      `«${KIND_LABELS[item.kind]}» از گوشی پاک می‌شود و دیگر ارسال نمی‌شود. اگر در دفتر هم ثبت نشده باشد، کاملاً از بین می‌رود.`,
      [
        { text: 'انصراف', style: 'cancel' },
        { text: 'حذف', style: 'destructive', onPress: () => void discard(item.key) },
      ],
    )

  if (items.length === 0) {
    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <Center>
          <Ionicons name="cloud-done-outline" size={48} color={colors.textFaint} />
          <AppText variant="body" color={colors.textMuted}>
            چیزی در صف نیست — همه‌چیز ثبت شده.
          </AppText>
        </Center>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <FlatList
        data={items}
        keyExtractor={(i) => i.key}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => {
          const { amount, when } = describe(item)
          const rejected = Boolean(item.rejectedReason)
          return (
            <Card style={rejected ? styles.cardBad : undefined}>
              <View style={styles.head}>
                <AppText variant="label">{KIND_LABELS[item.kind]}</AppText>
                <AppText variant="caption" color={colors.textFaint}>
                  {faDate(when)}
                </AppText>
              </View>

              {amount ? (
                <AppText variant="heading" style={{ marginTop: spacing.xs }}>
                  {faMoney(amount)}
                </AppText>
              ) : (
                // شماره‌ی سند را سرور می‌دهد؛ تا ارسال نشود وجود ندارد.
                <AppText variant="body" color={colors.textMuted} style={{ marginTop: spacing.xs }}>
                  هنوز شماره نگرفته
                </AppText>
              )}

              {rejected ? (
                <View style={styles.reason}>
                  <Ionicons name="alert-circle" size={15} color={colors.danger} />
                  <AppText variant="caption" color={colors.danger} style={{ flex: 1 }}>
                    {item.rejectedReason}
                  </AppText>
                </View>
              ) : (
                <AppText variant="caption" color={colors.textFaint} style={{ marginTop: spacing.xs }}>
                  {`در صفِ ارسال — ${faNum(item.attempts)} تلاش`}
                </AppText>
              )}

              <View style={styles.actions}>
                <Pressable
                  onPress={() => void onRetry(item)}
                  disabled={busy === item.key}
                  style={({ pressed }) => [styles.btn, pressed && { opacity: 0.85 }]}
                  accessibilityRole="button"
                  accessibilityLabel={`تلاشِ دوباره برای ${KIND_LABELS[item.kind]}`}
                >
                  <Ionicons name="refresh" size={16} color={colors.accent} />
                  <AppText variant="label" color={colors.accent}>
                    {busy === item.key ? 'در حالِ ارسال…' : 'تلاشِ دوباره'}
                  </AppText>
                </Pressable>

                <Pressable
                  onPress={() => onDiscard(item)}
                  style={({ pressed }) => [styles.btn, pressed && { opacity: 0.85 }]}
                  accessibilityRole="button"
                  accessibilityLabel={`حذفِ ${KIND_LABELS[item.kind]}`}
                >
                  <Ionicons name="trash-outline" size={16} color={colors.danger} />
                  <AppText variant="label" color={colors.danger}>
                    حذف
                  </AppText>
                </Pressable>
              </View>
            </Card>
          )
        }}
      />
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  list: { padding: spacing.lg, gap: spacing.md },
  cardBad: { borderColor: colors.danger },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  reason: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
  },
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    // ≥۴۸dp — همان قاعده‌ی هدفِ لمسِ فازِ ۵.
    minHeight: 48,
    flex: 1,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceAlt,
  },
})
