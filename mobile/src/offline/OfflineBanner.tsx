import { useEffect, useState } from 'react'
import { StyleSheet, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { onlineManager } from '@tanstack/react-query'

import { AppText } from '../ui'
import { colors, spacing } from '../theme'

/**
 * نوارِ «آفلاین» بالای اپ.
 *
 * **چرا لازم است:** حالا که کش روی دیسک می‌ماند، اپ در حالتِ آفلاین هم عدد نشان
 * می‌دهد — و این بدونِ هشدار *خطرناک* است. مدیری که «موجودیِ نقد» را می‌بیند باید
 * بداند این عدد مالِ آخرین باری است که شبکه وصل بوده، نه همین حالا. برای نرم‌افزارِ
 * حسابداری، عددِ کهنه‌ای که تازه به‌نظر برسد از نبودِ عدد بدتر است.
 */
export function OfflineBanner() {
  const [online, setOnline] = useState(onlineManager.isOnline())

  useEffect(() => onlineManager.subscribe(setOnline), [])

  if (online) return null

  return (
    <View style={styles.bar}>
      <Ionicons name="cloud-offline-outline" size={15} color={colors.warning} />
      <AppText variant="caption" color={colors.warning} style={styles.text}>
        آفلاین — اعداد مربوط به آخرین اتصال است
      </AppText>
    </View>
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
    backgroundColor: colors.warningSoft,
  },
  text: { textAlign: 'center' },
})
