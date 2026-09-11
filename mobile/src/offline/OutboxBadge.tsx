import { useEffect, useState } from 'react'
import { Pressable, StyleSheet, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

import { AppText } from '../ui'
import { colors, spacing } from '../theme'
import { KIND_LABELS, subscribeOutbox, type OutboxItem } from './outbox'
import { faNum } from '../theme'

/**
 * نوارِ «در صفِ ارسال».
 *
 * **چرا لازم است:** بدونِ این، کاربر فاکتوری ثبت می‌کند، در فهرست نمی‌بیندش (چون
 * هنوز به سرور نرفته) و فکر می‌کند کارش گم شده — پس دوباره ثبتش می‌کند. یعنی
 * نبودِ این نوار خودش باعثِ همان ثبتِ دوباره‌ای می‌شود که کلیدِ idempotency برای
 * جلوگیری از آن گذاشته شده.
 *
 * **و قابلِ لمس است.** نوارِ بی‌کنش بن‌بست بود: کاربر می‌دید چیزی ثبت نشده و هیچ
 * کاری نمی‌توانست بکند.
 */
export function OutboxBadge({ onPress }: { onPress?: () => void }) {
  const [items, setItems] = useState<OutboxItem[]>([])

  useEffect(() => subscribeOutbox(setItems), [])

  if (items.length === 0) return null

  const rejected = items.filter((i) => i.rejectedReason)
  const pending = items.length - rejected.length

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="دیدنِ صفِ ارسال"
      style={styles.bar}
    >
      {rejected.length > 0 ? (
        <>
          <Ionicons name="alert-circle-outline" size={15} color={colors.danger} />
          <AppText variant="caption" color={colors.danger}>
            {`${faNum(rejected.length)} مورد ثبت نشد — «${KIND_LABELS[rejected[0].kind]}»`}
          </AppText>
        </>
      ) : (
        <>
          <Ionicons name="cloud-upload-outline" size={15} color={colors.accent} />
          <AppText variant="caption" color={colors.accent}>
            {`${faNum(pending)} مورد در صفِ ارسال`}
          </AppText>
        </>
      )}
    </Pressable>
  )
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surfaceAlt,
  },
})
